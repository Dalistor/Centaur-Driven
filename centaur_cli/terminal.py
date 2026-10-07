"""Interface curses e navegação entre conversas."""

import copy
import curses
import shlex
import queue
import re
import textwrap
import threading
import time

from .attachments import prepare_file, capture_screen, check_support, persist, summary_attachments, load_copy, prepare_bytes, MAX_PENDING
from .backends import create_client
from .config import save_config, validate
from .settings import ConfigPicker
from .openrouter import OpenRouter
from .agent import run_turn, project_prompt
from .tools import TOOLS
from .context import compact_chat, context_label, estimate_tokens, save_compaction, save_compaction_progress, CompactionPaused
from .speed import validate_speed, fast_supported
from .native_usage import BalanceUnavailable
from .completion import SkillCompletion
from .conversation import TranscriptLine, generate_title, readable_markdown, tool_activity
from .tools import ProjectTools
from .appearance import TerminalView, fit_cells, cell_width
from .graphics import FRAME_SECONDS
from .subagents import SubagentTools
from .sessions import SessionRegistry, LABELS
from .agent_tree import AgentTree
from .status import ANALYSIS_INSTRUCTIONS, StatusTools, render_status
from .permissions import validate_mode, MODE_LABELS
from .interaction import QuestionPicker, TurnCancelled
from .computer import ComputerSession
from .computer_access import ComputerControl
from .composer import layout_input, attachment_span, atomic_cursor, replace_input, without_attachment_markers
from .clipboard import clipboard_content, pasted_paths
from .keyboard import KEY_NEWLINE, PastedText, KeyboardReader, keyboard_protocol, read_key


def display_lines(text, width):
    clean = ''.join(character if character.isprintable() or character == '\n' else ' '
                    for character in str(text))
    lines = []
    width = max(1, width)
    for paragraph in clean.split('\n'):
        for line in textwrap.wrap(paragraph, width) or ['']:
            while cell_width(line) > width:
                part = fit_cells(line, width)
                if not part:  # A wide glyph cannot fit a one-cell viewport.
                    lines.append('�')
                    line = line[1:]
                else:
                    lines.append(part)
                    line = line[len(part):]
            if line or not lines or not paragraph:
                lines.append(line)
    return lines



class SessionEvents:
    """Tag worker output with its originating chat, including late replies."""
    def __init__(self, events, chat_id):
        self.events, self.chat_id = events, chat_id

    def put(self, event):
        self.events.put(('session', (self.chat_id, *event)))


