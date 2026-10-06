"""Ferramentas de projeto disponíveis ao modelo."""

import os
import signal
import subprocess
from pathlib import Path
from tempfile import TemporaryFile

from .credentials import credentials_path
from . import skill_catalog


def tool(name, description, properties):
    return {'type': 'function', 'function': {
        'name': name, 'description': description,
        'parameters': {'type': 'object', 'properties': {
            key: {'type': 'string', 'description': value}
            for key, value in properties.items()},
            'required': list(properties), 'additionalProperties': False}}}


TOOLS = [
    tool('report_progress', 'Mostrar ao usuário um resumo público e curto do trabalho atual, sem executar ações.',
         {'message': 'Progresso, descoberta ou próximo passo; até 280 caracteres, sem raciocínio interno ou segredos'}),
    tool('read_skill', 'Ler uma skill ou referência incluída no CLI, até 200 linhas por chamada.',
         {'path': 'Caminho relativo ao catálogo, por exemplo spec/SKILL.md, graphify/references/lifecycle.md ou @minha-skill/SKILL.md (.centaur/skills)',
          'start_line': 'Número da primeira linha (1 para começar); use chamadas adicionais para continuar'}),
    tool('list_files', 'Listar arquivos de uma pasta do projeto.', {'path': 'Pasta relativa, use . para raiz'}),
    tool('read_file', 'Ler arquivo UTF-8 do projeto.', {'path': 'Arquivo relativo'}),
    tool('write_file', 'Gravar arquivo; exige confirmação humana.',
         {'path': 'Arquivo relativo', 'content': 'Conteúdo completo UTF-8'}),
    tool('run_command', 'Executar comando de shell; exige confirmação humana.',
         {'command': 'Comando executado na raiz do projeto'}),
]
MAX_OUTPUT = 24000


class ProjectTools:
    def __init__(self, root, approve, api_key=None, protected_keys=()):
        self.root = Path(root).resolve()
        self.approve = approve
        self.api_key = api_key
        self.protected_keys = tuple(key for key in (api_key, *protected_keys) if key)

    def redact(self, text):
        for key in self.protected_keys:
            text = text.replace(key, '[CHAVE OCULTA]')
        return text

    def path(self, relative):
        path = (self.root / relative).resolve()
        path.relative_to(self.root)
        if path == credentials_path().resolve():
            raise ValueError('Credenciais do CLI não podem ser acessadas pelas ferramentas.')
        return path

    def execute(self, name, arguments):
        try:
            return self.redact(self._execute(name, arguments))[:MAX_OUTPUT]
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            return self.redact(f'Erro na ferramenta: {error}')

    def _execute(self, name, arguments):
        if name == 'report_progress':
            message = arguments['message']
            if not isinstance(message, str) or not message.strip() or len(message) > 280:
                raise ValueError('Resumo de progresso deve ter 1 a 280 caracteres.')
            return message.strip()
        if name == 'read_skill':
            return skill_catalog.read(arguments['path'], arguments['start_line'], self.root)
        if name == 'run_command':
            command = arguments['command']
            if not self.approve(self.redact(f'Executar na pasta {self.root}:\n{command}')):
                return 'Execução recusada pelo usuário.'
            # Shell autorizado pelo usuário; cwd não é uma sandbox.
            with TemporaryFile() as output:
                process = subprocess.Popen(command, shell=True, cwd=self.root,
                                           stdin=subprocess.DEVNULL, stdout=output,
                                           stderr=subprocess.STDOUT, start_new_session=True,
                                           env={key: value for key, value in os.environ.items()
                                                if key not in ('OPENROUTER_API_KEY', 'OPENROUTER_CREDITS_KEY', 'OPENAI_API_KEY',
                                                                'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN', 'ANTHROPIC_API_KEY',
                                                                'CLAUDE_CODE_OAUTH_TOKEN')})
                try:
                    process.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    return 'Comando encerrado: limite de 60 segundos atingido.'
                output.seek(0)
                return f'Código de saída: {process.returncode}\n' + output.read(MAX_OUTPUT).decode('utf-8', errors='replace')
        if name not in ('list_files', 'read_file', 'write_file'):
            return f'Ferramenta desconhecida: {name}'
        path = self.path(arguments['path'])
        if name == 'list_files':
            return '\n'.join(sorted(item.name + ('/' if item.is_dir() else '')
                                    for item in path.iterdir()))
        if name == 'read_file':
            with path.open(encoding='utf-8') as source:
                return source.read(MAX_OUTPUT)
        if name == 'write_file':
            content = arguments['content']
            if not self.approve(self.redact(f'Gravar {path.relative_to(self.root)}:\n{content}')):
                return 'Alteração recusada pelo usuário.'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            return 'Arquivo gravado.'
