"""Approval policy shared by the coordinator and all delegated tools."""

import os
from pathlib import Path
import shlex
import shutil
import re
import sys
from .credentials import credentials_path
from . import skill_catalog

TRUSTED_PATH = os.pathsep.join((os.defpath, '/usr/local/bin', '/opt/homebrew/bin'))

APPROVAL_MODES = ('ask', 'auto', 'never')
MODE_LABELS = {'ask': 'Pedir aprovação', 'auto': 'Automático · baixo risco',
               'never': 'Sem perguntar'}
MODE_HELP = {
    'ask': 'Gravações e comandos pedem aprovação; leituras são livres.',
    'auto': 'Edições comuns e consultas; demais ações pedem aprovação.',
    'never': 'Arquivos/comandos sem confirmação, com acesso do usuário. Computer use sempre pede permissão.',
}


def validate_mode(mode):
    if mode not in APPROVAL_MODES:
        raise ValueError('Modo inválido: use ask, auto ou never.')
    return mode


def project_relative(root, supplied):
    """Accept aliases of the project root without resolving away links inside it."""
    if '..' in supplied.parts:
        raise ValueError('Parent traversal requires review.')
    if not supplied.is_absolute():
        return supplied
    try:
        return supplied.relative_to(root)
    except ValueError:
        for parent in supplied.parents:
            if parent.resolve() == root:
                return supplied.relative_to(parent)
        raise ValueError('Path outside the project.')


def ordinary_path(root, relative):
    """Hidden/configuration, executable and linked files require review in auto."""
    root = Path(root).resolve()
    try:
        supplied = project_relative(root, Path(relative))
    except (OSError, ValueError):
        return False
    parts = supplied.parts
    centaur_document = (len(parts) >= 3 and parts[0] == '.centaur'
                        and parts[1] in ('specs', 'implements', 'contracts', 'modules', 'system')
                        and supplied.suffix.lower() in ('.md', '.json', '.html'))
    checked_parts = parts[1:] if centaur_document else parts
    if any(part.startswith('.') or part.lower() in ('secrets', 'credentials') for part in checked_parts):
        return False
    current = root
    for part in parts:
        current /= part
        if current.is_symlink():
            return False
    try:
        current.resolve().relative_to(root)
        if current.resolve() == credentials_path().resolve():
            return False
        return not current.exists() or (current.is_file() and not current.stat().st_mode & 0o111
                                        and current.stat().st_nlink == 1)
    except (OSError, ValueError):
        return False


CONNECTORS = ('|', '&&', '||', ';')
# Redirecionamentos que não gravam nada; a saída de erro já vai junto com a padrão.
HARMLESS = re.compile(r'\s+(?:2>&1|[12]?>\s*/dev/null)(?=[\s;&|]|$)')
GIT_READ = ('status', 'diff', 'log', 'show', 'blame', 'ls-files', 'ls-tree', 'rev-parse', 'shortlog', 'describe', 'grep')
# Opções que gravam arquivo, executam outro programa ou leem fora do repositório.
GIT_BLOCKED = ('--output', '--ext-diff', '--textconv', '--no-index', '-O', '--open-files-in-pager', '--contents',
               '--untracked', '--no-exclude-standard', '--exec', '--upload-pack', '--receive-pack')
GIT_LISTS = {'branch': ('-a', '-r', '-v', '-vv', '--all', '--remotes', '--list', '--show-current'),
             'remote': ('-v',), 'tag': ('-l', '--list'), 'stash': ('list',)}
FIND_BLOCKED = ('-exec', '-execdir', '-ok', '-okdir', '-delete', '-fprint', '-fprint0', '-fprintf', '-fls')
SIMPLE_FLAGS = {'ls': r'-[laAhR1tSrFd]+', 'cat': r'-n', 'wc': r'-[lwcm]+', 'uniq': r'-[cdui]+', 'sort': r'-[rnufbV]+',
                'file': r'-b', 'stat': None, 'du': r'-[shac]+|--max-depth=\d+', 'tree': r'-[adfL]+|\d+',
                'diff': r'-[urqNwb]+', 'nl': None, 'basename': None, 'dirname': None}
READS_STDIN = ('cat', 'wc', 'uniq', 'sort', 'nl')


class ShellQuery(str):
    """Linha composta só de consultas reconhecidas, com executáveis absolutos e argumentos já citados."""


