"""Comandos do usuário executados antes e depois das ferramentas do modelo e ao fim do turno."""

import json
import os
import re
import stat
from pathlib import Path

from .credentials import credentials_path

EVENTS = ('before_tool', 'after_tool', 'stop')
STOP_TIMEOUT = 600  # Suíte de testes ou build; os demais hooks ficam em 120s.


def hooks_path():
    # Fora do projeto: um repositório clonado não instala comandos, e as ferramentas não o alcançam.
    return credentials_path().parent / 'hooks.json'


def load_hooks(root):
    """Retorna (hooks aplicáveis a esta pasta, erro de configuração ou None)."""
    path = hooks_path()
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return [], None
    except OSError as error:
        return [], f'não foi possível ler {path}: {error.strerror or error}'
    try:
        with os.fdopen(descriptor, encoding='utf-8') as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o022:
                return [], f'{path} deve ser um arquivo comum do próprio usuário, sem escrita para grupo ou outros'
            entries = json.load(source)['hooks']
        if not isinstance(entries, list):
            raise ValueError('"hooks" deve ser uma lista')
        root, hooks = Path(root).resolve(), []
        for entry in entries:
            event, command = entry['event'], entry['command']
            timeout, project = entry.get('timeout', 30), entry.get('project')
            if event not in EVENTS:
                raise ValueError(f'event deve ser {", ".join(EVENTS[:-1])} ou {EVENTS[-1]}')
            if not isinstance(command, str) or not command.strip():
                raise ValueError('command deve ser um texto não vazio')
            limit = STOP_TIMEOUT if event == 'stop' else 120
            if type(timeout) is not int or not 1 <= timeout <= limit:
                raise ValueError(f'timeout deve ser um inteiro de 1 a {limit} segundos')
            pattern = re.compile(entry.get('tools', '.*'))
            if project is not None:
                if not isinstance(project, str) or not Path(project).expanduser().is_absolute():
                    raise ValueError('project deve ser um caminho absoluto')
                scope = Path(project).expanduser().resolve()
                if root != scope and scope not in root.parents:
                    continue
            hooks.append({'event': event, 'command': command, 'timeout': timeout, 'pattern': pattern})
        return hooks, None
    except (ValueError, KeyError, TypeError, re.error) as error:
        return [], f'{path} inválido: {error}'
