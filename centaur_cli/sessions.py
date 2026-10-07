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


def read_record(root, chat_id, now=None):
    try:
        attachment_directory(root, chat_id)  # Reuse validated IDs and project confinement.
        directory = Path(root).resolve() / '.centaur' / 'runtime'
        path = directory / (chat_id + '.json')
        if directory.is_symlink() or path.is_symlink():
            return None
        with path.open('r', encoding='utf-8') as source:
            record = json.loads(source.read(4096))
        if (not isinstance(record, dict) or record.get('id') != chat_id or record.get('state') not in LABELS
                or type(record.get('pid')) is not int or record['pid'] <= 0
                or not isinstance(record.get('heartbeat'), (int,float))
                or not 0 <= (time.time() if now is None else now) - record['heartbeat'] <= 120):
            return None
        try:
            os.kill(record['pid'], 0)
        except PermissionError:
            pass
        except (ProcessLookupError, OSError):
            return None
        return record
    except (OSError, ValueError, TypeError, KeyError):
        return None


def read_state(root, chat_id, now=None):
    record = read_record(root, chat_id, now)
    return record['state'] if record else 'stopped'


def activity_label(root, chat_id, now=None):
    record = read_record(root, chat_id, now)
    if not record or record['state'] == 'stopped':
        return ''
    if record['state'] == 'waiting_input':
        return 'Aguardando input'
    labels = {'model': 'Aguardando modelo', 'compact': 'Compactando contexto',
              'tool:run_command': 'Executando comando', 'tool:read_file': 'Lendo arquivo',
              'tool:read_skill': 'Consultando skill', 'tool:write_file': 'Gravando arquivo',
              'tool:list_files': 'Consultando arquivos', 'tool:report_progress': 'Atualizando progresso',
              'tool:ask_user': 'Preparando pergunta'}
    phase = record.get('phase')
    label = labels.get(phase, 'Trabalhando') if isinstance(phase, str) else 'Trabalhando'
    started = record.get('phase_started')
    current = time.time() if now is None else now
    if type(started) in (int, float) and 0 <= current - started < 86400:
        elapsed = int(current - started)
        label += f' · {elapsed // 60}m {elapsed % 60:02}s'
    return label


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
            previous = self.records.get(chat_id, {})
            for key in ('phase', 'phase_started'):
                if key in previous and state != 'stopped':
                    record[key] = previous[key]
            if previous.get('state') == 'waiting_input' and state == 'running' and 'phase' in record:
                record['phase_started'] = time.time()
            self.records[chat_id] = record
            self._write(record)

    def activity(self, chat_id, phase):
        with self.lock:
            record = self.records.get(chat_id)
            if record is None or record['state'] == 'stopped':
                return
            record.update(phase=phase, phase_started=time.time(), heartbeat=time.time())
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
