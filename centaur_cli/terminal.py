"""Interface curses e navegação entre conversas."""

import curses
import queue
import textwrap
import threading
import time

from .backends import create_client
from .config import save_config, validate
from .settings import ConfigPicker
from .openrouter import OpenRouter
from .agent import run_turn
from .completion import SkillCompletion
from .tools import ProjectTools
from .appearance import TerminalView
from .graphics import FRAME_SECONDS
from .subagents import SubagentTools
from .status import ANALYSIS_INSTRUCTIONS, StatusTools, render_status


def display_lines(text, width):
    clean = ''.join(character if character.isprintable() or character == '\n' else ' '
                    for character in str(text))
    return [line for paragraph in clean.split('\n')
            for line in (textwrap.wrap(paragraph, max(1, width)) or [''])]


def read_key(screen, timeout=100):
    """Decode xterm Shift+Left when the terminal's terminfo lacks kLFT."""
    key = screen.get_wch()
    if key != '\x1b':
        return key
    sequence, consumed = '[1;2D', []
    screen.timeout(25)
    try:
        for expected in sequence:
            try:
                next_key = screen.get_wch()
            except curses.error:
                break
            consumed.append(next_key)
            if next_key != expected:
                break
        else:
            return curses.KEY_SLEFT
    finally:
        screen.timeout(timeout)
    # Preserve unrelated keystrokes after a standalone Escape.
    for next_key in reversed(consumed):
        if isinstance(next_key, str):
            curses.unget_wch(next_key)
        else:
            curses.ungetch(next_key)
    return key


