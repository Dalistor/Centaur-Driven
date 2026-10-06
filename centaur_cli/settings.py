"""Estado do seletor local, separado de persistência e chamadas de rede."""

import curses
import json
import os
from pathlib import Path

from .config import BACKENDS, effort_options, validate


def local_models(backend):
    if backend == 'claude':
        return {'haiku': 'Tasks simples', 'sonnet': 'Implementação', 'opus': 'Investigação'}
    if backend == 'codex':
        path = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'models_cache.json'
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return {entry['slug']: entry.get('description', '') for entry in data['models']
                    if isinstance(entry, dict) and entry.get('visibility') == 'list'
                    and isinstance(entry.get('slug'), str)}
        except (OSError, ValueError, KeyError, TypeError):
            return {}
    return {'openrouter/auto': 'Roteamento automático'}


class ConfigPicker:
    fields = ('Backend', 'Modelo', 'Effort', 'Salvar e abrir novo chat')

    def __init__(self, backend, model, effort):
        self.backend, self.model, self.effort = backend, model, effort
        self.row = 0
        self.page = 'fields'
        self.selected = 0
        self.query = ''
        self.error = ''
        self.pending = False
        self.catalog_status = ''
        self.catalog = local_models(backend)
        self.model_efforts = {}
        if backend == 'codex':
            self.load_native_efforts()
        if model:
            self.catalog.setdefault(model, 'Modelo atual')

    @property
    def values(self):
        return [self.backend, self.model or 'Padrão do provedor', self.effort, 'Enter para salvar']

    def options(self):
        if self.page == 'backend':
            return [(value, value) for value in BACKENDS]
        if self.page == 'effort':
            levels = self.model_efforts.get(self.model, effort_options(self.backend))
            return [(value, 'Padrão do provedor' if value == 'default' else value)
                    for value in levels if value in effort_options(self.backend)]
        models = [(name, name) for name in sorted(self.catalog)
                  if self.query.casefold() in name.casefold()]
        return [('', 'Padrão do provedor'), (None, 'Modelo personalizado…'), *models]

    def load_native_efforts(self):
        path = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'models_cache.json'
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            self.model_efforts = {entry['slug']: ['default', *[level['effort'] for level in
                                 entry['supported_reasoning_levels']]] for entry in data['models']
                                 if entry.get('visibility') == 'list' and 'supported_reasoning_levels' in entry}
        except (OSError, ValueError, KeyError, TypeError):
            self.model_efforts = {}

    def handle(self, key):
        if self.pending:
            return
        enter = key in ('\n', '\r', curses.KEY_ENTER)
        if key == '\x1b':
            if self.page == 'fields':
                return 'cancel'
            self.page, self.query, self.error = 'fields', '', ''
            return
        if self.page == 'custom':
            if enter:
                try:
                    validate(self.backend, self.query.strip(), self.effort)
                    self.model = self.query.strip()
                    if self.effort not in self.model_efforts.get(self.model, effort_options(self.backend)):
                        self.effort = 'default'
                    self.page, self.error = 'fields', ''
                except ValueError as error:
                    self.error = str(error)
            elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                self.query = self.query[:-1]
            elif key == '\x15':
                self.query = ''
            elif isinstance(key, str) and key.isprintable():
                self.query += key
            return
        if self.page == 'fields':
            if key in (curses.KEY_UP, '\x10'):
                self.row = max(0, self.row - 1)
            elif key in (curses.KEY_DOWN, '\t'):
                self.row = (self.row + 1) % len(self.fields)
            elif enter:
                if self.row == 3:
                    return 'save'
                self.page = ('backend', 'model', 'effort')[self.row]
                self.query = ''
                values = [item[0] for item in self.options()]
                current = (self.backend, self.model, self.effort)[self.row]
                self.selected = values.index(current) if current in values else 0
                if self.page == 'model':
                    return 'catalog'
            return
        choices = self.options()
        if key == curses.KEY_UP:
            self.selected = max(0, self.selected - 1)
        elif key == curses.KEY_DOWN:
            self.selected = min(len(choices) - 1, self.selected + 1)
        elif enter:
            value = choices[min(self.selected, len(choices) - 1)][0]
            if self.page == 'backend':
                if self.backend != value:
                    self.backend, self.model, self.effort = value, '', 'default'
                    self.catalog = local_models(value)
                    self.model_efforts = {}
                    if value == 'codex':
                        self.load_native_efforts()
                    self.catalog_status = ''
            elif self.page == 'effort':
                self.effort = value
            elif value is None:
                self.page, self.query, self.error = 'custom', self.model, ''
                return
            else:
                self.model = value
                if self.effort not in self.model_efforts.get(value, effort_options(self.backend)):
                    self.effort = 'default'
            self.page, self.query, self.error = 'fields', '', ''
        elif self.page == 'model':
            if key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                self.query = self.query[:-1]
            elif key == '\x15':
                self.query = ''
            elif isinstance(key, str) and key.isprintable():
                self.query += key
            self.selected = 0
