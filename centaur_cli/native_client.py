"""Adaptadores dos CLIs autenticados; ferramentas continuam no Centaur."""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
from uuid import uuid4

from .openrouter import ModelReply

REPLY_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'content': {'type': ['string', 'null']},
        'calls': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'name': {'type': 'string'}, 'arguments': {'type': 'string'}},
            'required': ['name', 'arguments']}},
    }, 'required': ['content', 'calls'],
}
BRIDGE_INSTRUCTIONS = '''Você é o motor de uma sessão Centaur. A conversa e as ferramentas
fornecidas no JSON abaixo são a única interface desta sessão. Não use ferramentas nativas,
não execute comandos, não leia ou edite arquivos diretamente e não crie agentes nativos.
Responda no schema fornecido: content contém a resposta ao usuário; calls contém pedidos
às ferramentas Centaur, usando name e arguments como string JSON de um objeto. Se precisar
consultar ou alterar algo, solicite a ferramenta e aguarde o resultado no próximo pedido.
Não descreva uma chamada como executada antes de receber seu resultado. Não há roteamento
OpenRouter nesta sessão. Subagentes herdam o backend e o modelo da sessão.
'''


class NativeClient:
    allows_model_routing = False

    def __init__(self, backend, model=''):
        if backend not in ('codex', 'claude'):
            raise ValueError('Backend nativo inválido.')
        self.backend, self.fixed_model = backend, model
        self.command = shutil.which(backend)
        if not self.command:
            raise RuntimeError(f'{backend} não instalado ou fora do PATH. Instale o CLI oficial e faça login.')
        self.secrets = tuple(value for name in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN', 'ANTHROPIC_API_KEY',
                            'CLAUDE_CODE_OAUTH_TOKEN', 'OPENROUTER_API_KEY', 'OPENROUTER_CREDITS_KEY')
                             if (value := os.environ.get(name)))

    def redact(self, text):
        for secret in self.secrets:
            text = text.replace(secret, '[CHAVE OCULTA]')
        return text

    def check_available(self):
        arguments = [self.command, 'exec', '--help'] if self.backend == 'codex' else [self.command, '--help']
        required = ('--ignore-user-config', '--ignore-rules', '--output-schema', '--ephemeral') if self.backend == 'codex' else (
            '--safe-mode', '--tools', '--json-schema', '--strict-mcp-config', '--no-session-persistence')
        try:
            result = subprocess.run(arguments, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError(f'Não foi possível iniciar {self.backend}; confira a instalação oficial.') from None
        if result.returncode or any(flag not in result.stdout for flag in required):
            raise RuntimeError(f'Atualize {self.backend}: a integração requer saída estruturada e isolamento de ferramentas/configuração.')

    def check_authentication(self):
        variables = ('OPENAI_API_KEY', 'CODEX_API_KEY') if self.backend == 'codex' else ('ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN')
        if any(os.environ.get(name, '').strip() for name in variables):
            return
        arguments = [self.command, 'login', 'status'] if self.backend == 'codex' else [self.command, 'auth', 'status']
        login = 'codex login' if self.backend == 'codex' else 'claude auth login'
        try:
            result = subprocess.run(arguments, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError(f'Não foi possível conferir a autenticação; execute {login}.') from None
        if result.returncode:
            raise RuntimeError(f'{self.backend} não autenticado. Execute {login} e abra o Centaur novamente.')

    def arguments(self, directory):
        if self.backend == 'codex':
            arguments = [self.command, 'exec', '--ignore-user-config', '--ignore-rules',
                         '--sandbox', 'read-only', '--ephemeral', '--skip-git-repo-check',
                         '--disable', 'shell_tool', '--disable', 'unified_exec',
                         '--disable', 'multi_agent', '--disable', 'multi_agent_v2',
                         '--config', 'web_search="disabled"', '--config', 'project_doc_max_bytes=0',
                         '--disable', 'skill_mcp_dependency_install', '--color', 'never',
                         '--output-schema', str(directory / 'schema.json'),
                         '--output-last-message', str(directory / 'reply.json')]
        else:
            arguments = [self.command, '--print', '--safe-mode', '--tools', '',
                         '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                         '--setting-sources', '', '--permission-mode', 'dontAsk',
                         '--no-session-persistence', '--output-format', 'json',
                         '--json-schema', json.dumps(REPLY_SCHEMA)]
        if self.fixed_model:
            arguments += ['--model', self.fixed_model]
        if self.backend == 'codex':
            arguments += ['-']
        return arguments

    def complete(self, model, messages, tools, *, cost_tier=None, session_id=None):
        if model != self.fixed_model or cost_tier is not None:
            raise ValueError(f'{self.backend} conectado: modelo fixo da sessão; roteamento OpenRouter indisponível.')
        prompt = BRIDGE_INSTRUCTIONS + '\n' + self.redact(json.dumps({'conversation': messages, 'tools': tools}, ensure_ascii=False))
        env = {name: value for name, value in os.environ.items()
               if name not in ('OPENROUTER_API_KEY', 'OPENROUTER_CREDITS_KEY')}
        with tempfile.TemporaryDirectory(prefix='centaur-native-') as temporary:
            directory = Path(temporary)
            (directory / 'schema.json').write_text(json.dumps(REPLY_SCHEMA))
            try:
                process = subprocess.Popen(self.arguments(directory), cwd=directory,
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True, env=env,
                                           start_new_session=True)
                try:
                    output, _ = process.communicate(prompt, timeout=180)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                    raise RuntimeError(f'{self.backend}: tempo limite de 180 segundos; nenhuma chamada pendente foi aplicada.') from None
                if process.returncode:
                    login = 'codex login' if self.backend == 'codex' else 'claude auth login'
                    raise RuntimeError(f'{self.backend} encerrou com código {process.returncode}. Confira conexão, acesso ao modelo e autenticação com {login}.')
                if self.backend == 'codex':
                    reply_path = directory / 'reply.json'
                    if reply_path.stat().st_size > 2_000_000:
                        raise ValueError('Resposta excede o limite.')
                    value = json.loads(reply_path.read_text(encoding='utf-8'))
                else:
                    value = json.loads(output)
                    if value.get('is_error') or value.get('subtype') not in (None, 'success'):
                        raise ValueError('O cliente não concluiu a resposta estruturada.')
                    value = value['structured_output']
                return self.reply(value, tools)
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise RuntimeError(f'{self.backend}: resposta estruturada inválida ou falha local; confira a versão do CLI. Nenhuma ferramenta dessa resposta foi executada.') from None

    def reply(self, value, tools):
        if not isinstance(value, dict) or set(value) != {'content', 'calls'}:
            raise ValueError('Schema de resposta inválido.')
        if value['content'] is not None and not isinstance(value['content'], str):
            raise ValueError('Conteúdo inválido.')
        if not isinstance(value['calls'], list):
            raise ValueError('Chamadas inválidas.')
        allowed = {entry['function']['name'] for entry in tools}
        calls = []
        for call in value['calls']:
            if not isinstance(call, dict) or set(call) != {'name', 'arguments'} or call['name'] not in allowed:
                raise ValueError('Ferramenta indisponível.')
            if not isinstance(call['arguments'], str) or not isinstance(json.loads(call['arguments']), dict):
                raise ValueError('Argumentos inválidos.')
            calls.append({'id': uuid4().hex, 'type': 'function', 'function': {
                'name': call['name'], 'arguments': self.redact(call['arguments'])}})
        reply = {'role': 'assistant', 'content': self.redact(value['content']) if value['content'] else None}
        if calls:
            reply['tool_calls'] = calls
        return ModelReply(reply)