def query_command(root, command):
    """Consulta reconhecida: argv confiável, ou ShellQuery para consultas encadeadas; None exige aprovação."""
    if not isinstance(command, str) or any(c in command for c in '\n\r'):
        return None
    if '"' not in command and "'" not in command:
        command = HARMLESS.sub('', ' ' + command).strip()
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|><')
        lexer.whitespace_split = True
        lexer.commenters = ''
        args = list(lexer)
    except ValueError:
        return None
    segments, connectors, current = [], [], []
    for token in args:
        if token and all(c in ';&|><' for c in token):
            if token not in CONNECTORS or not current:
                return None  # Redirecionamento, segundo plano ou conector solto.
            segments.append(current)
            connectors.append(token)
            current = []
        else:
            current.append(token)
    if not current or len(segments) >= 8:
        return None
    segments.append(current)
    if len(segments) > 1 and segments[0][0] == 'cd':
        # "cd <raiz> && ..." é só hábito do modelo; outra pasta mudaria o sentido dos caminhos validados.
        try:
            same = len(segments[0]) == 2 and (Path(root) / segments[0][1]).resolve() == Path(root).resolve()
        except OSError:
            same = False
        if not same or connectors[0] not in ('&&', ';'):
            return None
        segments, connectors = segments[1:], connectors[1:]
    parts = []
    for index, tokens in enumerate(segments):
        argv = simple_query(root, tokens, piped=index > 0 and connectors[index - 1] == '|')
        if argv is None:
            return None
        parts.append(argv)
    if len(parts) == 1:
        return parts[0]
    line = shlex.join(parts[0])
    for connector, argv in zip(connectors, parts[1:]):
        line += f' {connector} ' + shlex.join(argv)
    return ShellQuery(line)


def simple_query(root, args, piped=False):
    """Um comando de leitura; piped permite ler da entrada quando não há arquivo."""
    name, rest = args[0], args[1:]
    if name in ('python', 'python3'):
        return lifecycle_query(root, rest)
    # A project-local executable or custom PATH must not acquire automatic permission.
    executable = shutil.which(name, path=TRUSTED_PATH) if '/' not in name else None
    if not executable:
        return None
    paths_ok = lambda tokens: all(query_path(root, token) for token in tokens)
    if name in ('pwd', 'true') and not rest:
        return [executable]
    if name == 'date' and (not rest or len(rest) == 1 and rest[0].startswith('+')):
        return [executable, *rest]
    if name == 'echo':
        return [executable, *rest]
    if name == 'which' and rest and all(re.fullmatch(r'[\w.+-]+', token) for token in rest):
        return [executable, *rest]
    if name == 'git':
        if not rest:
            return None
        command, options = rest[0], rest[1:]
        if command in GIT_LISTS:
            if any(option not in GIT_LISTS[command] for option in options) or (command == 'stash' and options != ['list']):
                return None
        elif command not in GIT_READ or any(option.split('=', 1)[0] in GIT_BLOCKED or option.startswith('-O')
                                            for option in options):
            return None
        argv = [executable, '--no-pager', '-c', 'core.fsmonitor=false',
                '-c', 'core.pager=cat', '-c', 'log.showSignature=false', command]
        if command in ('diff', 'log', 'show'):
            argv += ['--no-ext-diff', '--no-textconv']
        return argv + options
    if name == 'rg':
        flags, rest = [], list(rest)
        file_list = False
        while rest and rest[0].startswith('-'):
            option = rest.pop(0)
            if option in ('-n', '-i', '-F', '-l', '-w', '-c', '-v', '-S', '-s', '--hidden', '--no-heading'):
                flags.append(option)
            elif option == '--files' and not file_list:
                file_list = True
                flags.append(option)
            elif option in ('-g', '--glob', '-t', '--type') and rest and not rest[0].startswith('-'):
                flags.extend([option, rest.pop(0)])
            elif option in ('-A', '-B', '-C', '-m') and rest and rest[0].isdigit():
                flags.extend([option, rest.pop(0)])
            else:
                return None
        if file_list:
            paths = rest or ['.']
            pattern = []
        else:
            if not rest:
                return None
            pattern, paths = rest[:1], rest[1:] or ([] if piped else ['.'])
        if not paths_ok(paths):
            return None
        return [executable, '--no-config', *flags, *pattern, *paths]
    if name == 'grep':
        # Sem -r: a busca recursiva é do rg, que respeita .gitignore e pula arquivos ocultos.
        flags, rest = [], list(rest)
        while rest and rest[0].startswith('-'):
            option = rest.pop(0)
            if re.fullmatch(r'-[niwvclLEFHhoqs]+', option) or re.fullmatch(r'--(?:include|exclude)=[^/]+', option):
                flags.append(option)
            elif option in ('-A', '-B', '-C', '-m') and rest and rest[0].isdigit():
                flags.extend([option, rest.pop(0)])
            elif option == '-e' and rest:
                flags.extend([option, rest.pop(0)])
            else:
                return None
        pattern = [] if '-e' in flags else rest[:1]
        paths = rest[len(pattern):]
        if not (pattern or '-e' in flags) or not paths_ok(paths) or not (paths or piped):
            return None
        return [executable, *flags, '--', *pattern, *paths]
    if name == 'sed':
        # Only numeric print addresses: no execution, writes, in-place edits or extra scripts.
        if len(rest) < 2 or rest[0] != '-n' or not re.fullmatch(r'\d+(?:,\d+)?p', rest[1]):
            return None
        if not paths_ok(rest[2:]) or not (rest[2:] or piped):
            return None
        return [executable, *rest]
    if name == 'find':
        index = 0
        while index < len(rest) and not rest[index].startswith(('-', '(', '!')):
            index += 1
        if not paths_ok(rest[:index]) or any(token in FIND_BLOCKED for token in rest[index:]):
            return None
        return [executable, *(rest[:index] or ['.']), *rest[index:]]
    if name in ('head', 'tail'):
        count = []
        if rest[:1] in (['-n'], ['-c']) and len(rest) >= 2:
            count, rest = rest[:2], rest[2:]
            if not count[1].isdigit() or not 1 <= int(count[1]) <= 10000:
                return None
        elif rest and re.fullmatch(r'-\d{1,5}', rest[0]):
            count, rest = rest[:1], rest[1:]
        if not paths_ok(rest) or not (rest or piped):
            return None
        return [executable, *count, *rest]
    if name == 'cut':
        options, rest = [], list(rest)
        while rest and re.fullmatch(r'-[dfc].{0,24}', rest[0]):
            option = rest.pop(0)
            options.append(option)
            if len(option) == 2:
                if not rest:
                    return None
                options.append(rest.pop(0))
        if not options or not paths_ok(rest) or not (rest or piped):
            return None
        return [executable, *options, *rest]
    if name not in SIMPLE_FLAGS:
        return None
    flags, paths = SIMPLE_FLAGS[name], []
    for position, token in enumerate(rest):
        if token.startswith('-') or (name == 'tree' and position and rest[position - 1] == '-L'):
            if not flags or not re.fullmatch(flags, token):
                return None
        elif not query_path(root, token):
            return None
        else:
            paths.append(token)
    if name == 'sort' and any(token in ('-k', '-t') for token in rest):
        return None
    if name == 'diff' and len(paths) != 2:
        return None
    if not paths and name not in ('ls', 'tree', 'du') and not (piped and name in READS_STDIN):
        return None
    return [executable, *rest]


