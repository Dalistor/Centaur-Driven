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
    'never': 'Executa sem confirmação, com as permissões do seu usuário.',
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


def query_command(root, command):
    """Return trusted argv for recognized queries; never run auto in a shell."""
    if not isinstance(command, str) or any(c in command for c in '\n\r'):
        return None
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|><')
        lexer.whitespace_split = True
        lexer.commenters = ''
        args = list(lexer)
    except ValueError:
        return None
    if not args:
        return None
    if any(token and all(c in ';&|><' for c in token) for token in args):
        return None
    name, rest = args[0], args[1:]
    if name in ('python', 'python3'):
        return lifecycle_query(root, rest)
    # A project-local executable or custom PATH must not acquire automatic permission.
    executable = shutil.which(name, path=TRUSTED_PATH) if '/' not in name else None
    if not executable:
        return None
    if name == 'pwd' and not rest:
        return [executable]
    if name == 'git':
        permitted = (
            ['status'], ['status', '--short'], ['status', '--porcelain'],
            ['diff'], ['diff', '--stat'], ['diff', '--cached'], ['diff', '--cached', '--stat'],
            ['log'], ['log', '--oneline'], ['log', '-5', '--oneline'],
            ['ls-files'], ['branch', '--show-current'], ['rev-parse', '--show-toplevel'],
        )
        if rest not in permitted:
            return None
        argv = [executable, '--no-pager', '-c', 'core.fsmonitor=false',
                '-c', 'core.pager=cat', '-c', 'log.showSignature=false', *rest]
        if rest[0] in ('diff', 'log'):
            argv += ['--no-ext-diff', '--no-textconv']
        return argv
    if name == 'rg':
        flags, rest = [], list(rest)
        file_list = False
        while rest and rest[0].startswith('-'):
            option = rest.pop(0)
            if option in ('-n', '-i', '-F', '-l', '--hidden'):
                flags.append(option)
            elif option == '--files' and not file_list:
                file_list = True
                flags.append(option)
            elif option in ('-g', '--glob') and rest and not rest[0].startswith('-'):
                flags.extend([option, rest.pop(0)])
            else:
                return None
        if file_list:
            paths = rest or ['.']
            pattern = []
        else:
            if not rest:
                return None
            pattern, paths = rest[:1], rest[1:] or ['.']
        for token in paths:
            if not query_path(root, token):
                return None
        return [executable, '--no-config', *flags, *pattern, *paths]
    if name == 'sed':
        # Only numeric print addresses: no execution, writes, in-place edits or extra scripts.
        if len(rest) < 3 or rest[0] != '-n' or not re.fullmatch(r'\d+(?:,\d+)?p', rest[1]):
            return None
        if not all(query_path(root, token) for token in rest[2:]):
            return None
        return [executable, *rest]
    if name not in ('ls', 'cat', 'head', 'tail', 'wc'):
        return None
    flags = {'ls': {'-l', '-a', '-la', '-al', '-1'}, 'cat': {'-n'},
             'head': set(), 'tail': set(), 'wc': {'-l', '-w', '-c'}}[name]
    if name in ('head', 'tail') and rest[:1] == ['-n']:
        if len(rest) < 3 or not rest[1].isdigit() or not 1 <= int(rest[1]) <= 10000:
            return None
        if not all(query_path(root, token) for token in rest[2:]):
            return None
        return [executable, *rest]
    paths = []
    for token in rest:
        if token.startswith('-'):
            if token not in flags:
                return None
        else:
            if not query_path(root, token):
                return None
            paths.append(token)
    if not paths and name != 'ls':
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
