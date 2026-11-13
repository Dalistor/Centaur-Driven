"""Ferramentas de projeto disponíveis ao modelo."""

import atexit
import difflib
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from tempfile import TemporaryFile
from uuid import uuid4

from .credentials import credentials_path
from . import skill_catalog
from .permissions import validate_mode, ordinary_path, query_command, query_environment, TRUSTED_PATH
from .interaction import ASK_USER, TurnCancelled, validate_question
from .computer import COMPUTER_TOOLS, ComputerSession
from .hooks import load_hooks


def tool(name, description, properties, optional=()):
    """Texto descreve um parâmetro string; um dicionário é o schema completo do parâmetro."""
    return {'type': 'function', 'function': {
        'name': name, 'description': description,
        'parameters': {'type': 'object', 'properties': {
            key: value if isinstance(value, dict) else {'type': 'string', 'description': value}
            for key, value in properties.items()},
            'required': [key for key in properties if key not in optional], 'additionalProperties': False}}}


MAX_OUTPUT = 24000
READ_LINES = 2000
LINE_CHARS = 2000
MATCH_LINES = 250
GLOB_FILES = 200
COMMAND_TIMEOUT = 120
BACKGROUND_LIMIT = 8
# Leituras sem efeitos colaterais podem rodar em paralelo no mesmo lote.
PARALLEL_SAFE = frozenset(('read_file', 'list_files', 'glob', 'grep', 'read_skill'))
PRUNED_DIRECTORIES = frozenset(('node_modules', '__pycache__', 'venv'))
SECRET_ENVIRONMENT = ('OPENROUTER_API_KEY', 'OPENROUTER_CREDITS_KEY', 'OPENAI_API_KEY', 'CODEX_API_KEY',
                      'CODEX_ACCESS_TOKEN', 'ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN')

PLAN_MARKS = {'pending': '○', 'in_progress': '▸', 'completed': '✓'}

