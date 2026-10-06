"""Preferências de backend e modelo por projeto, sem credenciais."""

import json
import os
from pathlib import Path
import re
import tempfile

BACKENDS = ('openrouter', 'codex', 'claude')


def config_path(root):
    project = Path(root).resolve()
    path = (project / '.centaur/config.json').resolve()
    path.relative_to(project)
    return path


def validate(backend, model):
    if backend not in BACKENDS:
        raise ValueError('Backend inválido: use openrouter, codex ou claude.')
    if not isinstance(model, str) or (model and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}', model)):
        raise ValueError('Nome do modelo inválido.')
    return {'backend': backend, 'model': model}


def load_config(root):
    path = config_path(root)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) != {'backend', 'model'}:
        raise ValueError('Configuração local inválida; use backend e model.')
    return validate(data['backend'], data['model'])


def save_config(root, backend, model):
    data = validate(backend, model)
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.config-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
