#!/usr/bin/env python3
"""Run Graphify on demand with all output rooted in .centaur/graphify."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

READ_COMMANDS = {'query', 'path', 'explain', 'affected', 'god-nodes', 'diagnose', 'benchmark'}
WRITE_COMMANDS = {'extract', 'update', 'cluster-only', 'label', 'export', 'reflect', 'save-result'}


def command_for(root, args):
    if not args or args[0] not in READ_COMMANDS | WRITE_COMMANDS:
        raise ValueError('Informe um comando local: query, path, explain, extract, update, export…')
    # Paths must be controlled here, not overridden by caller flags or global commands.
    forbidden = {'--out', '--output', '--graph', '--memory-dir', '--dir', '--global', '--postgres', '--push'}
    if any(arg.split('=', 1)[0] in forbidden for arg in args):
        raise ValueError('Destinos externos e operações remotas não são permitidos pelo adaptador local.')
    command = ['graphify', *args]
    if args[0] in {'extract', 'update', 'cluster-only', 'label'}:
        if len(args) > 1 and not args[1].startswith('-'):
            raise ValueError('A raiz já foi informada; não passe outro corpus.')
        command.insert(2, str(root))
    return command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = args.project.resolve(strict=True)
    output = root / '.centaur/graphify'
    if not root.is_dir() or not output.resolve().is_relative_to(root):
        parser.error('Raiz ou destino inválido.')
    try:
        command = command_for(root, args.args)
        if args.args[0] in READ_COMMANDS and not (output / 'graph.json').is_file():
            raise ValueError('Índice ausente. Use busca direta ou solicite extração explicitamente.')
        marker = output / 'migration.json'
        if args.args[0] in READ_COMMANDS and marker.is_file():
            status = json.loads(marker.read_text(encoding='utf-8'))
            if status.get('needs_sync'):
                print('Aviso: documentos migrados; confira caminhos nas fontes atuais. Índice preservado, sincronização sob demanda.', file=sys.stderr)
        env = {**os.environ, 'GRAPHIFY_OUT': str(output)}
        return subprocess.run(command, cwd=root, env=env, check=False).returncode
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
