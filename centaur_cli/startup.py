"""Choose the connection before authentication or chat creation."""

import curses
import os
import queue
import threading
import time
from types import SimpleNamespace

from .appearance import TerminalView, WORDMARK, TAGLINE, input_window
from .graphics import FRAME_SECONDS, WelcomeAnimation, mesh
from .config import validate
from .openrouter import OpenRouter
from .settings import ConfigPicker
from .permissions import MODE_LABELS
from . import models


class StartupPicker(ConfigPicker):
    startup = True
    @property
    def fields(self):
        fields = list(super().fields)
        fields[1], fields[-1] = 'Modelo padrão', 'Iniciar conversa'
        return tuple(fields)

    def __init__(self, backend, model, effort, approval_mode='ask', speed='standard'):
        super().__init__(backend, model, effort, approval_mode, speed)
        self.open_page('backend')

    @property
    def values(self):
        return [{'openrouter': 'OpenRouter', 'codex': 'Codex', 'claude': 'Claude'}[self.backend],
                self.model_label(), self.effort_label(),
                MODE_LABELS[self.approval_mode], 'Rápido · maior uso/custo' if self.speed == 'fast' else 'Padrão',
                *(['Cadastrar ou substituir chave'] if self.backend == 'openrouter' else []), 'Enter para iniciar']

    def open_page(self, page):
        self.page, self.query, self.error = page, '', ''
        current = {'backend': self.backend, 'model': self.model, 'effort': self.effort,
                   'permissions': self.approval_mode, 'speed': self.speed}[page]
        choices = [item[0] for item in self.options()]
        self.selected = choices.index(current) if current in choices else 0

    def handle(self, key):
        previous = self.page
        if key in ('\x03', '\x11'):
            return 'cancel'
        if key == '\x1b':
            if previous in ('backend', 'fields'):
                return 'cancel'
            self.open_page({'model': 'backend', 'custom': 'model', 'effort': 'model',
                            'permissions': 'effort', 'speed': 'permissions'}[previous])
            return 'catalog' if self.page == 'model' else None
        action = super().handle(key)
        if self.page == 'fields' and previous in ('backend', 'model', 'custom', 'effort', 'permissions', 'speed'):
            if previous == 'backend':
                self.open_page('model')
                return 'catalog'
            if previous in ('model', 'custom'):
                self.open_page('effort')
            elif previous == 'effort':
                self.open_page('permissions')
            elif previous == 'permissions':
                self.open_page('speed')
                return 'speed_catalog'
            else:
                self.row = len(self.fields) - 1
        if action == 'save':
            validate(self.backend, self.model, self.effort, self.approval_mode)
        return action


