"""Ferramentas de projeto disponíveis ao modelo."""

import os
import signal
import subprocess
import json
import time
from pathlib import Path
from tempfile import TemporaryFile

from .credentials import credentials_path
from . import skill_catalog
from .permissions import validate_mode, ordinary_path, query_command, query_environment
from .interaction import ASK_USER, TurnCancelled, validate_question
from .computer import COMPUTER_TOOLS, ComputerSession


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
    tool('write_file', 'Gravar arquivo; aprovação segue o modo de permissões selecionado pelo usuário.',
         {'path': 'Arquivo relativo', 'content': 'Conteúdo completo UTF-8'}),
    tool('run_command', 'Executar comando; aprovação segue o modo de permissões selecionado pelo usuário.',
         {'command': 'Comando executado na raiz do projeto'}),
]
MAX_OUTPUT = 24000


class ProjectTools:
    def __init__(self, root, approve, api_key=None, protected_keys=(), *, approval_mode='ask', ask_user=None, cancel_event=None, computer=None):
        self.root = Path(root).resolve()
        self.approve = approve
        self.api_key = api_key
        self.protected_keys = tuple(key for key in (api_key, *protected_keys) if key)
        self.approval_mode = validate_mode(approval_mode)
        self.ask_user = ask_user
        self.cancel_event = cancel_event
        self.computer = computer
        self.definitions = getattr(type(self), 'definitions', [*TOOLS, *([ASK_USER] if ask_user else []), *(COMPUTER_TOOLS if computer else [])])

    def check_cancelled(self):
        if self.cancel_event and self.cancel_event.is_set():
            raise TurnCancelled('Turno interrompido pelo usuário; confira ações já aplicadas antes de retomar.')

    @staticmethod
    def stop_command(process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # The process can exit between poll and kill.
        try:
            process.wait(timeout=2)
            return True
        except subprocess.TimeoutExpired:
            return False

    def observation_messages(self):
        return self.computer.observation_messages() if self.computer else []

    def redact(self, text):
        for key in self.protected_keys:
            text = text.replace(key, '[CHAVE OCULTA]')
        return text

    def path(self, relative):
        path = (self.root / relative).resolve()
        path.relative_to(self.root)
        permission_directory = self.root / '.centaur' / 'computer-permissions'
        if path == permission_directory.resolve() or permission_directory.resolve() in path.parents:
            raise ValueError('Autorizações de computer use são gerenciadas pelo usuário, fora das ferramentas do modelo.')
        if path == credentials_path().resolve():
            raise ValueError('Credenciais do CLI não podem ser acessadas pelas ferramentas.')
        return path

    def execute(self, name, arguments):
        try:
            return self.redact(self._execute(name, arguments))[:MAX_OUTPUT]
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            return self.redact(f'Erro na ferramenta: {error}')

    def _execute(self, name, arguments):
        self.check_cancelled()
        if name == 'ask_user' and self.ask_user:
            question, options = validate_question(arguments)
            return json.dumps(self.ask_user(self.redact(question), [self.redact(option) for option in options]), ensure_ascii=False)
        if name.startswith('computer_') and self.computer:
            try:
                return self.computer.execute(name, arguments)
            except TurnCancelled:
                raise
            except RuntimeError as error:
                raise ValueError(str(error)) from None
        if name == 'report_progress':
            message = arguments['message']
            if not isinstance(message, str) or not message.strip() or len(message) > 280:
                raise ValueError('Resumo de progresso deve ter 1 a 280 caracteres.')
            return message.strip()
        if name == 'read_skill':
            return skill_catalog.read(arguments['path'], arguments['start_line'], self.root)
        if name == 'run_command':
            command = arguments['command']
            if not isinstance(command, str) or not command.strip():
                raise ValueError('Informe um comando não vazio.')
            query = query_command(self.root, command) if self.approval_mode == 'auto' else None
            automatic = self.approval_mode == 'never' or query is not None
            if not automatic and not self.approve(self.redact(f'Executar na pasta {self.root}:\n{command}')):
                return 'Execução recusada pelo usuário.'
            self.check_cancelled()
            # Shell autorizado pelo usuário; cwd não é uma sandbox.
            with TemporaryFile() as output:
                env = {key: value for key, value in os.environ.items()
                       if key not in ('OPENROUTER_API_KEY', 'OPENROUTER_CREDITS_KEY', 'OPENAI_API_KEY',
                                      'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN', 'ANTHROPIC_API_KEY',
                                      'CLAUDE_CODE_OAUTH_TOKEN')}
                if query is not None:
                    env = query_environment(env)
                process = subprocess.Popen(query if query is not None else command, shell=query is None, cwd=self.root,
                                           stdin=subprocess.DEVNULL, stdout=output,
                                           stderr=subprocess.STDOUT, start_new_session=True,
                                           env=env)
                deadline = time.monotonic() + 60
                while process.poll() is None:
                    try:
                        self.check_cancelled()
                    except TurnCancelled:
                        self.stop_command(process)
                        raise
                    if time.monotonic() >= deadline:
                        if not self.stop_command(process):
                            return 'Comando encerrado: sinal enviado, mas o processo não confirmou saída; confira o estado antes de retomar.'
                        return 'Comando encerrado: limite de 60 segundos atingido.'
                    try:
                        process.wait(timeout=0.1)
                    except subprocess.TimeoutExpired:
                        pass
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
            if not isinstance(content, str):
                raise ValueError('Conteúdo deve ser texto UTF-8.')
            automatic = self.approval_mode == 'never' or (self.approval_mode == 'auto'
                        and ordinary_path(self.root, arguments['path']))
            if not automatic and not self.approve(self.redact(f'Gravar {path.relative_to(self.root)}:\n{content}')):
                return 'Alteração recusada pelo usuário.'
            self.check_cancelled()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            return 'Arquivo gravado.'
