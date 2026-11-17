"""Estado do seletor local, separado de persistência e chamadas de rede."""

import curses
import json
import os
from pathlib import Path

from .config import BACKENDS, effort_options, validate
from .permissions import APPROVAL_MODES, MODE_LABELS, validate_mode
from .speed import validate_speed, local_speed_support, fast_supported
from . import models


def codex_cache():
    path = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'models_cache.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return [entry for entry in data['models'] if isinstance(entry, dict) and entry.get('visibility') == 'list'
                and isinstance(entry.get('slug'), str)]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def local_models(backend):
    if backend == 'claude':
        # A lista guardada da última consulta ao CLI traz as versões exatas; sem ela, só os aliases.
        return models.claude_catalog(models.cached_claude())[0] or dict(models.CLAUDE_ALIASES)
    if backend == 'codex':
        return {entry['slug']: entry.get('description', '') for entry in codex_cache()}
    return {'openrouter/auto': 'Roteamento automático'}


def local_details(backend):
    """Metadados disponíveis sem rede: aliases do Claude e o cache de modelos do Codex."""
    if backend == 'claude':
        return models.claude_details()
    if backend == 'codex':
        return {entry['slug']: models.codex_details(entry) for entry in codex_cache()}
    return {'openrouter/auto': {'description': 'O OpenRouter escolhe o modelo a cada pedido, conforme o conteúdo.'}}


