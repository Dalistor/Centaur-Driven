"""Histórico de conversas da pasta aberta."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class ChatStore:
    def __init__(self, root):
        self.directory = Path(root).resolve() / '.centaur' / 'chats'

    def new(self, model, backend='openrouter'):
        return {'id': uuid4().hex, 'title': 'Novo chat', 'model': model, 'backend': backend,
                'updated': datetime.now(timezone.utc).isoformat(), 'messages': []}

    def save(self, chat):
        self.path(chat['id'])
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        chat['updated'] = datetime.now(timezone.utc).isoformat()
        descriptor, temporary = tempfile.mkstemp(dir=self.directory, suffix='.tmp')
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
                json.dump(chat, output, ensure_ascii=False, indent=2)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.directory / (chat['id'] + '.json'))
        finally:
            Path(temporary).unlink(missing_ok=True)

    def list(self):
        chats = []
        for path in self.directory.glob('*.json'):
            try:
                chat = json.loads(path.read_text(encoding='utf-8'))
                if (chat['id'] == path.stem and len(chat['id']) == 32
                        and all(c in '0123456789abcdef' for c in chat['id'])
                        and isinstance(chat.get('model'), str)
                        and chat.get('backend', 'openrouter') in ('openrouter', 'codex', 'claude')
                        and isinstance(chat['messages'], list)
                        and isinstance(chat['title'], str)
                        and isinstance(chat['updated'], str)):
                    chats.append(chat)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return sorted(chats, key=lambda chat: chat['updated'], reverse=True)

    def delete(self, chat_id):
        self.path(chat_id).unlink(missing_ok=True)

    def path(self, chat_id):
        if (not isinstance(chat_id, str) or len(chat_id) != 32
                or any(character not in '0123456789abcdef' for character in chat_id)):
            raise ValueError('Identificador de chat inválido.')
        path = (self.directory / (chat_id + '.json')).resolve()
        path.relative_to(self.directory.resolve())
        return path

    def rename(self, chat_id, title):
        if (not isinstance(title, str) or not title.strip() or len(title.strip()) > 80
                or any(not character.isprintable() for character in title)):
            raise ValueError('Use um título de 1 a 80 caracteres, sem quebras de linha.')
        chat = json.loads(self.path(chat_id).read_text(encoding='utf-8'))
        if chat.get('id') != chat_id:
            raise ValueError('Identificador do chat diverge do arquivo.')
        chat['title'], chat['title_custom'] = title.strip(), True
        self.save(chat)
        return chat

    def generated_title(self, chat_id, title):
        """Merge only title metadata into the latest file; manual rename always wins."""
        if (not isinstance(title, str) or not title.strip() or len(title) > 60
                or any(not c.isprintable() for c in title)):
            raise ValueError('Título gerado inválido.')
        chat = json.loads(self.path(chat_id).read_text(encoding='utf-8'))
        if chat.get('id') != chat_id:
            raise ValueError('Identificador do chat diverge do arquivo.')
        if chat.get('title_custom') or chat.get('title_generated'):
            return None
        chat['title'] = title.strip()
        chat['title_generated'] = True
        self.save(chat)
        return chat
