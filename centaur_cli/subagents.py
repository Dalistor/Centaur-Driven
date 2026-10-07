"""Execução de tasks em sessões próprias, com seleção de modelos por backend."""

import copy
import json
import threading

from .agent import run_turn
from .history import ChatStore
from .tools import ProjectTools
from .interaction import TurnCancelled
from .agent_runtime import AgentGroup, AGENT_TOOLS

COST_TIERS = ('low', 'medium', 'high', 'xhigh', 'max')
DELEGATE_TASK = {
    'type': 'function', 'function': {
        'name': 'delegate_task',
        'description': 'Iniciar uma task em subagente com contexto próprio e Auto Router. Em segundo plano retorna started, não conclusão; consulte agent_status e espere o relatório para validar. Limite compartilhado de seis executores simultâneos por principal.',
        'parameters': {
            'type': 'object', 'properties': {
                'title': {'type': 'string', 'description': 'ID qualificado da spec/task e título curto'},
                'task': {'type': 'string', 'description': 'Contrato, objetivo, fontes, posse de arquivos, dependências, modo, aceite e destino do registro'},
                'cost_tier': {'type': 'string', 'enum': list(COST_TIERS), 'default': 'medium',
                              'description': 'low para tarefas simples, medium para implementação comum, high/xhigh/max para maior risco; respeite o máximo configurado'},
                'model': {'type': 'string', 'default': 'openrouter/auto',
                          'description': 'Use openrouter/auto; modelo específico somente quando explicitamente definido pelo usuário ou pela task'},
            }, 'required': ['title', 'task'], 'additionalProperties': False,
        },
    },
}


class RoutedClient:
    def __init__(self, client, session_id, cost_tier):
        self.client, self.session_id, self.cost_tier = client, session_id, cost_tier

    def __getattr__(self, name):
        return getattr(self.client, name)

    def complete(self, model, messages, tools, **options):
        return self.client.complete(model, messages, tools,
                                    cost_tier=self.cost_tier, session_id=self.session_id, **options)


