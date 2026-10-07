"""Execução de tasks em sessões próprias, com seleção de modelos por backend."""

import copy
import json

from .agent import run_turn
from .history import ChatStore
from .tools import ProjectTools, TOOLS
from .interaction import TurnCancelled

COST_TIERS = ('low', 'medium', 'high', 'xhigh', 'max')
DELEGATE_TASK = {
    'type': 'function', 'function': {
        'name': 'delegate_task',
        'description': 'Executar uma task em um subagente com Auto Router. Execução sequencial; retorna relatório para validação do coordenador.',
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
    def __init__(self, base, client, parent_id, emit, max_tier='high', *, registry=None):
        if max_tier not in COST_TIERS:
            raise ValueError('Faixa máxima de subagentes inválida.')
        if (not isinstance(parent_id, str) or len(parent_id) != 32
                or any(character not in '0123456789abcdef' for character in parent_id)):
            raise ValueError('Identificador do chat coordenador inválido.')
        self.base, self.client, self.parent_id = base, client, parent_id
        self.root, self.emit, self.max_tier = base.root, emit, max_tier
        self.registry = registry
        self.approval_mode = base.approval_mode
        self.cancel_event = base.cancel_event
        self.routing = getattr(client, 'allows_model_routing', True)
        delegation = copy.deepcopy(DELEGATE_TASK)
        self.native_models = client.model_catalog() if not self.routing else {}
        if not self.routing:
            delegation['function']['description'] = 'Executar uma task sequencial no backend conectado, escolhendo modelo conforme complexidade e risco.'
            properties = delegation['function']['parameters']['properties']
            properties['model'] = {'type': 'string', 'enum': list(self.native_models),
                                   'description': 'Escolha conforme a task: ' + json.dumps(self.native_models, ensure_ascii=False)}
            if not self.native_models:
                del properties['model']
            del properties['cost_tier']
        self.definitions = [*base.definitions, delegation]
        self.count = 0

    def check_cancelled(self):
        self.base.check_cancelled()

    def observation_messages(self):
        return self.base.observation_messages()

    def execute(self, name, arguments):
        if name != 'delegate_task':
            return self.base.execute(name, arguments)
        try:
            return self.base.redact(self.delegate(arguments))
        except TurnCancelled:
            raise
        except (RuntimeError, OSError, ValueError, KeyError, TypeError) as error:
            return self.base.redact(f'Falha ao delegar task: {error}')

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
        if self.count >= 12:
            raise RuntimeError('Limite de 12 subagentes por turno atingido; continue em outro turno.')
        self.count += 1
        store = ChatStore(self.root)
        store.directory = self.root / '.centaur' / 'agents' / self.parent_id
        chat = store.new(model, backend=getattr(self.client, 'backend', 'openrouter'))
        chat.update({'title': title, 'parent_id': self.parent_id, 'cost_tier': tier,
                     'approval_mode': self.approval_mode,
                     'status': 'running', 'messages': [{'role': 'user', 'content': self.base.redact(task)}]})
        store.save(chat)
        if self.registry:
            self.registry.set(chat['id'], 'running')
        try:
            self.emit(f'Subagente: {title} · {model or getattr(self.client, "backend", "openrouter")} · {"faixa " + tier if tier else "backend conectado"}')
            def interact(callback, *args):
                if self.registry:
                    self.registry.set(chat['id'], 'waiting_input')
                try:
                    return callback(*args)
                finally:
                    if self.registry:
                        self.registry.set(chat['id'], 'running')
            tools = ProjectTools(self.root,
                                 lambda description: interact(self.base.approve, f'Subagente {title}\n{description}'),
                                 protected_keys=self.base.protected_keys, approval_mode=self.approval_mode,
                                 ask_user=lambda question, options: interact(self.base.ask_user, question, options), cancel_event=self.base.cancel_event)
            if self.registry:
                tools.activity = lambda phase: self.registry.activity(chat['id'], phase)
            instructions = ('\nVocê é executor de UMA task delegada. Não é o coordenador. '
                            'Leia clean-code e a skill implement/tdd conforme o modo. '
                            'Não crie outros subagentes. Edite somente os arquivos sob sua posse; '
                            'contratos, spec, índices, estado e documentos compartilhados são do coordenador. '
                            'Não substitua critérios de aceite. Relate arquivos, verificações, '
                            'evidências, pendências e limites. Seu relatório ainda será conferido.\n')
            try:
                run_turn(chat, RoutedClient(self.client, chat['id'], tier) if self.routing else self.client, tools, store,
                         lambda: self.emit(f'Subagente: {title} · {chat.get("models_used", [model])[-1]}'),
                         instructions)
                chat['status'] = 'reported'
                report = chat['messages'][-1].get('content') or ''
            except TurnCancelled:
                chat['status'] = 'cancelled'
                store.save(chat)
                raise
            except Exception as error:
                chat['status'] = 'failed'
                report = self.base.redact(str(error))
                chat['last_error'] = report
        finally:
            if self.registry:
                self.registry.set(chat['id'], 'stopped')
        store.save(chat)
        models = list(dict.fromkeys(chat.get('models_used', [])))
        result_label = 'concluído' if chat['status'] == 'reported' else 'interrompido/falhou'
        self.emit(f'Retomando coordenador · subagente {title}: {result_label} · {", ".join(models) or "modelo não informado"}')
        return json.dumps({'id': chat['id'], 'title': title, 'status': chat['status'],
                           'requested_model': model, 'models_used': models, 'cost_tier': tier,
                           'history': str(store.directory / (chat['id'] + '.json')),
                           'report': report}, ensure_ascii=False)
