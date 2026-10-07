"""Identidade visual e desenho da superfície do terminal."""

import curses
import os
import sys
import time
import unicodedata

from .credits import CreditBalance, credit_label
from .native_usage import native_label
from .graphics import WelcomeAnimation, flat_symbol

WORDMARK = 'C E N T A U R'
TAGLINE = 'HUMAN INTENT. AMPLIFIED.'


def cell_width(text):
    return sum(0 if unicodedata.combining(char) else
               2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1 for char in text)


def fit_cells(text, width):
    result, used = [], 0
    for char in text:
        cells = cell_width(char)
        if used + cells > width:
            break
        result.append(char)
        used += cells
    return ''.join(result)


def fit_notice(text, width):
    """Single row inside the composer; preserve an explicit truncation marker."""
    text = ' '.join(str(text).split())
    text = ''.join(c if c.isprintable() else ' ' for c in text)
    if cell_width(text) <= width:
        return text
    return fit_cells(text, max(0, width - 1)) + ('…' if width > 0 else '')


def input_window_details(text, cursor, width):
    start, used = cursor, 0
    while start > 0:
        cells = cell_width(text[start - 1])
        if used + cells >= width:
            break
        start -= 1
        used += cells
    return fit_cells(text[start:], width), used, start


def input_window(text, cursor, width):
    visible, column, _ = input_window_details(text, cursor, width)
    return visible, column


def setup_heading():
    colored = sys.stdout.isatty() and 'NO_COLOR' not in os.environ
    green = '\033[38;5;120m' if colored else ''
    muted = '\033[38;5;109m' if colored else ''
    reset = '\033[0m' if colored else ''
    print(f'\n  {green}{WORDMARK}{reset}\n  {muted}{TAGLINE}{reset}\n  {muted}' + '─' * 42 + reset)


class Palette:
    def __init__(self):
        self.styles = {name: 0 for name in ('text', 'green', 'muted', 'line', 'blue', 'selected', 'warning')}
        for accent in (False, True):
            for shade in range(16):
                self.styles[self.graphic_style(shade, accent)] = (
                    curses.A_DIM if shade < 5 else curses.A_BOLD if shade > 12 else 0)
        self.styles.update(title=curses.A_BOLD, user=curses.A_BOLD,
                           comment=0, action=curses.A_BOLD)

    @staticmethod
    def graphic_style(shade, accent):
        return f'graphic_{"green" if accent else "silver"}_{shade}'

    @staticmethod
    def ansi_color(rgb):
        levels = (0, 95, 135, 175, 215, 255)
        cube = tuple(min(range(6), key=lambda i: abs(levels[i] - channel)) for channel in rgb)
        index = 16 + cube[0] * 36 + cube[1] * 6 + cube[2]
        gray = min(range(24), key=lambda i: sum((8 + i * 10 - channel) ** 2 for channel in rgb))
        if sum((8 + gray * 10 - channel) ** 2 for channel in rgb) < sum(
                (levels[i] - channel) ** 2 for i, channel in zip(cube, rgb)):
            return 232 + gray
        return index

    def initialize(self):
        if 'NO_COLOR' in os.environ or not curses.has_colors():
            self.styles['selected'] = curses.A_REVERSE
            self.styles['green'] = curses.A_BOLD
            self.styles['warning'] = curses.A_BOLD
            return
        curses.start_color()
        extended = curses.COLORS >= 256
        background = 233 if extended else curses.COLOR_BLACK
        colors = [252, 120, 109, 239, 111, 120, 215] if extended else [
            curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_CYAN,
            curses.COLOR_BLUE, curses.COLOR_CYAN, curses.COLOR_GREEN, curses.COLOR_YELLOW]
        for pair, (name, color) in enumerate(zip(self.styles, colors), 1):
            curses.init_pair(pair, background if name == 'selected' else color,
                             color if name == 'selected' else background)
            self.styles[name] = curses.color_pair(pair)
        self.styles['green'] |= curses.A_BOLD
        self.styles['title'] = self.styles['text'] | curses.A_BOLD
        self.styles['comment'] = self.styles['text']
        self.styles['action'] = self.styles['blue'] | curses.A_BOLD
        self.styles['user'] = self.styles['text'] | curses.A_BOLD
        if extended and curses.COLOR_PAIRS > 40:
            curses.init_pair(40, 252, 236)
            self.styles['user'] = curses.color_pair(40) | curses.A_BOLD
        # Existing runtime tokens own the light endpoints: text 252 and green 120.
        for accent, target in ((False, (208, 208, 208)), (True, (135, 255, 135))):
            for shade in range(16):
                name = self.graphic_style(shade, accent)
                pair = 8 + int(accent) * 16 + shade
                if extended and pair < curses.COLOR_PAIRS:
                    rgb = tuple(round(18 + (channel - 18) * shade / 15) for channel in target)
                    curses.init_pair(pair, self.ansi_color(rgb), background)
                    self.styles[name] = curses.color_pair(pair)
                else:
                    base = self.styles['green' if accent else 'text']
                    self.styles[name] |= base


