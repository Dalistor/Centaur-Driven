"""Approval policy shared by the coordinator and all delegated tools."""

import os
from pathlib import Path
import shlex
import shutil
from .credentials import credentials_path

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


def ordinary_path(root, relative):
    """Hidden/configuration, executable and linked files require review in auto."""
    root = Path(root).resolve()
    supplied = Path(relative)
    if supplied.is_absolute() or '..' in supplied.parts:
        return False
    parts = supplied.parts
    if any(part.startswith('.') or part.lower() in ('secrets', 'credentials') for part in parts):
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
    """Return trusted argv for a deliberately small set; never run auto in a shell."""
    if not isinstance(command, str) or any(c in command for c in '\n\r;&|><`$\\'):
        return None
    try:
        args = shlex.split(command)
    except ValueError:
        return None
    if not args:
        return None
    name, rest = args[0], args[1:]
    # A project-local executable or custom PATH must not acquire automatic permission.
    executable = shutil.which(name, path=os.defpath) if '/' not in name else None
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
        if rest == ['--files']:
            return [executable, '--no-config', '--files']
        flags, rest = [], list(rest)
        while rest and rest[0] in ('-n', '-i', '-F', '-l'):
            flags.append(rest.pop(0))
        if not rest or rest[0].startswith('-'):
            return None
        pattern, paths = rest[0], rest[1:] or ['.']
        for token in paths:
            if not query_path(root, token):
                return None
        return [executable, '--no-config', *flags, pattern, *paths]
    if name not in ('ls', 'cat', 'head', 'tail', 'wc'):
        return None
    flags = {'ls': {'-l', '-a', '-la', '-al', '-1'}, 'cat': {'-n'},
             'head': set(), 'tail': set(), 'wc': {'-l', '-w', '-c'}}[name]
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


def query_path(root, token):
    path = Path(token)
    if (token.startswith('-') or path.is_absolute() or '..' in path.parts
            or any(p.startswith('.') and p != '.' for p in path.parts)):
        return False
    current = Path(root).resolve()
    for part in path.parts:
        current /= part
        if current.is_symlink():
            return False
    try:
        current.resolve().relative_to(Path(root).resolve())
        protected = credentials_path().resolve()
        return current.resolve() != protected and not (current.is_dir() and protected.is_relative_to(current.resolve()))
    except (OSError, ValueError):
        return False


def query_environment(environment):
    """Local Git configuration must not invoke hooks/helpers during automatic queries."""
    env = {k: v for k, v in environment.items() if not k.startswith('GIT_')}
    env.update({'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
                'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0'})
    return env
