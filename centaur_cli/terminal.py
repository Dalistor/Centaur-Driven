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
from .agent import run_turn, project_prompt
from .tools import TOOLS
from .context import compact_chat, context_label, estimate_tokens, save_compaction, save_compaction_progress
from .speed import validate_speed, fast_supported
from .native_usage import BalanceUnavailable
from .completion import SkillCompletion
from .conversation import generate_title, readable_markdown, tool_activity
from .tools import ProjectTools
from .appearance import TerminalView
from .graphics import FRAME_SECONDS
from .subagents import SubagentTools
from .status import ANALYSIS_INSTRUCTIONS, StatusTools, render_status
from .permissions import validate_mode, MODE_LABELS
from .interaction import QuestionPicker, TurnCancelled
from .computer import ComputerSession
from .composer import layout_input
from .keyboard import KEY_NEWLINE, PastedText, KeyboardReader, keyboard_protocol, read_key


def display_lines(text, width):
    clean = ''.join(character if character.isprintable() or character == '\n' else ' '
                    for character in str(text))
    return [line for paragraph in clean.split('\n')
            for line in (textwrap.wrap(paragraph, max(1, width)) or [''])]


class Terminal:
    def __init__(self, root, model, store, client, max_subagent_tier='high', *, effort='default', approval_mode='ask', speed='standard'):
        self.root, self.model, self.store, self.client = root, model, store, client
        self.backend = getattr(client, 'backend', 'openrouter')
        self.effort = effort
        self.speed = validate_speed(speed)
        self.approval_mode = validate_mode(approval_mode)
        self.wide_chat = False
        self.chat = store.new(model, backend=self.backend)
        self.chat['effort'] = effort
        self.chat['approval_mode'] = self.approval_mode
        self.chat['speed'] = self.speed
        self.events = queue.Queue()
        self.busy = False
        self.approval = None
        self.question = None
        self.cancel_event = threading.Event()
        self.computer = None
        self.saved_scroll = 0
        self.viewport_key = None
        self.viewport_lines = 0
        self.scroll_limit = 0
        self.draft = ''
        self.input_width = 74
        self.prompt_history = None
        self.prompt_index = None
        self.prompt_current = ('', 0)
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
        self.show_details = False
        self.pending_titles = {}
        self.title_tasks = set()
        self.context_overhead = estimate_tokens(project_prompt(root)) + estimate_tokens(TOOLS)

    def context_label(self, width):
        return context_label(self.chat, self.client, width, self.draft, self.context_overhead)

    def request_context_catalog(self):
        client = self.client
        if not callable(getattr(client, 'model_catalog', None)):
            return
        def fetch():
            try:
                client.model_catalog()
            except Exception:
                pass  # Unknown limits stay explicitly unknown; typing never waits on HTTP.
        threading.Thread(target=fetch, daemon=True).start()

    def request_credits(self):
        if self.credits_inflight:
            return
        if not self.credits_dirty and time.monotonic() < self.credits_next_refresh:
            return
        if not callable(getattr(self.client, 'credits', None)):
            self.credits_status = 'error' if self.backend == 'openrouter' else 'unsupported'
            return
        self.credits_inflight = True
        self.credits_dirty = False
        threading.Thread(target=self.fetch_credits, args=(self.client,), daemon=True).start()

    def fetch_credits(self, client):
        try:
            event = ('credits', client.credits())
        except BalanceUnavailable as error:
            event = ('credits_unavailable', error.status)
        except Exception:
            event = ('credits_error', None)
        if client is self.client:
            self.events.put(('backend_credits', (client, event)))

    def approve(self, description):
        answer = queue.Queue()
        self.events.put(('approval', (description, answer)))
        return self.wait_answer(answer)

    def wait_answer(self, answer):
        while True:
            if self.cancel_event.is_set():
                raise TurnCancelled('Turno interrompido pelo usuário.')
            try:
                return answer.get(timeout=0.1)
            except queue.Empty:
                pass

    def ask_user(self, question, options):
        answer = queue.Queue()
        self.events.put(('question', QuestionPicker(question, options, answer)))
        return self.wait_answer(answer)

    def cancel_work(self):
        self.cancel_event.set()
        if self.computer:
            self.computer.close()
        if self.approval or self.question:
            self.scroll = self.saved_scroll
        self.approval = None
        self.question = None
        self.notice = 'Interrompendo · captura parada e novas ações bloqueadas. Aguardando a chamada atual ao modelo.'

    def transcript_start(self, count, available, width):
        key = (self.chat['id'], width, self.show_details)
        # Preserve the top visible row when new content arrives during manual reading.
        if self.viewport_key == key and self.scroll and count > self.viewport_lines:
            self.scroll += count - self.viewport_lines
        self.viewport_key, self.viewport_lines = key, count
        self.scroll_limit = max(0, count - available)
        self.scroll = min(self.scroll_limit, max(0, self.scroll))
        return max(0, count - available - self.scroll)

    def scroll_chat(self, delta):
        self.scroll = min(self.scroll_limit, max(0, self.scroll + delta))

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
        if self.draft.strip() in ('/credits', '$credits'):
            self.draft = ''
            self.credits_dirty = True
            self.notice = ('Atualizando créditos. Saldo da conta: cadastre com --configure-credits-key.'
                           if self.backend == 'openrouter' else f'Atualizando uso {self.backend} · cotas/créditos apenas quando informados pelo CLI.')
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
        if command == '/wide':
            self.wide_chat = not self.wide_chat
            self.draft = ''
            self.notice = 'Conversa: ' + ('largura do terminal.' if self.wide_chat else 'coluna de leitura.')
            return
        if command in ('$compact', '/compact'):
            self.draft = ''
            self.cancel_event = threading.Event()
            self.busy = True
            self.busy_started = time.monotonic()
            self.notice = 'Compactando contexto com IA · histórico completo preservado · Ctrl+C interrompe.'
            threading.Thread(target=self.compact, args=(self.chat, self.client, self.cancel_event), daemon=True).start()
            return
        if command == '/retry':
            self.draft = ''
            if not self.chat.get('last_error'):
                self.notice = 'Nenhum turno com falha para retomar.'
                return
            self.chat.pop('last_error', None)
            self.start_work()
            return
        if command == '/rename':
            self.store.save(self.chat)
            self.draft = ''
            self.begin_rename(self.chat)
            return
        if command.startswith('/rename ') and '\n' not in command:
            self.store.save(self.chat)
            if self.rename_chat(self.chat, command[len('/rename '):]):
                self.draft = ''
            return
        if command.split()[0] == '$config' and '\n' not in command:
            return self.configure(command)
        if command.startswith(('/status', '$status')) and '\n' not in command:
            if command not in ('/status', '/status --ai', '$status', '$status --ai'):
                self.notice = 'Uso: $status ou $status --ai para analisar com IA.'
                return
            if command in ('/status', '$status'):
                self.chat['messages'].extend([
                    {'role': 'user', 'content': command},
                    {'role': 'assistant', 'content': render_status(self.root)}])
                if self.chat['title'] == 'Novo chat' and not self.chat.get('title_custom'):
                    self.chat['title'] = 'Status das specs'
                self.store.save(self.chat)
                self.draft = ''
                self.scroll = 0
                self.notice = 'Status local · $status --ai analisa evidências e recomenda próximos passos.'
                return
        self.chat['messages'].append({'role': 'user', 'content': self.draft})
        self.chat.pop('last_error', None)
        self.chat['approval_mode'] = self.approval_mode
        if self.chat['title'] == 'Novo chat' and not self.chat.get('title_custom'):
            self.chat['title'] = ' '.join(self.draft.split())[:80]
        self.store.save(self.chat)
        self.draft = ''
        self.start_work()

    def start_work(self):
        self.chat['approval_mode'] = self.approval_mode
        self.store.save(self.chat)
        self.scroll = 0
        self.viewport_key = None
        self.cancel_event = threading.Event()
        self.busy = True
        self.busy_started = time.monotonic()
        self.notice = f'Aguardando {self.backend}…'
        threading.Thread(target=self.work, args=(self.chat,), daemon=True).start()

    def compact(self, chat, client, cancel_event):
        try:
            state, before, after = compact_chat(chat, client, cancel_event,
                progress=lambda notice: self.events.put(('progress', notice)),
                checkpoint=lambda pending: save_compaction_progress(chat, self.store, pending, cancel_event))
            self.events.put(('compacted', (chat, cancel_event, state, before, after)))
        except Exception as error:
            message = getattr(client, 'redact', str)(str(error))
            self.events.put(('done', 'Compactação: ' + message))

    @property
    def draft(self):
        return self._draft

    @draft.setter
    def draft(self, value):
        self._draft = value
        self.cursor = len(value)
        self.preferred_input_column = None
        self.prompt_history = None
        self.prompt_index = None

    def insert_text(self, text):
        self.prompt_history = None
        self.prompt_index = None
        self._draft = self.draft[:self.cursor] + text + self.draft[self.cursor:]
        self.cursor += len(text)
        self.preferred_input_column = None

    def recall_prompt(self, direction):
        if self.prompt_history is None:
            if direction > 0: return False
            self.prompt_history = [m['content'] for m in self.chat['messages']
                                   if m.get('role') == 'user' and isinstance(m.get('content'), str)]
            if not self.prompt_history:
                self.prompt_history = None
                return False
            self.prompt_current = (self.draft, self.cursor)
            self.prompt_index = len(self.prompt_history)
        self.prompt_index = max(0, min(len(self.prompt_history), self.prompt_index + direction))
        if self.prompt_index == len(self.prompt_history):
            self._draft, self.cursor = self.prompt_current
            self.prompt_history = None
            self.prompt_index = None
        else:
            self._draft = self.prompt_history[self.prompt_index]
            self.cursor = len(self._draft)
        self.preferred_input_column = None
        self.completion.update('')
        return True

    def new_chat(self):
        chat = self.store.new(self.model, backend=self.backend)
        chat['effort'] = self.effort
        chat['approval_mode'] = self.approval_mode
        chat['speed'] = self.speed
        return chat

    def configure(self, command):
        parts = command.split()
        if len(parts) == 1:
            self.settings = ConfigPicker(self.backend, self.chat['model'], self.chat.get('effort', self.effort),
                                         self.approval_mode, self.chat.get('speed', self.speed))
            self.settings.speed_support.update(getattr(self.client, 'speed_support', {}))
            self.draft = ''
            self.notice = 'Escolha modelo, effort, permissões e velocidade. Salvar retorna ao chat. Esc cancela.'
            return
        try:
            if len(parts) > 6:
                raise ValueError('Uso: $config <backend> [modelo] [effort] [ask|auto|never] [standard|fast]')
            backend = parts[1]
            model = parts[2] if len(parts) >= 3 else ''
            effort = parts[3] if len(parts) >= 4 else 'default'
            approval_mode = parts[4] if len(parts) >= 5 else self.approval_mode
            speed = parts[5] if len(parts) == 6 else self.speed if (backend, model) == (self.backend, self.model) else 'standard'
            validate(backend, model, effort if len(parts) >= 4 else None, approval_mode)
            client = (self.client if self.client is not None and (backend, model) ==
                              (self.backend, self.model) else create_client(backend, model, allow_setup=False))
            if callable(getattr(client, 'check_speed', None)): client.check_speed(model, speed)
            save_config(self.root, backend, model, effort if len(parts) >= 4 else None, approval_mode, speed)
        except (RuntimeError, OSError, ValueError) as error:
            self.notice = f'Configuração não alterada: {error}'
            return
        self.activate_config(backend, model, effort, client, approval_mode, speed)

    def activate_config(self, backend, model, effort, client, approval_mode=None, speed=None):
        history_warning = ''
        same_client = client is self.client
        new_conversation = backend != self.backend
        model_changed = (model, effort) != (self.model, self.effort)
        speed_changed = speed is not None and speed != self.speed
        if speed is not None: self.speed = validate_speed(speed)
        self.backend, self.model, self.effort, self.client = backend, model, effort, client
        self.request_context_catalog()
        if approval_mode is not None:
            self.approval_mode = validate_mode(approval_mode)
        if new_conversation:
            self.chat = self.new_chat()
        else:
            self.chat['approval_mode'] = self.approval_mode
            if model_changed:
                self.chat.update(model=model, effort=effort)
                self.chat.pop('context_usage', None)
            if speed_changed or model_changed:
                self.chat['speed'] = self.speed
                self.chat.pop('speed_served', None)
            if self.chat['messages']:
                try:
                    self.store.save(self.chat)
                except OSError:
                    history_warning = ' Não foi possível registrar o modo no histórico.'
        self.draft = ''
        self.scroll = 0
        self.settings = None
        if not same_client:
            self.credits = None
            self.credits_inflight = False
            self.credits_next_refresh = 0
            self.credits_status = 'loading'
        self.credits_dirty = True
        self.notice = (f'Configuração salva: {MODE_LABELS[self.approval_mode]}. '
                       + ('Novo chat.' if new_conversation else 'Conversa preservada.') + history_warning)

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

    def load_speed(self, picker):
        backend, model = picker.backend, picker.model
        source = self.client if backend == self.backend else OpenRouter('') if backend == 'openrouter' else None
        picker.catalog_status = 'Verificando suporte Fast…'
        def fetch():
            try:
                supported = (source.supports_fast(model) if callable(getattr(source, 'supports_fast', None))
                             else fast_supported(backend, model, picker.speed_support))
                result = supported, ''
            except Exception:
                result = False, 'Suporte Fast indisponível; escolha Padrão.'
            self.events.put(('speed_support', (picker, backend, model, *result)))
        threading.Thread(target=fetch, daemon=True).start()

    def handle_settings(self, key):
        picker = self.settings
        action = picker.handle(key)
        if action == 'cancel':
            self.settings = None
            self.notice = 'Configuração cancelada.'
        elif action == 'catalog':
            self.load_catalog(picker)
        elif action == 'speed_catalog':
            self.load_speed(picker)
        elif action == 'save':
            secrets = getattr(self.client, 'secrets', ())
            if any(secret and secret in picker.model for secret in secrets):
                picker.error = 'Chave detectada; use somente o nome do modelo.'
                return
            picker.pending = True
            self.notice = 'Validando configuração…'
            def apply():
                try:
                    validate(picker.backend, picker.model, picker.effort, picker.approval_mode)
                    client = (self.client if self.client is not None and (picker.backend, picker.model) ==
                              (self.backend, self.model) else
                              create_client(picker.backend, picker.model, allow_setup=False))
                    if picker.backend == 'openrouter':
                        client.model_efforts = dict(picker.model_efforts)
                        client.speed_support = dict(picker.speed_support)
                    if callable(getattr(client, 'check_speed', None)): client.check_speed(picker.model, picker.speed)
                    save_config(self.root, picker.backend, picker.model, picker.effort, picker.approval_mode, picker.speed)
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
        computer = ComputerSession(self.approve, self.cancel_event)
        self.computer = computer
        try:
            base = ProjectTools(self.root, self.approve,
                                protected_keys=getattr(self.client, 'secrets', (getattr(self.client, 'api_key', None),)),
                                approval_mode=self.approval_mode, ask_user=self.ask_user,
                                cancel_event=self.cancel_event, computer=computer)
            last_request = next((message.get('content') or '' for message in reversed(chat['messages'])
                                 if message['role'] == 'user'), '')
            status_analysis = last_request.strip() in ('/status --ai', '$status --ai')
            if status_analysis:
                tools = StatusTools(self.root, lambda _: False,
                                    protected_keys=getattr(self.client, 'secrets', ()))
                tools.cancel_event = self.cancel_event
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
                     + (ANALYSIS_INSTRUCTIONS if status_analysis else ''),
                     progress=lambda notice: self.events.put(('progress', notice)))
            if (not chat.get('title_custom') and not chat.get('title_attempted')
                    and not status_analysis):
                chat['title_attempted'] = True
                try:
                    self.store.save(chat)
                    self.title_tasks.add(chat['id'])
                    snapshot = [dict(message) for message in chat['messages']]
                    threading.Thread(target=self.make_title,
                                     args=(chat['id'], self.client, chat['model'], snapshot), daemon=True).start()
                except (OSError, RuntimeError):
                    self.title_tasks.discard(chat['id'])
            self.events.put(('done', 'Pronto.'))
        except TurnCancelled as error:
            chat['last_error'] = str(error)
            self.store.save(chat)
            self.events.put(('done', 'Turno interrompido. /retry retoma; confira ações já aplicadas.'))
        except Exception as error:
            message = getattr(self.client, 'redact', str)(str(error))
            chat['last_error'] = message
            try:
                self.store.save(chat)
            except OSError:
                pass
            self.events.put(('done', f'Erro: {message} · /retry retoma este turno.'))
        finally:
            computer.close()
            if self.computer is computer:
                self.computer = None

    def make_title(self, chat_id, client, model, messages):
        try:
            title = generate_title(client, model, messages)
        except Exception:
            title = None  # Title failure must not interrupt a successful conversation.
        self.events.put(('title', (chat_id, title)))

    def apply_titles(self):
        for chat_id, title in list(self.pending_titles.items()):
            if self.busy and self.chat['id'] == chat_id:
                continue
            del self.pending_titles[chat_id]
            self.title_tasks.discard(chat_id)
            if not title:
                continue
            try:
                renamed = self.store.generated_title(chat_id, title)
                if renamed and self.chat['id'] == chat_id:
                    self.chat.update(title=renamed['title'], title_generated=True)
                if self.browser:
                    selected_id = self.chats[self.selected]['id'] if self.chats else None
                    self.chats = self.store.list()
                    self.selected = next((i for i, c in enumerate(self.chats) if c['id'] == selected_id), 0)
            except (OSError, ValueError):
                pass  # Deleted/renamed chats are not recreated by late title requests.

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
                    picker.update_catalog(backend, catalog, efforts, error)
            elif kind == 'configured':
                picker, client, error = value
                if self.settings is not picker:
                    continue
                picker.pending = False
                if error:
                    picker.error = 'Configuração não alterada: ' + error
                    self.notice = 'Confira a configuração e tente novamente.'
                else:
                    self.activate_config(picker.backend, picker.model, picker.effort, client, picker.approval_mode, picker.speed)
            elif kind == 'speed_support':
                picker, backend, model, supported, error = value
                if self.settings is picker and (picker.backend, picker.model) == (backend, model):
                    picker.speed_support[model] = supported
                    if picker.page == 'speed' and supported and picker.speed == 'fast': picker.selected = 1
                    picker.catalog_status = error or ('Fast disponível · custo maior' if supported else 'Fast não anunciado para este modelo.')
                    if picker.speed == 'fast' and not error and not supported: picker.speed = 'standard'
            elif kind == 'approval':
                if self.cancel_event.is_set():
                    continue
                self.approval = value
                self.browser = False
                self.rename_target = None
                self.saved_scroll, self.scroll = self.scroll, 0
            elif kind == 'question':
                if self.cancel_event.is_set():
                    continue
                self.question = value
                self.browser = False
                self.rename_target = None
                self.saved_scroll = self.scroll
            elif kind == 'done':
                self.busy = False
                self.approval = None
                self.question = None
                self.notice = value
                self.credits_dirty = True
            elif kind == 'compacted':
                chat, cancellation, state, before, after = value
                self.busy = False
                self.credits_dirty = True
                if cancellation.is_set():
                    self.notice = 'Compactação interrompida; contexto anterior preservado.'
                    continue
                try:
                    save_compaction(chat, self.store, state, cancellation)
                    self.notice = f'Contexto compactado: ~{before:,} → ~{after:,} tokens. Histórico preservado.'
                except OSError:
                    self.notice = 'Erro ao salvar compactação; contexto anterior preservado.'
            elif kind == 'title':
                chat_id, title = value
                self.pending_titles[chat_id] = title
                self.credits_dirty = True
            elif kind == 'progress':
                self.notice = value
                self.credits_dirty = True
            elif kind in ('credits', 'credits_error', 'credits_unavailable'):
                self.credits_inflight = False
                self.credits_next_refresh = time.monotonic() + 30
                self.credits_status = 'ready' if kind == 'credits' else value if kind == 'credits_unavailable' else 'error'
                if kind == 'credits':
                    self.credits = value
        self.apply_titles()

    def lines(self, width):
        if self.approval:
            return display_lines('CONFIRMAÇÃO — y: permitir / n: recusar\n\n' + self.approval[0], width)
        if self.browser:
            return [f'{">" if index == self.selected else " "} {chat["updated"][:16]}  {chat["title"]}'
                    for index, chat in enumerate(self.chats)] or ['Nenhum chat salvo nesta pasta.']
        lines, actions, working = [], {}, False
        messages = list(self.chat['messages'])
        results = {m.get('tool_call_id'): m.get('content', '') for m in messages if m['role'] == 'tool'}
        for message in messages:
            content = message.get('content') or ''
            if message['role'] == 'user':
                working = False
                lines.extend([''] + ['› ' + text for text in display_lines(content, max(1, width - 2))] + [''])
            elif message['role'] == 'assistant' and message.get('tool_calls'):
                if not working:
                    lines.append('◦ Trabalho · Ctrl+O detalhes')
                    working = True
                if content:
                    lines.extend('  ' + text for text in display_lines(readable_markdown(content), width - 2))
                for call in message['tool_calls']:
                    actions[call['id']] = call
                    if call['function']['name'] == 'report_progress':
                        continue
                    summary = tool_activity(call, results.get(call['id']))
                    lines.extend('  ' + text for text in display_lines(summary, width - 2))
            elif message['role'] == 'tool':
                call = actions.get(message.get('tool_call_id'), {})
                if call.get('function', {}).get('name') == 'report_progress':
                    lines.extend('  ' + text for text in display_lines(readable_markdown(content), width - 2))
                elif self.show_details:
                    lines.extend(['↳ Ferramenta'] + display_lines(content, width) + [''])
            elif message['role'] == 'assistant':
                if working:
                    lines.append('')
                    working = False
                lines.extend(['◆ Centaur'] + display_lines(readable_markdown(content), width) + [''])
        if self.busy and not self.approval:
            lines.extend(['◦ ' + self.view.activity(self, self.notice)])
        if self.chat.get('last_error'):
            lines.extend(['', '! Erro no turno'] + display_lines(self.chat['last_error'], width)
                         + display_lines('/retry retoma sem reenviar a mensagem; /new começa outra conversa.', width))
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
            if key == '\x03' and self.busy:
                self.cancel_work()
                return
            if self.busy or (self.settings and self.settings.pending):
                self.notice = 'Aguarde o turno ou configuração terminar para sair; recuse ações pendentes com n.'
                return
            return 'quit'
        if self.question:
            result = self.question.handle(key, getattr(self.client, 'secrets', ()))
            if result is not None:
                self.question.answer.put(result)
                self.question = None
                self.scroll = self.saved_scroll
                self.notice = 'Resposta enviada. Aguardando a IA…' if result['status'] == 'answered' else 'Pergunta pulada. Aguardando a IA…'
            return
        if self.approval:
            if key in ('y', 'Y', 'n', 'N'):
                self.approval[1].put(key.lower() == 'y')
                self.approval = None
                self.scroll = self.saved_scroll
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
                    # Historical metadata never grants permission to the current session.
                    self.chat['approval_mode'] = self.approval_mode
                    self.browser = False
                    self.draft = ''
                    self.scroll = 0
            return
        if key == curses.KEY_F5:
            if not self.chat['messages'] and not self.busy and not self.draft:
                self.view.animation.replay()
            return
        if key == '\x0f':
            self.show_details = not self.show_details
            self.notice = 'Detalhes das ferramentas abertos.' if self.show_details else 'Resumo do trabalho.'
            return
        if key == curses.KEY_MOUSE:
            try:
                _, _, _, _, state = curses.getmouse()
            except curses.error:
                return
            if state & getattr(curses, 'BUTTON4_PRESSED', 0):
                self.scroll_chat(3)
            elif state & getattr(curses, 'BUTTON5_PRESSED', 0):
                self.scroll_chat(-3)
            return
        if isinstance(key, PastedText):
            self.insert_text(key.text)
            return
        if key in (KEY_NEWLINE, '\n'):
            self.insert_text('\n')
            self.completion.update('')
            return
        self.completion.update(self.draft if self.cursor == len(self.draft) and self.prompt_history is None else '')
        if self.completion.visible:
            if key == curses.KEY_UP:
                self.completion.selected = max(0, self.completion.selected - 1)
                return
            if key == curses.KEY_DOWN:
                self.completion.selected = min(len(self.completion.options) - 1, self.completion.selected + 1)
                return
            if key in ('\t', '\n', '\r', curses.KEY_ENTER):
                execute = key != '\t' and self.completion.local_command(self.draft)
                self.draft = self.completion.choose(self.draft)
                self.completion.update(self.draft)
                if execute:
                    return self.submit()
                return
            if key == '\x1b':
                self.completion.dismiss(self.draft)
                return
        if key not in (curses.KEY_UP, curses.KEY_DOWN):
            self.preferred_input_column = None
        if key == curses.KEY_LEFT:
            self.cursor = max(0, self.cursor - 1)
        elif key == curses.KEY_RIGHT:
            self.cursor = min(len(self.draft), self.cursor + 1)
        elif key == curses.KEY_HOME:
            self.cursor = 0
        elif key == curses.KEY_END:
            self.cursor = len(self.draft)
        elif key in (curses.KEY_UP, curses.KEY_DOWN):
            layout = layout_input(self.draft, self.input_width)
            direction = -1 if key == curses.KEY_UP else 1
            if (self.prompt_history is not None or len(layout.lines) == 1) and self.recall_prompt(direction):
                return
            elif len(layout.lines) > 1:
                self.cursor, self.preferred_input_column = layout.vertical(self.cursor, direction, self.preferred_input_column)
            else:
                self.scroll_chat(-direction)
        elif key in (curses.KEY_PPAGE, curses.KEY_NPAGE):
            self.scroll_chat(5 if key == curses.KEY_PPAGE else -5)
        elif key == '\x05':
            self.scroll = 0
        elif key in ('\r', curses.KEY_ENTER):
            return self.submit()
        elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
            self.prompt_history = self.prompt_index = None
            if self.cursor:
                self._draft = self.draft[:self.cursor - 1] + self.draft[self.cursor:]
                self.cursor -= 1
        elif key == curses.KEY_DC:
            self.prompt_history = self.prompt_index = None
            self._draft = self.draft[:self.cursor] + self.draft[self.cursor + 1:]
        elif key == '\x15':
            self.draft = ''
        elif isinstance(key, str) and key.isprintable():
            self.insert_text(key)

    def run(self, screen):
        with keyboard_protocol():
            return self.run_screen(screen)

    def run_screen(self, screen):
        self.request_context_catalog()
        curses.raw()
        curses.nonl()  # Enter is CR; Ctrl+J is LF and inserts a line in the chat.
        self.view.palette.initialize()
        screen.keypad(True)
        try:
            curses.mousemask(getattr(curses, 'BUTTON4_PRESSED', 0) | getattr(curses, 'BUTTON5_PRESSED', 0))
        except curses.error:
            pass
        screen.timeout(100)
        keyboard = KeyboardReader()
        while True:
            frame_start = time.monotonic()
            self.drain_events()
            self.request_credits()
            try:
                curses.curs_set(0 if self.approval or (self.question and not self.question.custom) or (self.browser and not self.rename_target)
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
                key = keyboard.read(screen, timeout)
            except curses.error:
                continue
            if key == curses.KEY_RESIZE:
                curses.update_lines_cols()
                screen.clearok(True)
                continue
            if key in ('\x0f', '\x05', curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE,
                       curses.KEY_NPAGE, curses.KEY_MOUSE):
                # Navigation/disclosure can move many rows. Repaint rather than relying
                # on terminal-specific scroll-region optimizations.
                screen.clearok(True)
            if self.handle(key) == 'quit':
                return