class TerminalView:
    def __init__(self):
        self.palette = Palette()
        self.animation = WelcomeAnimation()
        self.graphic_visible = False

    def put(self, screen, row, column, text, style='text', limit=None):
        height, width = screen.getmaxyx()
        if not (0 <= row < height and 0 <= column < width - 1):
            return
        text = ''.join(character if character.isprintable() else ' ' for character in str(text))
        length = max(0, min(width - column - 1, limit if limit is not None else width))
        try:
            screen.addnstr(row, column, fit_cells(text, length), length, self.palette.styles[style])
        except curses.error:
            pass

    def logo(self, screen, row, column, compact=False, terminal=None):
        self.graphic_visible = False
        columns, rows = (26, 10) if compact else (36, 16)
        if os.environ.get('CENTAUR_GRAPHICS') == '0':
            self.animation.pause()
            self.static_logo(screen, row, column, compact)
            return
        try:
            '\u28ff'.encode(sys.stdout.encoding or 'utf-8')
        except (UnicodeEncodeError, LookupError):
            self.animation.pause()
            self.static_logo(screen, row, column, compact)
            return
        frame = self.animation.frame(columns, rows, time.monotonic(),
                                     reduced=os.environ.get('CENTAUR_REDUCED_MOTION') == '1',
                                     editing=bool(terminal and terminal.draft))
        self.graphic_visible = True
        for y, line in enumerate(frame):
            # Group adjacent cells sharing a shade to bound terminal writes.
            x = 0
            while x < columns:
                cell = line[x]
                if cell.glyph == ' ':
                    x += 1
                    continue
                end = x + 1
                while end < columns and (line[end].shade, line[end].accent) == (cell.shade, cell.accent):
                    end += 1
                self.put(screen, row + y, column + x,
                         ''.join(value.glyph for value in line[x:end]),
                         self.palette.graphic_style(cell.shade, cell.accent))
                x = end
        self.put(screen, row + rows + 1, column + (columns - len(WORDMARK)) // 2, WORDMARK)
        self.put(screen, row + rows + 2, column + (columns - len(TAGLINE)) // 2, TAGLINE, 'muted')

    def static_logo(self, screen, row, column, compact=False):
        columns, rows = (26, 10) if compact else (36, 16)
        try:
            '█▀▄'.encode(sys.stdout.encoding or 'utf-8')
            ascii_only = False
        except (UnicodeEncodeError, LookupError):
            ascii_only = True
        symbol = flat_symbol(columns, rows, ascii_only)
        for index, line in enumerate(symbol):
            self.put(screen, row + index, column, line, 'green' if index >= rows // 2 else 'text')
        symbol_width = max(map(len, symbol))
        self.put(screen, row + len(symbol) + 1, column + max(0, (symbol_width - len(WORDMARK)) // 2), WORDMARK)
        self.put(screen, row + len(symbol) + 2, column + max(0, (symbol_width - len(TAGLINE)) // 2), TAGLINE, 'muted')

    def welcome(self, screen, top, available, width, terminal):
        if available < 6:
            self.animation.pause()
            self.put(screen, top, 3, 'Digite sua intenção. $ skills · Shift+← chats.', 'muted')
            return
        text_column = 3
        if width >= 76 and available >= 13:
            compact = width < 96 or available < 19
            self.logo(screen, top, 5, compact, terminal)
            text_column = 36 if compact else 44
        elif width < 76 and available >= 29:
            self.logo(screen, top, 3, True, terminal)
            top += 14
            available -= 14
        else:
            self.animation.pause()
        commands = [('$spec', 'Planejar entrega'), ('$run master/0001', 'Executar spec'),
                    ('$check', 'Consultar projeto'), ('$skill', 'Instalar skill')]
        self.put(screen, top, text_column, 'Centaur CLI', 'green')
        self.put(screen, top + 1, text_column, 'Sua intenção. Mais alcance.', 'muted')
        self.put(screen, top + 2, text_column, 'Intenção → contrato → entrega verificada', 'muted')
        for index, (command, description) in enumerate(commands[:max(0, available - 5)], top + 4):
            self.put(screen, index, text_column, command, 'green')
            self.put(screen, index, text_column + 19, description)
        if available >= 11:
            self.put(screen, top + 9, text_column, '$status  Árvore das specs', 'blue')
            self.put(screen, top + 10, text_column, '$config  Modelo e effort', 'blue')
        if available >= 13 or available < 11:
            self.put(screen, top + min(12, available - 1), text_column,
                     '$ skills · @ adicionais · Shift+← chats', 'muted')
        if (width >= 76 and available >= 15 and self.graphic_visible
                and os.environ.get('CENTAUR_REDUCED_MOTION') != '1'):
            self.put(screen, top + 14, text_column, 'F5 · Repetir animação', 'muted')

    def settings(self, screen, terminal, top, available, width):
        from .permissions import MODE_HELP
        picker = terminal.settings
        startup = getattr(picker, 'startup', False)
        heading = {'backend': '1/5 · Escolha sua conexão', 'model': '2/5 · Modelo padrão',
                   'custom': '2/5 · Modelo personalizado', 'effort': '3/5 · Effort',
                   'permissions': '4/5 · Permissões', 'speed': '5/5 · Velocidade',
                   'fields': 'Tudo pronto para começar'}
        self.put(screen, top, 3, heading[picker.page] if startup else 'PREFERÊNCIAS DA IA', 'green')
        self.put(screen, top + 1, 3, 'Revise sua escolha antes de iniciar o chat.' if startup
                 else 'Escolha como a IA trabalha nesta pasta.', 'muted')
        if picker.page == 'fields':
            visible = max(1, available - 3)
            start = max(0, picker.row - visible + 1)
            for index, (label, value) in enumerate(list(zip(picker.fields, picker.values))[start:start + visible], start):
                row = top + 3 + index - start
                style = 'selected' if index == picker.row else 'text'
                self.put(screen, row, 2, ' ' * (width - 5), style)
                self.put(screen, row, 3, f'{">" if index == picker.row else " "} {label}', style,
                         width - 6 if index == len(picker.fields) - 1 else max(12, width // 2 - 5))
                if index != len(picker.fields) - 1:
                    self.put(screen, row, width // 2, value, style)
            if available > len(picker.fields) + 4:
                self.put(screen, top + 3 + len(picker.fields), 3, 'Effort: raciocínio · Fast: pode custar mais.', 'muted')
                self.put(screen, top + 4 + len(picker.fields), 3, 'Enter em Iniciar conversa confirma sua escolha.' if startup
                         else 'Modelo, effort e velocidade mantêm este chat.', 'muted')
        elif picker.page == 'custom':
            self.put(screen, top + 3, 3, 'ID ou alias do modelo', 'blue')
            visible, _ = input_window(picker.query, len(picker.query), max(1, width - 8))
            self.put(screen, top + 5, 3, '> ' + visible)
        else:
            title = {'backend': 'Backend', 'model': 'Modelo · digite para filtrar',
                     'effort': 'Effort · níveis dependem do modelo',
                     'speed': 'Velocidade · suporte depende do modelo/conta',
                     'permissions': 'Permissões das ferramentas'}[picker.page]
            self.put(screen, top + 3, 3, title, 'blue')
            if picker.page == 'model':
                self.put(screen, top + 4, 3, 'Filtro: ' + (picker.query or 'todos') + ' · Ctrl+U limpar', 'muted')
            choices = picker.options()
            offset = 5 if picker.page == 'model' else 4
            visible = max(1, available - offset)
            start = max(0, picker.selected - visible + 1)
            for index, (_, label) in enumerate(choices[start:start + visible]):
                selected = start + index == picker.selected
                style = 'selected' if selected else 'text'
                self.put(screen, top + offset + index, 2, ' ' * (width - 5), style)
                self.put(screen, top + offset + index, 3, f'{">" if selected else " "} {label}', style)
            if picker.page == 'speed':
                room = available - offset - len(choices[start:start + visible])
                from .terminal import display_lines
                explanation = ('Fast solicita maior velocidade, com maior consumo/custo; effort e modelo são preservados.'
                               if len(choices) > 1 else 'Fast não anunciado. Consulte o catálogo ou escolha um modelo compatível.')
                for row_offset, line in enumerate(display_lines(explanation, width - 6)[:max(0, room)]):
                    self.put(screen, top + offset + len(choices[start:start + visible]) + row_offset, 3, line, 'muted')
            if picker.page == 'permissions':
                from .terminal import display_lines
                mode = choices[picker.selected][0]
                shown = len(choices[start:start + visible])
                room = max(0, available - offset - shown)
                help_text = ('Sem confirmar; acesso do usuário.' if mode == 'never' and room == 1 else MODE_HELP[mode])
                for line_offset, line in enumerate(display_lines(help_text, width - 6)[:room]):
                    self.put(screen, top + offset + shown + line_offset, 3, line,
                             'warning' if mode == 'never' else 'muted')
        if picker.pending:
            self.put(screen, top + 1, 3, self.activity(terminal, 'Validando configuração'), 'blue')

    def activity(self, terminal, label):
        reduced = os.environ.get('CENTAUR_REDUCED_MOTION') == '1'
        frames = ('◐', '◓', '◑', '◒')
        marker = '•' if reduced else frames[int(time.monotonic() * 8) % len(frames)]
        elapsed = int(time.monotonic() - (terminal.busy_started or terminal.started_at))
        return f'{marker} {label} · {elapsed}s'

    def question(self, screen, terminal, top, available, width):
        from .terminal import display_lines
        picker = terminal.question
        lines = [('PERGUNTA DA IA', 'green')]
        lines += [(line, 'text') for line in display_lines(picker.question, width - 6)]
        lines.append(('', 'text'))
        selected_start = 0
        for index, option in enumerate([*picker.options, 'Escrever outra resposta…']):
            selected = index == picker.selected
            if selected:
                selected_start = len(lines)
            label = ('> ' if selected else '  ') + option
            lines += [(line, 'selected' if selected else 'text') for line in display_lines(label, width - 6)]
        start = min(max(0, selected_start - available + 1) if picker.scroll is None else picker.scroll, max(0, len(lines) - available))
        picker.view_start = start
        for row, (line, style) in enumerate(lines[start:start + available], top):
            self.put(screen, row, 2, ' ' * (width - 5), style)
            self.put(screen, row, 3, line, style)

    def browser(self, screen, terminal, top, available, width):
        from .sessions import LABELS
        if terminal.agent_preview:
            agent = terminal.agent_preview
            self.put(screen, top, 3, 'SUBAGENTE · ' + agent['title'], 'green')
            self.put(screen, top + 1, 3, LABELS[terminal.session_state(agent)] + ' · ' + agent['model'], 'blue')
            lines = terminal.lines(width - 6)
            room = max(1, available - 3)
            start = terminal.transcript_start(len(lines), room, width - 6)
            for row, line in enumerate(lines[start:start + room], top + 3):
                self.put(screen, row, 3, line, getattr(line, 'style', 'text'), width - 6)
            return
        states = [terminal.session_state(chat) for chat in terminal.chats]
        self.put(screen, top, 2, 'AGENTES DESTA PASTA' if terminal.browser_mode == 'agents' else 'CHATS DESTA PASTA', 'green')
        self.put(screen, top + 1, 2, f'{len(states)} sessões · {states.count("running")} trabalhando · {states.count("waiting_input")} input · {states.count("stopped")} paradas', 'muted')
        self.put(screen, top + 2, 2, 'N + Novo chat · sessões anteriores continuam', 'blue')
        visible = max(1, available - 3)
        start = max(0, terminal.selected - visible + 1)
        for row, chat in enumerate(terminal.chats[start:start + visible], top + 3):
            selected = start + row - top - 3 == terminal.selected
            state = terminal.session_state(chat)
            title = f' {">" if selected else " "} {LABELS[state]} · [{chat.get("backend", "openrouter")}] {chat["title"]}'
            style = 'selected' if selected else 'warning' if state == 'waiting_input' else 'green' if state == 'running' else 'muted'
            self.put(screen, row, 2, ' ' * (width - 5), style)
            self.put(screen, row, 2, title, style, width - 25 if width >= 78 else width - 5)
            if width >= 78:
                self.put(screen, row, width - 21, chat['updated'][:16],
                         'selected' if selected else 'muted')
        if not terminal.chats:
            self.put(screen, top + 4, 3, 'Nenhum subagente registrado. Tab mostra chats.' if terminal.browser_mode == 'agents' else 'Nenhum chat salvo. Esc volta para começar.', 'muted')

    def agent_panels(self, screen, terminal, left, top, width, bottom):
        """Live cards close when their runtime stops; overflow remains scrollable."""
        from datetime import datetime, timezone
        from .sessions import LABELS
        agents = terminal.active_agents
        if not agents or bottom - top < 8:
            return
        self.put(screen, top, left, f'SUBAGENTES · {len(agents)} ativos', 'blue', width)
        room = bottom - top - 2
        capacity = max(1, room // 8)
        terminal.agent_panel_scroll = min(max(0, terminal.agent_panel_scroll), max(0, len(agents) - capacity))
        start = terminal.agent_panel_scroll
        visible = agents[start:start + capacity]
        card_height = min(12, room // len(visible))
        terminal.agent_panel_area = (left, top, width, bottom - top)
        for index, agent in enumerate(visible):
            row = top + 1 + index * card_height
            state = terminal.session_state(agent)
            style = 'warning' if state == 'waiting_input' else 'blue'
            self.put(screen, row, left, '┌' + '─' * (width - 2) + '┐', style, width)
            for y in range(row + 1, row + card_height - 1):
                self.put(screen, y, left, '│', style, 1)
                self.put(screen, y, left + width - 1, '│', style, 1)
            self.put(screen, row + card_height - 1, left, '└' + '─' * (width - 2) + '┘', style, width)
            inner = width - 4
            self.put(screen, row + 1, left + 2, fit_notice(agent['title'], inner), 'title', inner)
            model = (agent.get('models_used') or [agent['model']])[-1] or 'padrão'
            self.put(screen, row + 2, left + 2, fit_notice(model, inner), 'muted', inner)
            try:
                created = datetime.fromisoformat(agent['created'].replace('Z', '+00:00'))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                elapsed = max(0, int((datetime.now(timezone.utc) - created).total_seconds()))
                duration = f'{elapsed // 60}m {elapsed % 60:02}s'
            except (KeyError, TypeError, ValueError):
                duration = ''
            self.put(screen, row + 3, left + 2, fit_notice(LABELS[state] + ' · ' + duration, inner), style, inner)
            lines = terminal.lines(inner, chat=agent) if any(m.get('role') == 'assistant' for m in agent['messages']) else ['Aguardando resposta do modelo…']
            lines = [line for line in lines if str(line).strip()]
            count = max(1, card_height - 6)
            for offset, line in enumerate(lines[-count:]):
                self.put(screen, row + 4 + offset, left + 2, line, getattr(line, 'style', 'muted'), inner)
            terminal.agent_panel_hits.append((left, row, width, card_height, agent))
        self.put(screen, bottom - 1, left, fit_notice(f'{start + 1}–{start + len(visible)}/{len(agents)} · roda: rolar · clique: abrir', width), 'muted', width)

    def draw(self, screen, terminal):
        # Only the welcome surface owns animation time; hidden editors never advance it.
        if (terminal.settings or terminal.rename_target or terminal.browser
                or terminal.chat['messages'] or terminal.approval or terminal.question):
            self.animation.pause()
        self.animation.active = False
        self.graphic_visible = False
        screen.bkgd(' ', self.palette.styles['text'])
        screen.erase()
        height, width = screen.getmaxyx()
        terminal.input_hitbox = None
        terminal.agent_panel_hits = []
        terminal.agent_panel_area = None
        credits, credit_style = (native_label(terminal.credits, terminal.credits_status, max(16, (width - 5) // 2), terminal.backend)
                                 if terminal.backend != 'openrouter' else credit_label(terminal.credits, terminal.credits_status, width))
        if height < 12 or width < 40:
            self.animation.pause()
            self.put(screen, 0, 0, WORDMARK, 'green')
            self.put(screen, 2, 0, 'Amplie o terminal para 40 × 12.', 'muted')
            if height >= 5:
                self.put(screen, height - 2, 0, credits, credit_style)
            self.put(screen, height - 1, 0, '> ' + terminal.draft, 'green')
            screen.refresh()
            return
        self.put(screen, 1, 2, WORDMARK, 'muted')
        if width >= 66:
            self.put(screen, 1, width - len(TAGLINE) - 3, TAGLINE, 'muted')
        transcript_width = width - 6 if terminal.wide_chat else min(100, width - 6)
        transcript_left = max(3, (width - transcript_width) // 2)
        sidebar = None
        if terminal.active_agents and width >= 112 and height >= 18 and not (terminal.settings or terminal.rename_target or terminal.browser):
            right_space = width - transcript_left - transcript_width - 6
            panel_width = min(44, right_space)
            if panel_width < 32:
                panel_width = min(44, max(32, width // 4))
                transcript_width = min(transcript_width, width - panel_width - 9)
                transcript_left = 3
            sidebar = (transcript_left + transcript_width + 3, panel_width)
        from .permissions import MODE_LABELS
        speed_label = ''
        if terminal.chat.get('speed') == 'fast':
            served = terminal.chat.get('speed_served')
            speed_label = ('Fast' if served in ('fast', 'priority') else 'Padrão (fallback)' if served in ('standard', 'default')
                           else 'Fast solicitado' if width >= 80 else 'Fast?') + ' · '
        model = MODE_LABELS[terminal.approval_mode] + ' · ' + speed_label + terminal.backend + ' · ' + (terminal.chat['model'] or 'padrão')
        if terminal.computer and terminal.computer.active:
            model = 'TELA ATIVA · ' + model
        if terminal.chat.get('effort', 'default') != 'default':
            model += ' · ' + terminal.chat['effort']
        model_style = 'warning' if terminal.approval_mode == 'never' else 'blue'
        self.put(screen, 2, transcript_left, '◆ ' + terminal.chat['title'], 'title', transcript_width)
        if width >= 100:
            self.put(screen, 3, transcript_left, str(terminal.root), 'muted', transcript_width // 2 - 2)
            self.put(screen, 3, transcript_left + transcript_width // 2, model, model_style, transcript_width // 2)
        else:
            self.put(screen, 3, transcript_left, model, model_style, transcript_width)
        self.put(screen, 4, transcript_left, '─' * transcript_width, 'line')
        top, available = 5, height - 11
        modal = bool(terminal.settings or terminal.rename_target or terminal.browser or terminal.approval or terminal.question)
        draft = terminal.rename_text if terminal.rename_target else '' if terminal.browser else terminal.question.text if terminal.question and terminal.question.custom else '' if terminal.question else terminal.draft
        cursor = terminal.rename_cursor if terminal.rename_target else 0 if terminal.browser else terminal.question.cursor if terminal.question and terminal.question.custom else 0 if terminal.question else terminal.cursor
        composer_left = 2 if modal else transcript_left - 1
        if modal:
            composer_width = transcript_left + transcript_width - composer_left + 1 if sidebar else width - 5
        else:
            composer_width = transcript_width + 2 if sidebar or composer_left != 2 else width - 5
        input_width = max(1, composer_width - 2)
        terminal.input_width = input_width
        from .composer import layout_input
        layout = layout_input(draft, input_width)
        cursor_row, cursor_column = layout.positions[min(len(draft), max(0, cursor))]
        if height < 20 and (terminal.settings or terminal.rename_target or terminal.question
                            or terminal.browser or terminal.approval):
            # A compact editor owns the content region so every field remains reachable.
            top, available = 0, height - 6
            for row in range(height - 5):
                self.put(screen, row, 0, ' ' * (width - 1))
        elif height < 20 and (terminal.chat['messages'] or terminal.draft or terminal.pending_attachments):
            # Preserve a useful conversation viewport even at the minimum 40 × 12.
            top, available = 3, height - 9
            for row in range(height - 5):
                self.put(screen, row, 0, ' ' * (width - 1))
            self.put(screen, 0, transcript_left, '◆ ' + terminal.chat['title'], 'title', transcript_width)
            self.put(screen, 1, transcript_left, model, model_style, transcript_width)
            self.put(screen, 2, transcript_left, '─' * transcript_width, 'line')
        # Keep at least two conversation rows when space allows. The chat input
        # grows to eight rows; modal editors retain their single-line geometry.
        capacity = min(8, max(1, available - 1))
        composer_rows = 1 if modal else min(capacity, max(3, len(layout.lines)))
        attachment_rows = int(bool(terminal.pending_attachments) and not modal and height >= 16)
        extra_rows = composer_rows - 1 + attachment_rows
        available = max(1, available - extra_rows)
        composer_separator = height - 5 - extra_rows
        input_top = height - 3 - extra_rows + attachment_rows
        input_start = max(0, min(cursor_row - composer_rows + 1, len(layout.lines) - composer_rows))
        if terminal.settings:
            self.settings(screen, terminal, top, available, width)
        elif terminal.rename_target:
            self.put(screen, top, 3, 'RENOMEAR CHAT', 'green')
            self.put(screen, top + 2, 3, terminal.rename_target['title'], 'muted')
            self.put(screen, top + 4, 3, 'Título · 1 a 80 caracteres', 'blue')
        elif terminal.browser:
            self.browser(screen, terminal, top, available, width)
        elif terminal.question:
            self.question(screen, terminal, top, available, transcript_left + transcript_width + 2 if sidebar else width)
        elif not terminal.chat['messages'] and not terminal.approval and not terminal.pending_attachments:
            if sidebar:
                self.put(screen, top, transcript_left, 'Digite sua intenção. $ skills · Shift+← chats.', 'muted', transcript_width)
            else:
                self.welcome(screen, top, available, width, terminal)
        else:
            lines = terminal.lines(transcript_width)
            if terminal.approval:
                start = min(terminal.scroll, max(0, len(lines) - available))
            else:
                start = terminal.transcript_start(len(lines), available, transcript_width)
                if terminal.scroll:
                    self.put(screen, composer_separator - 1, transcript_left,
                             f'Histórico · linhas {start + 1}–{min(len(lines), start + available)} de {len(lines)} · Ctrl+E fim', 'blue')
            for row, line in enumerate(lines[start:start + available], top):
                style = getattr(line, 'style', None)
                if style is None:
                    style = 'text'
                    if line.startswith('› '): style = 'user'
                    elif line.startswith('◆ Centaur'): style = 'green'
                    elif line.startswith('◦ ') or line.startswith('  '): style = 'muted'
                    elif line.startswith('↳ Ferramenta'): style = 'blue'
                    elif line.startswith(('CONFIRMAÇÃO', '! Erro')): style = 'warning'
                if style == 'user':
                    self.put(screen, row, transcript_left - 1, ' ' * (transcript_width + 2), style)
                self.put(screen, row, transcript_left, line, style, transcript_width)
        terminal.completion.update(terminal.draft if terminal.cursor == len(terminal.draft) else '')
        completing = (terminal.completion.visible and not terminal.browser and not terminal.approval
                      and not terminal.settings and not terminal.rename_target and not terminal.question)
        if completing:
            visible = min(6, max(1, available - 1))
            start = max(0, terminal.completion.selected - visible + 1)
            choices = terminal.completion.options[start:start + visible]
            popup_top = composer_separator - len(choices) - 1
            prefix = terminal.completion.context[1]
            heading = 'Skills Centaur ($)' if prefix == '$' else 'Skills do projeto (@) · .centaur/skills'
            popup_width = transcript_left + transcript_width - 1 if sidebar else width - 5
            self.put(screen, popup_top, 2, ' ' * popup_width)
            self.put(screen, popup_top, 3, f'{heading} · {len(terminal.completion.options)}', 'green', popup_width - 1)
            for index, name in enumerate(choices):
                selected = start + index == terminal.completion.selected
                style = 'selected' if selected else 'text'
                row = popup_top + index + 1
                self.put(screen, row, 2, ' ' * popup_width, style)
                self.put(screen, row, 3, f'{">" if selected else " "} {prefix}{name}', style, popup_width - 1)
        # The composer follows the same reading column as the conversation.
        self.put(screen, composer_separator, composer_left, '─' * composer_width, 'line')
        notice = terminal.notice
        if terminal.browser and not terminal.rename_target and not notice.startswith(('Aguarde', 'Não', 'Este', 'Esta', 'Abra', 'Erro', 'Chat', 'Chave')):
            notice = ('Enter abre coordenador/input · Esc lista · PgUp/PgDn lê.' if terminal.agent_preview else 'N cria chat · Tab alterna chats/agentes · Esc volta ao chat/input · limpeza após 64h.')
        elif terminal.question:
            notice = terminal.question.error or ('Digite abaixo e pressione Enter.' if terminal.question.custom else 'Escolha uma resposta; Esc pula a pergunta.')
        elif terminal.busy and not terminal.approval:
            notice = self.activity(terminal, notice)
        elif terminal.settings:
            notice = terminal.settings.error or terminal.settings.catalog_status or notice
        if (not terminal.browser and not terminal.approval and not terminal.settings
                and not terminal.rename_target and not terminal.question and terminal.completion.context
                and not terminal.completion.options and terminal.completion.dismissed != terminal.draft):
            prefix = terminal.completion.context[1]
            notice = ('Nenhuma skill adicional encontrada em .centaur/skills/.' if prefix == '@'
                      else 'Nenhuma skill Centaur corresponde ao nome digitado.')
        if terminal.chat.get('last_error') and notice.startswith('Erro: ' + terminal.chat['last_error']):
            notice = 'Erro no turno · detalhes na conversa · /retry retoma.'
        self.put(screen, composer_separator + 1, composer_left, fit_notice(notice, composer_width),
                 'warning' if notice.startswith(('Erro', 'Não foi', 'Chave detectada')) else 'muted', composer_width)
        if attachment_rows:
            names = ', '.join(item['name'] for item in terminal.pending_attachments)
            self.put(screen, composer_separator + 2, composer_left,
                     f'▧ {len(terminal.pending_attachments)} anexo(s): {names} · $detach remove', 'blue', composer_width)
        if sidebar:
            self.agent_panels(screen, terminal, sidebar[0], top, sidebar[1], composer_separator)
        horizontal_start = 0
        if modal:
            visible_draft, cursor_column, horizontal_start = input_window_details(draft, cursor, input_width)
            visible_lines, cursor_row, input_start = [visible_draft], 0, 0
        else:
            visible_lines = layout.lines[input_start:input_start + composer_rows]
        for offset in range(composer_rows):
            self.put(screen, input_top + offset, composer_left, ' ' * composer_width, 'user')
            if offset < len(visible_lines):
                self.put(screen, input_top + offset, composer_left + 2, visible_lines[offset], 'user', input_width)
        if not modal:
            from .composer import attachment_span
            for item in terminal.pending_attachments:
                span = attachment_span(item, draft)
                if not span:
                    continue
                for index in range(*span):
                    row, column = layout.positions[index]
                    if input_start <= row < input_start + composer_rows:
                        self.put(screen, input_top + row - input_start, composer_left + 2 + column,
                                 draft[index], 'blue', 1)
        target = ('rename' if terminal.rename_target else 'question' if terminal.question and terminal.question.custom
                  else 'draft' if not modal else None)
        if target:
            hit_layout = layout_input(visible_lines[0], input_width) if modal else layout
            terminal.input_hitbox = {'chat_id': terminal.chat['id'], 'size': (height, width),
                'text': draft, 'target': target, 'top': input_top, 'left': composer_left,
                'text_left': composer_left + 2, 'width': composer_width, 'rows': composer_rows, 'start_row': 0 if modal else input_start,
                'start_index': horizontal_start, 'layout': hit_layout}
        self.put(screen, input_top, composer_left, '↑' if input_start else '›', 'green')
        if input_start + composer_rows < len(layout.lines) and not modal:
            self.put(screen, input_top + composer_rows - 1, composer_left, '↓', 'muted')
        footer_width = width - 5
        if terminal.credits_status == 'unsupported' and terminal.backend == 'openrouter':
            credits = 'Créditos: CLI'
        credit_width = min(len(credits), max(12, footer_width - 17))
        if len(credits) > credit_width and isinstance(terminal.credits, CreditBalance) and terminal.credits.remaining is not None:
            scope = 'Conta' if terminal.credits.scope == 'account' else 'Chave'
            credits = f'{scope}: US$ {terminal.credits.remaining:.2f}'
        credits = fit_cells(credits, credit_width)
        context_width = footer_width - cell_width(credits) - 2
        context, context_style = terminal.context_label(context_width)
        self.put(screen, height - 2, 2, context, context_style, context_width)
        self.put(screen, height - 2, width - cell_width(credits) - 3, credits, credit_style)
        hints = ('Enter salvar · Esc cancelar · Ctrl+U limpar' if terminal.rename_target else
                 'Enter coordenador · Esc lista · PgUp/PgDn ler subagente' if terminal.agent_preview and terminal.browser else
                 '↑↓ escolher · Enter abrir · N novo chat · Tab chats/agentes · Esc voltar' if terminal.browser else
                 'Aguarde a validação…' if terminal.settings and terminal.settings.pending else
                 '↑↓/Tab escolher · Enter responder · Esc pular · PgUp/PgDn ler' if terminal.question else
                 '↑↓ escolher · Enter abrir/salvar · Esc voltar/cancelar' if terminal.settings else
                 'Enter salvar · Esc cancelar · Ctrl+U limpar' if terminal.rename_target else
                 ('↑↓ escolher · Tab completar · Enter executar · Esc fechar'
                  if terminal.completion.local_command(terminal.draft) else
                  '↑↓ escolher · Tab/Enter inserir · Esc fechar') if completing else
                 'y permitir · n recusar · PgUp/PgDn revisar' if terminal.approval else
                 '↑↓ selecionar · Enter retomar · R renomear · Del excluir · Esc voltar' if terminal.browser else
                 '↑↓ prompts · PgUp/PgDn rolar · Ctrl+C parar' if terminal.busy else
                 'Ctrl+V imagem · ↑↓ prompts · Enter enviar · Shift+Enter linha · Shift+← chats')
        if terminal.active_agents and not terminal.agent_panel_area and not modal:
            hints = f'{len(terminal.active_agents)} subagentes · Shift+←/Tab · ' + hints
        self.put(screen, height - 1, 2, hints, 'blue')
        if terminal.rename_target or (not terminal.approval and not terminal.browser):
            if terminal.settings and terminal.settings.page == 'custom':
                _, custom_cursor = input_window(terminal.settings.query, len(terminal.settings.query),
                                                max(1, width - 8))
                screen.move(top + 5, min(width - 2, 5 + custom_cursor))
            elif not terminal.settings:
                screen.move(input_top + cursor_row - input_start, min(width - 2, composer_left + 2 + cursor_column))
        screen.refresh()
