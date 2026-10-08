"""Render actual TerminalView cells to SVG using deterministic demonstration data.

Usage: python -m scripts.render_cli_preview docs/images/cli-0.9.3.svg
No terminal, model, desktop or third-party rendering dependency is required.
"""
import argparse
import curses
from html import escape
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from centaur_cli.appearance import cell_width
from centaur_cli import __version__
from centaur_cli.history import ChatStore
from centaur_cli.terminal import Terminal


# Emulator examples only: the application inherits these settings, never writes them.
THEMES = {
    'dark': ('#1e1e1e', '#d0d0d0', ('#1e1e1e', '#e06c75', '#98c379', '#e5c07b',
                                 '#61afef', '#c678dd', '#56b6c2', '#d0d0d0')),
    'light': ('#fafafa', '#303030', ('#303030', '#b42318', '#2e6f40', '#a66b00',
                                  '#245ea8', '#7d42a6', '#007e8a', '#fafafa')),
}


class Screen:
    def __init__(self, rows, columns, pairs, theme='dark'):
        self.rows, self.columns, self.pairs = rows, columns, pairs
        self.theme = THEMES[theme]
        self.cells = {}
        self.background = 0

    def getmaxyx(self): return self.rows, self.columns
    def bkgd(self, char, style): self.background = style
    def erase(self): self.cells.clear()
    def refresh(self): pass
    def move(self, row, column): pass

    def addnstr(self, row, column, text, length, style):
        if text.startswith(getattr(self, 'project_path', '\0')):
            text = '/projetos/centaur' + text[len(self.project_path):]
        for char in text:
            self.cells[row, column] = (char, style)
            column += cell_width(char)

    def svg(self):
        cw, ch = 10, 21
        def color(index, *, background=False, dim=False):
            bg, fg, ansi = self.theme
            value = (bg if background else fg) if index == -1 else ansi[index]
            if dim and not background:
                channels = [round(int(value[i:i+2], 16) * .65 + int(bg[i:i+2], 16) * .35)
                            for i in (1, 3, 5)]
                return '#%02x%02x%02x' % tuple(channels)
            return value
        _, bg = self.pairs[self.background >> 8 & 255]
        result = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.columns*cw}" height="{self.rows*ch}" viewBox="0 0 {self.columns*cw} {self.rows*ch}">',
                  f'<title>Centaur CLI {__version__} — demonstração do renderer real</title>',
                  f'<rect width="100%" height="100%" fill="{color(bg, background=True)}"/>',
                  '<g font-family="DejaVu Sans Mono, DejaVu Sans, monospace" font-size="15">']
        runs = []
        for (row, column), (char, style) in sorted(self.cells.items()):
            if runs and runs[-1][0] == row and runs[-1][1] + cell_width(runs[-1][2]) == column and runs[-1][3] == style:
                runs[-1][2] += char
            else:
                runs.append([row, column, char, style])
        for row, column, text, style in runs:
            fg, surface = self.pairs.get(style >> 8 & 255, self.pairs[self.background >> 8 & 255])
            x, y = column*cw, row*ch
            result.append(f'<rect x="{x}" y="{y}" width="{cw*max(1,cell_width(text))}" height="{ch}" fill="{color(surface, background=True)}"/>')
            if text.strip():
                weight = 'bold' if style & curses.A_BOLD else 'normal'
                glyphs = []
                for char in text:
                    if char.strip(): glyphs.append(f'<tspan x="{x}">{escape(char)}</tspan>')
                    x += cw*cell_width(char)
                result.append(f'<text y="{y+16}" fill="{color(fg, dim=bool(style & curses.A_DIM))}" font-weight="{weight}">{"".join(glyphs)}</text>')
        return '\n'.join([*result, '</g></svg>']) + '\n'


