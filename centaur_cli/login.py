"""Sessão expirada ou encerrada nos CLIs oficiais (Codex e Claude).

O harness não guarda credenciais desses backends: detecta que o CLI perdeu o login e
entrega o terminal ao fluxo oficial, que mostra o link de acesso e abre o navegador.
"""

import re
import subprocess
import sys

LOGIN = {'codex': ('login',), 'claude': ('auth', 'login')}
STATUS = {'codex': ('login', 'status'), 'claude': ('auth', 'status')}
# Diagnósticos públicos dos CLIs e das APIs quando falta ou venceu a credencial.
MARKS = re.compile(r'not logged in|please run /login|\b401\b|unauthorized|authentication_error|authentication_failed'
                   r'|invalid api key|invalid bearer token|invalid authentication|failed to authenticate'
                   r'|token (?:has )?expired|token (?:has been |was )?revoked|refresh token|(?:sign|log) in again'
                   r'|missing bearer')


def command_text(backend):
    return ' '.join((backend, *LOGIN[backend]))


class LoginRequired(RuntimeError):
    """O CLI oficial deste backend precisa de um novo login antes de continuar."""

    def __init__(self, backend, message=None):
        self.backend = backend
        super().__init__(message or f'{backend} não autenticado: a sessão foi encerrada ou expirou. '
                         f'Execute {command_text(backend)} para entrar novamente.')


def mentions_logout(text):
    return bool(MARKS.search(text.lower()))


def logged_in(backend, command):
    """True/False segundo o próprio CLI; None quando ele não respondeu."""
    try:
        result = subprocess.run([command, *STATUS[backend]], capture_output=True, text=True, timeout=15)
    except Exception:  # Consulta de melhor esforço: qualquer falha aqui significa apenas "não sei".
        return None
    return result.returncode == 0


def sign_in(backend, command, output=None):
    """Roda o login oficial neste terminal (link, navegador e código); True se o CLI confirmar o acesso."""
    output = output or sys.stdout
    output.write(f'\n{backend} perdeu o login. Abrindo o login oficial ({command_text(backend)}).\n'
                 'Abra o link abaixo se o navegador não abrir sozinho · Ctrl+C cancela.\n\n')
    output.flush()
    try:
        code = subprocess.run([command, *LOGIN[backend]]).returncode
    except KeyboardInterrupt:
        return False
    except OSError:
        return False
    return code == 0 and logged_in(backend, command) is not False