TOOLS = [
    tool('update_plan', 'Registrar ou atualizar o plano visível de uma tarefa com várias etapas. Envie sempre a lista '
         'completa; mantenha uma etapa in_progress por vez e marque completed assim que terminar cada uma.',
         {'steps': {'type': 'array', 'minItems': 1, 'maxItems': 20, 'description': 'Etapas na ordem de execução',
                    'items': {'type': 'object', 'additionalProperties': False, 'required': ['step', 'status'],
                              'properties': {'step': {'type': 'string', 'maxLength': 200, 'description': 'Etapa curta e verificável'},
                                             'status': {'type': 'string', 'enum': list(PLAN_MARKS)}}}}}),
    tool('report_progress', 'Mostrar ao usuário um resumo público e curto do trabalho atual, sem executar ações.',
         {'message': 'Progresso, descoberta ou próximo passo; até 280 caracteres, sem raciocínio interno ou segredos'}),
    tool('read_skill', 'Ler uma skill ou referência incluída no CLI, até 200 linhas por chamada.',
         {'path': 'Caminho relativo ao catálogo, por exemplo spec/SKILL.md, graphify/references/lifecycle.md ou @minha-skill/SKILL.md (.centaur/skills)',
          'start_line': 'Número da primeira linha (1 para começar); use chamadas adicionais para continuar'}),
    tool('list_files', 'Listar arquivos de uma pasta do projeto.', {'path': 'Pasta relativa, use . para raiz'}),
    tool('read_file', 'Ler arquivo UTF-8 do projeto com linhas numeradas (número, tabulação, texto). '
         f'Retorna até {READ_LINES} linhas por chamada e avisa quando há mais; continue com offset. '
         'Os números de linha não fazem parte do arquivo.',
         {'path': 'Arquivo relativo',
          'offset': {'type': 'integer', 'minimum': 1, 'description': 'Primeira linha a ler; padrão 1'},
          'limit': {'type': 'integer', 'minimum': 1, 'maximum': READ_LINES, 'description': 'Quantidade máxima de linhas'}},
         optional=('offset', 'limit')),
    tool('write_file', 'Criar um arquivo ou substituir todo o seu conteúdo; aprovação segue o modo de permissões. '
         'Para alterar parte de um arquivo existente, prefira edit_file.',
         {'path': 'Arquivo relativo', 'content': 'Conteúdo completo UTF-8'}),
    tool('edit_file', 'Substituir um trecho exato de um arquivo existente; aprovação segue o modo de permissões. '
         'old_string deve ser copiado do arquivo, com a indentação e sem os números de linha, e ser único '
         '(inclua linhas vizinhas) ou use replace_all.',
         {'path': 'Arquivo relativo', 'old_string': 'Trecho exato a substituir', 'new_string': 'Texto novo',
          'replace_all': {'type': 'boolean', 'description': 'Substituir todas as ocorrências; padrão false'}},
         optional=('replace_all',)),
    tool('glob', f'Encontrar arquivos por padrão de nome, mais recentes primeiro (até {GLOB_FILES}). '
         'Respeita .gitignore quando o ripgrep está instalado; pastas ocultas só entram se indicadas em path.',
         {'pattern': 'Padrão como **/*.py, src/**/test_*.ts ou *.{ts,tsx}', 'path': 'Pasta relativa; padrão raiz'},
         optional=('path',)),
    tool('grep', f'Buscar uma expressão regular no conteúdo dos arquivos (até {MATCH_LINES} linhas path:linha:texto). '
         'Respeita .gitignore quando o ripgrep está instalado; pastas ocultas só entram se indicadas em path.',
         {'pattern': 'Expressão regular', 'path': 'Arquivo ou pasta relativa; padrão raiz',
          'glob': 'Filtro de arquivos, por exemplo *.py',
          'ignore_case': {'type': 'boolean', 'description': 'Ignorar maiúsculas/minúsculas'},
          'files_only': {'type': 'boolean', 'description': 'Listar somente os arquivos com ocorrência'},
          'context': {'type': 'integer', 'minimum': 0, 'maximum': 5, 'description': 'Linhas de contexto antes e depois'}},
         optional=('path', 'glob', 'ignore_case', 'files_only', 'context')),
    tool('run_command', 'Executar comando de shell na raiz do projeto; aprovação segue o modo de permissões. '
         'Saídas longas mostram início e fim e ficam salvas para read_file. background=true devolve um id '
         'imediatamente (servidores, builds longos); acompanhe com command_output.',
         {'command': 'Comando executado na raiz do projeto',
          'timeout': {'type': 'integer', 'minimum': 1, 'maximum': 600,
                      'description': f'Limite em segundos; padrão {COMMAND_TIMEOUT}'},
          'background': {'type': 'boolean', 'description': 'Executar em segundo plano; padrão false'}},
         optional=('timeout', 'background')),
    tool('command_output', 'Consultar um comando em segundo plano: estado e saída nova desde a última consulta.',
         {'id': 'Identificador devolvido por run_command',
          'wait': {'type': 'integer', 'minimum': 0, 'maximum': 60,
                   'description': 'Aguardar até N segundos pelo término antes de responder'},
          'stop': {'type': 'boolean', 'description': 'Encerrar o comando'}},
         optional=('wait', 'stop')),
]

BACKGROUND = {}
BACKGROUND_LOCK = threading.Lock()


def stop_background(root=None):
    """Encerra comandos em segundo plano; sem root, todos (saída do CLI)."""
    with BACKGROUND_LOCK:
        entries = [entry for entry in BACKGROUND.values() if root is None or entry['root'] == root]
    for entry in entries:
        if entry['process'].poll() is None:
            ProjectTools.stop_command(entry['process'])


atexit.register(stop_background)


def expand_braces(pattern):
    match = re.search(r'\{([^{}]*)\}', pattern)
    if not match:
        return [pattern]
    return [expanded for option in match.group(1).split(',')
            for expanded in expand_braces(pattern[:match.start()] + option + pattern[match.end():])]


