"""Short-lived runtime states, separate from durable conversation messages."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from uuid import uuid4

from .attachments import attachment_directory

LABELS = {'running': '● Trabalhando', 'waiting_input': '? Aguardando input', 'stopped': '○ Parado'}


def read_state(root, chat_id, now=None):
    try:
        attachment_directory(root, chat_id)  # Reuse validated IDs and project confinement.
        directory = Path(root).resolve() / '.centaur' / 'runtime'
        path = directory / (chat_id + '.json')
        if directory.is_symlink() or path.is_symlink():
            return 'stopped'
        with path.open('r', encoding='utf-8') as source:
            record = json.loads(source.read(4096))
        if (not isinstance(record, dict) or record.get('id') != chat_id or record.get('state') not in LABELS
                or type(record.get('pid')) is not int or record['pid'] <= 0
                or not isinstance(record.get('heartbeat'), (int,float))
                or not 0 <= (time.time() if now is None else now) - record['heartbeat'] <= 120):
            return 'stopped'
        try:
            os.kill(record['pid'], 0)
        except PermissionError:
            pass
        except (ProcessLookupError, OSError):
            return 'stopped'
        return record['state']
    except (OSError, ValueError, TypeError, KeyError):
        return 'stopped'


class SessionRegistry:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.owner = uuid4().hex
        self.records = {}
        self.lock = threading.Lock()
        self.last_heartbeat = 0

    def set(self, chat_id, state):
        if state not in LABELS:
            raise ValueError('Estado de sessão inválido.')
        with self.lock:
            record = {'id':chat_id,'state':state,'pid':os.getpid(),'owner':self.owner,'heartbeat':time.time()}
            self.records[chat_id] = record
            self._write(record)

    def _write(self, record):
        try:
            attachment_directory(self.root, record['id'])
            directory = self.root / '.centaur' / 'runtime'
            if directory.is_symlink():
                return
            directory.parent.mkdir(exist_ok=True, mode=0o700)
            directory.mkdir(exist_ok=True, mode=0o700)
            descriptor, temporary = tempfile.mkstemp(dir=directory)
            try:
                with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
                    json.dump(record, output)
                os.replace(temporary, directory / (record['id'] + '.json'))
            finally:
                Path(temporary).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass  # Display telemetry cannot stop or corrupt an authorized turn.

    def heartbeat(self):
        with self.lock:
            now = time.time()
            if now - self.last_heartbeat < 20:
                return
            self.last_heartbeat = now
            for record in self.records.values():
                if record['state'] != 'stopped':
                    record['heartbeat'] = now
                    self._write(record)

    def state(self, chat_id):
        return read_state(self.root, chat_id)
