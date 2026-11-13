"""Conteúdo anterior dos arquivos alterados pelas ferramentas, para desfazer um turno."""

import json
import shutil
import threading
from pathlib import Path
from uuid import uuid4

MAX_FILE = 5_000_000
MAX_TURNS = 50


class Checkpoints:
    """Um diário por chat: a primeira versão de cada arquivo em cada turno.

    Cobre write_file e edit_file, inclusive de subagentes. Efeitos de comandos
    executados pelo shell não são registrados nem desfeitos.
    """
    lock = threading.Lock()

    def __init__(self, root, chat_id):
        self.root = Path(root).resolve()
        self.directory = self.root / '.centaur' / 'checkpoints' / chat_id
        self.journal = self.directory / 'journal.json'

    def load(self):
        try:
            entries = json.loads(self.journal.read_text(encoding='utf-8'))
            return entries if isinstance(entries, list) else []
        except (OSError, ValueError):
            return []

    def save(self, entries):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.directory / f'journal.{uuid4().hex}.tmp'
        temporary.write_text(json.dumps(entries, ensure_ascii=False), encoding='utf-8')
        temporary.replace(self.journal)

    def record(self, path, turn):
        """Chamado antes de gravar: guarda o estado do arquivo uma vez por turno."""
        relative = Path(path).resolve().relative_to(self.root).as_posix()
        with self.lock:
            entries = self.load()
            if any(entry['turn'] == turn and entry['path'] == relative for entry in entries):
                return
            entry = {'turn': turn, 'path': relative, 'existed': Path(path).is_file(), 'blob': None}
            if entry['existed'] and Path(path).stat().st_size <= MAX_FILE:
                entry['blob'] = uuid4().hex
                self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copyfile(path, self.directory / entry['blob'])
            entries.append(entry)
            turns = list(dict.fromkeys(item['turn'] for item in entries))
            for stale in [item for item in entries if item['turn'] in turns[:-MAX_TURNS]]:
                entries.remove(stale)
                if stale['blob']:
                    (self.directory / stale['blob']).unlink(missing_ok=True)
            self.save(entries)

    def rewind(self):
        """Desfaz o turno mais recente com alterações; retorna (restaurados, não restaurados)."""
        with self.lock:
            entries = self.load()
            if not entries:
                return [], []
            turn = entries[-1]['turn']
            restored, skipped = [], []
            for entry in reversed([item for item in entries if item['turn'] == turn]):
                target = self.root / entry['path']
                if not entry['existed']:
                    target.unlink(missing_ok=True)
                    restored.append(entry['path'] + ' (removido)')
                elif entry['blob'] and (self.directory / entry['blob']).is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(self.directory / entry['blob'], target)
                    (self.directory / entry['blob']).unlink(missing_ok=True)
                    restored.append(entry['path'])
                else:
                    skipped.append(entry['path'])
            self.save([item for item in entries if item['turn'] != turn])
            return restored, skipped