def lifecycle_query(root, args):
    """Only the bundled read-only validator; arbitrary Python still requires approval."""
    if len(args) < 2:
        return None
    script = skill_catalog.SKILL_ROOT / 'graphify/scripts/validate-lifecycle.py'
    try:
        supplied = Path(args[0])
        if not supplied.is_absolute():
            supplied = Path(root) / supplied
        if supplied.resolve() != script.resolve() or not script.is_file():
            return None
        project = Path(args[1])
        if not project.is_absolute():
            project = Path(root) / project
        if project.resolve() != Path(root).resolve():
            return None
    except (OSError, ValueError):
        return None
    remaining = args[2:]
    if len(remaining) % 2:
        return None
    used = set()
    for option, value in zip(remaining[::2], remaining[1::2]):
        if option not in ('--ready', '--complete') or option in used or not re.fullmatch(r'[\w-]+/[\w-]+', value):
            return None
        used.add(option)
    # Ignore Python environment and site hooks; imports come from the installed script directory.
    return [sys.executable, '-E', '-s', '-S', str(script.resolve()), str(Path(root).resolve()), *remaining]


def query_path(root, token):
    root = Path(root).resolve()
    try:
        path = project_relative(root, Path(token))
    except (OSError, ValueError):
        return False
    if (token.startswith('-') or any(c in token for c in '$`\\') or '..' in path.parts
            or any(p.startswith('.') and p not in ('.', '.centaur') for p in path.parts)):
        return False
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            return False
    try:
        current.resolve().relative_to(root)
        protected = credentials_path().resolve()
        return current.resolve() != protected and not (current.is_dir() and protected.is_relative_to(current.resolve()))
    except (OSError, ValueError):
        return False


def query_environment(environment):
    """Local Git configuration must not invoke hooks/helpers during automatic queries."""
    env = {k: v for k, v in environment.items() if not k.startswith('GIT_')}
    env.update({'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
                'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0', 'PATH': TRUSTED_PATH,
                'GIT_CONFIG_COUNT': '3', 'GIT_CONFIG_KEY_0': 'core.fsmonitor',
                'GIT_CONFIG_VALUE_0': 'false', 'GIT_CONFIG_KEY_1': 'core.pager',
                'GIT_CONFIG_VALUE_1': 'cat', 'GIT_CONFIG_KEY_2': 'log.showSignature',
                'GIT_CONFIG_VALUE_2': 'false'})
    return env
