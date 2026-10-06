"""Seleção explícita de backend, sem fallback entre provedores."""

import os

from .credentials import CredentialStore
from .native_client import NativeClient
from .openrouter import OpenRouter
from .setup import configure_key

BACKENDS = ('openrouter', 'codex', 'claude')


def resolve_model(backend, model=None):
    if model is not None:
        return model
    return os.environ.get('OPENROUTER_MODEL', '') if backend == 'openrouter' else os.environ.get('CENTAUR_MODEL', '')


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
