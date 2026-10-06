"""Entrada do executável centaur."""

import argparse
import curses
import sys
from pathlib import Path

from . import __version__

from .history import ChatStore
from .credentials import CredentialStore
from .backends import BACKENDS, create_client, resolve_selection, resolve_effort
from .config import EFFORTS
from .setup import configure_key
from .terminal import Terminal
from .subagents import COST_TIERS


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        from .status_command import main as status_main
        return status_main(sys.argv[2:])
    parser = argparse.ArgumentParser(description='Centaur CLI experimental: OpenRouter, Codex e Claude',
                                     epilog='Status sem abrir o chat: centaur status [pasta] [--ai]')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('path', nargs='?', default='.', help='Pasta do projeto (padrão: atual)')
    parser.add_argument('--backend', choices=BACKENDS, default=None,
                        help='Backend conectado: openrouter (padrão), codex ou claude')
    parser.add_argument('--model', default=None,
                        help='Modelo principal; subagentes podem escolher modelos do mesmo backend')
    parser.add_argument('--effort', choices=EFFORTS, default=None,
                        help='Esforço de raciocínio do modelo principal (padrão: do provedor)')
    parser.add_argument('--configure-key', action='store_true',
                        help='Cadastrar ou substituir a chave com entrada oculta, sem abrir um chat')
    parser.add_argument('--configure-credits-key', action='store_true',
                        help='Cadastrar chave de gerenciamento para consultar o saldo da conta')
    parser.add_argument('--max-subagent-tier', choices=COST_TIERS, default='high',
                        help='Somente OpenRouter: maior faixa de subagentes (padrão: high; não é teto monetário)')
    options = parser.parse_args()
    root = Path(options.path).expanduser().resolve()
    if not root.is_dir():
        parser.error('A pasta do projeto não existe.')
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error('O CLI precisa de um terminal interativo.')
    try:
        if options.configure_credits_key:
            configure_key(CredentialStore(), purpose='credits')
            return
        if options.configure_key:
            configure_key(CredentialStore())
            return
        options.backend, model = resolve_selection(root, options.backend, options.model)
        effort = resolve_effort(root, options.backend, options.effort)
        client = create_client(options.backend, model)
        curses.wrapper(Terminal(root, model, ChatStore(root), client,
                                options.max_subagent_tier, effort=effort).run)
    except (RuntimeError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    except (OSError, curses.error) as error:
        parser.exit(1, f'Falha no terminal ou histórico: {error}\n')


if __name__ == '__main__':
    main()