class StartupWizard:
    STEPS = (('backend', 'Conexão'), ('model', 'Modelo'), ('effort', 'Effort'),
             ('permissions', 'Permissões'), ('speed', 'Velocidade'), ('fields', 'Revisão'))

    def __init__(self, backend, model, effort, approval_mode='ask', speed='standard'):
        self.picker = StartupPicker(backend, model, effort, approval_mode, speed)
        self.view = TerminalView()
        self.top, self.played, self.opening = 3, False, False
        self.catalog_backend = backend  # Resultado atrasado de outro backend nunca altera a lista.
        self.events = queue.Queue()
        self.catalog_request = 0

    def load_catalog(self):
        if self.picker.backend == 'codex':
            return  # Codex options come from its local model cache.
        self.catalog_request += 1
        request, self.catalog_backend = self.catalog_request, self.picker.backend
        if self.picker.backend == 'claude':
            self.picker.catalog_status = 'Consultando os modelos do Claude Code…'
            def fetch_claude():
                try:
                    result = (*models.claude_catalog(models.refresh_claude()), )
                    result = result[0], result[1], '', result[2]
                except RuntimeError:
                    result = {}, {}, 'Lista do Claude Code indisponível; mostrando os aliases conhecidos.'
                self.events.put((request, result))
            threading.Thread(target=fetch_claude, daemon=True).start()
            return
        self.picker.catalog_status = 'Carregando catálogo público…'
        def fetch():
            source = OpenRouter('')
            try:
                catalog = source.model_catalog()
                result = catalog, source.model_efforts, '', source.model_details
            except Exception:
                result = {}, {}, 'Catálogo indisponível; use Modelo personalizado ou Padrão do provedor.'
            self.events.put((request, result))
        threading.Thread(target=fetch, daemon=True).start()

    def drain_events(self):
        while not self.events.empty():
            request, result = self.events.get_nowait()
            if request == 'speed':
                backend, model, supported, error = result
                if (self.picker.backend, self.picker.model) == (backend, model):
                    self.picker.speed_support[model] = supported
                    if self.picker.page == 'speed' and supported and self.picker.speed == 'fast': self.picker.selected = 1
                    self.picker.catalog_status = error or ('Fast disponível · custo maior' if supported else 'Fast não anunciado para este modelo.')
                continue
            if request == self.catalog_request and self.picker.backend == self.catalog_backend:
                self.picker.update_catalog(self.picker.backend, *result)

    def load_speed(self):
        if self.picker.backend != 'openrouter': return
        backend, model = self.picker.backend, self.picker.model
        self.picker.catalog_status = 'Consultando capacidade Fast…'
        def fetch():
            try: result = OpenRouter('').supports_fast(model), ''
            except Exception: result = False, 'Capacidade Fast indisponível; escolha Padrão.'
            self.events.put(('speed', (backend, model, *result)))
        threading.Thread(target=fetch, daemon=True).start()

    def draw(self, screen):
        screen.bkgd(' ', self.view.palette.styles['text'])
        screen.erase()
        height, width = screen.getmaxyx()
        self.view.animation.active = False
        self.view.put(screen, 1, 3, WORDMARK, 'muted')
        if width >= 66:
            self.view.put(screen, 1, width - len(TAGLINE) - 3, TAGLINE, 'muted')
        if getattr(self, 'root', None):
            self.view.put(screen, 2, 3, str(self.root), 'muted')
        if width < 40 or height < 18:
            self.view.animation.pause()
            self.view.put(screen, 3, 1, 'Amplie para 40 × 18 para escolher sua IA.', 'muted')
            self.view.put(screen, height - 1, 1, 'Esc / Ctrl+Q cancela', 'muted')
            screen.refresh()
            return
        surface = SimpleNamespace(settings=self.picker, busy_started=None)
        # Com espaço, uma trilha mostra onde o usuário está na sequência de abertura.
        self.top = 3
        if height >= 22 and width >= 78:
            self.top = 5
            column = 3
            for index, (page, label) in enumerate(self.STEPS):
                current = self.STEPS[[name for name, _ in self.STEPS].index(
                    'model' if self.picker.page == 'custom' else self.picker.page)][0]
                position = [name for name, _ in self.STEPS].index(current)
                marker, style = ('●', 'green') if index == position else ('●', 'text') if index < position else ('○', 'muted')
                self.view.put(screen, 3, column, f'{marker} {label}', style)
                column += len(label) + 2
                if index < len(self.STEPS) - 1:
                    self.view.put(screen, 3, column, ' ── ', 'line')
                    column += 4
        # A marca acompanha a escolha ao lado, sem tirar linhas dos controles.
        emblem = (26, 10) if height >= 30 else (20, 8)
        branded = width >= 104 and height >= 24 and self.picker.page != 'custom'
        self.view.settings(screen, surface, self.top, height - 6 - self.top, width - (emblem[0] + 6 if branded else 0))
        if branded:
            # Ao lado das escolhas a marca fica em repouso: o movimento pertence à abertura.
            self.view.animation.settle()
            self.view.logo(screen, self.top + 1, width - emblem[0] - 4, size=emblem, caption=False)
        else:
            self.view.animation.pause()
        self.view.put(screen, height - 6, 2, '─' * (width - 5), 'line')
        self.view.put(screen, height - 5, 3, 'Modelo e effort: agente principal.', 'text')
        explanation = ('Subagentes: o Centaur escolhe modelos do mesmo backend por complexidade e risco.'
                       if width >= 85 else 'Subagentes: modelos por complexidade e risco, no mesmo backend.')
        from .terminal import display_lines
        for offset, line in enumerate(display_lines(explanation, width - 6)[:2]):
            self.view.put(screen, height - 4 + offset, 3, line, 'muted')
        notice = self.picker.error or self.picker.catalog_status
        if self.picker.error:
            for offset, line in enumerate(display_lines(self.picker.error, width - 6)[:3]):
                self.view.put(screen, height - 5 + offset, 3, ' ' * (width - 6))
                self.view.put(screen, height - 5 + offset, 3, line, 'warning')
        elif notice:
            # O caminho da pasta continua visível; o estado do catálogo fica ao lado quando cabe.
            column = width - len(notice) - 3 if getattr(self, 'root', None) and width >= len(str(self.root)) + len(notice) + 10 else 3
            self.view.put(screen, 2, column, notice.ljust(width - column - 3) if column == 3 else notice, 'muted')
        self.view.put(screen, height - 1, 3, '↑↓ escolher · Enter confirmar · Esc voltar/cancelar · Ctrl+Q sair', 'muted')
        if self.picker.page == 'custom':
            _, cursor = input_window(self.picker.query, len(self.picker.query), width - 15)
            screen.move(self.top + 5, min(width - 2, 8 + cursor))
        screen.refresh()

    def draw_opening(self, screen):
        """A abertura ocupa a tela sozinha; as escolhas só aparecem depois dela. False se não couber."""
        screen.bkgd(' ', self.view.palette.styles['text'])
        screen.erase()
        height, width = screen.getmaxyx()
        size = (36, 16) if height >= 24 and width >= 44 else (26, 10)
        if height < size[1] + 5 or width < size[0] + 4:
            return False
        self.view.animation.active = False
        self.view.logo(screen, max(1, (height - size[1] - 4) // 2), (width - size[0]) // 2, size=size)
        if self.view.graphic_visible and self.view.animation.staged(2.6):
            hint = 'Enter continua'
            self.view.put(screen, height - 2, (width - len(hint)) // 2, hint, 'muted')
        screen.refresh()
        return self.view.graphic_visible

    def end_opening(self):
        self.opening, self.played = False, True
        self.view.animation.settle()

    def run(self, screen):
        try:
            return self._run(screen)
        finally:
            self.view.palette.restore()

    def _run(self, screen):
        curses.raw()
        self.view.palette.initialize()
        screen.keypad(True)
        self.opening = os.environ.get('CENTAUR_REDUCED_MOTION') != '1'
        if self.opening:
            mesh()  # Calculada antes do primeiro quadro, fora do relógio da animação.
            try:
                curses.curs_set(0)
            except curses.error:
                pass
        rested = None
        while True:
            started = time.monotonic()
            self.drain_events()
            if self.opening:
                if not self.draw_opening(screen):
                    self.opening = False  # Sem espaço ou sem Braille: direto às escolhas.
                    continue
                if not self.view.animation.active:
                    rested = rested or started
                    if started - rested >= .8:
                        self.end_opening()
                        continue
            else:
                try:
                    curses.curs_set(int(self.picker.page == 'custom'))
                except curses.error:
                    pass
                self.draw(screen)
            # Em movimento, o tempo gasto desenhando é descontado para manter 30 quadros por segundo.
            screen.timeout(max(1, round((FRAME_SECONDS - (time.monotonic() - started)) * 1000))
                           if self.view.animation.active else 100)
            try:
                key = screen.get_wch()
            except curses.error:
                continue
            if key == curses.KEY_RESIZE:
                curses.update_lines_cols()
                screen.clearok(True)
                continue
            if self.opening:
                if key in ('\x03', '\x11'):
                    return None
                self.end_opening()  # Qualquer tecla pula a abertura.
                continue
            if screen.getmaxyx()[0] < 18 or screen.getmaxyx()[1] < 40:
                if key in ('\x1b', '\x03', '\x11'):
                    return None
                continue
            before = self.picker.backend
            action = self.picker.handle(key)
            if before != self.picker.backend:
                self.catalog_request += 1  # Invalidate results from earlier backend visits.
            if action == 'catalog':
                self.load_catalog()
            elif action == 'speed_catalog':
                self.load_speed()
            elif action == 'cancel':
                return None
            elif action == 'configure_credits':
                return action
            elif action == 'save':
                # A abertura já foi vista aqui: o chat começa com a marca em repouso (F5 repete).
                WelcomeAnimation.opening_played = self.played
                return self.picker.backend, self.picker.model, self.picker.effort, self.picker.approval_mode
