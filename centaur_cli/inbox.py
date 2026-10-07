"""Durable user steering, delivered only at harness boundaries by its worker."""
import json
import os
from pathlib import Path
import tempfile
import threading
from uuid import uuid4

from .attachments import attachment_directory


class Inbox:
    def __init__(self, root, chat_id):
        attachment_directory(root, chat_id)
        self.directory = Path(root).resolve() / '.centaur' / 'inbox'
        self.path = self.directory / (chat_id + '.json')
        self.lock = threading.RLock()
        self.root, self.chat_id = root, chat_id
        self.items = []
        if self.directory.is_symlink() or self.path.is_symlink():
            raise ValueError('Fila de mensagens fora do projeto.')
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, list) or len(data) > 16 or any(
                not isinstance(item, dict) or not isinstance(item.get('id'), str)
                or not isinstance(item.get('message'), dict) or item['message'].get('role') != 'user'
                for item in data):
                raise ValueError('Fila de mensagens inválida; histórico preservado.')
            self.items = data

    def save(self):
        attachment_directory(self.root, self.chat_id)
        if self.directory.is_symlink() or self.path.is_symlink():
            raise ValueError('Fila de mensagens fora do projeto.')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(dir=self.directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                json.dump(self.items, output, ensure_ascii=False)
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def put(self, message):
        with self.lock:
            if len(self.items) >= 16:
                raise ValueError('Até 16 mensagens aguardando; aguarde a entrega antes de enviar outra.')
            item = {'id': uuid4().hex, 'message': message}
            self.items.append(item)
            try:
                self.save()
            except Exception:
                self.items.remove(item)
                raise

    def snapshot(self):
        with self.lock:
            return list(self.items)

    def acknowledge(self, identifiers):
        with self.lock:
            previous = self.items
            self.items = [item for item in self.items if item['id'] not in identifiers]
            try:
                self.save()
            except Exception:
                self.items = previous
                raise
