"""Explicit speed selection; never switch models to obtain fast mode."""

import json
import os
from pathlib import Path

SPEEDS = ('standard', 'fast')


def validate_speed(speed):
    if speed not in SPEEDS:
        raise ValueError('Velocidade inválida: use standard ou fast.')
    return speed


def advertised_fast(entry):
    return (any(isinstance(tier, dict) and tier.get('id') in ('fast', 'priority')
                for tier in entry.get('service_tiers', []) or [])
            or 'fast' in (entry.get('additional_speed_tiers') or []))


def local_speed_support(backend):
    if backend != 'codex':
        return {}
    path = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'models_cache.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return {entry['slug']: advertised_fast(entry) for entry in data['models']
                if isinstance(entry, dict) and isinstance(entry.get('slug'), str)}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def fast_supported(backend, model, support=None):
    if backend == 'claude':
        # Official fast-mode models, including the current Opus alias. Unknown IDs
        # stay standard; selecting fast must never silently select another model.
        return model in ('opus', 'claude-opus-5-5', 'claude-opus-5', 'claude-opus-4-8')
    return (support or {}).get(model) is True