def render(output, *, rows=32, columns=140, welcome=False, tree=False, agents=False, startup=False, theme='dark'):
    pairs = {}
    with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'CENTAUR_REDUCED_MOTION': '1'}):
        root = Path(temporary)
        client = SimpleNamespace(backend='codex', context_windows={'modelo-principal': 200000})
        terminal = Terminal(root, 'modelo-principal', ChatStore(root), client, effort='medium', approval_mode='auto')
        terminal.chat['title'] = 'Nova conversa' if welcome else 'Refinar o fluxo de desenvolvimento'
        terminal.notice = 'Digite sua intenção · $config · Shift+← chats'
        if not (welcome or startup):
            terminal.chat['messages'] = [
                {'role': 'user', 'content': 'Revise os fluxos e melhore a experiência do CLI.'},
                {'role': 'assistant', 'content': 'Vou revisar o ciclo de vida e validar as mudanças no terminal.', 'tool_calls': [
                    {'id': 'read', 'function': {'name': 'read_file', 'arguments': json.dumps({'path': 'centaur_cli/terminal.py'})}}]},
                {'role': 'tool', 'tool_call_id': 'read', 'content': 'Conteúdo consultado.'},
                {'role': 'assistant', 'content': 'O campo preserva o rascunho ao trocar de chat. Agora vou conferir os subagentes.', 'tool_calls': [
                    {'id': 'task', 'function': {'name': 'delegate_task', 'arguments': json.dumps({'title': 'Validar sessões', 'task': 'Revisar ciclo de vida'})}}]}]
            agent = terminal.store.new('modelo-de-revisão', backend='codex')
            agent.update(title='Validar sessões', parent_id=terminal.chat['id'], messages=[
                {'role': 'assistant', 'content': 'Os testes de pausa e retomada passaram. Vou conferir a expiração da sessão.'}])
            terminal.registry.set(agent['id'], 'running')
            terminal.registry.activity(agent['id'], 'model')
            terminal.registry.native_event(agent['id'], {'event': 'turn.started', 'warning': '', 'output_bytes': 40, 'stderr_bytes': 0})
            store = ChatStore(root)
            store.directory = root / '.centaur' / 'agents' / terminal.chat['id']
            store.save(agent)
            terminal.store.save(terminal.chat)
            if tree:
                nested = store.new('modelo-de-verificação', backend='codex')
                nested.update(title='Conferir evidências', parent_id=agent['id'], messages=[
                    {'role': 'assistant', 'content': 'O comando terminou. Aguardando a próxima resposta estruturada.'}])
                store.directory = root / '.centaur' / 'agents' / agent['id']
                store.save(nested)
                terminal.registry.set(nested['id'], 'running')
                terminal.registry.activity(nested['id'], 'model')
                terminal.registry.native_event(nested['id'], {'event': 'turn.started', 'warning': 'rede', 'output_bytes': 40, 'stderr_bytes': 50})
            terminal.refresh_agents()
            terminal.draft = 'Confira também o comportamento ao retomar uma conversa.\nPreserve as verificações já concluídas.'
            terminal.cursor = len(terminal.draft)
            if agents:
                terminal.open_chats('agents')
        with patch.dict(os.environ, {'CENTAUR_REDUCED_MOTION': '1'}, clear=True), \
                patch('centaur_cli.appearance.curses.has_colors', return_value=True), \
                patch('centaur_cli.appearance.curses.start_color'), \
                patch('centaur_cli.appearance.curses.use_default_colors'), \
                patch('centaur_cli.appearance.curses.COLORS', 256, create=True), \
                patch('centaur_cli.appearance.curses.COLOR_PAIRS', 256, create=True), \
                patch('centaur_cli.appearance.curses.init_pair', side_effect=lambda i,f,b: pairs.update({i:(f,b)})), \
                patch('centaur_cli.appearance.curses.color_pair', side_effect=lambda i: i << 8):
            if startup:
                from centaur_cli.startup import StartupWizard
                surface = StartupWizard('codex', 'modelo-principal', 'medium', approval_mode='auto')
            else:
                surface = terminal
            surface.view.palette.initialize()
            surface.view.animation.elapsed = 6
            screen = Screen(rows, columns, pairs, theme)
            screen.project_path = str(root)
            surface.draw(screen)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(screen.svg(), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--rows', type=int, default=32)
    parser.add_argument('--columns', type=int, default=140)
    parser.add_argument('--welcome', action='store_true')
    parser.add_argument('--startup', action='store_true', help='Mostrar a seleção inicial de conexão')
    parser.add_argument('--theme', choices=THEMES, default='dark', help='Tema do emulador usado na demonstração')
    parser.add_argument('--tree', action='store_true', help='Demonstrar árvore recursiva com dados sintéticos')
    parser.add_argument('--agents', action='store_true', help='Mostrar o menu de agentes')
    options = parser.parse_args()
    render(options.output, rows=options.rows, columns=options.columns, welcome=options.welcome, tree=options.tree, agents=options.agents, startup=options.startup, theme=options.theme)
