"""Adaptadores dos CLIs autenticados; ferramentas continuam no Centaur."""

import json
import copy
import os
import re
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
from uuid import uuid4

from .openrouter import ModelReply
from .config import validate_effort

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
às ferramentas Centaur, usando name e arguments como objeto JSON tipado. Campos opcionais
sem valor usam null. Sem chamadas, calls deve ser []. Nunca inclua cercas Markdown fora do JSON. Se precisar
consultar ou alterar algo, solicite a ferramenta e aguarde o resultado no próximo pedido.
Não descreva uma chamada como executada antes de receber seu resultado. Não há roteamento
OpenRouter nesta sessão. Subagentes mantêm o backend e podem escolher modelos do catálogo fornecido.
'''


def reply_schema(tools):
    """Typed arguments avoid double-escaping code, quotes and multiline content."""
    schema = copy.deepcopy(REPLY_SCHEMA)
    variants = []
    for entry in tools:
        function = entry['function']
        arguments = copy.deepcopy(function['parameters'])
        for key in arguments['properties']:
            arguments['properties'][key].pop('default', None)
            if key not in arguments.get('required', []):
                arguments['properties'][key] = {'anyOf': [arguments['properties'][key], {'type': 'null'}]}
        arguments['required'] = list(arguments['properties'])
        arguments['additionalProperties'] = False
        variants.append({'type': 'object', 'additionalProperties': False,
                         'properties': {'name': {'type': 'string', 'enum': [function['name']]},
                                        'arguments': arguments}, 'required': ['name', 'arguments']})
    if variants:
        schema['properties']['calls']['items'] = {'anyOf': variants}
    return schema


def decode_reply(text):
    text = text.lstrip('\ufeff').strip()
    # Accept a single complete fenced object, never scrape JSON from arbitrary prose.
    if text.startswith('```json\n') and text.endswith('\n```'):
        text = text[8:-4]
    elif text.startswith('```\n') and text.endswith('\n```'):
        text = text[4:-4]
    return json.loads(text)


def codex_output(directory, output):
    path = directory / 'reply.json'
    if path.is_file() and path.stat().st_size:
        if path.stat().st_size > 8_000_000:
            raise ValueError('Resposta excede 8 MB; divida o pedido em partes menores.')
        return decode_reply(path.read_text(encoding='utf-8'))
    # Only completed public agent messages, not reasoning or partial event fragments.
    candidate, completed = None, False
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get('type') in ('error', 'turn.failed'):
            raise ValueError('O Codex interrompeu o turno; confira conexão, limite e acesso ao modelo.')
        if event.get('type') == 'item.completed':
            item = event.get('item', {})
            if isinstance(item, dict) and item.get('type') == 'agent_message':
                candidate = item.get('text')
        if event.get('type') == 'turn.completed':
            completed = True
    if completed and isinstance(candidate, str) and len(candidate.encode()) <= 8_000_000:
        return decode_reply(candidate)
    raise ValueError('O Codex não entregou uma resposta final; tente novamente ou confira a instalação.')


def process_failure(backend, code, stderr):
    """Classify known diagnostics without echoing prompts, account data or reasoning."""
    text = stderr.lower()
    if 'schema' in text:
        hint = 'O CLI ou modelo recusou o schema de ferramentas; atualize o CLI ou selecione outro modelo.'
    elif any(key in text for key in ('context length', 'context window', 'too many tokens')):
        hint = 'O contexto excedeu o limite do modelo; use /new ou selecione um modelo com mais contexto.'
    elif any(key in text for key in ('rate limit', 'usage limit', 'quota', 'exceeded your')):
        hint = 'Limite de uso atingido; aguarde a renovação ou selecione outro modelo/backend.'
    elif 'unexpected argument' in text or 'unrecognized' in text:
        hint = 'O CLI não aceita uma opção de integração; atualize o CLI oficial.'
    else:
        hint = 'Confira conexão, acesso ao modelo e autenticação com ' + ('codex login.' if backend == 'codex' else 'claude auth login.')
    return f'{backend} encerrou com código {code}. {hint} Nenhuma ferramenta dessa resposta foi executada.'


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

    def model_catalog(self):
        if self.backend == 'claude':
            catalog = {'haiku': 'Tasks simples e rápidas', 'sonnet': 'Implementação comum',
                       'opus': 'Investigação complexa e maior risco'}
        else:
            cache = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'models_cache.json'
            try:
                data = json.loads(cache.read_text(encoding='utf-8'))
                catalog = {entry['slug']: entry.get('description', '') for entry in data['models']
                           if isinstance(entry, dict) and entry.get('visibility') == 'list' and isinstance(entry.get('slug'), str)}
            except (OSError, ValueError, KeyError, TypeError):
                catalog = {}
        if self.fixed_model:
            catalog.setdefault(self.fixed_model, 'Modelo principal configurado')
        return {name: description for name, description in catalog.items()
                if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', name)}

    def redact(self, text):
        for secret in self.secrets:
            text = text.replace(secret, '[CHAVE OCULTA]')
        return text

    def check_available(self):
        arguments = [self.command, 'exec', '--help'] if self.backend == 'codex' else [self.command, '--help']
        required = ('--model', '--ignore-user-config', '--ignore-rules', '--output-schema', '--output-last-message', '--json', '--ephemeral') if self.backend == 'codex' else (
            '--model', '--safe-mode', '--tools', '--json-schema', '--strict-mcp-config', '--no-session-persistence')
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

    def arguments(self, directory, model=None, effort='default', schema=None):
        validate_effort(self.backend, effort)
        if self.backend == 'codex':
            arguments = [self.command, 'exec', '--ignore-user-config', '--ignore-rules',
                         '--sandbox', 'read-only', '--ephemeral', '--skip-git-repo-check',
                         '--disable', 'shell_tool', '--disable', 'unified_exec',
                         '--disable', 'multi_agent', '--disable', 'multi_agent_v2',
                         '--config', 'web_search="disabled"', '--config', 'project_doc_max_bytes=0',
                         '--disable', 'skill_mcp_dependency_install', '--color', 'never',
                         '--json',
                         '--output-schema', str(directory / 'schema.json'),
                         '--output-last-message', str(directory / 'reply.json')]
        else:
            arguments = [self.command, '--print', '--safe-mode', '--tools', '',
                         '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                         '--setting-sources', '', '--permission-mode', 'dontAsk',
                         '--no-session-persistence', '--output-format', 'json',
                         '--json-schema', json.dumps(schema or REPLY_SCHEMA)]
        selected = self.fixed_model if model is None else model
        if selected:
            arguments += ['--model', selected]
        if effort != 'default':
            if self.backend == 'codex':
                arguments += ['--config', 'model_reasoning_effort=' + json.dumps(effort)]
            else:
                arguments += ['--effort', effort]
        if self.backend == 'codex':
            arguments += ['-']
        return arguments

    def complete(self, model, messages, tools, *, cost_tier=None, session_id=None, effort='default'):
        if cost_tier is not None:
            raise ValueError('cost_tier é exclusivo de OpenRouter.')
        if model != self.fixed_model and model not in self.model_catalog():
            raise ValueError(f'Modelo não listado no catálogo {self.backend}.')
        prompt = BRIDGE_INSTRUCTIONS + '\n' + self.redact(json.dumps({'conversation': messages, 'tools': tools}, ensure_ascii=False))
        env = {name: value for name, value in os.environ.items()
               if name not in ('OPENROUTER_API_KEY', 'OPENROUTER_CREDITS_KEY')}
        with tempfile.TemporaryDirectory(prefix='centaur-native-') as temporary:
            directory = Path(temporary)
            schema = reply_schema(tools)
            (directory / 'schema.json').write_text(json.dumps(schema), encoding='utf-8')
            try:
                process = subprocess.Popen(self.arguments(directory, model, effort, schema), cwd=directory,
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True, env=env,
                                           start_new_session=True)
                try:
                    output, errors = process.communicate(prompt, timeout=180)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                    raise RuntimeError(f'{self.backend}: tempo limite de 180 segundos; nenhuma chamada pendente foi aplicada.') from None
                if process.returncode:
                    raise RuntimeError(process_failure(self.backend, process.returncode, errors))
                if self.backend == 'codex':
                    value = codex_output(directory, output)
                else:
                    if len(output.encode('utf-8')) > 8_000_000:
                        raise ValueError('Resposta excede 8 MB; divida o pedido em partes menores.')
                    value = json.loads(output)
                    if value.get('is_error') or value.get('subtype') not in (None, 'success'):
                        raise ValueError('O cliente não concluiu a resposta estruturada.')
                    value = value['structured_output']
                return self.reply(value, tools)
            except json.JSONDecodeError as error:
                raise RuntimeError(f'{self.backend}: JSON incompleto ou inválido na linha {error.lineno}, coluna {error.colno}. '
                                   'Tente novamente com /retry ou divida a solicitação. Nenhuma ferramenta dessa resposta foi executada.') from None
            except (OSError, ValueError, KeyError, TypeError) as error:
                detail = str(error) if isinstance(error, ValueError) else 'Não foi possível ler a resposta local do CLI.'
                raise RuntimeError(f'{self.backend}: {self.redact(detail)} Nenhuma ferramenta dessa resposta foi executada.') from None

    def reply(self, value, tools):
        if not isinstance(value, dict) or set(value) != {'content', 'calls'}:
            raise ValueError('Schema de resposta inválido.')
        if value['content'] is not None and not isinstance(value['content'], str):
            raise ValueError('Conteúdo inválido.')
        if not isinstance(value['calls'], list):
            raise ValueError('Chamadas inválidas.')
        allowed = {entry['function']['name']: entry['function']['parameters'] for entry in tools}
        calls = []
        for call in value['calls']:
            if not isinstance(call, dict) or set(call) != {'name', 'arguments'} or call['name'] not in allowed:
                raise ValueError('Ferramenta indisponível.')
            arguments = json.loads(call['arguments']) if isinstance(call['arguments'], str) else call['arguments']
            if not isinstance(arguments, dict):
                raise ValueError('Argumentos inválidos.')
            parameters = allowed[call['name']]
            arguments = {key: val for key, val in arguments.items()
                         if val is not None or key in parameters.get('required', [])}
            if (set(arguments) - set(parameters['properties'])
                    or not set(parameters.get('required', [])) <= set(arguments)):
                raise ValueError('Argumentos fora do contrato da ferramenta; tente novamente com /retry.')
            for name, val in arguments.items():
                spec = parameters['properties'][name]
                if spec.get('type') == 'string' and not isinstance(val, str):
                    raise ValueError('Argumentos devem respeitar os tipos da ferramenta.')
                if 'enum' in spec and val not in spec['enum']:
                    raise ValueError('Opção de ferramenta fora do catálogo permitido.')
            calls.append({'id': uuid4().hex, 'type': 'function', 'function': {
                'name': call['name'], 'arguments': self.redact(json.dumps(arguments, ensure_ascii=False))}})
        reply = {'role': 'assistant', 'content': self.redact(value['content']) if value['content'] else None}
        if calls:
            reply['tool_calls'] = calls
        return ModelReply(reply)
