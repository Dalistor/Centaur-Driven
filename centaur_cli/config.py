"""Preferências de backend e modelo por projeto, sem credenciais."""

import json
import os
from pathlib import Path
import re
import tempfile

BACKENDS = ('openrouter', 'codex', 'claude')
EFFORTS = ('default', 'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max')


def effort_options(backend):
    if backend == 'claude':
        return ('default', 'low', 'medium', 'high', 'xhigh', 'max')
    if backend == 'codex':
        return ('default', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max')
    return EFFORTS


def validate_effort(backend, effort):
    if effort not in effort_options(backend):
        raise ValueError(f'Effort inválido para {backend}: {", ".join(effort_options(backend))}.')
    return effort


def config_path(root):
    project = Path(root).resolve()
    path = (project / '.centaur/config.json').resolve()
    path.relative_to(project)
    return path


def validate(backend, model, effort=None):
    if backend not in BACKENDS:
        raise ValueError('Backend inválido: use openrouter, codex ou claude.')
    if not isinstance(model, str) or (model and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}', model)):
        raise ValueError('Nome do modelo inválido.')
    data = {'backend': backend, 'model': model}
    if effort is not None:
        data['effort'] = validate_effort(backend, effort)
    return data


def load_config(root):
    path = config_path(root)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or not {'backend', 'model'} <= set(data)
            or set(data) - {'backend', 'model', 'effort'}):
        raise ValueError('Configuração local inválida; use backend, model e effort opcional.')
    if 'effort' in data:
        validate_effort(data['backend'], data['effort'])
    return validate(data['backend'], data['model'], data.get('effort'))


def save_config(root, backend, model, effort=None):
    data = validate(backend, model, effort)
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
