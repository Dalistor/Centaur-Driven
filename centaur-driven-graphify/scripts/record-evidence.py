#!/usr/bin/env python3
"""Run an explicitly supplied check and capture an immutable, file-bound evidence record."""
import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from lifecycle import load_project, digest, readable_path, project_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('rule', help='contract/R1')
    parser.add_argument('--summary', required=True, help='Observable behavior this check verifies')
    parser.add_argument('--file', action='append', default=[], help='Additional affected sources/tests/configs to fingerprint')
    parser.add_argument('--timeout', type=int, default=300)
    argv = sys.argv[1:]
    if '--' not in argv:
        parser.error('Informe o comando depois de --')
    boundary = argv.index('--')
    args = parser.parse_args(argv[:boundary])
    command = argv[boundary + 1:]
    root = args.project.resolve()
    data = load_project(root)
    contract, rule = next(((c, r) for c in data['contracts'] for r in c['rules'] if r['key'] == args.rule), (None, None))
    if not rule:
        parser.error('Regra não encontrada no contrato vigente')
    if not rule['sources'] and not args.file:
        parser.error('Informe --file para as fontes de uma regra ainda sem estado')
    if args.timeout <= 0:
        parser.error('timeout deve ser positivo')
    if not command:
        parser.error('Informe o comando depois de --')
    paths = sorted({s['path'] for s in rule['sources']} | set(args.file))
    before = {p: digest(readable_path(root, p)) for p in paths}
    eid = 'ev-' + uuid.uuid4().hex
    try:
        result = subprocess.run(command, cwd=root, timeout=args.timeout)
        exit_code = result.returncode
    except (OSError, subprocess.TimeoutExpired):
        exit_code = -1
    after = {p: digest(readable_path(root, p)) if readable_path(root, p).is_file() else None for p in paths}
    stable = before == after
    evidence = {'schema': 1, 'id': eid, 'contract': f'{contract["id"]}@{contract["version"]}', 'rule': rule['id'], 'contract_hash': contract['hash'], 'method': 'test', 'command': command, 'result': 'passed' if exit_code == 0 and stable else 'failed', 'exit_code': exit_code, 'at': datetime.now(timezone.utc).isoformat(), 'revision': data['revision'], 'summary': args.summary, 'reference': 'Comando executado no checkout; saída exibida no terminal', 'files': before, 'sources_stable': stable}
    output = project_path(root, f'.centaur/evidence/{eid}.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(f'\nEvidência: {output}\nVincule {eid} à regra após conferir a cobertura do comportamento.')
    return 0 if evidence['result'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
