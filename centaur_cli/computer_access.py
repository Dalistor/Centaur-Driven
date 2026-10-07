"""Chat-scoped consent and exclusive foreground desktop ownership."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import weakref

from .attachments import attachment_directory
from .interaction import TurnCancelled


class ComputerPermissions:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.directory = self.root / '.centaur' / 'computer-permissions'

    def path(self, chat_id):
        attachment_directory(self.root, chat_id)
        path = self.directory / (chat_id + '.json')
        if self.directory.parent.is_symlink() or self.directory.is_symlink() or path.is_symlink():
            raise ValueError('Permissões de computer use não podem ser redirecionadas.')
        return path

    def granted(self, chat_id):
        try:
            with self.path(chat_id).open(encoding='utf-8') as source:
                record = json.loads(source.read(4096))
            return (isinstance(record, dict) and record.get('schema') == 1
                    and record.get('id') == chat_id and record.get('granted') is True)
        except (OSError, ValueError, TypeError):
            return False

    def grant(self, chat_id):
        path = self.path(chat_id)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary = tempfile.mkstemp(dir=self.directory)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
                json.dump({'schema':1,'id':chat_id,'granted':True,
                           'granted_at':datetime.now(timezone.utc).isoformat()}, output)
                output.flush(); os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def revoke(self, chat_id):
        self.path(chat_id).unlink(missing_ok=True)


class DesktopLease:
    """An OS lock survives threads, spans projects, and releases on process exit."""
    def __init__(self, path=None):
        # Linux and macOS share /tmp across projects, including custom TMPDIRs.
        self.path = Path(path) if path else Path('/tmp') / f'centaur-desktop-{os.getuid()}.lock'
        self.descriptor = None

    def acquire(self):
        if self.descriptor is not None:
            return
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise ValueError('Registro de controle do desktop inválido.')
            os.fchmod(descriptor, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('Outro chat/processo controla o desktop; aguarde ou pause nele antes de iniciar.') from None
        except BaseException:
            os.close(descriptor)
            raise
        self.descriptor = descriptor

    def release(self):
        if self.descriptor is not None:
            descriptor, self.descriptor = self.descriptor, None
            os.close(descriptor)  # Do not unlink the lock: another process may own the same inode.


class ComputerControl:
    def __init__(self, root, foreground, *, lease=None):
        self.permissions = ComputerPermissions(root)
        self.foreground = foreground
        self.paused = set()
        self.condition = threading.Condition(threading.RLock())
        self.sessions = weakref.WeakSet()
        self.owner = None
        self.lease = lease or DesktopLease()

    def register(self, session):
        with self.condition:
            self.sessions.add(session)

    def allowed(self, chat_id):
        return self.foreground == chat_id and chat_id not in self.paused

    def focus(self, chat_id):
        with self.condition:
            if self.foreground == chat_id:
                return
            self.foreground = chat_id  # Block input before waiting for an in-flight chunk.
            sessions = [s for s in self.sessions if s.chat_id != chat_id]
        for session in sessions:
            session.suspend()
        with self.condition:
            self.condition.notify_all()

    def wait(self, chat_id, cancellation, emit):
        waiting = False
        with self.condition:
            while not self.allowed(chat_id):
                if cancellation and cancellation.is_set():
                    raise TurnCancelled('Controle de computador interrompido.')
                if not waiting:
                    emit('Computador pausado · volte ao chat ou use $computer resume.')
                    waiting = True
                self.condition.wait(.1)
        if cancellation and cancellation.is_set():
            raise TurnCancelled('Controle de computador interrompido.')
        if waiting:
            emit('Retomando controle do computador…')

    def claim(self, session):
        with self.condition:
            if not self.allowed(session.chat_id):
                raise ValueError('Controle pausado; volte ao chat antes de continuar.')
            if self.owner is not None and self.owner is not session:
                raise ValueError('Outro chat controla o desktop; aguarde a liberação.')
            self.lease.acquire()
            self.owner = session

    def release(self, session):
        with self.condition:
            if self.owner is session:
                self.owner = None
                self.lease.release()
            self.condition.notify_all()

    def pause(self, chat_id):
        with self.condition:
            self.paused.add(chat_id)
            sessions = [s for s in self.sessions if s.chat_id == chat_id]
        for session in sessions:
            session.suspend()

    def resume(self, chat_id):
        with self.condition:
            self.paused.discard(chat_id)
            self.condition.notify_all()

    def grant(self, chat_id, cancellation):
        # Serialize persistence with revoke; a late approval cannot resurrect access.
        with self.condition:
            if cancellation and cancellation.is_set():
                raise TurnCancelled('Autorização interrompida antes de salvar.')
            self.permissions.grant(chat_id)

    def revoke(self, chat_id):
        with self.condition:
            self.permissions.revoke(chat_id)
            sessions = [s for s in self.sessions if s.chat_id == chat_id]
        for session in sessions:
            session.authorized = False
            session.close()
