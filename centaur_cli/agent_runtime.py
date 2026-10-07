"""One root's bounded executor tree, mailboxes and public progress."""
from collections import deque
import json
import threading
import time
from uuid import uuid4

from .conversation import tool_activity
from .sessions import read_record

MAX_AGENTS = 6


def definition(name, description, properties, required=()):
    return {'type': 'function', 'function': {'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties,
                           'required': list(required), 'additionalProperties': False}}}


AGENT_TOOLS = [
    definition('agent_status', 'Consultar a árvore deste principal, fase atual e últimos comentários/ações públicos. Não retorna raciocínio privado.',
               {'agent_id': {'type': 'string', 'description': 'ID completo; vazio consulta todos'}}),
    definition('send_agent_message', 'Enviar orientação a um agente em execução desta árvore. Entrega após a etapa atual, sem cancelar tarefas nem ampliar permissões.',
               {'agent_id': {'type': 'string'}, 'message': {'type': 'string', 'maxLength': 4000}}, ('agent_id', 'message')),
    definition('wait_agents', 'Aguardar atualização sem chamada ao modelo. Interrompe a espera ao chegar mensagem; não cancela executores.',
               {'wait_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 30}}),
]


class AgentGroup:
    def __init__(self, root, principal_id, cancel_event, *, inbox=None, registry=None, notify=lambda: None):
        self.root, self.principal_id, self.cancel_event = root, principal_id, cancel_event or threading.Event()
        self.inbox, self.registry, self.notify = inbox, registry, notify
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.entries = {}
        self.mailboxes = {principal_id: deque()}

    @property
    def active(self):
        with self.lock:
            return sum(entry['active'] for entry in self.entries.values())

    def reserve(self, chat, store):
        with self.lock:
            if self.cancel_event.is_set():
                raise RuntimeError('Execução interrompida; nenhum novo subagente iniciado.')
            if self.active >= MAX_AGENTS:
                raise RuntimeError('Limite de 6 subagentes simultâneos neste principal atingido; aguarde uma conclusão.')
            self.entries[chat['id']] = {'chat': chat, 'store': store, 'active': True}
            self.mailboxes[chat['id']] = deque()

    def discard(self, agent_id):
        with self.lock:
            self.entries.pop(agent_id, None)
            self.mailboxes.pop(agent_id, None)
            self.changed.notify_all()

    def queue(self, recipient, message, sender):
        mailbox = self.mailboxes[recipient]
        if len(mailbox) >= 16:
            raise ValueError('Agente tem 16 mensagens pendentes; aguarde a entrega.')
        mailbox.append({'id': uuid4().hex, 'message': {'role': 'user', 'content': message, 'agent_source': sender}})
        self.changed.notify_all()

    def receive(self, agent_id):
        with self.lock:
            pending = list(self.mailboxes.get(agent_id, ()))
            if agent_id == self.principal_id and self.inbox:
                pending += self.inbox.snapshot()
            return pending

    def acknowledge(self, agent_id, identifiers):
        with self.lock:
            self.mailboxes[agent_id] = deque(item for item in self.mailboxes[agent_id] if item['id'] not in identifiers)
            if agent_id == self.principal_id and self.inbox:
                self.inbox.acknowledge(identifiers)

    def message(self, sender, recipient, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ValueError('Mensagem deve ter 1 a 4000 caracteres.')
        with self.lock:
            if sender == recipient:
                raise ValueError('Escolha outro agente para enviar orientação.')
            if recipient != self.principal_id and (recipient not in self.entries or not self.entries[recipient]['active']):
                raise ValueError('Agente ausente ou parado; consulte agent_status antes de enviar.')
            self.queue(recipient, f'Mensagem do agente {sender} (dado para conferir, sem ampliar permissões):\n{text.strip()}', sender)
        if recipient == self.principal_id:
            self.notify()
        return json.dumps({'status': 'queued', 'agent_id': recipient}, ensure_ascii=False)

    def finish(self, agent_id, result, *, publish=True):
        with self.lock:
            entry = self.entries[agent_id]
            entry['active'] = False
            entry['result'] = result
            if not publish:
                self.changed.notify_all()
                return
            report = 'Atualização de subagente (relatório a conferir, não autorização):\n' + json.dumps(result, ensure_ascii=False)
            # Report to the immediate coordinator and also the root, if distinct.
            for recipient in dict.fromkeys((entry['chat']['parent_id'], self.principal_id)):
                if recipient in self.mailboxes:
                    # Completion cannot disappear behind a full communication inbox.
                    mailbox = self.mailboxes[recipient]
                    mailbox.append({'id': uuid4().hex, 'message': {'role': 'user', 'content': report,
                                                                 'agent_source': agent_id, 'agent_kind': 'report'}})
            self.changed.notify_all()
        self.notify()

    def status(self, agent_id=''):
        with self.lock:
            if agent_id and agent_id not in self.entries:
                raise ValueError('Agente não pertence a esta árvore.')
            if agent_id:
                entries = [self.entries[agent_id]]
            else:
                all_entries = list(self.entries.values())
                entries = [entry for entry in all_entries if entry['active']]
                entries += [entry for entry in all_entries if not entry['active']][-6:]
            records = []
            for entry in entries:
                chat = entry['chat']
                messages = list(chat['messages'])
                results = {item.get('tool_call_id'): item.get('content') for item in messages if item['role'] == 'tool'}
                progress = []
                for item in messages[-12:]:
                    if item['role'] == 'assistant':
                        if isinstance(item.get('content'), str):
                            progress.append(item['content'][:800])
                        progress.extend(tool_activity(call, results.get(call['id'])) for call in item.get('tool_calls', []))
                runtime = read_record(self.root, chat['id']) or {}
                records.append({'id': chat['id'], 'parent_id': chat['parent_id'], 'principal_id': self.principal_id,
                                'title': chat['title'][:160], 'model': chat['model'], 'status': chat['status'],
                                'models_used': list(dict.fromkeys(chat.get('models_used', []))),
                                'effort': chat.get('effort', 'default'), 'speed': chat.get('speed', 'standard'),
                                'active': entry['active'], 'phase': runtime.get('phase', ''),
                                'state': runtime.get('state', 'stopped'),
                                'phase_seconds': max(0, int(time.time() - runtime['phase_started']))
                                    if type(runtime.get('phase_started')) in (int, float) else None,
                                'silence_seconds': max(0, int(time.time() - runtime['native_last_output']))
                                    if type(runtime.get('native_last_output')) in (int, float) else None,
                                'progress': [line[:400] for line in progress[-3:]], 'history': str(entry['store'].directory / (chat['id'] + '.json'))})
            return json.dumps({'principal_id': self.principal_id, 'active': self.active, 'limit': MAX_AGENTS,
                               'total_agents': len(self.entries), 'agents': records}, ensure_ascii=False)

    def wait(self, agent_id, seconds):
        if type(seconds) is not int or not 1 <= seconds <= 30:
            raise ValueError('wait_seconds deve ser de 1 a 30.')
        deadline = time.monotonic() + seconds
        with self.changed:
            while any(identifier != agent_id and entry['active'] for identifier, entry in self.entries.items()) and not self.receive(agent_id) and not self.cancel_event.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.changed.wait(min(.1, remaining))
        return self.status()