class Terminal:
    def __init__(self, root, model, store, client, max_subagent_tier='high', *, effort='default'):
        self.root, self.model, self.store, self.client = root, model, store, client
        self.backend = getattr(client, 'backend', 'openrouter')
        self.effort = effort
        self.chat = store.new(model, backend=self.backend)
        self.chat['effort'] = effort
        self.events = queue.Queue()
        self.busy = False
        self.approval = None
        self.draft = ''
        self.completion = SkillCompletion(root)
        self.notice = 'Digite sua intenção. Shift+← chats · $config preferências.'
        self.settings = None
        self.rename_target = None
        self.rename_text = ''
        self.rename_cursor = 0
        self.started_at = time.monotonic()
        self.busy_started = None
        self.browser = False
        self.chats = []
        self.selected = 0
        self.scroll = 0
        self.view = TerminalView()
        self.credits = None
        self.credits_status = 'loading'
        self.credits_inflight = False
        self.credits_next_refresh = 0
        self.credits_dirty = False
        self.max_subagent_tier = max_subagent_tier

    def request_credits(self):
        if self.backend != 'openrouter':
            self.credits_status = 'unsupported'
            return
        if self.credits_inflight:
            return
        if not self.credits_dirty and time.monotonic() < self.credits_next_refresh:
            return
        if not callable(getattr(self.client, 'credits', None)):
            self.credits_status = 'error'
            return
        self.credits_inflight = True
        self.credits_dirty = False
        threading.Thread(target=self.fetch_credits, args=(self.client,), daemon=True).start()

    def fetch_credits(self, client):
        try:
            event = ('credits', client.credits())
        except Exception:
            event = ('credits_error', None)
        if client is self.client:
            self.events.put(('backend_credits', (client, event)))

    def approve(self, description):
        answer = queue.Queue()
        self.events.put(('approval', (description, answer)))
        return answer.get()

    def submit(self):
        if self.busy or not self.draft.strip():
            return
        if self.draft.strip() == '/quit':
            return 'quit'
        if self.draft.strip() == '/new':
            self.chat = self.new_chat()
            self.draft = ''
            self.scroll = 0
            return
        if self.draft.strip() == '/credits':
            self.draft = ''
            self.credits_dirty = True
            self.notice = ('Atualizando créditos. Saldo da conta: cadastre com --configure-credits-key.'
                           if self.backend == 'openrouter' else f'{self.backend}: saldo não exposto nesta integração; consulte o cliente.')
            return
        secrets = getattr(self.client, 'secrets', (getattr(self.client, 'api_key', None),))
        if any(key and key in self.draft for key in secrets):
            self.draft = ''
            self.notice = 'Chave detectada: mensagem descartada para proteger a credencial.'
            return
        command = self.draft.strip()
        if command == '/chats':
            self.draft = ''
            self.open_chats()
            return
        if command == '/rename':
            self.store.save(self.chat)
            self.draft = ''
            self.begin_rename(self.chat)
            return
        if command.startswith('/rename '):
            self.store.save(self.chat)
            if self.rename_chat(self.chat, command[len('/rename '):]):
                self.draft = ''
            return
        if command.split()[0] == '$config':
            return self.configure(command)
        if command.startswith('/status'):
            if command not in ('/status', '/status --ai'):
                self.notice = 'Uso: /status ou /status --ai para analisar com IA.'
                return
            if command == '/status':
                self.chat['messages'].extend([
                    {'role': 'user', 'content': command},
                    {'role': 'assistant', 'content': render_status(self.root)}])
                if self.chat['title'] == 'Novo chat' and not self.chat.get('title_custom'):
                    self.chat['title'] = 'Status das specs'
                self.store.save(self.chat)
                self.draft = ''
                self.scroll = 0
                self.notice = 'Status local · /status --ai analisa evidências e recomenda próximos passos.'
                return
        self.chat['messages'].append({'role': 'user', 'content': self.draft})
        if self.chat['title'] == 'Novo chat' and not self.chat.get('title_custom'):
            self.chat['title'] = self.draft[:80]
        self.store.save(self.chat)
        self.draft = ''
        self.scroll = 0
        self.busy = True
        self.busy_started = time.monotonic()
        self.notice = f'Aguardando {self.backend}…'
        threading.Thread(target=self.work, args=(self.chat,), daemon=True).start()

    @property
    def draft(self):
        return self._draft

    @draft.setter
    def draft(self, value):
        self._draft = value
        self.cursor = len(value)

    def new_chat(self):
        chat = self.store.new(self.model, backend=self.backend)
        chat['effort'] = self.effort
        return chat

    def configure(self, command):
        parts = command.split()
        if len(parts) == 1:
            self.settings = ConfigPicker(self.backend, self.model, self.effort)
            self.draft = ''
            self.notice = 'Escolha backend, modelo e effort. Esc cancela sem salvar.'
            return
        try:
            if len(parts) > 4:
                raise ValueError('Uso: $config <backend> [modelo] [effort]')
            backend = parts[1]
            model = parts[2] if len(parts) >= 3 else ''
            effort = parts[3] if len(parts) == 4 else 'default'
            validate(backend, model, effort if len(parts) == 4 else None)
            client = create_client(backend, model, allow_setup=False)
            # Preserve the older two-field format for legacy command invocations.
            save_config(self.root, backend, model, effort if len(parts) == 4 else None)
        except (RuntimeError, OSError, ValueError) as error:
            self.notice = f'Configuração não alterada: {error}'
            return
        self.activate_config(backend, model, effort, client)

    def activate_config(self, backend, model, effort, client):
        self.backend, self.model, self.effort, self.client = backend, model, effort, client
        self.chat = self.new_chat()
        self.draft = ''
        self.scroll = 0
        self.settings = None
        self.credits = None
        self.credits_inflight = False
        self.credits_next_refresh = 0
        self.credits_status = 'loading' if backend == 'openrouter' else 'unsupported'
        self.credits_dirty = True
        self.notice = f'Configuração salva: {backend} · {model or "padrão"} · effort {effort}. Novo chat.'

    def load_catalog(self, picker):
        backend = picker.backend
        # Other native backends use their local catalog, without starting a client.
        source = self.client if backend == self.backend else None
        if source is None and backend == 'openrouter':
            source = OpenRouter('')  # Public catalog; switching never asks for credentials here.
        if not callable(getattr(source, 'model_catalog', None)):
            return
        picker.catalog_status = 'Carregando catálogo…'
        def fetch():
            try:
                result = (source.model_catalog(), getattr(source, 'model_efforts', {}), '')
            except Exception:
                result = ({}, {}, 'Catálogo indisponível. Use Modelo personalizado ou reabra para tentar.')
            self.events.put(('catalog', (picker, backend, result)))
        threading.Thread(target=fetch, daemon=True).start()

    def handle_settings(self, key):
        picker = self.settings
        action = picker.handle(key)
        if action == 'cancel':
            self.settings = None
            self.notice = 'Configuração cancelada.'
        elif action == 'catalog':
            self.load_catalog(picker)
        elif action == 'save':
            secrets = getattr(self.client, 'secrets', ())
            if any(secret and secret in picker.model for secret in secrets):
                picker.error = 'Chave detectada; use somente o nome do modelo.'
                return
            picker.pending = True
            self.notice = 'Validando configuração…'
            def apply():
                try:
                    validate(picker.backend, picker.model, picker.effort)
                    client = create_client(picker.backend, picker.model, allow_setup=False)
                    if picker.backend == 'openrouter':
                        client.model_efforts = dict(picker.model_efforts)
                    save_config(self.root, picker.backend, picker.model, picker.effort)
                    self.events.put(('configured', (picker, client, None)))
                except Exception as error:
                    redact = getattr(self.client, 'redact', str)
                    self.events.put(('configured', (picker, None, redact(str(error)))))
            threading.Thread(target=apply, daemon=True).start()

    def begin_rename(self, chat):
        if self.busy and chat['id'] == self.chat['id']:
            self.notice = 'Aguarde o turno terminar para renomear o chat em execução.'
            return
        self.rename_target = chat
        self.rename_text = chat['title']
        self.rename_cursor = len(self.rename_text)
        self.notice = 'Renomear chat · 1 a 80 caracteres · Enter salvar · Esc cancelar.'

    def rename_chat(self, chat, title):
        if self.busy and chat['id'] == self.chat['id']:
            self.notice = 'Aguarde o turno terminar para renomear o chat em execução.'
            return False
        if any(secret and secret in title for secret in getattr(self.client, 'secrets', ())):
            self.notice = 'Chave detectada: título não salvo.'
            return False
        try:
            renamed = self.store.rename(chat['id'], title)
        except (OSError, ValueError) as error:
            self.notice = f'Não foi possível renomear: {error}'
            return False
        if chat['id'] == self.chat['id']:
            self.chat = renamed
        self.chats = self.store.list()
        self.selected = next((index for index, item in enumerate(self.chats)
                              if item['id'] == chat['id']), 0)
        self.notice = 'Chat renomeado.'
        return True

    def handle_rename(self, key):
        if key == '\x1b':
            self.rename_target = None
            self.notice = 'Renomeação cancelada.'
        elif key in ('\n', '\r', curses.KEY_ENTER):
            if self.rename_chat(self.rename_target, self.rename_text):
                self.rename_target = None
        elif key == curses.KEY_LEFT:
            self.rename_cursor = max(0, self.rename_cursor - 1)
        elif key == curses.KEY_RIGHT:
            self.rename_cursor = min(len(self.rename_text), self.rename_cursor + 1)
        elif key in (curses.KEY_BACKSPACE, '\x7f', '\b') and self.rename_cursor:
            self.rename_text = self.rename_text[:self.rename_cursor - 1] + self.rename_text[self.rename_cursor:]
            self.rename_cursor -= 1
        elif key == '\x15':
            self.rename_text, self.rename_cursor = '', 0
        elif isinstance(key, str) and key.isprintable():
            self.rename_text = self.rename_text[:self.rename_cursor] + key + self.rename_text[self.rename_cursor:]
            self.rename_cursor += 1

    def work(self, chat):
        try:
            base = ProjectTools(self.root, self.approve,
                                protected_keys=getattr(self.client, 'secrets', (getattr(self.client, 'api_key', None),)))
            status_analysis = chat['messages'][-1].get('content', '').strip() == '/status --ai'
            if status_analysis:
                tools = StatusTools(self.root, lambda _: False,
                                    protected_keys=getattr(self.client, 'secrets', ()))
            else:
                tools = SubagentTools(base, self.client, chat['id'],
                                      lambda notice: self.events.put(('progress', notice)), self.max_subagent_tier)
            backend_instructions = (f'\nBackend conectado: {self.backend}. Escolha o modelo por complexidade e risco '
                                    'entre os modelos listados em delegate_task. Não use cost_tier ou outro provedor. '
                                    'Se não houver catálogo, mantenha o modelo principal.\n'
                                    if self.backend != 'openrouter' else '')
            run_turn(chat, self.client, tools,
                     self.store, lambda: self.events.put(('refresh', None)),
                     (f'\nA faixa máxima configurada para subagentes é {self.max_subagent_tier}. '
                      'Não solicite faixas superiores; isso exige configuração explícita do usuário.\n'
                      if self.backend == 'openrouter' else backend_instructions)
                     + (ANALYSIS_INSTRUCTIONS if status_analysis else ''))
            self.events.put(('done', 'Pronto.'))
        except Exception as error:
            self.events.put(('done', f'Erro: {error}'))

    def drain_events(self):
        while not self.events.empty():
            kind, value = self.events.get_nowait()
            if kind == 'backend_credits':
                source, event = value
                if source is not self.client:
                    continue
                kind, value = event
            if kind == 'catalog':
                picker, backend, (catalog, efforts, error) = value
                if self.settings is picker and picker.backend == backend:
                    # Keep the focused model stable when the async catalog arrives.
                    choices = picker.options()
                    current = choices[min(picker.selected, len(choices) - 1)][0]
                    picker.catalog.update({name: description for name, description in catalog.items()
                                           if isinstance(name, str)})
                    picker.model_efforts.update(efforts)
                    if picker.effort not in picker.model_efforts.get(picker.model, [picker.effort]):
                        picker.effort = 'default'
                    choices = [item[0] for item in picker.options()]
                    picker.selected = choices.index(current) if current in choices else 0
                    picker.catalog_status = error or f'{len(picker.catalog)} modelos disponíveis'
            elif kind == 'configured':
                picker, client, error = value
                if self.settings is not picker:
                    continue
                picker.pending = False
                if error:
                    picker.error = 'Configuração não alterada: ' + error
                    self.notice = 'Confira a configuração e tente novamente.'
                else:
                    self.activate_config(picker.backend, picker.model, picker.effort, client)
            elif kind == 'approval':
                self.approval = value
                self.browser = False
                self.rename_target = None
                self.scroll = 0
            elif kind == 'done':
                self.busy = False
                self.notice = value
                self.credits_dirty = True
            elif kind == 'progress':
                self.notice = value
                self.credits_dirty = True
            elif kind in ('credits', 'credits_error'):
                self.credits_inflight = False
                self.credits_next_refresh = time.monotonic() + 30
                self.credits_status = 'ready' if kind == 'credits' else 'error'
                if kind == 'credits':
                    self.credits = value

    def lines(self, width):
        if self.approval:
            return display_lines('CONFIRMAÇÃO — y: permitir / n: recusar\n\n' + self.approval[0], width)
        if self.browser:
            return [f'{">" if index == self.selected else " "} {chat["updated"][:16]}  {chat["title"]}'
                    for index, chat in enumerate(self.chats)] or ['Nenhum chat salvo nesta pasta.']
        lines = []
        for message in list(self.chat['messages']):
            role = {'user': '› Você', 'assistant': '◆ Centaur', 'tool': '↳ Ferramenta'}[message['role']]
            content = message.get('content') or ''
            if message.get('tool_calls'):
                content += '\n' + ', '.join(call['function']['name'] for call in message['tool_calls'])
            lines.extend([role] + display_lines(content, width) + [''])
        return lines or ['Centaur experimental · OpenRouter', '', '/new cria chat · /quit sai']

    def draw(self, screen):
        self.view.draw(screen, self)

    def delete_selected_chat(self):
        if not self.chats:
            return
        selected_chat = self.chats[self.selected]
        is_current_chat = selected_chat['id'] == self.chat['id']
        if self.busy and is_current_chat:
            self.notice = 'Aguarde o turno terminar para excluir o chat em execução.'
            return
        try:
            self.store.delete(selected_chat['id'])
        except (OSError, ValueError) as error:
            self.notice = f'Não foi possível excluir o chat: {error}'
            return
        if is_current_chat:
            self.chat = self.new_chat()
            self.draft = ''
            self.scroll = 0
        self.chats = self.store.list()
        self.selected = min(self.selected, max(0, len(self.chats) - 1))
        self.notice = 'Chat excluído.'

    def open_chats(self):
        self.browser = True
        self.chats = self.store.list()
        self.selected = 0

    def handle(self, key):
        if key in ('\x11', '\x03'):
            if self.busy or (self.settings and self.settings.pending):
                self.notice = 'Aguarde o turno ou configuração terminar para sair; recuse ações pendentes com n.'
                return
            return 'quit'
        if self.approval:
            if key in ('y', 'Y', 'n', 'N'):
                self.approval[1].put(key.lower() == 'y')
                self.approval = None
                self.scroll = 0
            elif key == curses.KEY_NPAGE:
                self.scroll += 5
            elif key == curses.KEY_PPAGE:
                self.scroll = max(0, self.scroll - 5)
            return
        if self.settings:
            return self.handle_settings(key)
        if self.rename_target:
            return self.handle_rename(key)
        if key == curses.KEY_SLEFT:
            self.open_chats()
            return
        if self.browser:
            if key in ('\x1b', curses.KEY_RIGHT):
                self.browser = False
            elif key == curses.KEY_UP:
                self.selected = max(0, self.selected - 1)
            elif key == curses.KEY_DOWN:
                self.selected = min(max(0, len(self.chats) - 1), self.selected + 1)
            elif key in ('r', 'R', curses.KEY_F2) and self.chats:
                self.begin_rename(self.chats[self.selected])
            elif key == curses.KEY_DC:
                self.delete_selected_chat()
            elif key in ('\n', '\r', curses.KEY_ENTER) and self.chats:
                if self.busy:
                    self.notice = 'Aguarde o turno terminar para retomar outro chat.'
                elif self.chats[self.selected].get('backend', 'openrouter') != self.backend:
                    self.notice = 'Este chat usa outro backend; abra o Centaur com --backend ' + self.chats[self.selected].get('backend', 'openrouter')
                elif (self.backend != 'openrouter' and self.chats[self.selected]['model'] != self.model):
                    self.notice = 'Este chat usa outro modelo; abra com o mesmo --model ou crie um chat novo.'
                else:
                    self.chat = self.chats[self.selected]
                    self.browser = False
                    self.draft = ''
                    self.scroll = 0
            return
        if key == curses.KEY_F5:
            if not self.chat['messages'] and not self.busy and not self.draft:
                self.view.animation.replay()
            return
        self.completion.update(self.draft if self.cursor == len(self.draft) else '')
        if self.completion.visible:
            if key == curses.KEY_UP:
                self.completion.selected = max(0, self.completion.selected - 1)
                return
            if key == curses.KEY_DOWN:
                self.completion.selected = min(len(self.completion.options) - 1, self.completion.selected + 1)
                return
            if key in ('\t', '\n', '\r', curses.KEY_ENTER):
                self.draft = self.completion.choose(self.draft)
                self.completion.update(self.draft)
                return
            if key == '\x1b':
                self.completion.dismiss(self.draft)
                return
        if key == curses.KEY_LEFT:
            self.cursor = max(0, self.cursor - 1)
        elif key == curses.KEY_RIGHT:
            self.cursor = min(len(self.draft), self.cursor + 1)
        elif key == curses.KEY_HOME:
            self.cursor = 0
        elif key == curses.KEY_END:
            self.cursor = len(self.draft)
        elif key == curses.KEY_PPAGE:
            self.scroll += 5
        elif key == curses.KEY_NPAGE:
            self.scroll = max(0, self.scroll - 5)
        elif key in ('\n', '\r', curses.KEY_ENTER):
            return self.submit()
        elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
            if self.cursor:
                self._draft = self.draft[:self.cursor - 1] + self.draft[self.cursor:]
                self.cursor -= 1
        elif key == curses.KEY_DC:
            self._draft = self.draft[:self.cursor] + self.draft[self.cursor + 1:]
        elif key == '\x15':
            self.draft = ''
        elif isinstance(key, str) and key.isprintable():
            self._draft = self.draft[:self.cursor] + key + self.draft[self.cursor:]
            self.cursor += 1

    def run(self, screen):
        curses.raw()
        self.view.palette.initialize()
        screen.keypad(True)
        screen.timeout(100)
        while True:
            frame_start = time.monotonic()
            self.drain_events()
            self.request_credits()
            try:
                curses.curs_set(0 if self.approval or (self.browser and not self.rename_target)
                                or (self.settings and self.settings.page != 'custom') else 1)
            except curses.error:
                pass
            self.draw(screen)
            # Render only while the welcome sequence moves. Idle work retains the
            # existing 100 ms event cadence and does not reproject the mesh.
            timeout = max(1, round((FRAME_SECONDS - (time.monotonic() - frame_start)) * 1000)) \
                if self.view.animation.active else 100
            screen.timeout(timeout)
            try:
                key = read_key(screen, timeout)
            except curses.error:
                continue
            if key == curses.KEY_RESIZE:
                curses.update_lines_cols()
                screen.clearok(True)
                continue
            if self.handle(key) == 'quit':
                return
