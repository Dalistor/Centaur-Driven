"""Read-only quota adapters. Credentials remain owned by the native CLIs."""

import json
import math
import os
import selectors
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from decimal import Decimal

from .credits import amount
from . import __version__


@dataclass(frozen=True)
class QuotaWindow:
    label: str
    remaining: float | None
    resets_at: int | None = None
    status: str = ''


@dataclass(frozen=True)
class NativeBalance:
    backend: str
    windows: tuple = ()
    credits: Decimal | None = None
    has_credits: bool | None = None
    unlimited: bool = False


class BalanceUnavailable(RuntimeError):
    def __init__(self, message, status='unsupported'):
        super().__init__(message)
        self.status = status


def percentage(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    return max(0, min(100, 100 - value))


def timestamp(value):
    return value if type(value) is int and value >= 0 else None


def codex_balance(result):
    snapshot = (result.get('rateLimitsByLimitId') or {}).get('codex') or result.get('rateLimits') or {}
    if not isinstance(snapshot, dict):
        raise BalanceUnavailable('Codex não informou limites de uso.')
    windows = []
    for key, fallback in (('primary', 'Sessão'), ('secondary', 'Semana')):
        value = snapshot.get(key)
        if not isinstance(value, dict): continue
        duration = value.get('windowDurationMins')
        label = ('7d' if duration == 10080 else f'{duration // 60}h' if type(duration) is int and duration % 60 == 0
                 else f'{duration}m' if type(duration) is int else fallback)
        remaining = percentage(value.get('usedPercent'))
        if remaining is not None:
            windows.append(QuotaWindow(label, remaining, timestamp(value.get('resetsAt'))))
    credits = snapshot.get('credits') or {}
    if not isinstance(credits, dict): credits = {}
    balance = None
    try:
        if credits.get('balance') is not None: balance = amount(credits['balance'])
    except (ValueError, TypeError, ArithmeticError): pass
    has_credits = credits.get('hasCredits') if type(credits.get('hasCredits')) is bool else None
    unlimited = credits.get('unlimited') is True
    if not windows and balance is None and has_credits is None and not unlimited:
        raise BalanceUnavailable('Codex não expôs saldo/cota para esta autenticação.')
    return NativeBalance('codex', tuple(windows), balance, has_credits, unlimited)


def claude_windows(events):
    result = {}
    names = {'five_hour': '5h', 'seven_day': 'Semana', 'seven_day_opus': '7d Opus',
             'seven_day_sonnet': '7d Sonnet', 'overage': 'Extra'}
    for event in events:
        info = event.get('rate_limit_info')
        if not isinstance(info, dict): continue
        kind, status = info.get('rateLimitType'), info.get('status')
        if kind not in names or status not in ('allowed', 'allowed_warning', 'rejected'): continue
        value = info.get('utilization')
        remaining = percentage(value * 100) if type(value) in (int, float) else None
        # An allowed event without utilization does not imply a full allowance.
        if remaining is None and status == 'rejected': remaining = 0
        result[kind] = QuotaWindow(names[kind], remaining, timestamp(info.get('resetsAt')), status)
        # O evento nomeia só a janela mais apertada; o uso de todas vem junto em unifiedWindows.
        unified = info.get('unifiedWindows')
        for name, window in (unified.items() if isinstance(unified, dict) else ()):
            used = window.get('utilization') if isinstance(window, dict) else None
            if name not in names or type(used) not in (int, float) or percentage(used * 100) is None:
                continue
            state = window.get('status') if window.get('status') in ('allowed', 'allowed_warning', 'rejected') else (
                status if name == kind else 'allowed')
            result[name] = QuotaWindow(names[name], percentage(used * 100), timestamp(window.get('resetsAt')), state)
    return result


def store_windows(windows):
    """Forma gravável das janelas, para mostrá-las antes da primeira resposta da próxima sessão."""
    return {name: {'label': window.label, 'remaining': window.remaining, 'resets_at': window.resets_at, 'status': window.status}
            for name, window in windows.items()}


def restore_windows(stored, now=None):
    """Janelas ainda vigentes de uma sessão anterior; a que já reiniciou não é mostrada."""
    now, result = time.time() if now is None else now, {}
    for name, entry in (stored.items() if isinstance(stored, dict) else ()):
        if not isinstance(entry, dict) or not isinstance(entry.get('label'), str):
            continue
        remaining, resets = entry.get('remaining'), timestamp(entry.get('resets_at'))
        if resets is None or resets <= now:
            continue
        if remaining is not None and (type(remaining) not in (int, float) or not 0 <= remaining <= 100):
            continue
        result[name] = QuotaWindow(entry['label'][:16], remaining, resets, str(entry.get('status') or '')[:20])
    return result


def reset_label(resets_at, now=None):
    """Hora do reinício se for nas próximas 24h; depois disso, dia da semana e data."""
    now = time.time() if now is None else now
    if type(resets_at) is not int or resets_at <= now:
        return ''
    moment = time.localtime(resets_at)
    if resets_at - now < 86400:
        return time.strftime('%H:%M', moment)
    return ('seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom')[moment.tm_wday] + time.strftime(' %d/%m', moment)


def native_label(balance, status, width, backend=''):
    name = (balance.backend if balance else backend).capitalize() or 'Uso'
    if not balance:
        suffix = 'após resposta' if status == 'awaiting' else 'consultando' if status == 'loading' else 'indisponível'
        return f'{name}: {suffix}', 'muted'
    values = []
    if balance.credits is not None:
        values.append(f'créditos {balance.credits:.2f}')
    elif balance.unlimited:
        values.append('créditos sem limite')
    elif balance.has_credits is not None:
        values.append('créditos disponíveis' if balance.has_credits else 'créditos esgotados')
    for window in balance.windows:
        value = f'{window.remaining:.0f}% livre' if window.remaining is not None else {
            'allowed': 'disponível', 'allowed_warning': 'quase no limite', 'rejected': 'limite atingido'}.get(window.status, '?')
        values.append(f'{window.label}: {value}')
    stale = '~' if status == 'error' or balance.backend == 'claude' else ''
    label = f'{name} {stale}' + ' · '.join(values)
    # Com espaço, diz também quando cada janela reinicia.
    resets = [reset_label(window.resets_at) for window in balance.windows]
    if any(resets) and len(values) >= len(resets):
        offset = len(values) - len(resets)
        detailed = f'{name} {stale}' + ' · '.join(values[:offset] + [
            value + (f' (reinicia {reset})' if reset else '') for value, reset in zip(values[offset:], resets)])
        if len(detailed) <= width:
            label = detailed
    if len(label) > width:
        parts = ([f'Créd {balance.credits:.1f}'] if balance.credits is not None else [])
        parts += [f'{w.label} {w.remaining:.0f}%' if w.remaining is not None else f'{w.label} ?' for w in balance.windows]
        label = stale + ' · '.join(parts or values)
    low = any((w.remaining is not None and w.remaining <= 20) or w.status in ('allowed_warning', 'rejected') for w in balance.windows)
    return label, 'warning' if low or status == 'error' or balance.has_credits is False else 'green'


def read_codex_balance(command, timeout=10):
    """One isolated stdio handshake and account read; no thread, prompt or tools."""
    with tempfile.TemporaryDirectory(prefix='centaur-usage-') as directory:
        process = subprocess.Popen([command, 'app-server', '--listen', 'stdio://',
                                    '--config', 'mcp_servers={}'], cwd=directory,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   env={key: value for key, value in os.environ.items()
                                        if key not in ('OPENROUTER_API_KEY', 'OPENROUTER_CREDITS_KEY')},
                                   start_new_session=True)
        try:
            def send(value):
                process.stdin.write(json.dumps(value).encode() + b'\n')
                process.stdin.flush()
            send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {
                'name': 'centaur_cli', 'title': 'Centaur CLI', 'version': __version__}}})
            deadline, pending, initialized = time.monotonic() + timeout, b'', False
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while time.monotonic() < deadline:
                    for key, _ in selector.select(min(.1, max(0, deadline - time.monotonic()))):
                        data = os.read(key.fd, 65536)
                        if not data: raise BalanceUnavailable('Codex App Server encerrou a consulta.')
                        pending += data
                        if len(pending) > 1_000_000: raise BalanceUnavailable('Resposta de uso excedeu o limite.')
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n', 1)
                            try: value = json.loads(line)
                            except ValueError: continue
                            if not isinstance(value, dict): continue
                            if value.get('id') in (1, 2) and 'error' in value:
                                raise BalanceUnavailable('Consulta de uso indisponível nesta versão ou autenticação do Codex.')
                            if value.get('id') == 1 and 'result' in value and not initialized:
                                initialized = True
                                send({'method': 'initialized', 'params': {}})
                                send({'id': 2, 'method': 'account/rateLimits/read'})
                            elif initialized and value.get('id') == 2 and isinstance(value.get('result'), dict):
                                return codex_balance(value['result'])
            raise BalanceUnavailable('Consulta de uso Codex excedeu 10 segundos.', 'error')
        finally:
            if process.poll() is None:
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
            try: process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                process.communicate(timeout=1)
