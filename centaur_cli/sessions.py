"""Short-lived runtime states, separate from durable conversation messages."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import math
from uuid import uuid4

from .attachments import attachment_directory

LABELS = {'running': '● Trabalhando', 'waiting_input': '? Aguardando input', 'stopped': '○ Parado'}
NATIVE_PHASES = {'thread.started': 'sessão iniciada', 'turn.started': 'turno iniciado',
                 'turn.completed': 'turno concluído', 'turn.failed': 'turno falhou',
                 'error': 'aviso de erro', 'item.started': 'item iniciado',
                 'item.updated': 'item atualizado', 'item.completed': 'item concluído',
                 'system': 'sessão iniciada', 'assistant': 'resposta em andamento',
                 'result': 'resultado recebido', 'rate_limit_event': 'aviso de cota'}
NATIVE_WARNINGS = ('rede', 'TLS', 'cota', 'contexto', 'schema', 'configuração')
NATIVE_STATES = ('running', 'completed', 'cancelled', 'timeout', 'failed')


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
              'tool:delegate_task': 'Aguardando subagente',
              'tool:wait_agents': 'Aguardando subagentes',
              'tool:agent_status': 'Consultando agentes',
              'tool:send_agent_message': 'Enviando orientação',
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


def native_activity_label(root, chat_id, now=None):
    record = read_record(root, chat_id, now)
    if not record or record['state'] != 'running' or record.get('phase') != 'model':
        return ''
    started = record.get('native_last_output')
    if type(started) not in (int, float):
        return ''
    current = time.time() if now is None else now
    elapsed = max(0, int(current - started))
    duration = f'{elapsed // 60}m {elapsed % 60:02}s'
    warning = record.get('native_warning')
    recovery = record.get('native_recovery_started')
    if record.get('native_recovering') is True and type(recovery) in (int, float):
        seconds = max(0, int(current - recovery))
        return f'CLI · Reconectando há {seconds // 60}m {seconds % 60:02}s · erro de rede observado'
    if warning in NATIVE_WARNINGS:
        return f'Aviso: {warning} · sem saída há {duration}'
    kind = record.get('native_event')
    if elapsed >= 30:
        phase = NATIVE_PHASES.get(kind, 'sem evento completo') if isinstance(kind, str) else 'sem evento completo'
        return f'CLI · {phase} · Sem nova saída do CLI há {duration}'
    return 'CLI · ' + (NATIVE_PHASES.get(kind, 'aguardando eventos') if isinstance(kind, str) else 'aguardando eventos')


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
            for key in ('phase', 'phase_started', *(key for key in previous if key.startswith('native_'))):
                if key in previous:
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
            for key in list(record):
                if key.startswith('native_'):
                    record.pop(key)
            self._write(record)

    def native_event(self, chat_id, event):
        """Copy fixed metadata only; activity/heartbeat never renew inference time."""
        with self.lock:
            record = self.records.get(chat_id)
            if not record or record['state'] != 'running' or record.get('phase') != 'model' or not isinstance(event, dict):
                return
            now = time.time()
            sizes = tuple(event.get(key) for key in ('output_bytes', 'stderr_bytes'))
            if not all(type(size) is int and 0 <= size <= 8_000_000 for size in sizes):
                return
            previous = (record.get('native_output_bytes'), record.get('native_stderr_bytes'))
            if sizes != previous:
                record['native_last_output'] = now
            record.update(native_output_bytes=sizes[0], native_stderr_bytes=sizes[1])
            kind, warning = event.get('event'), event.get('warning')
            record['native_event'] = kind if isinstance(kind, str) and kind in NATIVE_PHASES else ''
            record['native_warning'] = warning if isinstance(warning, str) and warning in NATIVE_WARNINGS else ''
            recovering = event.get('recovering') is True
            episode = event.get('recovery_episode')
            if type(episode) is not int or not 0 <= episode <= 1_000_000:
                episode = 0
            if recovering and (not record.get('native_recovering') or episode != record.get('native_recovery_episode')):
                record['native_recovery_started'] = now
            elif not recovering:
                record.pop('native_recovery_started', None)
            record['native_recovering'] = recovering
            record['native_recovery_episode'] = episode
            errors = event.get('recovery_errors')
            if type(errors) is int and 0 <= errors <= 1_000_000:
                record['native_recovery_errors'] = errors
            for key, maximum in (('process_pid', 2**31 - 1), ('input_bytes', 100_000_000)):
                value = event.get(key)
                if type(value) is int and 0 <= value <= maximum:
                    record['native_' + key] = value
            for key in ('timeout_seconds', 'elapsed_seconds'):
                value = event.get(key)
                if type(value) in (int, float) and 0 <= value <= 100_000 and math.isfinite(value):
                    record['native_' + key] = value
            if event.get('status') in NATIVE_STATES:
                record['native_status'] = event['status']
            if event.get('backend') in ('codex', 'claude'):
                record['native_backend'] = event['backend']
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