def glob_matcher(pattern):
    """** atravessa pastas, * e ? ficam em um segmento; sem barra, vale em qualquer profundidade."""
    if not isinstance(pattern, str) or not pattern.strip() or len(pattern) > 500:
        raise ValueError('Informe um padrão de arquivos de até 500 caracteres.')
    alternatives = []
    for option in expand_braces(pattern.strip())[:64]:
        option = option[2:] if option.startswith('./') else option
        parts, index = ['' if '/' in option else '(?:.*/)?'], 0
        while index < len(option):
            if option.startswith('**/', index):
                parts.append('(?:.*/)?')
                index += 3
            elif option.startswith('**', index):
                parts.append('.*')
                index += 2
            else:
                parts.append({'*': '[^/]*', '?': '[^/]'}.get(option[index], re.escape(option[index])))
                index += 1
        alternatives.append(''.join(parts))
    return re.compile('(?:' + '|'.join(alternatives) + r')\Z').match


def clip_middle(text, budget, note=''):
    """Erros costumam estar no fim: preserva o início e, principalmente, o final."""
    if len(text) <= budget:
        return text
    head = budget // 3
    omitted = len(text) - budget
    return (text[:head] + f'\n[… {omitted:,} caracteres omitidos no meio{note} …]\n' + text[len(text) - (budget - head):])


def change_preview(relative, before, after):
    if before is None:
        return f'Gravar {relative} (arquivo novo):\n{after}'
    diff = '\n'.join(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                          f'a/{relative}', f'b/{relative}', lineterm='', n=3))
    return f'Gravar {relative} (alteração):\n{diff or "(sem diferenças de conteúdo)"}'


