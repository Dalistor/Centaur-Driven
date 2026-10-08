"""Choose the connection before authentication or chat creation."""

import curses
import queue
import threading
from types import SimpleNamespace

from .appearance import TerminalView, WORDMARK, input_window
from .config import validate
from .openrouter import OpenRouter
from .settings import ConfigPicker
from .permissions import MODE_LABELS


class StartupPicker(ConfigPicker):
    startup = True
    fields = ('Backend', 'Modelo padrão', 'Effort', 'Permissões', 'Velocidade', 'Iniciar conversa')

    def __init__(self, backend, model, effort, approval_mode='ask', speed='standard'):
        super().__init__(backend, model, effort, approval_mode, speed)
        self.open_page('backend')

    @property
    def values(self):
        return [{'openrouter': 'OpenRouter', 'codex': 'Codex', 'claude': 'Claude'}[self.backend],
                self.model or 'Padrão do provedor', self.effort,
                MODE_LABELS[self.approval_mode], 'Rápido · maior uso/custo' if self.speed == 'fast' else 'Padrão', 'Enter para iniciar']

    def open_page(self, page):
        self.page, self.query, self.error = page, '', ''
        current = {'backend': self.backend, 'model': self.model, 'effort': self.effort,
                   'permissions': self.approval_mode, 'speed': self.speed}[page]
        choices = [item[0] for item in self.options()]
        self.selected = choices.index(current) if current in choices else 0

    def options(self):
        if self.page == 'backend':
            return [('openrouter', 'OpenRouter · API key e créditos'),
                    ('codex', 'Codex · autenticação do CLI local'),
                    ('claude', 'Claude · autenticação do CLI local')]
        choices = super().options()
        if self.page == 'effort':
            descriptions = {'default': 'Padrão do provedor', 'none': 'Sem raciocínio adicional',
                            'minimal': 'Mínimo', 'low': 'Baixo', 'medium': 'Equilibrado',
                            'high': 'Alto', 'xhigh': 'Muito alto', 'max': 'Máximo'}
            return [(level, f'{level} · {descriptions[level]}') for level, _ in choices]
        return choices

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
    def __init__(self, backend, model, effort, approval_mode='ask', speed='standard'):
        self.picker = StartupPicker(backend, model, effort, approval_mode, speed)
        self.view = TerminalView()
        self.events = queue.Queue()
        self.catalog_request = 0

    def load_catalog(self):
        if self.picker.backend != 'openrouter':
            return  # Native options come from the existing local catalog/cache.
        self.catalog_request += 1
        request = self.catalog_request
        self.picker.catalog_status = 'Carregando catálogo público…'
        def fetch():
            source = OpenRouter('')
            try:
                catalog = source.model_catalog()
                result = catalog, source.model_efforts, ''
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
            if request == self.catalog_request and self.picker.backend == 'openrouter':
                self.picker.update_catalog('openrouter', *result)

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
        self.view.put(screen, 1, 3, WORDMARK, 'muted')
        if width < 40 or height < 18:
            self.view.put(screen, 3, 1, 'Amplie para 40 × 18 para escolher sua IA.', 'muted')
            self.view.put(screen, height - 1, 1, 'Esc / Ctrl+Q cancela', 'muted')
            screen.refresh()
            return
        surface = SimpleNamespace(settings=self.picker, busy_started=None)
        self.view.settings(screen, surface, 3, height - 9, width)
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
            self.view.put(screen, 2, 3, notice, 'muted')
        self.view.put(screen, height - 1, 3, '↑↓ escolher · Enter confirmar · Esc voltar/cancelar · Ctrl+Q sair', 'muted')
        if self.picker.page == 'custom':
            _, cursor = input_window(self.picker.query, len(self.picker.query), width - 8)
            screen.move(8, min(width - 2, 5 + cursor))
        screen.refresh()

    def run(self, screen):
        try:
            return self._run(screen)
        finally:
            self.view.palette.restore()

    def _run(self, screen):
        curses.raw()
        self.view.palette.initialize()
        screen.keypad(True)
        screen.timeout(100)
        while True:
            self.drain_events()
            try:
                curses.curs_set(int(self.picker.page == 'custom'))
            except curses.error:
                pass
            self.draw(screen)
            try:
                key = screen.get_wch()
            except curses.error:
                continue
            if key == curses.KEY_RESIZE:
                curses.update_lines_cols()
                screen.clearok(True)
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
            elif action == 'save':
                return self.picker.backend, self.picker.model, self.picker.effort, self.picker.approval_mode
