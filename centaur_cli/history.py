"""Histórico de conversas da pasta aberta."""

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .attachments import attachment_directory
from .sessions import read_state
from .computer_access import ComputerPermissions


class ChatStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.directory = self.root / '.centaur' / 'chats'

    def new(self, model, backend='openrouter'):
        created = datetime.now(timezone.utc).isoformat()
        return {'created': created, 'id': uuid4().hex, 'title': 'Novo chat', 'model': model, 'backend': backend,
                'updated': created, 'messages': []}

    def save(self, chat, *, touch=True):
        path = self.path(chat['id'])
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(existing, dict):
                    raise ValueError('Histórico inválido.')
                chat['created'] = existing.get('created') or existing['updated']
            except (OSError, ValueError, KeyError, TypeError):
                chat.setdefault('created', chat.get('updated') or datetime.now(timezone.utc).isoformat())
        else:
            chat.setdefault('created', chat.get('updated') or datetime.now(timezone.utc).isoformat())
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if touch:
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

    def list(self, *, active_only=False):
        chats = []
        for path in self.directory.glob('*.json'):
            try:
                if path.is_symlink():
                    continue
                if active_only and read_state(self.root, path.stem) == 'stopped':
                    continue  # Do not repeatedly deserialize archived transcripts.
                chat = json.loads(path.read_text(encoding='utf-8'))
                if (chat['id'] == path.stem and len(chat['id']) == 32
                        and all(c in '0123456789abcdef' for c in chat['id'])
                        and isinstance(chat.get('model'), str)
                        and chat.get('backend', 'openrouter') in ('openrouter', 'codex', 'claude')
                        and isinstance(chat['messages'], list)
                        and isinstance(chat['title'], str)
                        and isinstance(chat['updated'], str)):
                    if not chat.get('created'):
                        chat['created'] = chat['updated']
                        self.save(chat, touch=False)
                    chats.append(chat)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return sorted(chats, key=lambda chat: chat['updated'], reverse=True)

    def delete(self, chat_id):
        path = self.path(chat_id)
        if read_state(self.root, chat_id) != 'stopped':
            raise ValueError('Aguarde a sessão terminar antes de excluir o chat.')
        directory = attachment_directory(self.root, chat_id)
        descendants = self.root / '.centaur' / 'agents' / chat_id
        runtime = self.root / '.centaur' / 'runtime'
        if descendants.is_symlink() or descendants.parent.is_symlink() or runtime.is_symlink():
            raise ValueError('Histórico de agentes/runtime não pode ser redirecionado.')
        children = []
        if descendants.exists():
            all_agents = self.agents()
            pending = {chat_id}
            seen = set()
            while pending:
                parent = pending.pop()
                if parent in seen:
                    continue
                seen.add(parent)
                direct = [child for child in all_agents if child['parent_id'] == parent and child['id'] != chat_id]
                children.extend(direct)
                pending.update(child['id'] for child in direct)
            if any(read_state(self.root, child['id']) != 'stopped' for child in children):
                raise ValueError('Aguarde os subagentes terminarem antes de excluir o chat.')
            for child in children:
                (runtime / (child['id'] + '.json')).unlink(missing_ok=True)
                child_attachments = attachment_directory(self.root, child['id'])
                if child_attachments.exists():
                    shutil.rmtree(child_attachments)
                child_directory = descendants.parent / child['id']
                if child_directory.is_symlink():
                    raise ValueError('Histórico de agentes não pode ser redirecionado.')
                if child_directory.exists():
                    shutil.rmtree(child_directory)
            if descendants.exists():
                shutil.rmtree(descendants)
        if directory.exists():
            shutil.rmtree(directory)
        (runtime / (chat_id + '.json')).unlink(missing_ok=True)
        ComputerPermissions(self.root).revoke(chat_id)
        inbox_directory = self.root / '.centaur' / 'inbox'
        inbox_path = inbox_directory / (chat_id + '.json')
        if not inbox_directory.is_symlink() and not inbox_path.is_symlink():
            inbox_path.unlink(missing_ok=True)
        path.unlink(missing_ok=True)

    def agents(self, parent_id=None, *, active_only=False):
        base = self.root / '.centaur' / 'agents'
        if base.is_symlink():
            return []
        output = []
        for directory in base.glob('*'):
            if not directory.is_dir() or directory.is_symlink():
                continue
            try:
                self.path(directory.name)
            except ValueError:
                continue
            if parent_id and directory.name != parent_id:
                continue
            store = ChatStore(self.root)
            store.directory = directory
            output.extend(chat for chat in store.list(active_only=active_only) if chat.get('parent_id') == directory.name)
        return sorted(output, key=lambda chat: chat['updated'], reverse=True)

    def ancestors(self, agents):
        """Read only the parents needed by live cards, never unrelated archives."""
        base = self.root / '.centaur' / 'agents'
        pending = [agent.get('parent_id') for agent in agents]
        seen, output = set(), []
        while pending:
            parent = pending.pop()
            if not isinstance(parent, str) or parent in seen:
                continue
            seen.add(parent)
            try:
                self.path(parent)  # Validate before using IDs as file names.
            except ValueError:
                continue
            candidates = [self.root / '.centaur' / 'chats' / (parent + '.json')]
            if not base.is_symlink():
                candidates.extend(base.glob('*/' + parent + '.json'))
            for path in candidates:
                if path.is_symlink() or path.parent.is_symlink():
                    continue
                try:
                    record = json.loads(path.read_text(encoding='utf-8'))
                    if not isinstance(record, dict) or record.get('id') != parent or not isinstance(record.get('title'), str):
                        continue
                    if path.parent != self.root / '.centaur' / 'chats' and record.get('parent_id') != path.parent.name:
                        continue
                    output.append({key: record[key] for key in ('id', 'title', 'parent_id', 'updated', 'created') if key in record})
                    pending.append(record.get('parent_id'))
                    break
                except (OSError, ValueError, TypeError):
                    continue
        return output

    def prune(self, protected=(), now=None):
        """Delete expired, inactive sessions by immutable creation time."""
        now = datetime.now(timezone.utc) if now is None else now
        protected = set(protected)
        agents = self.agents() if self.directory == self.root / '.centaur' / 'chats' else []
        active = [chat for chat in agents if read_state(self.root, chat['id']) != 'stopped']
        protected.update(chat['parent_id'] for chat in active)
        protected.update(parent['id'] for parent in self.ancestors(active))
        for chat in self.list():
            try:
                inbox = self.root / '.centaur' / 'inbox' / (chat['id'] + '.json')
                if inbox.is_file() and not inbox.is_symlink() and not inbox.parent.is_symlink() and json.loads(inbox.read_text()):
                    protected.add(chat['id'])
            except (OSError, ValueError):
                pass
        removed = []
        for chat in self.list():
            try:
                if not isinstance(chat.get('created'), str):
                    continue
                created = datetime.fromisoformat(chat['created'].replace('Z','+00:00'))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                expired = (now - created).total_seconds() > 64 * 3600
                if expired and chat['id'] not in protected and read_state(self.root, chat['id']) == 'stopped':
                    self.delete(chat['id'])
                    removed.append(chat['id'])
            except (OSError, ValueError, TypeError):
                continue
        # Subagent records also expire independently, unless their parent is active.
        for chat in agents:
            if chat['parent_id'] in protected or read_state(self.root, chat['parent_id']) != 'stopped':
                continue
            store = ChatStore(self.root)
            store.directory = self.root / '.centaur' / 'agents' / chat['parent_id']
            removed.extend(store.prune(protected, now))
        return removed

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
