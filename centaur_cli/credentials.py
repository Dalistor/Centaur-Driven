"""Credencial local do CLI, independente das pastas e históricos de projeto."""

import json
import os
import stat
import tempfile
from pathlib import Path


def credentials_path():
    base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    if not base.is_absolute():
        base = Path.home() / '.config'
    return base / 'centaur' / 'credentials.json'


def valid_key_input(key):
    return isinstance(key, str) and bool(key) and key.isascii() and not any(character.isspace() or not character.isprintable() for character in key)


class CredentialStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else credentials_path()

    def load(self):
        key = self._load_data().get('openrouter_api_key')
        return key if valid_key_input(key) else None

    def load_credits_key(self):
        key = self._load_data().get('openrouter_credits_key')
        return key if valid_key_input(key) else None

    def _load_data(self):
        try:
            descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return {}
        with os.fdopen(descriptor, encoding='utf-8') as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise ValueError('Arquivo de credenciais não pertence ao usuário.')
            os.fchmod(source.fileno(), 0o600)
            try:
                data = json.load(source)
            except (ValueError, KeyError, TypeError):
                return {}
        return data if isinstance(data, dict) else {}

    def save(self, key):
        self._save_key('openrouter_api_key', key)

    def save_credits_key(self, key):
        self._save_key('openrouter_credits_key', key)

    def _save_key(self, field, key):
        if not valid_key_input(key):
            raise ValueError('Chave inválida.')
        data = self._load_data()
        data[field] = key
        directory = self.path.parent
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if directory.is_symlink() or directory.stat().st_uid != os.getuid():
            raise ValueError('Pasta de credenciais insegura.')
        directory.chmod(0o700)
        descriptor, temporary = tempfile.mkstemp(dir=directory, suffix='.tmp')
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
                json.dump(data, output)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)
