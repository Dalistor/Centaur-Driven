"""Preferências de backend e modelo por projeto, sem credenciais."""

import json
import os
from pathlib import Path
import re
import tempfile
from .permissions import validate_mode
from .speed import validate_speed

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


def validate(backend, model, effort=None, approval_mode=None, speed=None):
    if backend not in BACKENDS:
        raise ValueError('Backend inválido: use openrouter, codex ou claude.')
    if not isinstance(model, str) or (model and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}', model)):
        raise ValueError('Nome do modelo inválido.')
    data = {'backend': backend, 'model': model}
    if effort is not None:
        data['effort'] = validate_effort(backend, effort)
    if approval_mode is not None:
        data['approval_mode'] = validate_mode(approval_mode)
    if speed is not None:
        data['speed'] = validate_speed(speed)
    return data


def load_config(root):
    path = config_path(root)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or not {'backend', 'model'} <= set(data)
            or set(data) - {'backend', 'model', 'effort', 'approval_mode', 'speed', 'setup_complete'}):
        raise ValueError('Configuração local inválida; use backend, model, effort e approval_mode opcionais.')
    if 'effort' in data:
        validate_effort(data['backend'], data['effort'])
    result = validate(data['backend'], data['model'], data.get('effort'), data.get('approval_mode'), data.get('speed'))
    if 'setup_complete' in data:
        if not isinstance(data['setup_complete'], bool):
            raise ValueError('Configuração local inválida: setup_complete.')
        result['setup_complete'] = data['setup_complete']
    return result


def save_config(root, backend, model, effort=None, approval_mode=None, speed=None):
    data = validate(backend, model, effort, approval_mode, speed)
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            previous = load_config(root)
        except ValueError:
            backup_dir = (path.parent / 'backups').resolve()
            backup_dir.relative_to(Path(root).resolve())
            backup_dir.mkdir(parents=True, exist_ok=True)
            descriptor, backup = tempfile.mkstemp(prefix='config-', suffix='.json', dir=backup_dir)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(path.read_text(encoding='utf-8'))
            previous = {}
        data.update({field: previous[field] for field in ('approval_mode', 'speed')
                     if field in previous and field not in data and previous.get('backend') == backend})
    data['setup_complete'] = True
    descriptor, temporary = tempfile.mkstemp(prefix='.config-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