class ConfigPicker:
    @property
    def fields(self):
        fields = ('Backend', 'Modelo', 'Effort', 'Permissões', 'Velocidade')
        if self.backend == 'openrouter':
            fields += ('Saldo da conta',)
        return (*fields, 'Salvar preferências')

    def __init__(self, backend, model, effort, approval_mode='ask', speed='standard'):
        self.backend, self.model, self.effort = backend, model, effort
        self.approval_mode = validate_mode(approval_mode)
        self.speed = validate_speed(speed)
        self.speed_support = local_speed_support(backend)
        self.row = 0
        self.page = 'fields'
        self.selected = 0
        self.query = ''
        self.error = ''
        self.pending = False
        self.catalog_status = ''
        self.catalog = local_models(backend)
        self.details = local_details(backend)
        self.model_efforts = {}
        if backend == 'codex':
            self.load_native_efforts()
        if backend == 'claude':
            self.model_efforts = models.claude_catalog(models.cached_claude())[1]
        if model:
            self.catalog.setdefault(model, 'Modelo atual')

    def summary(self, model):
        """Texto curto ao lado do ID na lista: modelo servido, contexto e preço quando conhecidos."""
        if model == '':
            default = models.load_learned(self.backend).get('') if self.backend == 'claude' else None
            listed = self.details.get('') or {}
            if listed.get('served'):
                return ' · '.join(part for part in (listed.get('name'), listed['served']) if part)
            return default['id'] if default else 'definido fora do Centaur'
        if model is None:
            return 'informar um ID ou alias'
        return models.summary(model, self.details.get(model)) or self.catalog.get(model, '')

    def detail(self, model):
        return models.detail_lines(self.backend, model, self.details.get(model) if model is not None else None)

    def effort_label(self):
        return 'Padrão do provedor' if self.effort == 'default' else self.effort

    def model_label(self):
        """Modelo escolhido, com o que o identifica, para a revisão e o resumo."""
        if not self.model:
            return models.DEFAULT_LABELS[self.backend]
        extra = self.summary(self.model)
        return self.model + (' · ' + extra if extra else '')

    @property
    def values(self):
        return [models.BACKEND_LABELS[self.backend], self.model_label(), self.effort_label(),
                MODE_LABELS[self.approval_mode], 'Rápido · maior uso/custo' if self.speed == 'fast' else 'Padrão',
                *(['Cadastrar ou substituir chave'] if self.backend == 'openrouter' else []), 'Enter para salvar']

    def options(self):
        if self.page == 'backend':
            labels = {'openrouter': 'OpenRouter · API key e créditos', 'codex': 'Codex · autenticação do CLI local',
                      'claude': 'Claude · autenticação do CLI local'}
            return [(value, labels[value]) for value in BACKENDS]
        if self.page == 'permissions':
            return [(value, MODE_LABELS[value]) for value in APPROVAL_MODES]
        if self.page == 'speed':
            choices = [('standard', 'Padrão · uso e custo normais')]
            if fast_supported(self.backend, self.model, self.speed_support):
                choices.append(('fast', 'Rápido · pode consumir/custar mais'))
            return choices
        if self.page == 'effort':
            levels = self.model_efforts.get(self.model, effort_options(self.backend))
            descriptions = {'default': 'Padrão do provedor', 'none': 'none · Sem raciocínio adicional',
                            'minimal': 'minimal · Mínimo', 'low': 'low · Baixo', 'medium': 'medium · Equilibrado',
                            'high': 'high · Alto', 'xhigh': 'xhigh · Muito alto', 'max': 'max · Máximo'}
            return [(value, descriptions[value]) for value in levels if value in effort_options(self.backend)]
        # O catálogo público é longo e fica em ordem alfabética; os nativos seguem a ordem do provedor.
        names = sorted(self.catalog) if self.backend == 'openrouter' else list(self.catalog)
        query = self.query.casefold()
        listed = [(name, name) for name in names
                  if query in name.casefold() or query in str((self.details.get(name) or {}).get('name', '')).casefold()]
        return [('', 'Padrão do provedor'), (None, 'Modelo personalizado…'), *listed]

    def load_native_efforts(self):
        path = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'models_cache.json'
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            self.model_efforts = {entry['slug']: ['default', *[level['effort'] for level in
                                 entry['supported_reasoning_levels']]] for entry in data['models']
                                 if entry.get('visibility') == 'list' and 'supported_reasoning_levels' in entry}
        except (OSError, ValueError, KeyError, TypeError):
            self.model_efforts = {}

    def update_catalog(self, backend, catalog, efforts, error='', details=None):
        if self.backend != backend:
            return
        self.details.update({name: value for name, value in (details or {}).items() if isinstance(value, dict)})
        choices = self.options()
        current = choices[min(self.selected, len(choices) - 1)][0]
        for name, description in catalog.items():
            try:
                validate(backend, name)
            except ValueError:
                continue
            self.catalog[name] = description
        self.model_efforts.update(efforts)
        if self.effort not in self.model_efforts.get(self.model, [self.effort]):
            self.effort = 'default'
        choices = [item[0] for item in self.options()]
        self.selected = choices.index(current) if current in choices else 0
        self.catalog_status = error or f'{len(self.catalog)} modelos disponíveis'

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
                    if self.model != self.query.strip(): self.speed = 'standard'
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
                if self.row == len(self.fields) - 1:
                    return 'save'
                if self.fields[self.row] == 'Saldo da conta':
                    return 'configure_credits'
                self.page = ('backend', 'model', 'effort', 'permissions', 'speed')[self.row]
                self.query = ''
                values = [item[0] for item in self.options()]
                current = (self.backend, self.model, self.effort, self.approval_mode, self.speed)[self.row]
                self.selected = values.index(current) if current in values else 0
                if self.page == 'model':
                    return 'catalog'
                if self.page == 'speed':
                    return 'speed_catalog'
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
                    self.speed, self.speed_support = 'standard', local_speed_support(value)
                    self.catalog = local_models(value)
                    self.details = local_details(value)
                    self.model_efforts = {}
                    if value == 'codex':
                        self.load_native_efforts()
                    if value == 'claude':
                        self.model_efforts = models.claude_catalog(models.cached_claude())[1]
                    self.catalog_status = ''
            elif self.page == 'effort':
                self.effort = value
            elif self.page == 'permissions':
                self.approval_mode = value
            elif self.page == 'speed':
                self.speed = value
            elif value is None:
                self.page, self.query, self.error = 'custom', self.model, ''
                return
            else:
                if self.model != value:
                    self.speed = 'standard'
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