class SubagentTools:
    def __init__(self, base, client, parent_id, emit, max_tier='high', *, registry=None, effort='default', speed='standard', group=None, background=False):
        while isinstance(client, RoutedClient):
            client = client.client
        if max_tier not in COST_TIERS:
            raise ValueError('Faixa máxima de subagentes inválida.')
        if (not isinstance(parent_id, str) or len(parent_id) != 32
                or any(character not in '0123456789abcdef' for character in parent_id)):
            raise ValueError('Identificador do chat coordenador inválido.')
        self.base, self.client, self.parent_id = base, client, parent_id
        self.root, self.emit, self.max_tier = base.root, emit, max_tier
        self.registry = registry
        self.effort, self.speed = effort, speed
        self.approval_mode = base.approval_mode
        self.approve_callback = getattr(base, 'agent_approve', base.approve)
        self.ask_callback = getattr(base, 'agent_ask', base.ask_user)
        self.cancel_event = base.cancel_event
        self.group = group or AgentGroup(base.root, parent_id, base.cancel_event, registry=registry)
        self.cancel_event = self.group.cancel_event
        self.background = background
        self.routing = getattr(client, 'allows_model_routing', True)
        delegation = copy.deepcopy(DELEGATE_TASK)
        self.native_models = client.model_catalog() if not self.routing else {}
        if not self.routing:
            delegation['function']['description'] = 'Iniciar uma task no backend conectado, escolhendo modelo conforme complexidade e risco. started indica execução em segundo plano, não conclusão; consulte agent_status. Limite compartilhado de seis executores simultâneos.'
            properties = delegation['function']['parameters']['properties']
            properties['model'] = {'type': 'string', 'enum': list(self.native_models),
                                   'description': 'Escolha conforme a task: ' + json.dumps(self.native_models, ensure_ascii=False)}
            if not self.native_models:
                del properties['model']
            del properties['cost_tier']
        self.definitions = [*base.definitions, delegation, *copy.deepcopy(AGENT_TOOLS)]

    def check_cancelled(self):
        if self.cancel_event.is_set():
            raise TurnCancelled('Execução interrompida pelo usuário.')
        self.base.check_cancelled()

    def observation_messages(self):
        return self.base.observation_messages()

    def activity(self, phase):
        return getattr(self.base, 'activity', lambda _: None)(phase)

    def native_progress(self, event):
        return getattr(self.base, 'native_progress', lambda _: None)(event)

    def receive_messages(self):
        return self.group.receive(self.parent_id)

    def acknowledge_messages(self, identifiers):
        self.group.acknowledge(self.parent_id, identifiers)

    def has_messages(self):
        return bool(self.receive_messages())

    def wait_for_children(self):
        if not self.background or self.parent_id == self.group.principal_id:
            return
        while True:
            self.check_cancelled()
            with self.group.lock:
                active = any(entry['active'] and entry['chat']['parent_id'] == self.parent_id
                             for entry in self.group.entries.values())
            if not active or self.has_messages():
                return
            self.activity('tool:wait_agents')
            self.group.wait(self.parent_id, 30)

    def execute(self, name, arguments):
        if name not in ('delegate_task', 'agent_status', 'send_agent_message', 'wait_agents'):
            return self.base.execute(name, arguments)
        try:
            self.check_cancelled()
            if name == 'agent_status':
                return self.base.redact(self.group.status(arguments.get('agent_id', '')))
            if name == 'send_agent_message':
                text = arguments['message']
                if not isinstance(text, str):
                    raise ValueError('Mensagem deve ser texto.')
                return self.group.message(self.parent_id, arguments['agent_id'], self.base.redact(text))
            if name == 'wait_agents':
                return self.base.redact(self.group.wait(self.parent_id, arguments.get('wait_seconds', 10)))
            return self.base.redact(self.delegate(arguments))
        except TurnCancelled:
            raise
        except (RuntimeError, OSError, ValueError, KeyError, TypeError) as error:
            return self.base.redact(f'Falha ao delegar task: {error}' if name == 'delegate_task' else f'Erro na ferramenta: {error}')

    def delegate(self, arguments):
        title, task = arguments['title'], arguments['task']
        if not self.routing and 'cost_tier' in arguments:
            raise ValueError('cost_tier é exclusivo de OpenRouter.')
        tier = arguments.get('cost_tier', 'medium') if self.routing else None
        model = arguments.get('model', 'openrouter/auto') if self.routing else arguments.get('model', self.client.fixed_model)
        if not isinstance(title, str) or not title.strip() or not isinstance(task, str) or not task.strip():
            raise ValueError('Informe título e contrato da task.')
        title = self.base.redact(title)
        if self.routing and (tier not in COST_TIERS or COST_TIERS.index(tier) > COST_TIERS.index(self.max_tier)):
            raise ValueError(f'Faixa solicitada excede o máximo {self.max_tier}; ajuste a task ou a configuração.')
        if self.routing and (not isinstance(model, str) or '/' not in model):
            raise ValueError('Modelo inválido; use openrouter/auto ou um ID explícito do OpenRouter.')
        if not self.routing and model != self.client.fixed_model and model not in self.native_models:
            raise ValueError('Modelo não listado no catálogo do backend conectado.')
        store = ChatStore(self.root)
        store.directory = self.root / '.centaur' / 'agents' / self.parent_id
        chat = store.new(model, backend=getattr(self.client, 'backend', 'openrouter'))
        chat.update({'title': title, 'parent_id': self.parent_id, 'cost_tier': tier,
                     'approval_mode': self.approval_mode,
                     'status': 'running', 'messages': [{'role': 'user', 'content': self.base.redact(task)}]})
        levels = getattr(self.client, 'model_efforts', {}).get(model)
        chat['effort'] = self.effort if not levels or self.effort in levels or self.effort == 'default' else 'default'
        chat['speed'] = self.speed if self.speed != 'fast' or getattr(self.client, 'supports_fast', lambda _: False)(model) else 'standard'
        chat['principal_id'] = self.group.principal_id
        self.group.reserve(chat, store)
        try:
            store.save(chat)
        except Exception:
            self.group.discard(chat['id'])
            raise
        if self.background:
            try:
                thread = threading.Thread(target=self.run_child, args=(chat, store, title, task, tier, model), daemon=True)
                thread.start()
            except Exception:
                chat['status'] = 'failed'
                try:
                    store.save(chat)
                finally:
                    self.group.discard(chat['id'])
                raise
            return json.dumps({'id': chat['id'], 'title': title, 'status': 'started',
                               'parent_id': self.parent_id, 'principal_id': self.group.principal_id,
                               'history': str(store.directory / (chat['id'] + '.json'))}, ensure_ascii=False)
        return self.run_child(chat, store, title, task, tier, model)

    def run_child(self, chat, store, title, task, tier, model):
        report = 'Executor encerrado antes de produzir relatório.'
        def state(value):
            if self.registry:
                try:
                    self.registry.set(chat['id'], value)
                except (OSError, ValueError):
                    pass  # Runtime display failures must not leak executor slots.
        state('running')
        try:
            self.emit(f'└─↳ Subagente: {title} · {model or getattr(self.client, "backend", "openrouter")} · {"faixa " + tier if tier else "backend conectado"}')
            def interact(callback, *args):
                state('waiting_input')
                try:
                    return callback(*args)
                finally:
                    state('running')
            tools = ProjectTools(self.root,
                                 lambda description: interact(self.approve_callback, f'Subagente {title}\n{description}'),
                                 protected_keys=self.base.protected_keys, approval_mode=self.approval_mode,
                                 ask_user=(lambda question, options: interact(self.ask_callback, question, options)) if self.ask_callback else None,
                                 cancel_event=self.cancel_event)
            tools.agent_approve, tools.agent_ask = self.approve_callback, self.ask_callback
            if self.registry:
                tools.activity = lambda phase: self.registry.activity(chat['id'], phase)
                tools.native_progress = lambda event: self.registry.native_event(chat['id'], event)
            instructions = ('\nVocê é executor de UMA task delegada. Não é o coordenador. '
                            'Leia clean-code e a skill implement/tdd conforme o modo. '
                            'Siga graphify/references/testing.md: reutilize proteção existente; novos testes '
                            'só para falha concreta em ponto vital ainda sem proteção suficiente. '
                            'Não crie uma bateria própria nem duplique a cobertura de outra task. '
                            'Pode delegar partes independentes, mantendo o limite global de seis executores '
                            'e a posse de arquivos. Consulte agent_status e send_agent_message para coordenar. '
                            'Edite somente os arquivos sob sua posse; '
                            'contratos, spec, índices, estado e documentos compartilhados são do coordenador. '
                            'Não substitua critérios de aceite. Relate arquivos, verificações, '
                            'evidências, pendências e limites. Seu relatório ainda será conferido.\n')
            try:
                child_client = RoutedClient(self.client, chat['id'], tier) if self.routing else self.client
                child_tools = SubagentTools(tools, child_client, chat['id'], self.emit, self.max_tier,
                                            registry=self.registry, effort=chat['effort'], speed=chat['speed'],
                                            group=self.group, background=self.background)
                run_turn(chat, child_client, child_tools, store,
                         lambda: self.emit(f'└─↳ Subagente: {title} · {chat.get("models_used", [model])[-1]}'),
                         instructions)
                chat['status'] = 'reported'
                report = chat['messages'][-1].get('content') or ''
            except TurnCancelled:
                chat['status'] = 'cancelled'
                report = 'Execução interrompida; confira ações já aplicadas.'
            except Exception as error:
                chat['status'] = 'failed'
                report = self.base.redact(str(error))
                chat['last_error'] = report
        finally:
            state('stopped')
            if chat['status'] == 'running':
                chat['status'] = 'failed'
                report = 'Executor encerrado antes de produzir relatório.'
            models = list(dict.fromkeys(chat.get('models_used', [])))
            result = {'id': chat['id'], 'title': title, 'status': chat['status'],
                      'parent_id': self.parent_id, 'principal_id': self.group.principal_id,
                      'requested_model': model, 'models_used': models, 'cost_tier': tier,
                      'history': str(store.directory / (chat['id'] + '.json')), 'report': report}
            try:
                store.save(chat)
            except (OSError, ValueError, RuntimeError):
                result['status'] = chat['status'] = 'failed'
                result['report'] = 'Não foi possível salvar o relatório; confira o armazenamento e as ações já aplicadas.'
            self.group.finish(chat['id'], result, publish=self.background)
        models = list(dict.fromkeys(chat.get('models_used', [])))
        result_label = 'concluído' if chat['status'] == 'reported' else 'interrompido/falhou'
        self.emit(f'Retomando coordenador · subagente {title}: {result_label} · {", ".join(models) or "modelo não informado"}')
        if chat['status'] == 'cancelled' and not self.background:
            raise TurnCancelled('Execução interrompida pelo usuário.')
        return json.dumps(result, ensure_ascii=False)
