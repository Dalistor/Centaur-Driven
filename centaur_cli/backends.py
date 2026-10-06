"""Seleção explícita de backend, sem fallback entre provedores."""

import os

from .config import BACKENDS, load_config, validate_effort
from .credentials import CredentialStore
from .native_client import NativeClient
from .openrouter import OpenRouter
from .setup import configure_key
from .permissions import validate_mode
from .speed import validate_speed


def resolve_model(backend, model=None):
    if model is not None:
        return model
    return os.environ.get('OPENROUTER_MODEL', '') if backend == 'openrouter' else os.environ.get('CENTAUR_MODEL', '')


def resolve_selection(root, backend=None, model=None):
    saved = load_config(root)
    selected = backend or os.environ.get('CENTAUR_BACKEND') or saved.get('backend', 'openrouter')
    if selected not in BACKENDS:
        raise ValueError('Backend inválido; use openrouter, codex ou claude.')
    if model is None:
        variable = 'OPENROUTER_MODEL' if selected == 'openrouter' else 'CENTAUR_MODEL'
        model = os.environ.get(variable)
        if model is None and saved.get('backend') == selected:
            model = saved.get('model')
    return selected, resolve_model(selected, model)


def resolve_effort(root, backend, effort=None):
    saved = load_config(root)
    selected = effort or os.environ.get('CENTAUR_EFFORT')
    if selected is None and saved.get('backend') == backend:
        selected = saved.get('effort')
    return validate_effort(backend, selected or 'default')


def resolve_approval_mode(root, mode=None):
    return validate_mode(mode or os.environ.get('CENTAUR_APPROVAL_MODE')
                         or load_config(root).get('approval_mode', 'ask'))


def resolve_speed(root, backend, speed=None):
    saved = load_config(root)
    return validate_speed(speed or os.environ.get('CENTAUR_SPEED')
                          or (saved.get('speed') if saved.get('backend') == backend else None) or 'standard')


def create_client(backend, model, allow_setup=True, include_credits=True):
    if backend not in BACKENDS:
        raise ValueError('Backend inválido; use openrouter, codex ou claude.')
    if backend != 'openrouter':
        client = NativeClient(backend, model)
        client.check_available()
        client.check_authentication()
        return client
    credentials = CredentialStore()
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        try:
            key = credentials.load()
        except (OSError, ValueError):
            print('Não foi possível ler a credencial OpenRouter local. Cadastre a chave novamente.')
    if not key:
        if not allow_setup:
            raise RuntimeError('Cadastre a chave com centaur --configure-key em um terminal antes de usar OpenRouter.')
        key = configure_key(credentials)
    credits_key = None
    if include_credits:
        credits_key = os.environ.get('OPENROUTER_CREDITS_KEY', '').strip()
        if not credits_key:
            try:
                credits_key = credentials.load_credits_key()
            except (OSError, ValueError):
                print('Credencial de créditos indisponível; usando apenas o limite da chave de chat.')
    return OpenRouter(key, credits_key)