class Terminal:
    SESSION_DEFAULTS = {'busy': False, 'approval': None, 'question': None,
                        'computer': None, 'busy_started': None, 'saved_scroll': 0,
                        'notice': ''}

    def session_value(name):
        def get(self):
            state = self.session_states.setdefault(self.chat['id'], {})
            if name == 'cancel_event':
                return state.setdefault(name, threading.Event())
            return state.get(name, self.SESSION_DEFAULTS[name])
        def set(self, value):
            self.session_states.setdefault(self.chat['id'], {})[name] = value
        return property(get, set)

    busy = session_value('busy')
    approval = session_value('approval')
    question = session_value('question')
    computer = session_value('computer')
    busy_started = session_value('busy_started')
    saved_scroll = session_value('saved_scroll')
    notice = session_value('notice')
    cancel_event = session_value('cancel_event')
    del session_value

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
        self.session_states = {}
        self.session_contexts = {}
        self.live_chats = {}
        self.registry = SessionRegistry(root)
        self.computer_control = ComputerControl(root, self.chat["id"])
        self.browser_mode = 'chats'
        self.agent_preview = None
        self.active_agents = []
        self.agent_tree = AgentTree([self.chat])
        self.agent_ancestors = []
        self.agent_parent_ids = set()
        self.agents_refreshed = 0
        self.agent_panel_scroll = 0
        self.agent_panel_hits = []
        self.agent_panel_area = None
        self.input_hitbox = None
        self.browser_refreshed = 0
        self.next_cleanup = 0
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
        self.pending_by_chat = {}
        self.drafts_by_chat = {}
        self.attachment_sequence = 0
        self.preparation_context = {}
        self.preparing_attachment = None
        self.attachment_cancel = threading.Event()
        self.draft = ''
        self.input_width = 74
        self.prompt_history = None
        self.prompt_index = None
        self.prompt_current = ('', 0)
        self.completion = SkillCompletion(root)
        self.notice = 'Digite sua intenção · Ctrl+V cola imagem · arraste um arquivo · $config.'
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
        if self.browser and self.agent_preview:
            label, style = context_label(self.agent_preview, self.client, width, '', 0)
            return label.replace('Contexto ', 'Agente ', 1).replace('Ctx[', 'Ag[', 1), style
        draft = {'text': self.draft, 'attachments': summary_attachments(self.pending_attachments)} if self.pending_attachments else self.draft
        return context_label(self.chat, self.client, width, draft, self.context_overhead)

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
        self.registry.set(self.chat['id'], 'waiting_input')
        self.events.put(('approval', (description, answer)))
        try:
            return self.wait_answer(answer)
        finally:
            self.registry.set(self.chat['id'], 'running')

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
        self.registry.set(self.chat['id'], 'waiting_input')
        self.events.put(('question', QuestionPicker(question, options, answer)))
        try:
            return self.wait_answer(answer)
        finally:
            self.registry.set(self.chat['id'], 'running')

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
        key = ((self.agent_preview or self.chat)['id'], width, self.show_details)
        # Preserve the top visible row when new content arrives during manual reading.
        if self.viewport_key == key and self.scroll and count > self.viewport_lines:
            self.scroll += count - self.viewport_lines
        self.viewport_key, self.viewport_lines = key, count
        self.scroll_limit = max(0, count - available)
        self.scroll = min(self.scroll_limit, max(0, self.scroll))
        return max(0, count - available - self.scroll)

    def scroll_chat(self, delta):
        self.scroll = min(self.scroll_limit, max(0, self.scroll + delta))

    @property
    def pending_attachments(self):
        return self.pending_by_chat.setdefault(self.chat['id'], [])

    def add_attachment(self, item, chat_id=None):
        chat_id = chat_id or self.chat['id']
        pending = self.pending_by_chat.setdefault(chat_id, [])
        self.attachment_sequence += 1
        item = dict(item)
        text = self.draft if chat_id == self.chat['id'] else self.drafts_by_chat.get(chat_id, ('', 0))[0]
        while True:
            item['marker'] = f'[{"Imagem" if item["kind"] == "image" else "Arquivo"} #{self.attachment_sequence}]'
            if item['marker'] not in text:
                break
            self.attachment_sequence += 1
        if chat_id == self.chat['id']:
            self.insert_text(item['marker'])
            item['span'] = [self.cursor - len(item['marker']), self.cursor]
            pending.append(item)
        else:
            text, cursor = self.drafts_by_chat.get(chat_id, ('', 0))
            text, cursor = replace_input(text, pending, cursor, cursor, item['marker'])
            item['span'] = [cursor - len(item['marker']), cursor]
            pending.append(item)
            self.drafts_by_chat[chat_id] = (text, cursor)

    def remove_attachment(self, item):
        span = attachment_span(item, self.draft)
        if span:
            self.replace_draft(*span, '')
        elif item in self.pending_attachments:
            self.pending_attachments.remove(item)

    def begin_attachment_read(self, prepare, label, *, command='', replace_range=None, snapshot=None):
        if self.preparing_attachment:
            self.notice = 'Preparando a colagem anterior · Ctrl+C cancela.'
            return
        try:
            if len(self.pending_attachments) >= MAX_PENDING:
                raise ValueError('Até oito anexos por mensagem; apague um marcador ou use $detach.')
            self.store.save(self.chat)
        except (ValueError, OSError) as error:
            self.notice = 'Erro ao preparar anexo: ' + str(error)
            return
        token, chat_id = object(), self.chat['id']
        cancellation = self.attachment_cancel = threading.Event()
        self.preparing_attachment = token
        self._preparing_chat_id = chat_id
        self.attachment_command = command
        self.preparation_context = {'snapshot': snapshot, 'replace_range': replace_range}
        self.notice = label + ' · Ctrl+C cancela.'
        def work():
            try:
                result = prepare(cancellation)
                if not cancellation.is_set():
                    self.events.put(('attachment_ready', (token, chat_id, result, None)))
            except Exception as error:
                if not cancellation.is_set():
                    self.events.put(('attachment_ready', (token, chat_id, None,
                        getattr(client, 'redact', str)(str(error)))))
        client = self.client
        threading.Thread(target=work, daemon=True).start()

    def prepare_attachment(self, command):
        client, model = self.client, self.chat['model']
        try:
            parts = shlex.split(command)
            name = parts[0].lstrip('$/')
            if name == 'attach':
                if len(parts) != 2:
                    raise ValueError('Uso: $attach "caminho"; você também pode colar/arrastar o arquivo no campo.')
                prepare = lambda cancellation: {'items': [prepare_file(self.root, parts[1], client, model)]}
                label = 'Preparando anexo'
            else:
                if len(parts) > 2 or len(parts) == 2 and not parts[1].isdigit():
                    raise ValueError('Uso: $screenshot [segundos de espera, 0–10]. Captura única do monitor principal.')
                delay = int(parts[1]) if len(parts) == 2 else 0
                if not 0 <= delay <= 10:
                    raise ValueError('Espera deve ser de 0 a 10 segundos.')
                def prepare(cancellation):
                    if cancellation.wait(delay):
                        return None
                    return {'items': [capture_screen(client, model)]}
                label = f'Capturando em {delay}s'
        except ValueError as error:
            self.notice = 'Erro: ' + str(error)
            return
        self.draft = ''
        self.begin_attachment_read(prepare, label, command=command)
        if not self.preparing_attachment:
            self.draft = command

    def paste_text(self, text):
        text = self.clean_pasted_text(text)
        paths = pasted_paths(self.root, text)
        start = self.cursor
        self.insert_text(text)
        if paths and not self.busy:
            self.prepare_paths(paths, replace_range=(start, self.cursor), snapshot=(self.draft, self.cursor))

    def prepare_paths(self, paths, *, replace_range=None, snapshot=None):
        if len(paths) + len(self.pending_attachments) > MAX_PENDING:
            self.notice = 'Erro: até oito anexos por mensagem; caminhos preservados.'
            return
        client, model = self.client, self.chat['model']
        self.begin_attachment_read(lambda cancellation: {'items': [prepare_file(self.root, path, client, model) for path in paths]},
                                   'Preparando arquivos colados', replace_range=replace_range, snapshot=snapshot)

    def paste_clipboard(self):
        if self.busy:
            self.notice = 'Aguarde o turno terminar para colar anexos.'
            return
        client, model = self.client, self.chat['model']
        root = self.root
        def prepare(cancellation):
            kind, value = clipboard_content(cancellation=cancellation)
            if kind == 'image':
                return {'items': [prepare_bytes('clipboard.png', value, client, model)]}
            paths = pasted_paths(root, value)
            if paths:
                if len(paths) > MAX_PENDING:
                    raise ValueError('Até oito anexos por mensagem; colagem não aplicada.')
                return {'items': [prepare_file(root, path, client, model) for path in paths]}
            return {'text': value}
        self.begin_attachment_read(prepare, 'Lendo clipboard', snapshot=(self.draft, self.cursor))

    def computer_command(self, command):
        parts = command.split()
        action = parts[1] if len(parts) == 2 else 'status' if len(parts) == 1 else ''
        chat_id = self.chat['id']
        if action == 'revoke':
            if self.busy:
                self.cancel_work()
            self.computer_control.revoke(chat_id)
            self.notice = 'Computer use revogado neste chat · próxima utilização exige autorização.'
        elif action == 'pause':
            self.computer_control.pause(chat_id)
            self.notice = 'Computador pausado · $computer resume retoma sem nova autorização.'
        elif action == 'resume':
            self.computer_control.resume(chat_id)
            self.notice = 'Computer use disponível · o agente retoma durante a tarefa.'
        elif action == 'status':
            granted = self.computer_control.permissions.granted(chat_id)
            state = 'em uso' if self.computer and self.computer.active else 'pausado' if chat_id in self.computer_control.paused else 'parado'
            self.notice = f'Computador {state} · autorização ' + ('deste chat ativa' if granted else 'não concedida') + ' · $computer pause/resume/revoke'
        else:
            self.notice = 'Uso: $computer [status|pause|resume|revoke] · Ctrl+G revoga imediatamente.'
            return
        self.draft = ''

    def submit(self):
        command = without_attachment_markers(self.draft, self.pending_attachments).strip()
        if command.split(maxsplit=1)[0:1] in (['$computer'], ['/computer']):
            return self.computer_command(command)
        if self.busy or self.preparing_attachment or not (self.draft.strip() or self.pending_attachments):
            return
        command = without_attachment_markers(self.draft, self.pending_attachments).strip()
        if command == '/quit':
            if any(state.get('busy') for state in self.session_states.values()):
                self.notice = 'Aguarde as sessões terminarem ou interrompa cada uma com Ctrl+C para sair.'
                return
            return 'quit'
        if command == '/new':
            self.switch_chat(self.new_chat())
            self.draft = ''
            self.scroll = 0
            return
        if command in ('/credits', '$credits'):
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
        command = without_attachment_markers(self.draft, self.pending_attachments).strip()
        local_name = command.split(maxsplit=1)[0] if command else ''
        if local_name in ('$attach', '/attach', '$screenshot', '/screenshot'):
            return self.prepare_attachment(command)
        if local_name in ('$attachments', '/attachments'):
            self.draft = ''
            self.scroll = 0
            self.notice = 'Anexos pendentes no fim da conversa · $detach <número|all> remove.' if self.pending_attachments else 'Nenhum anexo pendente.'
            return
        if local_name in ('$detach', '/detach'):
            parts = command.split()
            if len(parts) == 2 and parts[1] == 'all':
                for item in list(self.pending_attachments):
                    self.remove_attachment(item)
            elif len(parts) == 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= len(self.pending_attachments):
                self.remove_attachment(self.pending_attachments[int(parts[1]) - 1])
            else:
                self.notice = 'Erro: use $detach <número|all>; $attachments lista os anexos.'
                return
            self.draft = ''
            self.notice = 'Anexo removido; Enter envia os restantes com sua mensagem.'
            return
        if command in ('/agents', '$agents'):
            self.draft = ''
            self.open_chats('agents')
            return
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
            self.registry.set(self.chat['id'], 'running')
            self.notice = 'Compactando contexto com IA · histórico completo preservado · Ctrl+C interrompe.'
            worker = self.worker_context()
            threading.Thread(target=worker.compact, args=(worker.chat, worker.client, worker.cancel_event), daemon=True).start()
            return
        if command == '/retry':
            self.draft = ''
            if not self.chat.get('last_error') and not self.chat.get('turn_paused'):
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
        if local_name == '$config' and '\n' not in command:
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
        if command.startswith(("'", '"', '/', './', '../', '~/', 'file:')):
            paths = pasted_paths(self.root, command)
            if paths:
                self.prepare_paths(paths, replace_range=(0, len(self.draft)), snapshot=(self.draft, self.cursor))
                return
        try:
            check_support(self.client, self.chat['model'], self.pending_attachments)
            attachments = persist(self.root, self.chat['id'], self.pending_attachments) if self.pending_attachments else []
            candidate = copy.deepcopy(self.chat)
            message = {'role': 'user', 'content': self.draft or 'Analise os anexos desta mensagem.'}
            if attachments:
                message['attachments'] = attachments
            candidate['messages'].append(message)
            candidate.pop('last_error', None)
            candidate['approval_mode'] = self.approval_mode
            if candidate['title'] == 'Novo chat' and not candidate.get('title_custom'):
                candidate['title'] = ' '.join(self.draft.split())[:80] or attachments[0]['name']
            self.store.save(candidate)
        except (ValueError, RuntimeError, OSError) as error:
            self.notice = 'Erro: ' + getattr(self.client, 'redact', str)(str(error))
            return
        self.chat.clear()
        self.chat.update(candidate)
        self.pending_attachments.clear()
        self.draft = ''
        self.start_work()

    def start_work(self):
        self.chat.pop('turn_paused', None)
        self.chat['approval_mode'] = self.approval_mode
        self.store.save(self.chat)
        self.scroll = 0
        self.viewport_key = None
        self.cancel_event = threading.Event()
        self.busy = True
        self.registry.set(self.chat['id'], 'running')
        self.busy_started = time.monotonic()
        self.notice = f'Aguardando {self.backend}…'
        worker = self.worker_context()
        threading.Thread(target=worker.work, args=(worker.chat,), daemon=True).start()

    def worker_context(self):
        # The worker keeps its chat, client and permissions even when the UI changes.
        worker = copy.copy(self)
        worker.events = SessionEvents(self.events, self.chat['id'])
        self.live_chats[self.chat['id']] = self.chat
        self.session_contexts[self.chat['id']] = worker
        return worker

    def switch_chat(self, chat):
        if chat["id"] != self.chat["id"] and self.computer and not hasattr(self.computer, 'suspend'):
            self.computer.close()
        self.chat = self.live_chats.get(chat['id'], chat)
        self.computer_control.focus(self.chat['id'])
        context = self.session_contexts.get(chat['id'])
        if context:
            for name in ('client', 'backend', 'model', 'effort', 'speed', 'approval_mode'):
                setattr(self, name, getattr(context, name))
        if not context:
            self.chat['approval_mode'] = self.approval_mode
        self.draft = ''  # The setter saves/restores each chat's unsent input.
        self.scroll = 0
        self.viewport_key = None
        self.completion.update('')
        self.browser = False
        self.agent_preview = None

    def create_chat_from_menu(self):
        if self.chat.get('messages') or self.draft or self.pending_attachments:
            # Running workers already saved their messages; do not race their writes.
            if not self.busy:
                self.store.save(self.chat)
        chat = self.new_chat()
        self.store.save(chat)
        self.switch_chat(chat)
        self.notice = 'Novo chat · outras sessões continuam trabalhando.'

    def compact(self, chat, client, cancel_event):
        try:
            state, before, after = compact_chat(chat, client, cancel_event,
                progress=lambda notice: self.events.put(('progress', notice)),
                checkpoint=lambda pending: save_compaction_progress(chat, self.store, pending, cancel_event))
            self.events.put(('compacted', (chat, cancel_event, state, before, after)))
        except Exception as error:
            message = getattr(client, 'redact', str)(str(error))
            if isinstance(error, (TurnCancelled, CompactionPaused)):
                self.events.put(('done', message))
            else:
                self.events.put(('compaction_failed', (chat, message)))

    @property
    def draft(self):
        return self._draft

    @draft.setter
    def draft(self, value):
        old_id = getattr(self, '_draft_chat_id', None)
        current_id = self.chat['id']
        if old_id and old_id != current_id:
            self.drafts_by_chat[old_id] = (self._draft, self.cursor)
            value, cursor = self.drafts_by_chat.get(current_id, (value, len(value)))
        else:
            if not value:
                value = ''.join(item.get('marker', '') for item in self.pending_attachments)
            cursor = len(value)
        self._draft, self.cursor, self._draft_chat_id = value, cursor, current_id
        for item in self.pending_attachments:
            marker = item.get('marker')
            index = value.find(marker) if marker else -1
            item['span'] = [index, index + len(marker)] if index >= 0 else None
        self.preferred_input_column = None
        self.prompt_history = None
        self.prompt_index = None

    def replace_draft(self, start, end, text):
        self.prompt_history = self.prompt_index = None
        self._draft, self.cursor = replace_input(self.draft, self.pending_attachments, start, end, text)
        self.preferred_input_column = None

    @staticmethod
    def clean_pasted_text(text):
        text = str(text).replace('\r\n', '\n').replace('\r', '\n').replace('\t', '    ')
        return ''.join(c for c in text if c.isprintable() or c == '\n')

    def insert_text(self, text):
        self.replace_draft(self.cursor, self.cursor, text)

    def recall_prompt(self, direction):
        if self.preparing_attachment:
            return True
        if self.prompt_history is None:
            if direction > 0: return False
            self.prompt_history = [m for m in self.chat['messages']
                                   if m.get('role') == 'user' and isinstance(m.get('content'), str)]
            if not self.prompt_history:
                self.prompt_history = None
                return False
            self.prompt_current = (self.draft, self.cursor, copy.deepcopy(self.pending_attachments))
            self.prompt_index = len(self.prompt_history)
        index = max(0, min(len(self.prompt_history), self.prompt_index + direction))
        if index == len(self.prompt_history):
            self._draft, self.cursor, pending = self.prompt_current
            self.pending_by_chat[self.chat['id']] = pending
            self.prompt_history = None
            self.prompt_index = None
        else:
            message = self.prompt_history[index]
            try:
                pending = [dict(item, data=load_copy(self.root, self.chat['id'], item)) for item in message.get('attachments', [])]
            except (ValueError, OSError) as error:
                self.notice = 'Erro ao recuperar anexos: ' + str(error)
                return True
            self._draft = message['content']
            self.cursor = len(self._draft)
            self.pending_by_chat[self.chat['id']] = pending
            for item in pending:
                marker = item.get('marker')
                start = self._draft.find(marker) if marker else -1
                item['span'] = [start, start + len(marker)] if start >= 0 else None
                match = re.fullmatch(r'\[(?:Imagem|Arquivo) #(\d{1,6})\]', marker or '')
                if match:
                    self.attachment_sequence = max(self.attachment_sequence, int(match.group(1)))
        self.prompt_index = index if self.prompt_history is not None else None
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
            self.switch_chat(self.new_chat())
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
        if self.session_state(chat) != 'stopped':
            self.notice = 'Aguarde o turno terminar para renomear o chat em execução.'
            return
        self.rename_target = chat
        self.rename_text = chat['title']
        self.rename_cursor = len(self.rename_text)
        self.notice = 'Renomear chat · 1 a 80 caracteres · Enter salvar · Esc cancelar.'

    def rename_chat(self, chat, title):
        if self.session_state(chat) != 'stopped':
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
        live = self.live_chats.get(chat['id'])
        if live is not None:
            live.clear()
            live.update(renamed)
        if chat['id'] == self.chat['id']:
            self.chat = live if live is not None else renamed
        self.refresh_browser()
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

    def computer_progress(self, notice):
        self.registry.set(self.chat['id'], 'waiting_input' if notice.startswith('Computador pausado') else 'running')
        self.events.put(('progress', notice))

    def work(self, chat):
        completion_notice = 'Turno encerrado.'
        computer = ComputerSession(self.approve, self.cancel_event, control=self.computer_control,
                                   chat_id=chat['id'], emit=self.computer_progress)
        self.computer = computer
        try:
            base = ProjectTools(self.root, self.approve,
                                protected_keys=getattr(self.client, 'secrets', (getattr(self.client, 'api_key', None),)),
                                approval_mode=self.approval_mode, ask_user=self.ask_user,
                                cancel_event=self.cancel_event, computer=computer)
            base.activity = lambda phase: self.registry.activity(chat['id'], phase)
            base.native_progress = lambda event: self.registry.native_event(chat['id'], event)
            last_request = next((message.get('content') or '' for message in reversed(chat['messages'])
                                 if message['role'] == 'user'), '')
            status_analysis = last_request.strip() in ('/status --ai', '$status --ai')
            if status_analysis:
                tools = StatusTools(self.root, lambda _: False,
                                    protected_keys=getattr(self.client, 'secrets', ()))
                tools.cancel_event = self.cancel_event
            else:
                tools = SubagentTools(base, self.client, chat['id'],
                                      lambda notice: self.events.put(('progress', notice)), self.max_subagent_tier,
                                      registry=self.registry, effort=chat.get('effort', 'default'), speed=chat.get('speed', 'standard'))
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
            completion_notice = 'Pronto.'
        except CompactionPaused as error:
            chat['turn_paused'] = str(error)
            notice = str(error)
            try:
                self.store.save(chat)
            except OSError:
                notice += ' Não foi possível salvar a pausa; confira o armazenamento antes de fechar a sessão.'
            completion_notice = notice
        except TurnCancelled as error:
            chat['last_error'] = str(error)
            try:
                self.store.save(chat)
            except OSError:
                pass
            completion_notice = 'Turno interrompido. /retry retoma; confira ações já aplicadas.'
        except Exception as error:
            message = getattr(self.client, 'redact', str)(str(error))
            chat['last_error'] = message
            try:
                self.store.save(chat)
            except OSError:
                pass
            completion_notice = f'Erro: {message} · /retry retoma este turno.'
        finally:
            self.registry.set(chat['id'], 'stopped')
            computer.close()
            if self.computer is computer:
                self.computer = None
            self.events.put(('done', completion_notice))

    def make_title(self, chat_id, client, model, messages):
        try:
            title = generate_title(client, model, messages)
        except Exception:
            title = None  # Title failure must not interrupt a successful conversation.
        self.events.put(('title', (chat_id, title)))

    def apply_titles(self):
        for chat_id, title in list(self.pending_titles.items()):
            if self.session_states.get(chat_id, {}).get('busy'):
                continue
            del self.pending_titles[chat_id]
            self.title_tasks.discard(chat_id)
            if not title:
                continue
            try:
                renamed = self.store.generated_title(chat_id, title)
                if renamed:
                    target = self.live_chats.get(chat_id)
                    if target is not None:
                        target.update(title=renamed['title'], title_generated=True)
                    if self.chat['id'] == chat_id:
                        self.chat.update(title=renamed['title'], title_generated=True)
                if self.browser:
                    self.refresh_browser()
            except (OSError, ValueError):
                pass  # Deleted/renamed chats are not recreated by late title requests.

    def drain_events(self, *, apply_titles=True):
        while not self.events.empty():
            kind, value = self.events.get_nowait()
            if kind == 'session':
                chat_id, kind, value = value
                if chat_id != self.chat['id']:
                    context = self.session_contexts.get(chat_id)
                    if context:
                        receiver = copy.copy(context)
                        receiver.events = queue.Queue()
                        receiver.events.put((kind, value))
                        receiver.browser = False
                        receiver.drain_events(apply_titles=False)
                    continue
            if kind == 'backend_credits':
                source, event = value
                if source is not self.client:
                    continue
                kind, value = event
            if kind == 'attachment_ready':
                token, chat_id, result, error = value
                if token is not self.preparing_attachment:
                    continue
                self.preparing_attachment = None
                context = self.preparation_context
                if error:
                    if chat_id == self.chat['id']:
                        if not self.draft:
                            self.draft = self.attachment_command
                        self.notice = 'Erro: ' + error
                    continue
                if not result:
                    continue
                # Accept the old single-item event shape for internal integrations.
                if 'kind' in result:
                    result = {'items': [result]}
                snapshot = context.get('snapshot')
                replacement = context.get('replace_range')
                origin = (self.draft, self.cursor) if chat_id == self.chat['id'] else self.drafts_by_chat.get(chat_id, ('', 0))
                if (replacement or 'text' in result) and snapshot and origin != snapshot:
                    if chat_id == self.chat['id']:
                        self.notice = 'Colagem alterada durante a leitura; rascunho preservado. Cole novamente.'
                    continue
                items = result.get('items', [])
                if len(items) + len(self.pending_by_chat.setdefault(chat_id, [])) > MAX_PENDING:
                    if chat_id == self.chat['id']:
                        self.notice = 'Erro: até oito anexos; colagem não aplicada.'
                    continue
                if replacement:
                    if chat_id == self.chat['id']:
                        self.replace_draft(*replacement, '')
                    else:
                        text, cursor = replace_input(origin[0], self.pending_by_chat[chat_id], *replacement, '')
                        self.drafts_by_chat[chat_id] = (text, cursor)
                for item in items:
                    self.add_attachment(item, chat_id)
                if 'text' in result:
                    result['text'] = self.clean_pasted_text(result['text'])
                    if chat_id == self.chat['id']:
                        self.insert_text(result['text'])
                    else:
                        text, cursor = origin
                        text, cursor = replace_input(text, self.pending_by_chat[chat_id], cursor, cursor, result['text'])
                        self.drafts_by_chat[chat_id] = (text, cursor)
                if chat_id == self.chat['id']:
                    self.scroll = 0
                    self.notice = ('Anexo inserido na mensagem · Backspace/Delete remove · Enter envia.' if items
                                   else 'Texto colado; Enter envia.' if result.get('text') else 'Clipboard sem imagem ou texto.')
            elif kind == 'catalog':
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
                self.rename_target = None
                self.saved_scroll, self.scroll = self.scroll, 0
            elif kind == 'question':
                if self.cancel_event.is_set():
                    continue
                self.question = value
                self.rename_target = None
                self.saved_scroll = self.scroll
            elif kind == 'done':
                self.registry.set(self.chat['id'], 'stopped')
                self.busy = False
                self.approval = None
                self.question = None
                self.notice = value
                self.credits_dirty = True
            elif kind == 'compaction_failed':
                chat, message = value
                chat['compaction_error'] = message
                try:
                    self.store.save(chat)
                except OSError:
                    pass
                self.registry.set(chat['id'], 'stopped')
                self.busy = False
                self.notice = 'Erro na compactação · detalhes na conversa · $compact retoma.'
                self.credits_dirty = True
            elif kind == 'compacted':
                self.registry.set(self.chat['id'], 'stopped')
                chat, cancellation, state, before, after = value
                self.busy = False
                self.credits_dirty = True
                if cancellation.is_set():
                    self.notice = 'Compactação interrompida; contexto anterior preservado.'
                    continue
                try:
                    save_compaction(chat, self.store, state, cancellation)
                    self.notice = f'Contexto compactado: ~{before:,} → ~{after:,} tokens. Histórico preservado.'
                    if state.get('partial'):
                        self.notice += ' Restante integral no contexto; $compact pode reduzir mais.'
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
        if apply_titles:
            self.apply_titles()

    def lines(self, width, *, chat=None):
        if chat is None and self.approval and not self.agent_preview:
            return display_lines('CONFIRMAÇÃO — y: permitir / n: recusar\n\n' + self.approval[0], width)
        if chat is None and self.browser and not self.agent_preview:
            return [f'{">" if index == self.selected else " "} {chat["updated"][:16]}  {chat["title"]}'
                    for index, chat in enumerate(self.chats)] or ['Nenhum chat salvo nesta pasta.']
        lines, actions, working = [], {}, False
        def append_text(text, style='text', indent=''):
            lines.extend(TranscriptLine(indent + line, style)
                         for line in display_lines(text, max(1, width - len(indent))))
        current_chat = chat if chat is not None else self.agent_preview if self.browser and self.agent_preview else self.chat
        messages = list(current_chat['messages'])
        results = {m.get('tool_call_id'): m.get('content', '') for m in messages if m['role'] == 'tool'}
        for message in messages:
            content = message.get('content') or ''
            if message['role'] == 'user':
                working = False
                lines.append(TranscriptLine(''))
                append_text(content, 'user', '› ')
                for index, item in enumerate(message.get('attachments', []), 1):
                    append_text(f'  ▧ {index}. {item["name"]} · {item["kind"]} · {item["size"]:,} bytes', 'muted')
                lines.append(TranscriptLine(''))
            elif message['role'] == 'assistant' and message.get('tool_calls'):
                if not working:
                    lines.append(TranscriptLine('◦ Trabalho · Ctrl+O detalhes', 'muted'))
                    working = True
                if content:
                    append_text(readable_markdown(content), 'comment', '  ')
                for call_index, call in enumerate(message['tool_calls']):
                    actions[call['id']] = call
                    if call['function']['name'] == 'report_progress':
                        continue
                    summary = tool_activity(call, results.get(call['id']))
                    if call['function']['name'] == 'delegate_task':
                        siblings_after = any(other['function']['name'] == 'delegate_task'
                                             for other in message['tool_calls'][call_index + 1:])
                        summary = ('├─↳ ' if siblings_after else '└─↳ ') + summary
                    append_text(summary, 'warning' if summary.startswith(('!', '–')) else 'action', '  ')
            elif message['role'] == 'tool':
                call = actions.get(message.get('tool_call_id'), {})
                if call.get('function', {}).get('name') == 'report_progress':
                    append_text(readable_markdown(content), 'comment', '  ')
                elif self.show_details:
                    lines.append(TranscriptLine('↳ Ferramenta', 'action'))
                    append_text(content)
                    lines.append(TranscriptLine(''))
            elif message['role'] == 'assistant':
                if working:
                    lines.append(TranscriptLine(''))
                    working = False
                lines.append(TranscriptLine('◆ Centaur', 'green'))
                append_text(readable_markdown(content))
                lines.append(TranscriptLine(''))
        if chat is None and self.busy and not self.approval and not self.agent_preview:
            append_text('◦ ' + self.view.activity(self, self.notice), 'muted')
        if current_chat.get('last_error'):
            error = current_chat['last_error']
            legacy_pause = (error.startswith('Compactação automática falhou;')
                            and 'Compactação atingiu o limite de ' in error)
            if legacy_pause:
                lines.append(TranscriptLine('◦ Compactação anterior pausada por tempo', 'muted'))
                append_text('Progresso salvo; $compact continua e /retry retoma o turno.', 'muted')
            else:
                lines.extend([TranscriptLine(''), TranscriptLine('! Erro anterior' if self.busy else '! Erro no turno', 'warning')])
                append_text(error, 'warning')
            append_text('/retry retoma sem reenviar a mensagem; /new começa outra conversa.', 'muted')
        if current_chat.get('compaction_error'):
            lines.extend([TranscriptLine(''), TranscriptLine('! Erro anterior na compactação' if self.busy else '! Erro na compactação', 'warning')])
            append_text(current_chat['compaction_error'], 'warning')
            append_text('$compact retoma o progresso salvo; histórico preservado.', 'muted')
        if current_chat.get('turn_paused'):
            lines.append(TranscriptLine('◦ Pausa anterior do turno' if self.busy else '◦ Turno pausado', 'muted'))
            append_text(current_chat['turn_paused'], 'muted')
        if chat is None and self.pending_attachments and not self.agent_preview:
            lines.append(TranscriptLine('▧ Anexos pendentes · Enter envia · $detach <número|all> remove', 'blue'))
            for index, item in enumerate(self.pending_attachments, 1):
                if width < 45:
                    lines.append(TranscriptLine(f'{index}. {item["name"]}', 'muted'))
                else:
                    append_text(f'{index}. {item["name"]} · {item["kind"]} · {item["size"]:,} bytes', 'muted')
        return lines or ['Centaur experimental · OpenRouter', '', '/new cria chat · /quit sai']

    def draw(self, screen):
        self.view.draw(screen, self)

    def delete_selected_chat(self):
        if not self.chats:
            return
        selected_chat = self.chats[self.selected]
        is_current_chat = selected_chat['id'] == self.chat['id']
        if self.session_state(selected_chat) != 'stopped':
            self.notice = 'Aguarde o turno terminar para excluir o chat em execução.'
            return
        try:
            self.store.delete(selected_chat['id'])
        except (OSError, ValueError) as error:
            self.notice = f'Não foi possível excluir o chat: {error}'
            return
        if is_current_chat:
            self.chat = self.new_chat()
            self.computer_control.focus(None if self.browser else self.chat['id'])
            self.draft = ''
            self.scroll = 0
        self.refresh_browser()
        self.selected = min(self.selected, max(0, len(self.chats) - 1))
        if self.preparing_attachment and selected_chat['id'] == getattr(self, '_preparing_chat_id', None):
            self.attachment_cancel.set()
            self.preparing_attachment = None
        self.pending_by_chat.pop(selected_chat['id'], None)
        self.drafts_by_chat.pop(selected_chat['id'], None)
        self.live_chats.pop(selected_chat['id'], None)
        self.session_contexts.pop(selected_chat['id'], None)
        self.session_states.pop(selected_chat['id'], None)
        self.notice = 'Chat excluído.'

    def session_state(self, chat):
        state = self.session_states.get(chat['id'], {})
        if state.get('busy'):
            return 'waiting_input' if state.get('approval') or state.get('question') else self.registry.state(chat['id']) if self.registry.state(chat['id']) != 'stopped' else 'running'
        return self.registry.state(chat['id'])

    def housekeeping(self):
        self.computer_control.focus(None if self.browser or self.settings or self.rename_target or self.question or self.approval else self.chat['id'])
        self.registry.heartbeat()
        now = time.monotonic()
        if now >= self.next_cleanup:
            protected = set(self.title_tasks)
            protected.update(chat_id for chat_id, state in self.session_states.items() if state.get('busy'))
            protected.update(chat_id for chat_id, draft in self.drafts_by_chat.items() if draft[0])
            protected.update(chat_id for chat_id, pending in self.pending_by_chat.items() if pending)
            if self.preparing_attachment:
                protected.add(self._preparing_chat_id)
            if self.busy or self.preparing_attachment or self.draft or self.pending_attachments:
                protected.add(self.chat['id'])
            removed = self.store.prune(protected)
            for chat_id in removed:
                self.pending_by_chat.pop(chat_id, None)
                self.drafts_by_chat.pop(chat_id, None)
                self.live_chats.pop(chat_id, None)
                self.session_contexts.pop(chat_id, None)
                self.session_states.pop(chat_id, None)
            if self.chat['id'] in removed:
                self.chat = self.new_chat()
                self.computer_control.focus(None if self.browser else self.chat['id'])
                self.draft = ''
                self.notice = 'Chat com mais de 64h removido; nova conversa aberta.'
            self.next_cleanup = now + 60
        if now - self.agents_refreshed >= .5:
            self.refresh_agents()
        if self.browser and now - self.browser_refreshed >= .5:
            self.refresh_browser()

    def refresh_agents(self):
        self.active_agents = [agent for agent in self.store.agents(active_only=True) if self.session_state(agent) != 'stopped']
        parents = {agent['parent_id'] for agent in self.active_agents}
        if parents != self.agent_parent_ids:
            self.agent_ancestors = self.store.ancestors(self.active_agents)
            self.agent_parent_ids = parents
        self.agent_tree = AgentTree([*self.agent_ancestors, *self.chats, *self.live_chats.values(), self.chat, *self.active_agents])
        active = {agent['id'] for agent in self.active_agents}
        self.active_agents = [record for record in self.agent_tree.ordered() if record['id'] in active]
        self.agents_refreshed = time.monotonic()

    def handle_mouse(self):
        try:
            _, x, y, _, state = curses.getmouse()
        except curses.error:
            return
        area = self.agent_panel_area
        in_panel = area and area[0] <= x < area[0] + area[2] and area[1] <= y < area[1] + area[3]
        wheel_up, wheel_down = getattr(curses, 'BUTTON4_PRESSED', 0), getattr(curses, 'BUTTON5_PRESSED', 0)
        if state & (wheel_up | wheel_down):
            delta = 1 if state & wheel_down else -1
            if in_panel:
                self.agent_panel_scroll = max(0, self.agent_panel_scroll + delta)
            elif self.browser and not self.agent_preview:
                self.selected = min(max(0, len(self.chats) - 1), max(0, self.selected + delta))
            else:
                self.scroll_chat(-3 * delta)
            return
        clicked = (getattr(curses, 'BUTTON1_PRESSED', 0) | getattr(curses, 'BUTTON1_CLICKED', 0)
                   | getattr(curses, 'BUTTON1_DOUBLE_CLICKED', 0))
        if not state & clicked:
            return
        for left, top, width, height, agent in self.agent_panel_hits:
            if left <= x < left + width and top <= y < top + height:
                principal = self.agent_tree.principal(agent)
                parent = self.live_chats.get(principal['id'])
                pending = self.session_states.get(principal['id'], {})
                if parent and (pending.get('question') or pending.get('approval')):
                    self.switch_chat(parent)
                else:
                    self.open_chats('agents')
                    self.agent_preview = agent
                    self.scroll = 0
                return
        box = self.input_hitbox
        if (not box or box['chat_id'] != self.chat['id']
                or not box['left'] <= x < box['left'] + box['width']
                or not box['top'] <= y < box['top'] + box['rows']):
            return
        target = box['target']
        text = None
        if target == 'rename' and self.rename_target:
            text = self.rename_text
        elif target == 'question' and self.question and self.question.custom:
            text = self.question.text
        elif target == 'draft' and not (self.browser or self.settings or self.question or self.rename_target or self.approval):
            text = self.draft
        if text is None or text != box['text']:
            return  # A late click must never edit another draft or a replaced picker.
        cursor = box['start_index'] + box['layout'].at(y - box['top'] + box['start_row'], x - box['text_left'])
        if target == 'draft':
            for item in self.pending_attachments:
                span = attachment_span(item, self.draft)
                if span and span[0] < cursor < span[1]:
                    cursor = span[0] if cursor - span[0] <= span[1] - cursor else span[1]
            self.cursor = cursor
            self.prompt_history = self.prompt_index = None
            self.preferred_input_column = None
            self.completion.update('')
        elif target == 'rename':
            self.rename_cursor = cursor
        else:
            self.question.cursor = cursor

    def refresh_browser(self):
        selected_id = self.chats[self.selected]['id'] if self.chats and self.selected < len(self.chats) else None
        self.chats = self.store.list()
        if self.browser_mode == 'agents':
            self.agent_tree = AgentTree([*self.chats, *self.store.agents()])
            self.chats = self.agent_tree.ordered()
        self.selected = next((i for i, chat in enumerate(self.chats) if chat['id'] == selected_id), min(self.selected, max(0,len(self.chats)-1)))
        if self.agent_preview:
            self.agent_preview = next((chat for chat in self.chats if chat['id'] == self.agent_preview['id']), None)
        self.browser_refreshed = time.monotonic()

    def open_chats(self, mode='chats'):
        self.computer_control.focus(None)
        self.browser = True
        self.browser_mode = mode
        self.agent_preview = None
        self.selected = 0
        self.housekeeping()
        self.chats = []
        self.refresh_browser()

    def handle_browser(self, key):
        if key in ('n', 'N', '\x0e') and not self.agent_preview:
            self.create_chat_from_menu()
        elif key == '\t':
            self.browser_mode = 'agents' if self.browser_mode == 'chats' else 'chats'
            self.agent_preview = None
            self.selected = 0
            self.refresh_browser()
        elif key in ('\x1b', curses.KEY_RIGHT):
            if self.agent_preview:
                self.agent_preview = None
            else:
                self.browser = False
                self.computer_control.focus(self.chat['id'])
        elif key in (curses.KEY_UP, curses.KEY_DOWN) and not self.agent_preview:
            self.selected = min(max(0,len(self.chats)-1), max(0,self.selected + (-1 if key == curses.KEY_UP else 1)))
        elif key in (curses.KEY_PPAGE, curses.KEY_NPAGE) and self.agent_preview:
            self.scroll_chat(5 if key == curses.KEY_PPAGE else -5)
        elif self.agent_preview and key in ('\n', '\r', curses.KEY_ENTER):
            parent_id = self.agent_tree.principal(self.agent_preview)['id']
            parent = self.live_chats.get(parent_id) or next((chat for chat in self.store.list() if chat['id'] == parent_id), None)
            if parent and parent_id in self.session_contexts:
                self.switch_chat(parent)
            else:
                self.notice = 'Abra o chat coordenador no processo que executa o subagente para responder.'
        elif self.chats and self.chats[self.selected].get('parent_id'):
            if key in ('\n', '\r', curses.KEY_ENTER):
                self.agent_preview = self.chats[self.selected]
                self.scroll = 0
        elif key in ('r','R',curses.KEY_F2) and self.chats:
            self.begin_rename(self.chats[self.selected])
        elif key == curses.KEY_DC:
            self.delete_selected_chat()
        elif key in ('\n','\r',curses.KEY_ENTER) and self.chats:
            selected = self.chats[self.selected]
            owned = selected['id'] in self.session_contexts
            if not owned and selected.get('backend','openrouter') != self.backend:
                self.notice = 'Este chat usa outro backend; abra o Centaur com --backend ' + selected.get('backend','openrouter')
            elif not owned and self.backend != 'openrouter' and selected['model'] != self.model:
                self.notice = 'Este chat usa outro modelo; abra com o mesmo --model ou crie um chat novo.'
            elif not owned and self.session_state(selected) != 'stopped':
                self.notice = 'Esta sessão está ativa em outro processo; acompanhe seu estado pelo menu.'
            else:
                self.switch_chat(selected)

    def handle(self, key):
        if key == '\x07':
            return self.computer_command('$computer revoke')
        if key in ('\x11', '\x03'):
            if self.preparing_attachment:
                self.attachment_cancel.set()
                self.preparing_attachment = None
                self.notice = 'Preparação cancelada; nenhum novo anexo adicionado.'
                return
            if key == '\x03' and self.busy:
                self.cancel_work()
                return
            if any(state.get('busy') for state in self.session_states.values()) or (self.settings and self.settings.pending):
                self.notice = 'Aguarde o turno ou configuração terminar para sair; recuse ações pendentes com n.'
                return
            return 'quit'
        if key == curses.KEY_MOUSE:
            return self.handle_mouse()
        if key == curses.KEY_SLEFT and not self.settings and not self.rename_target:
            self.open_chats()
            return
        if self.browser and not self.rename_target:
            return self.handle_browser(key)
        if self.settings:
            return self.handle_settings(key)
        if self.rename_target:
            return self.handle_rename(key)
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
        if key == curses.KEY_F5:
            if not self.chat['messages'] and not self.busy and not self.draft:
                self.view.animation.replay()
            return
        if key == '\x0f':
            self.show_details = not self.show_details
            self.notice = 'Detalhes das ferramentas abertos.' if self.show_details else 'Resumo do trabalho.'
            return
        if key == '\x16':
            return self.paste_clipboard()
        if isinstance(key, PastedText):
            self.paste_text(key.text)
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
            self.cursor = atomic_cursor(self.draft, self.pending_attachments, max(0, self.cursor - 1), -1)
        elif key == curses.KEY_RIGHT:
            self.cursor = atomic_cursor(self.draft, self.pending_attachments, min(len(self.draft), self.cursor + 1))
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
                self.cursor = atomic_cursor(self.draft, self.pending_attachments, self.cursor, direction)
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
                self.replace_draft(self.cursor - 1, self.cursor, '')
            elif not self.draft and self.pending_attachments:
                self.remove_attachment(self.pending_attachments[-1])
        elif key == curses.KEY_DC:
            self.replace_draft(self.cursor, self.cursor + 1, '')
        elif key == '\x15':
            self.replace_draft(0, len(self.draft), '')
            self.pending_attachments.clear()
        elif isinstance(key, str) and key.isprintable():
            self.insert_text(key)

    def run(self, screen):
        try:
            return self._run(screen)
        finally:
            self.view.palette.restore()

    def _run(self, screen):
        with keyboard_protocol():
            return self.run_screen(screen)

    def run_screen(self, screen):
        self.request_context_catalog()
        curses.raw()
        curses.nonl()  # Enter is CR; Ctrl+J is LF and inserts a line in the chat.
        self.view.palette.initialize()
        screen.keypad(True)
        try:
            curses.mousemask(getattr(curses, 'BUTTON4_PRESSED', 0) | getattr(curses, 'BUTTON5_PRESSED', 0)
                             | getattr(curses, 'BUTTON1_PRESSED', 0) | getattr(curses, 'BUTTON1_CLICKED', 0)
                             | getattr(curses, 'BUTTON1_DOUBLE_CLICKED', 0))
            curses.mouseinterval(0)
        except curses.error:
            pass
        screen.timeout(100)
        keyboard = KeyboardReader()
        while True:
            frame_start = time.monotonic()
            self.drain_events()
            self.housekeeping()
            self.request_credits()
            try:
                curses.curs_set(1 if self.rename_target else 0 if self.approval or (self.question and not self.question.custom) or (self.browser and not self.rename_target)
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