class ProjectTools:
    parallel_safe = PARALLEL_SAFE

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
        # Chamado com o caminho antes de cada gravação (checkpoints para /rewind).
        self.before_change = None
        self.hooks, self.hook_error = load_hooks(self.root)

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
            blocked = self.run_hooks('before_tool', name, arguments) if self.hooks else None
            if blocked is not None:
                return self.redact(blocked)[:MAX_OUTPUT]
            result = self.redact(self._execute(name, arguments))[:MAX_OUTPUT]
            if self.hooks or self.hook_error:
                result = (result + self.redact(self.run_hooks('after_tool', name, arguments, result) or ''))[:MAX_OUTPUT]
            return result
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            return self.redact(f'Erro na ferramenta: {error}')

    def run_hooks(self, event, name, arguments, result=None):
        """before_tool com código 2 bloqueia a ação; after_tool com falha anexa sua saída ao resultado."""
        notes = []
        if self.hook_error:
            notes.append(f'\n[Hooks desativados: {self.hook_error}.]')
            self.hook_error = None
        for hook in self.hooks:
            if hook['event'] != event or not hook['pattern'].fullmatch(name):
                continue
            payload = {'event': event, 'tool': name, 'arguments': arguments, 'root': str(self.root)}
            if result is not None:
                payload['result'] = result[:4000]
            env = {**self.command_environment(), 'CENTAUR_TOOL_NAME': name, 'CENTAUR_PROJECT': str(self.root),
                   'CENTAUR_TOOL_PATH': str(arguments.get('path') or '') if isinstance(arguments, dict) else ''}
            with TemporaryFile() as source, TemporaryFile() as output:
                source.write(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
                source.seek(0)
                process = subprocess.Popen(hook['command'], shell=True, cwd=self.root, stdin=source, stdout=output,
                                           stderr=subprocess.STDOUT, start_new_session=True, env=env)
                finished = self.wait_process(process, hook['timeout'])
                output.seek(0)
                text = output.read(8000).decode('utf-8', errors='replace').strip()
            if event == 'before_tool' and finished and process.returncode == 2:
                return 'Bloqueado por hook do usuário: ' + (text or hook['command'])
            if event == 'after_tool' and (not finished or process.returncode != 0):
                status = f'código {process.returncode}' if finished else 'tempo esgotado'
                notes.append(f'\n[Hook após {name} ({status}): {text[:4000]}]')
        return ''.join(notes) or None

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
        if name == 'update_plan':
            steps = arguments['steps']
            if (not isinstance(steps, list) or not 1 <= len(steps) <= 20 or any(
                    not isinstance(item, dict) or not isinstance(item.get('step'), str) or not item['step'].strip()
                    or item.get('status') not in PLAN_MARKS for item in steps)):
                raise ValueError('Plano deve ter de 1 a 20 etapas com step e status pending, in_progress ou completed.')
            done = sum(item['status'] == 'completed' for item in steps)
            return (f'Plano · {done}/{len(steps)} concluídas\n'
                    + '\n'.join(f'{PLAN_MARKS[item["status"]]} {" ".join(item["step"].split())[:200]}' for item in steps))
        if name == 'read_skill':
            return skill_catalog.read(arguments['path'], arguments['start_line'], self.root)
        if name == 'run_command':
            return self.run_command(arguments)
        if name == 'command_output':
            return self.command_output(arguments)
        if name == 'glob':
            return self.glob(arguments)
        if name == 'grep':
            return self.grep(arguments)
        if name not in ('list_files', 'read_file', 'write_file', 'edit_file'):
            return f'Ferramenta desconhecida: {name}'
        path = self.path(arguments['path'])
        if name == 'list_files':
            return '\n'.join(sorted(item.name + ('/' if item.is_dir() else '')
                                    for item in path.iterdir()))
        if name == 'read_file':
            return self.read_file(path, arguments.get('offset'), arguments.get('limit'))
        if name == 'write_file':
            content = arguments['content']
            if not isinstance(content, str):
                raise ValueError('Conteúdo deve ser texto UTF-8.')
            try:
                before = path.read_text(encoding='utf-8') if path.is_file() else None
            except ValueError:
                before = None  # Conteúdo não textual: a aprovação mostra o arquivo novo.
            return self.change_file(path, arguments['path'], before, content, 'Arquivo gravado.')
        return self.edit_file(path, arguments)

    @staticmethod
    def integer(value, default, low, high, label):
        if value is None:
            return default
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{label} deve ser um inteiro de {low} a {high}.')
        return value

    def read_file(self, path, offset=None, limit=None):
        offset = self.integer(offset, 1, 1, 10 ** 9, 'offset')
        limit = self.integer(limit, READ_LINES, 1, READ_LINES, 'limit')
        budget, shown, size, total, last = MAX_OUTPUT - 200, [], 0, 0, offset - 1
        with path.open(encoding='utf-8') as source:
            for total, line in enumerate(source, 1):
                if total < offset or last < total - 1:
                    continue  # Antes do intervalo, ou a página já encheu: só conta as linhas.
                line = line.rstrip('\n')
                if len(line) > LINE_CHARS:
                    line = line[:LINE_CHARS] + f' …[linha truncada: {len(line):,} caracteres]'
                entry = f'{total}\t{line}'
                if len(shown) >= limit or size + len(entry) + 1 > budget:
                    continue
                shown.append(entry)
                size += len(entry) + 1
                last = total
        if not total:
            return '[Arquivo vazio.]'
        if not shown:
            return f'[Arquivo tem {total} linhas; offset {offset} está além do fim.]'
        if offset == 1 and last == total:
            return '\n'.join(shown)
        footer = f'\n[Linhas {offset}–{last} de {total}.'
        return '\n'.join(shown) + footer + (f' Há mais conteúdo: continue com offset={last + 1}.]' if last < total else ']')

    def change_file(self, path, supplied, before, content, done):
        relative = path.relative_to(self.root)
        automatic = self.approval_mode == 'never' or (self.approval_mode == 'auto'
                    and ordinary_path(self.root, supplied))
        if not automatic and not self.approve(self.redact(change_preview(relative, before, content))):
            return 'Alteração recusada pelo usuário.'
        self.check_cancelled()
        if self.before_change:
            self.before_change(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8', newline='') as target:
            target.write(content)
        return f'{done} {content.count(chr(10)) + (1 if content and not content.endswith(chr(10)) else 0)} linhas em {relative}.'

    def edit_file(self, path, arguments):
        old, new, every = arguments['old_string'], arguments['new_string'], arguments.get('replace_all') or False
        if not isinstance(old, str) or not isinstance(new, str) or type(every) is not bool:
            raise ValueError('old_string e new_string devem ser texto; replace_all, booleano.')
        if not old:
            raise ValueError('old_string vazio; use write_file para criar ou substituir um arquivo inteiro.')
        if old == new:
            raise ValueError('old_string e new_string são iguais; nada a alterar.')
        if not path.is_file():
            raise ValueError('Arquivo não encontrado; use write_file para criar.')
        with path.open(encoding='utf-8', newline='') as source:
            before = source.read()
        if old not in before and '\r\n' in before:
            # O modelo lê linhas sem o \r; preserve as quebras de linha originais do arquivo.
            old, new = (re.sub(r'\r?\n', '\r\n', value) for value in (old, new))
        count = before.count(old)
        if not count:
            raise ValueError('Trecho não encontrado: copie o texto exato do arquivo, com a mesma indentação '
                             'e sem os números de linha de read_file. Releia o trecho antes de tentar de novo.')
        if count > 1 and not every:
            raise ValueError(f'Trecho aparece {count} vezes; inclua linhas vizinhas para torná-lo único ou use replace_all.')
        after = before.replace(old, new) if every else before.replace(old, new, 1)
        return self.change_file(path, arguments['path'], before, after,
                                f'Arquivo editado ({f"{count} substituições" if every and count > 1 else "1 substituição"}).')

    def visible(self, relative):
        return not relative.startswith('.centaur/computer-permissions/')

    def capture(self, argv, timeout, *, query=False):
        """Consulta sem shell, com cancelamento; retorna (código ou None se expirou, saída)."""
        env = {key: value for key, value in os.environ.items() if key not in SECRET_ENVIRONMENT}
        with TemporaryFile() as output:
            process = subprocess.Popen(argv, cwd=self.root, stdin=subprocess.DEVNULL, stdout=output,
                                       stderr=subprocess.STDOUT, start_new_session=True,
                                       env=query_environment(env) if query else env)
            finished = self.wait_process(process, timeout)
            output.seek(0)
            return (process.returncode if finished else None), output.read(4_000_000).decode('utf-8', errors='replace')

    def wait_process(self, process, timeout):
        """True ao terminar; False se expirou (processo encerrado); None se não confirmou saída."""
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            try:
                self.check_cancelled()
            except TurnCancelled:
                self.stop_command(process)
                raise
            if time.monotonic() >= deadline:
                return False if self.stop_command(process) else None
            try:
                process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                pass
        return True

    def files(self, base):
        """Arquivos sob base, relativos à raiz; segue .gitignore com ripgrep, senão ignora ocultos."""
        if base.is_file():
            yield base.relative_to(self.root).as_posix()
            return
        if not base.is_dir():
            raise ValueError('Pasta não encontrada.')
        ripgrep = shutil.which('rg', path=TRUSTED_PATH)
        if ripgrep:
            code, text = self.capture([ripgrep, '--no-config', '--files', '--', base.relative_to(self.root).as_posix()], 30, query=True)
            if code in (0, 1):
                for line in text.splitlines():
                    line = line[2:] if line.startswith('./') else line
                    if line and self.visible(line):
                        yield line
                return
        for directory, names, filenames in os.walk(base):
            self.check_cancelled()
            names[:] = sorted(name for name in names if not name.startswith('.') and name not in PRUNED_DIRECTORIES)
            for filename in sorted(filenames):
                target = Path(directory, filename)
                relative = target.relative_to(self.root).as_posix()
                # Links poderiam apontar para fora do projeto.
                if not filename.startswith('.') and not target.is_symlink() and self.visible(relative):
                    yield relative

    def glob(self, arguments):
        matches = glob_matcher(arguments['pattern'])
        base = self.path(arguments.get('path') or '.')
        prefix = base.relative_to(self.root).as_posix()
        prefix = '' if prefix == '.' else prefix + '/'
        found = [relative for relative in self.files(base) if matches(relative[len(prefix):] if relative.startswith(prefix) else relative)]
        if not found:
            return 'Nenhum arquivo encontrado.'
        def modified(relative):
            try:
                return (self.root / relative).stat().st_mtime
            except OSError:
                return 0
        found.sort(key=lambda relative: (-modified(relative), relative))
        note = f'\n[{len(found)} arquivos; exibidos os {GLOB_FILES} mais recentes. Refine o padrão ou o path.]' if len(found) > GLOB_FILES else ''
        return '\n'.join(found[:GLOB_FILES]) + note

    def grep(self, arguments):
        pattern, filter_glob = arguments['pattern'], arguments.get('glob')
        ignore_case, files_only = arguments.get('ignore_case') or False, arguments.get('files_only') or False
        context = self.integer(arguments.get('context'), 0, 0, 5, 'context')
        if not isinstance(pattern, str) or not pattern or len(pattern) > 2000 or '\n' in pattern:
            raise ValueError('Informe uma expressão regular de uma linha, com até 2000 caracteres.')
        if type(ignore_case) is not bool or type(files_only) is not bool:
            raise ValueError('ignore_case e files_only devem ser booleanos.')
        matches = glob_matcher(filter_glob) if filter_glob else None
        base = self.path(arguments.get('path') or '.')
        ripgrep = shutil.which('rg', path=TRUSTED_PATH)
        if ripgrep:
            argv = [ripgrep, '--no-config', '--no-heading', '--color', 'never', '--with-filename',
                    '--max-columns', '300', '--max-columns-preview']
            argv += ['--files-with-matches'] if files_only else ['--line-number']
            if ignore_case:
                argv.append('--ignore-case')
            if context and not files_only:
                argv += ['--context', str(context)]
            for option in expand_braces(filter_glob)[:64] if filter_glob else ():
                argv += ['--glob', option]
            code, text = self.capture([*argv, '--regexp', pattern, '--', base.relative_to(self.root).as_posix()], 30, query=True)
            if code is None:
                raise ValueError('Busca excedeu 30 segundos; restrinja path ou glob.')
            if code not in (0, 1):
                raise ValueError('Busca recusada pelo ripgrep: ' + ' '.join(text.split())[:500])
            lines = [line[2:] if line.startswith('./') else line for line in text.splitlines()]
            lines = [line for line in lines if self.visible(line)]
        else:
            lines = self.search(re.compile(pattern, re.IGNORECASE if ignore_case else 0), base, matches, files_only, context)
        if not lines:
            return 'Nenhuma ocorrência.'
        note = f'\n[Resultado limitado a {MATCH_LINES} linhas; refine pattern, path ou glob.]' if len(lines) > MATCH_LINES else ''
        return clip_middle('\n'.join(lines[:MATCH_LINES]), MAX_OUTPUT - 300) + note

    def search(self, expression, base, matches, files_only, context):
        """Busca sem ripgrep: arquivos de texto até 2 MB, mesmo formato de saída."""
        lines, deadline = [], time.monotonic() + 30
        for relative in self.files(base):
            if len(lines) > MATCH_LINES or time.monotonic() >= deadline:
                break
            self.check_cancelled()
            if matches and not matches(relative):
                continue
            target = self.root / relative
            try:
                if target.stat().st_size > 2_000_000:
                    continue
                raw = target.read_bytes()
            except OSError:
                continue
            if b'\0' in raw[:4096]:
                continue
            content = raw.decode('utf-8', errors='replace').splitlines()
            hits = [index for index, line in enumerate(content) if expression.search(line)]
            if hits and files_only:
                lines.append(relative)
                continue
            selected = sorted({near for index in hits for near in range(max(0, index - context), min(len(content), index + context + 1))})
            for index in selected:
                separator = ':' if index in hits else '-'
                lines.append(f'{relative}{separator}{index + 1}{separator}{content[index][:300]}')
        return lines

    def output_directory(self):
        directory = self.root / '.centaur' / 'tool-output'
        directory.mkdir(parents=True, exist_ok=True)
        stale = sorted(directory.iterdir(), key=lambda item: item.stat().st_mtime)[:-40]
        active = {entry['log'] for entry in list(BACKGROUND.values()) if entry['process'].poll() is None}
        for item in stale:
            if item not in active:
                item.unlink(missing_ok=True)
        return directory

    def command_environment(self):
        return {key: value for key, value in os.environ.items() if key not in SECRET_ENVIRONMENT}

    def run_command(self, arguments):
        command, background = arguments['command'], arguments.get('background') or False
        if not isinstance(command, str) or not command.strip():
            raise ValueError('Informe um comando não vazio.')
        if type(background) is not bool:
            raise ValueError('background deve ser booleano.')
        timeout = self.integer(arguments.get('timeout'), COMMAND_TIMEOUT, 1, 600, 'timeout')
        query = query_command(self.root, command) if self.approval_mode == 'auto' else None
        automatic = self.approval_mode == 'never' or query is not None
        label = 'Executar em segundo plano' if background else 'Executar'
        if not automatic and not self.approve(self.redact(f'{label} na pasta {self.root}:\n{command}')):
            return 'Execução recusada pelo usuário.'
        self.check_cancelled()
        env = self.command_environment()
        if query is not None:
            env = query_environment(env)
        # Shell autorizado pelo usuário; cwd não é uma sandbox.
        options = dict(shell=query is None, cwd=self.root, stdin=subprocess.DEVNULL,
                       stderr=subprocess.STDOUT, start_new_session=True, env=env)
        if background:
            return self.start_background(query if query is not None else command, command, options)
        with TemporaryFile() as output:
            process = subprocess.Popen(query if query is not None else command, stdout=output, **options)
            finished = self.wait_process(process, timeout)
            if finished is None:
                return 'Comando encerrado: sinal enviado, mas o processo não confirmou saída; confira o estado antes de retomar.'
            size = output.seek(0, os.SEEK_END)
            output.seek(0)
            text = self.redact(output.read(4_000_000).decode('utf-8', errors='replace'))
            header = (f'Código de saída: {process.returncode}\n' if finished else
                      f'Comando encerrado: limite de {timeout} segundos atingido. Para tarefas longas, '
                      'aumente timeout (até 600) ou use background=true.\n')
            budget = MAX_OUTPUT - len(header) - 300
            if len(text) > budget:
                saved = self.output_directory() / f'{time.strftime("%Y%m%d-%H%M%S")}-{uuid4().hex[:6]}.txt'
                saved.write_text(text, encoding='utf-8')
                note = (f'\n[Saída de {size:,} bytes; íntegra em {saved.relative_to(self.root)} '
                        '(use read_file com offset ou grep).]')
                return header + clip_middle(text, budget) + note
            return header + text

    def start_background(self, argv, command, options):
        with BACKGROUND_LOCK:
            running = sum(entry['process'].poll() is None for entry in BACKGROUND.values())
            if running >= BACKGROUND_LIMIT:
                raise ValueError(f'Limite de {BACKGROUND_LIMIT} comandos em segundo plano; encerre um com command_output stop=true.')
            identifier = uuid4().hex[:8]
            log = self.output_directory() / f'background-{identifier}.log'
            with log.open('wb') as output:
                process = subprocess.Popen(argv, stdout=output, **options)
            BACKGROUND[identifier] = {'process': process, 'log': log, 'root': self.root, 'command': command,
                                      'started': time.monotonic(), 'offset': 0}
        return (f'Comando em segundo plano iniciado: id={identifier}. Isto não é conclusão; consulte '
                f'command_output (id, wait, stop). Saída em {log.relative_to(self.root)}.')

    def command_output(self, arguments):
        wait = self.integer(arguments.get('wait'), 0, 0, 60, 'wait')
        stop = arguments.get('stop') or False
        if type(stop) is not bool:
            raise ValueError('stop deve ser booleano.')
        with BACKGROUND_LOCK:
            entry = BACKGROUND.get(arguments['id'])
        if not entry or entry['root'] != self.root:
            raise ValueError('Comando em segundo plano desconhecido nesta pasta; confira o id devolvido por run_command.')
        process = entry['process']
        if stop and process.poll() is None:
            self.stop_command(process)
        deadline = time.monotonic() + wait
        while process.poll() is None and time.monotonic() < deadline:
            self.check_cancelled()
            time.sleep(.1)
        code = process.poll()
        with BACKGROUND_LOCK, entry['log'].open('rb') as source:
            source.seek(entry['offset'])
            raw = source.read(MAX_OUTPUT * 4)
            entry['offset'] += len(raw)
            remaining = source.seek(0, os.SEEK_END) - entry['offset']
        header = (f'Em execução há {int(time.monotonic() - entry["started"])}s · {entry["command"][:120]}\n' if code is None else
                  f'Código de saída: {code}\n' if code >= 0 else f'Comando encerrado por sinal {-code}.\n')
        text = clip_middle(raw.decode('utf-8', errors='replace'), MAX_OUTPUT - len(header) - 300)
        if remaining > 0:
            text += f'\n[Mais {remaining:,} bytes de saída; consulte novamente.]'
        return header + (text or '[Sem saída nova.]')
