"""Interface curses e navegação entre conversas."""

import curses
import queue
import textwrap
import threading
import time

from .agent import run_turn
from .completion import SkillCompletion
from .tools import ProjectTools
from .appearance import TerminalView
from .subagents import SubagentTools
from .status import ANALYSIS_INSTRUCTIONS, StatusTools, render_status


def display_lines(text, width):
    clean = ''.join(character if character.isprintable() or character == '\n' else ' '
                    for character in str(text))
    return [line for paragraph in clean.split('\n')
            for line in (textwrap.wrap(paragraph, max(1, width)) or [''])]


class Terminal:
    def __init__(self, root, model, store, client, max_subagent_tier='high'):
        self.root, self.model, self.store, self.client = root, model, store, client
        self.backend = getattr(client, 'backend', 'openrouter')
        self.chat = store.new(model, backend=self.backend)
        self.events = queue.Queue()
        self.busy = False
        self.approval = None
        self.draft = ''
        self.completion = SkillCompletion(root)
        self.notice = 'Digite uma mensagem. ← abre os chats desta pasta.'
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
        threading.Thread(target=self.fetch_credits, daemon=True).start()

    def fetch_credits(self):
        try:
            self.events.put(('credits', self.client.credits()))
        except Exception:
            self.events.put(('credits_error', None))

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
            self.chat = self.store.new(self.model, backend=self.backend)
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
        if command.startswith('/status'):
            if command not in ('/status', '/status --ai'):
                self.notice = 'Uso: /status ou /status --ai para analisar com IA.'
                return
            if command == '/status':
                self.chat['messages'].extend([
                    {'role': 'user', 'content': command},
                    {'role': 'assistant', 'content': render_status(self.root)}])
                if self.chat['title'] == 'Novo chat':
                    self.chat['title'] = 'Status das specs'
                self.store.save(self.chat)
                self.draft = ''
                self.scroll = 0
                self.notice = 'Status local · /status --ai analisa evidências e recomenda próximos passos.'
                return
        self.chat['messages'].append({'role': 'user', 'content': self.draft})
        if self.chat['title'] == 'Novo chat':
            self.chat['title'] = self.draft[:80]
        self.store.save(self.chat)
        self.draft = ''
        self.scroll = 0
        self.busy = True
        self.notice = f'Aguardando {self.backend}…'
        threading.Thread(target=self.work, args=(self.chat,), daemon=True).start()

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
            backend_instructions = (f'\nBackend conectado: {self.backend}. Subagentes devem herdar o modelo da sessão. '
                                    'Não use OpenRouter, não selecione modelos ou cost_tier e não invoque CLIs externos '
                                    'para contornar a restrição; delegate_task aceita somente title e task.\n'
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
            if kind == 'approval':
                self.approval = value
                self.browser = False
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
            role = {'user': 'Você', 'assistant': 'Centaur', 'tool': 'Ferramenta'}[message['role']]
            content = message.get('content') or ''
            if message.get('tool_calls'):
                content += '\n' + ', '.join(call['function']['name'] for call in message['tool_calls'])
            lines.extend(display_lines(f'{role}: {content}', width) + [''])
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
            self.chat = self.store.new(self.model, backend=self.backend)
            self.draft = ''
            self.scroll = 0
        self.chats = self.store.list()
        self.selected = min(self.selected, max(0, len(self.chats) - 1))
        self.notice = 'Chat excluído.'

    def handle(self, key):
        if key in ('\x11', '\x03'):
            if self.busy:
                self.notice = 'Aguarde o turno terminar para sair; recuse ações pendentes com n.'
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
        if key == curses.KEY_LEFT:
            self.browser = True
            self.chats = self.store.list()
            self.selected = 0
            return
        if self.browser:
            if key in ('\x1b', curses.KEY_RIGHT):
                self.browser = False
            elif key == curses.KEY_UP:
                self.selected = max(0, self.selected - 1)
            elif key == curses.KEY_DOWN:
                self.selected = min(max(0, len(self.chats) - 1), self.selected + 1)
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
        self.completion.update(self.draft)
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
        if key == curses.KEY_PPAGE:
            self.scroll += 5
        elif key == curses.KEY_NPAGE:
            self.scroll = max(0, self.scroll - 5)
        elif key in ('\n', '\r', curses.KEY_ENTER):
            return self.submit()
        elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
            self.draft = self.draft[:-1]
        elif key == '\x15':
            self.draft = ''
        elif isinstance(key, str) and key.isprintable():
            self.draft += key

    def run(self, screen):
        curses.raw()
        self.view.palette.initialize()
        screen.keypad(True)
        screen.timeout(100)
        while True:
            self.drain_events()
            self.request_credits()
            try:
                curses.curs_set(0 if self.browser or self.approval else 1)
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
            if self.handle(key) == 'quit':
                return
