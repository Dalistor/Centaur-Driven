"""Comando status utilizável fora da interface interativa."""

import argparse
import sys
from pathlib import Path

from .agent import run_turn
from .history import ChatStore
from .backends import BACKENDS, create_client, resolve_selection
from .status import ANALYSIS_INSTRUCTIONS, StatusTools, render_status


def main(arguments=None):
    parser = argparse.ArgumentParser(prog='centaur status', description='Árvore de specs e análise opcional de evidências')
    parser.add_argument('path', nargs='?', default='.', help='Pasta do projeto')
    parser.add_argument('--ai', action='store_true', help='Usar o backend conectado para recomendar conclusão e execução; não altera specs')
    parser.add_argument('--backend', choices=BACKENDS, default=None)
    parser.add_argument('--model', default=None, help='Modelo do backend para a análise')
    options = parser.parse_args(arguments)
    root = Path(options.path).expanduser().resolve()
    if not root.is_dir():
        parser.error('A pasta do projeto não existe.')
    report = render_status(root)
    print(report)
    if not options.ai:
        return
    try:
        options.backend, model = resolve_selection(root, options.backend, options.model)
        client = create_client(options.backend, model,
                               allow_setup=sys.stdin.isatty() and sys.stdout.isatty(), include_credits=False)
        store = ChatStore(root)
        chat = store.new(model, backend=options.backend)
        chat['title'] = 'Análise de status das specs'
        chat['messages'] = [{'role': 'user', 'content': '/status --ai\n\n' + report}]
        tools = StatusTools(root, lambda _: False, protected_keys=client.secrets)
        print(f'\nAnalisando evidências com {options.backend}…', flush=True)
        run_turn(chat, client, tools, store, lambda: None, ANALYSIS_INSTRUCTIONS)
        answers = [message['content'] for message in chat['messages'][1:]
                   if message['role'] == 'assistant' and message.get('content')]
        print('\n'.join(answers) or 'Análise interrompida; consulte o histórico para retomar.')
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f'Análise indisponível: {error}\n')
