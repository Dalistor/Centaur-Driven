"""Sandbox opcional (Linux, bubblewrap) para comandos do modo auto.

Com CENTAUR_SANDBOX=1, um comando que pediria confirmação no modo auto roda sem perguntar
dentro de um sandbox: sem rede, sistema somente leitura, gravação apenas na pasta do projeto
(exceto .git, .centaur e configurações que executam código depois) e sem acesso às pastas de
credenciais do usuário. Fora do Linux, sem bwrap ou se o teste inicial falhar, nada muda: o
comando continua pedindo confirmação.
"""

import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from .credentials import credentials_path

# Gravar aqui executaria código fora do sandbox mais tarde, ou mudaria o próprio harness.
PROTECTED = ('.git', '.centaur', '.github', '.vscode', '.idea', '.husky', '.envrc', '.gitmodules')
# Conteúdo que não deve chegar ao modelo nem a um comando sem revisão.
PRIVATE_HOME = ('.ssh', '.gnupg', '.aws', '.azure', '.kube', '.docker', '.config/gcloud', '.config/gh',
                '.netrc', '.npmrc', '.pypirc', '.git-credentials', '.password-store')
SECRET_NAME = re.compile(r'TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API_?KEY|PRIVATE_KEY|SSH_AUTH_SOCK', re.IGNORECASE)
NOTE = ('[Executado em sandbox: sem rede, gravação só na pasta do projeto (não em .git/.centaur). Se o comando '
        'precisa de rede ou de gravar fora, repita com outside_sandbox=true para pedir confirmação ao usuário.]\n')
PROBED = {}
LOCK = threading.Lock()


def enabled():
    return os.environ.get('CENTAUR_SANDBOX', '').strip().lower() in ('1', 'true', 'on')


def arguments(root):
    root, home = Path(root).resolve(), Path.home().resolve()
    argv = ['--die-with-parent', '--unshare-net', '--unshare-pid', '--unshare-ipc',
            '--ro-bind', '/', '/', '--dev', '/dev', '--proc', '/proc', '--tmpfs', '/tmp']
    for private in (*(home / name for name in PRIVATE_HOME), credentials_path().parent):
        try:
            private = private.resolve()
            if private.is_dir():
                argv += ['--tmpfs', str(private)]
            elif private.is_file():
                argv += ['--ro-bind', os.devnull, str(private)]
        except OSError:
            continue
    argv += ['--bind', str(root), str(root)]
    for name in PROTECTED:
        target = root / name
        if target.is_symlink():
            continue
        if target.exists():
            argv += ['--ro-bind', str(target), str(target)]
    try:
        entries = list(root.iterdir())
    except OSError:
        entries = []
    for entry in entries:
        # Segredos locais do projeto: o comando vê um arquivo vazio.
        if entry.name.startswith('.env') and entry.name != '.envrc' and entry.is_file() and not entry.is_symlink():
            argv += ['--ro-bind', os.devnull, str(entry)]
    scratch = root / '.centaur' / 'tmp'
    if scratch.is_dir() and not scratch.is_symlink():
        argv += ['--bind', str(scratch), str(scratch)]
    return argv + ['--chdir', str(root)]


def wrap(root, command):
    """argv que executa o comando no sandbox; None quando o sandbox não está ativo ou não funciona aqui."""
    if not enabled() or not sys.platform.startswith('linux'):
        return None
    from .permissions import TRUSTED_PATH
    bwrap = shutil.which('bwrap', path=TRUSTED_PATH)
    if not bwrap:
        return None
    try:
        base = [bwrap, *arguments(root)]
    except OSError:
        return None
    key = str(Path(root).resolve())
    with LOCK:
        if key not in PROBED:
            # Distribuições que restringem user namespaces recusam o bwrap: melhor perguntar do que falhar sempre.
            try:
                PROBED[key] = subprocess.run([*base, '/bin/sh', '-c', 'true'], stdin=subprocess.DEVNULL,
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode == 0
            except (OSError, subprocess.SubprocessError):
                PROBED[key] = False
        if not PROBED[key]:
            return None
    return [*base, '/bin/sh', '-c', command]


def environment(env):
    """Sem variáveis com cara de segredo; caches que ficariam somente leitura vão para o /tmp do sandbox."""
    env = {key: value for key, value in env.items() if not SECRET_NAME.search(key)}
    env.update({'XDG_CACHE_HOME': '/tmp/.cache', 'GOCACHE': '/tmp/.cache/go-build', 'npm_config_cache': '/tmp/.cache/npm',
                'PIP_CACHE_DIR': '/tmp/.cache/pip', 'GIT_OPTIONAL_LOCKS': '0', 'CENTAUR_SANDBOXED': '1'})
    return env
