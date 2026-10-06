"""Identidade visual e desenho da superfície do terminal."""

import curses
import os
import sys
import time
import unicodedata

from .credits import credit_label
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


def input_window(text, cursor, width):
    start, used = cursor, 0
    while start > 0:
        cells = cell_width(text[start - 1])
        if used + cells >= width:
            break
        start -= 1
        used += cells
    return fit_cells(text[start:], width), used


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
        self.styles.update(title=curses.A_BOLD, user=curses.A_BOLD)

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
            self.put(screen, top + 9, text_column, '/status  Árvore das specs', 'blue')
            self.put(screen, top + 10, text_column, '$config  Modelo e effort', 'blue')
        if available >= 13 or available < 11:
            self.put(screen, top + min(12, available - 1), text_column,
                     '$ skills · @ adicionais · Shift+← chats', 'muted')
        if (width >= 76 and available >= 15 and self.graphic_visible
                and os.environ.get('CENTAUR_REDUCED_MOTION') != '1'):
            self.put(screen, top + 14, text_column, 'F5 · Repetir animação', 'muted')

    def settings(self, screen, terminal, top, available, width):
        picker = terminal.settings
        startup = getattr(picker, 'startup', False)
        heading = {'backend': '1/3 · Escolha sua conexão', 'model': '2/3 · Modelo padrão',
                   'custom': '2/3 · Modelo personalizado', 'effort': '3/3 · Effort',
                   'fields': 'Tudo pronto para começar'}
        self.put(screen, top, 3, heading[picker.page] if startup else 'PREFERÊNCIAS DA IA', 'green')
        self.put(screen, top + 1, 3, 'Revise sua escolha antes de iniciar o chat.' if startup
                 else 'Configure a próxima conversa nesta pasta.', 'muted')
        if picker.page == 'fields':
            for index, (label, value) in enumerate(zip(picker.fields, picker.values)):
                row = top + 3 + index
                style = 'selected' if index == picker.row else 'text'
                self.put(screen, row, 2, ' ' * (width - 5), style)
                self.put(screen, row, 3, f'{">" if index == picker.row else " "} {label}', style,
                         max(12, width // 2 - 5))
                self.put(screen, row, width // 2, value, style)
            if available > 9:
                self.put(screen, top + 8, 3, 'Effort: raciocínio do modelo principal.', 'muted')
                self.put(screen, top + 9, 3, 'Enter em Iniciar conversa confirma sua escolha.' if startup
                         else 'Salvar preserva o histórico e abre um novo chat.', 'muted')
        elif picker.page == 'custom':
            self.put(screen, top + 3, 3, 'ID ou alias do modelo', 'blue')
            visible, _ = input_window(picker.query, len(picker.query), max(1, width - 8))
            self.put(screen, top + 5, 3, '> ' + visible)
        else:
            title = {'backend': 'Backend', 'model': 'Modelo · digite para filtrar',
                     'effort': 'Effort · níveis dependem do modelo'}[picker.page]
            self.put(screen, top + 3, 3, title, 'blue')
            if picker.page == 'model':
                self.put(screen, top + 4, 3, 'Filtro: ' + (picker.query or 'todos') + ' · Ctrl+U limpar', 'muted')
            choices = picker.options()
            visible = max(1, available - 6)
            start = max(0, picker.selected - visible + 1)
            for index, (_, label) in enumerate(choices[start:start + visible]):
                selected = start + index == picker.selected
                style = 'selected' if selected else 'text'
                self.put(screen, top + 5 + index, 2, ' ' * (width - 5), style)
                self.put(screen, top + 5 + index, 3, f'{">" if selected else " "} {label}', style)
        if picker.pending:
            self.put(screen, top + 1, 3, self.activity(terminal, 'Validando configuração'), 'blue')

    def activity(self, terminal, label):
        reduced = os.environ.get('CENTAUR_REDUCED_MOTION') == '1'
        frames = ('◐', '◓', '◑', '◒')
        marker = '•' if reduced else frames[int(time.monotonic() * 8) % len(frames)]
        elapsed = int(time.monotonic() - (terminal.busy_started or terminal.started_at))
        return f'{marker} {label} · {elapsed}s'

    def draw(self, screen, terminal):
        # Only the welcome surface owns animation time; hidden editors never advance it.
        if (terminal.settings or terminal.rename_target or terminal.browser
                or terminal.chat['messages'] or terminal.approval):
            self.animation.pause()
        self.animation.active = False
        self.graphic_visible = False
        screen.bkgd(' ', self.palette.styles['text'])
        screen.erase()
        height, width = screen.getmaxyx()
        credits, credit_style = credit_label(terminal.credits, terminal.credits_status, width)
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
        transcript_width = min(100, width - 6)
        transcript_left = max(3, (width - transcript_width) // 2)
        model = terminal.backend + ' · ' + (terminal.chat['model'] or 'padrão')
        if terminal.chat.get('effort', 'default') != 'default':
            model += ' · ' + terminal.chat['effort']
        self.put(screen, 2, transcript_left, '◆ ' + terminal.chat['title'], 'title', transcript_width)
        if width >= 100:
            self.put(screen, 3, transcript_left, str(terminal.root), 'muted', transcript_width // 2 - 2)
            self.put(screen, 3, transcript_left + transcript_width // 2, model, 'blue', transcript_width // 2)
        else:
            self.put(screen, 3, transcript_left, model, 'muted', transcript_width)
        self.put(screen, 4, transcript_left, '─' * transcript_width, 'line')
        top, available = 5, height - 11
        if height < 20 and (terminal.settings or terminal.rename_target):
            # A compact editor owns the content region so every field remains reachable.
            top, available = 0, height - 6
            for row in range(height - 5):
                self.put(screen, row, 0, ' ' * (width - 1))
        if terminal.settings:
            self.settings(screen, terminal, top, available, width)
        elif terminal.rename_target:
            self.put(screen, top, 3, 'RENOMEAR CHAT', 'green')
            self.put(screen, top + 2, 3, terminal.rename_target['title'], 'muted')
            self.put(screen, top + 4, 3, 'Título · 1 a 80 caracteres', 'blue')
        elif terminal.browser:
            self.put(screen, top, 2, 'CHATS DESTA PASTA', 'green')
            self.put(screen, top + 1, 2, f'{len(terminal.chats)} conversas salvas', 'muted')
            visible = max(1, available - 3)
            start = max(0, terminal.selected - visible + 1)
            for row, chat in enumerate(terminal.chats[start:start + visible], top + 3):
                selected = start + row - top - 3 == terminal.selected
                title = f' {">" if selected else " "} [{chat.get("backend", "openrouter")}] {chat["title"]}'
                style = 'selected' if selected else 'text'
                self.put(screen, row, 2, ' ' * (width - 5), style)
                self.put(screen, row, 2, title, style, width - 25 if width >= 78 else width - 5)
                if width >= 78:
                    self.put(screen, row, width - 21, chat['updated'][:16],
                             'selected' if selected else 'muted')
            if not terminal.chats:
                self.put(screen, top + 4, 3, 'Nenhum chat salvo. Esc volta para começar.', 'muted')
        elif not terminal.chat['messages'] and not terminal.approval:
            self.welcome(screen, top, available, width, terminal)
        else:
            lines = terminal.lines(transcript_width)
            if terminal.approval:
                start = min(terminal.scroll, max(0, len(lines) - available))
            else:
                start = max(0, len(lines) - available - terminal.scroll)
            for row, line in enumerate(lines[start:start + available], top):
                style = 'text'
                if line.startswith('› '):
                    style = 'user'
                    self.put(screen, row, transcript_left - 1, ' ' * (transcript_width + 2), style)
                elif line.startswith('◆ Centaur'):
                    style = 'green'
                elif line.startswith('◦ ') or line.startswith('  '):
                    style = 'muted'
                elif line.startswith('↳ Ferramenta'):
                    style = 'blue'
                elif line.startswith('CONFIRMAÇÃO'):
                    style = 'warning'
                self.put(screen, row, transcript_left, line, style, transcript_width)
        terminal.completion.update(terminal.draft if terminal.cursor == len(terminal.draft) else '')
        completing = (terminal.completion.visible and not terminal.browser and not terminal.approval
                      and not terminal.settings and not terminal.rename_target)
        if completing:
            visible = min(6, max(1, available - 1))
            start = max(0, terminal.completion.selected - visible + 1)
            choices = terminal.completion.options[start:start + visible]
            popup_top = height - 5 - len(choices) - 1
            prefix = terminal.completion.context[1]
            heading = 'Skills Centaur ($)' if prefix == '$' else 'Skills do projeto (@) · .centaur/skills'
            self.put(screen, popup_top, 2, ' ' * (width - 5))
            self.put(screen, popup_top, 3, f'{heading} · {len(terminal.completion.options)}', 'green')
            for index, name in enumerate(choices):
                selected = start + index == terminal.completion.selected
                style = 'selected' if selected else 'text'
                row = popup_top + index + 1
                self.put(screen, row, 2, ' ' * (width - 5), style)
                self.put(screen, row, 3, f'{">" if selected else " "} {prefix}{name}', style)
        # The composer follows the same reading column as the conversation.
        composer_left = 2 if (terminal.settings or terminal.rename_target or terminal.browser or terminal.approval) else transcript_left - 1
        composer_width = width - 5 if composer_left == 2 else transcript_width + 2
        self.put(screen, height - 5, composer_left, '─' * composer_width, 'line')
        notice = terminal.notice
        if terminal.busy and not terminal.approval:
            notice = self.activity(terminal, notice)
        elif terminal.settings:
            notice = terminal.settings.error or terminal.settings.catalog_status or notice
        if (not terminal.browser and not terminal.approval and not terminal.settings
                and not terminal.rename_target and terminal.completion.context
                and not terminal.completion.options and terminal.completion.dismissed != terminal.draft):
            prefix = terminal.completion.context[1]
            notice = ('Nenhuma skill adicional encontrada em .centaur/skills/.' if prefix == '@'
                      else 'Nenhuma skill Centaur corresponde ao nome digitado.')
        self.put(screen, height - 4, composer_left, notice,
                 'warning' if notice.startswith(('Erro', 'Não foi', 'Chave detectada')) else 'muted')
        self.put(screen, height - 3, composer_left, ' ' * composer_width, 'user')
        self.put(screen, height - 3, composer_left, '›', 'green')
        draft = terminal.rename_text if terminal.rename_target else terminal.draft
        cursor = terminal.rename_cursor if terminal.rename_target else terminal.cursor
        input_width = max(1, composer_width - 2)
        visible_draft, cursor_column = input_window(draft, cursor, input_width)
        self.put(screen, height - 3, composer_left + 2, visible_draft, 'user')
        credits = credits[:max(1, width - 5)]
        self.put(screen, height - 2, max(2, width - len(credits) - 3), credits, credit_style)
        hints = ('Aguarde a validação…' if terminal.settings and terminal.settings.pending else
                 '↑↓ escolher · Enter abrir/salvar · Esc voltar/cancelar' if terminal.settings else
                 'Enter salvar · Esc cancelar · Ctrl+U limpar' if terminal.rename_target else
                 '↑↓ escolher · Tab/Enter inserir · Esc fechar' if completing else
                 'y permitir · n recusar · PgUp/PgDn revisar' if terminal.approval else
                 '↑↓ selecionar · Enter retomar · R renomear · Del excluir · Esc voltar' if terminal.browser else
                 'Enter enviar · Shift+← chats · Ctrl+O detalhes · PgUp/PgDn rolar · Ctrl+Q sair')
        self.put(screen, height - 1, 2, hints, 'blue')
        if not terminal.approval and (terminal.rename_target or not terminal.browser):
            if terminal.settings and terminal.settings.page == 'custom':
                _, custom_cursor = input_window(terminal.settings.query, len(terminal.settings.query),
                                                max(1, width - 8))
                screen.move(top + 5, min(width - 2, 5 + custom_cursor))
            elif not terminal.settings:
                screen.move(height - 3, min(width - 2, composer_left + 2 + cursor_column))
        screen.refresh()
