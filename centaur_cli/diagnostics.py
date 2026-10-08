"""Read-only native inference evidence, without prompts, logs or authentication."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import time

from . import __version__
from .sessions import LABELS, NATIVE_PHASES, NATIVE_STATES, NATIVE_WARNINGS


def number(value, maximum=100_000_000):
    return type(value) in (int, float) and 0 <= value <= maximum and math.isfinite(value)


def collect(root, chat_id=None):
    root = Path(root).resolve()
    directory = root / '.centaur' / 'runtime'
    report = {'centaur_version': __version__, 'sessions': []}
    if directory.is_symlink() or directory.parent.is_symlink():
        return report
    for path in sorted(directory.glob('*.json')):
        if path.is_symlink() or not re.fullmatch(r'[0-9a-f]{32}', path.stem) or chat_id and path.stem != chat_id:
            continue
        try:
            with path.open(encoding='utf-8') as source:
                raw = source.read(4097)
            if len(raw) > 4096:
                continue
            record = json.loads(raw)
            if not isinstance(record, dict) or record.get('id') != path.stem or record.get('state') not in LABELS:
                continue
            entry = {'id': path.stem, 'state': record['state']}
            phase = record.get('phase')
            entry['phase'] = phase if phase in ('model', 'compact') else 'tool' if isinstance(phase, str) and phase.startswith('tool:') else 'unknown'
            heartbeat = record.get('heartbeat')
            age = max(0, time.time() - heartbeat) if number(heartbeat, 10_000_000_000) else None
            entry['heartbeat_age_seconds'] = round(age, 1) if age is not None else None
            native = {}
            for key, choices in (('event', NATIVE_PHASES), ('warning', NATIVE_WARNINGS),
                                 ('status', NATIVE_STATES), ('backend', ('codex', 'claude'))):
                value = record.get('native_' + key)
                if isinstance(value, str) and value in choices:
                    native[key] = value
            for key in ('output_bytes', 'stderr_bytes', 'input_bytes', 'process_pid',
                        'timeout_seconds', 'elapsed_seconds', 'recovery_errors', 'recovery_episode'):
                value = record.get('native_' + key)
                if number(value):
                    native[key] = value
            if type(record.get('native_recovering')) is bool:
                native['recovering'] = record['native_recovering']
            pid = native.get('process_pid')
            if age is not None and age <= 120 and native.get('status') == 'running' and type(pid) is int and pid > 0:
                try:
                    os.kill(pid, 0)
                    native['process_exists'] = True
                except PermissionError:
                    native['process_exists'] = True
                except OSError:
                    native['process_exists'] = False
            entry['native'] = native
            report['sessions'].append(entry)
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return report


def render(report):
    lines = [f'Diagnóstico local · Centaur {report["centaur_version"]}']
    for entry in report['sessions']:
        native = entry['native']
        lines.append(f'Chat {entry["id"][:8]} · {LABELS[entry["state"]]} · fase: {entry["phase"]}')
        lines.append(f'  CLI: {native.get("backend", "não observado")} · evento: {native.get("event", "nenhum")} · estado: {native.get("status", "desconhecido")}')
        if 'elapsed_seconds' in native:
            lines.append(f'  Chamada: {native["elapsed_seconds"]:.1f}s / {native.get("timeout_seconds", 0):g}s · PID: {native.get("process_pid", "?")}')
        lines.append(f'  Bytes: entrada {native.get("input_bytes", "?")} · saída {native.get("output_bytes", "?")} · stderr {native.get("stderr_bytes", "?")}')
        if native.get('warning'):
            lines.append('  Aviso observado: ' + native['warning'])
        if 'process_exists' in native:
            lines.append('  Processo local: ' + ('existe; isso não prova progresso remoto' if native['process_exists'] else 'não encontrado'))
    if not report['sessions']:
        lines.append('Nenhum registro de execução nesta pasta.')
    lines.append('Sem prompts, argumentos, logs brutos ou credenciais. centaur diagnose --json exporta este diagnóstico.')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Diagnóstico local de chamadas; não chama modelos nem abre autenticação.')
    parser.add_argument('path', nargs='?', default='.')
    parser.add_argument('--json', action='store_true', dest='as_json')
    options = parser.parse_args(argv)
    root = Path(options.path).expanduser().resolve()
    if not root.is_dir():
        parser.error('A pasta do projeto não existe.')
    report = collect(root)
    print(json.dumps(report, ensure_ascii=False, indent=2) if options.as_json else render(report))
