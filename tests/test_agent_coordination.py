"""Concurrent execution boundaries and root-wide limits, without model accounts."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from centaur_cli.agent import run_turn
from centaur_cli.agent_runtime import AgentGroup
from centaur_cli.history import ChatStore
from centaur_cli.inbox import Inbox
from centaur_cli.sessions import SessionRegistry
from centaur_cli.subagents import SubagentTools
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools
from test_terminal_settings import Screen


def call(name, identifier='call', **arguments):
    return {'id': identifier, 'function': {'name': name, 'arguments': json.dumps(arguments)}}


def until(predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('Fixture did not reach expected state')


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ChatStore(self.root)
        self.chat = self.store.new('provider/main')
        self.cancel = threading.Event()
        self.group = AgentGroup(self.root, self.chat['id'], self.cancel, inbox=Inbox(self.root, self.chat['id']), registry=SessionRegistry(self.root))

    def tools(self, client, parent=None, background=True):
        return SubagentTools(ProjectTools(self.root, lambda _: True, approval_mode='never', cancel_event=self.cancel),
                             client, parent or self.chat['id'], lambda _: None, group=self.group, background=background)

    def test_new_message_waits_for_current_tool_then_skips_unstarted_batch(self):
        running, release = threading.Event(), threading.Event()
        executed, requests = [], []
        class Client:
            def complete(inner, model, messages, definitions, **options):
                requests.append(list(messages))
                if len(requests) == 1:
                    return {'role': 'assistant', 'tool_calls': [call('run_command', 'first', command='first'), call('write_file', 'second', path='old.txt', content='old')]}
                return {'role': 'assistant', 'content': 'Nova orientação recebida'}
        tools = self.tools(Client())
        def execute(name, args):
            executed.append(name)
            running.set()
            self.assertTrue(release.wait(3))
            return 'Código de saída: 0\nfeito'
        self.chat['messages'] = [{'role': 'user', 'content': 'Pedido original'}]
        errors = []
        def work():
            try:
                run_turn(self.chat, tools.client, tools, self.store, lambda: None)
            except Exception as error:
                errors.append(error)
        with patch.object(tools.base, 'execute', side_effect=execute):
            thread = threading.Thread(target=work)
            thread.start()
            self.assertTrue(running.wait(3))
            self.group.inbox.put({'role': 'user', 'content': 'Mude a direção'})
            self.assertEqual(len(self.chat['messages']), 2)
            release.set()
            thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(executed, ['run_command'])
        self.assertEqual([m['role'] for m in requests[-1]][-4:], ['assistant', 'tool', 'tool', 'user'])
        self.assertIn('Não executada', requests[-1][-2]['content'])
        self.assertEqual(requests[-1][-1]['content'], 'Mude a direção')
        self.assertEqual(self.group.inbox.snapshot(), [])

    def test_background_child_continues_while_main_answers_user_steering(self):
        child_running, release_child, model_running, release_main = (threading.Event() for _ in range(4))
        root_calls = []
        class Client:
            backend = 'openrouter'
            def complete(inner, model, messages, definitions, **options):
                if model == 'provider/worker':
                    child_running.set()
                    if not release_child.wait(4):
                        raise RuntimeError('child fixture timeout')
                    return {'role': 'assistant', 'content': 'Relatório independente'}
                root_calls.append(list(messages))
                if len(root_calls) == 1:
                    return {'role': 'assistant', 'tool_calls': [call('delegate_task', title='Child', task='Independent', model='provider/worker')]}
                if len(root_calls) == 2:
                    model_running.set()
                    if not release_main.wait(4):
                        raise RuntimeError('main fixture timeout')
                return {'role': 'assistant', 'content': 'Resposta: ' + str(messages[-1]['content'])}
        terminal = Terminal(self.root, 'provider/main', self.store, Client())
        terminal.chat['title_attempted'] = True
        terminal.draft = 'Execute a tarefa'
        terminal.submit()
        try:
            self.assertTrue(child_running.wait(3))
            self.assertTrue(model_running.wait(3))
            terminal.draft = 'Explique o progresso antes de continuar'
            terminal.submit()
            self.assertIn('etapa atual', terminal.notice)
            self.assertTrue(any('Aguardando entrega' in line for line in terminal.lines(40)))
            release_main.set()
            until(lambda: len(root_calls) >= 3)
            self.assertIn('Explique o progresso', root_calls[-1][-1]['content'])
            self.assertEqual(terminal.agent_group.active, 1)
            self.assertFalse(terminal.cancel_event.is_set())
            terminal.drain_events()
            self.assertEqual(terminal.session_state(terminal.chat), 'running')
        finally:
            release_main.set()
            release_child.set()
            until(lambda: terminal.agent_group.active == 0)
        until(lambda: any(event[0] == 'session' for event in list(terminal.events.queue)))
        terminal.drain_events()
        until(lambda: any('Relatório independente' in str(m.get('content')) for m in terminal.chat['messages']))
        def idle():
            terminal.drain_events()
            return not terminal.busy
        until(idle)
        self.assertFalse(terminal.busy)

    def test_recursive_execution_keeps_root_identity_and_router_session(self):
        calls = []
        class Client:
            def complete(inner, model, messages, definitions, **options):
                calls.append(options)
                if messages[-1]['role'] == 'user' and messages[-1]['content'] == 'Spawn a child':
                    return {'role': 'assistant', 'tool_calls': [call('delegate_task', title='Grandchild', task='Read only')]}
                return {'role': 'assistant', 'content': 'Relatório'}
        tools = self.tools(Client(), background=False)
        first = json.loads(tools.delegate({'title': 'Child', 'task': 'Spawn a child'}))
        agents = self.store.agents()
        grand = next(c for c in agents if c['title'] == 'Grandchild')
        self.assertEqual(grand['parent_id'], first['id'])
        self.assertTrue(all(c['principal_id'] == self.chat['id'] for c in agents))
        self.assertNotEqual(calls[0]['session_id'], calls[1]['session_id'])
        self.assertEqual(self.group.active, 0)

    def test_limit_is_atomic_and_shared_across_all_descendants(self):
        barrier, accepted, rejected = threading.Barrier(7), [], []
        def reserve(index):
            child = self.store.new('provider/worker')
            child.update(parent_id=self.chat['id'] if index % 2 else 'b' * 32, status='running', title=str(index))
            barrier.wait()
            try:
                self.group.reserve(child, self.store)
                accepted.append(child['id'])
            except RuntimeError as error:
                rejected.append(str(error))
        threads = [threading.Thread(target=reserve, args=(i,)) for i in range(7)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(3)
        self.assertEqual(len(accepted), 6)
        self.assertEqual(len(rejected), 1)
        self.assertIn('6 subagentes', rejected[0])
        self.group.finish(accepted[0], {'status': 'reported'}, publish=False)
        new = self.store.new('provider/worker')
        self.group.reserve(new, self.store)
        self.assertEqual(self.group.active, 6)

    def test_messages_and_status_hide_private_reasoning_and_reject_other_roots(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        class Client:
            def complete(inner, model, messages, definitions, **options):
                calls.append(messages)
                if len(calls) == 1:
                    entered.set()
                    if not release.wait(3): raise RuntimeError('timeout')
                return {'role': 'assistant', 'content': 'Comentário público', 'reasoning': 'PRIVATE'}
        tools = self.tools(Client())
        started = json.loads(tools.delegate({'title': 'Child', 'task': 'Read'}))
        try:
            self.assertTrue(entered.wait(3))
            result = tools.execute('send_agent_message', {'agent_id': started['id'], 'message': 'Confira também o teste'})
            self.assertEqual(json.loads(result)['status'], 'queued')
            self.assertEqual(len(calls), 1)
            self.assertIn('Erro na ferramenta', tools.execute('send_agent_message', {'agent_id': 'f'*32, 'message': 'outro chat'}))
            release.set()
            until(lambda: self.group.active == 0)
        finally:
            release.set()
        self.assertEqual(len(calls), 2)
        self.assertIn('Confira também', calls[-1][-1]['content'])
        status = tools.execute('agent_status', {})
        self.assertNotIn('PRIVATE', status)
        self.assertIn('Comentário público', status)
        self.assertIn('Erro na ferramenta', tools.execute('agent_status', {'agent_id': 'f'*32}))

    def test_background_descendant_keeps_parent_alive_until_its_report(self):
        entered, release = threading.Event(), threading.Event()
        requests = []
        class Client:
            def complete(inner, model, messages, definitions, **options):
                requests.append((model, list(messages)))
                if model == 'provider/grand':
                    entered.set()
                    if not release.wait(3): raise RuntimeError('fixture timeout')
                    return {'role': 'assistant', 'content': 'Grandchild report'}
                if len(messages) == 2:
                    return {'role': 'assistant', 'tool_calls': [call('delegate_task', title='Grandchild', task='Read', model='provider/grand')]}
                return {'role': 'assistant', 'content': 'Parent consolidation'}
        tools = self.tools(Client())
        started = json.loads(tools.delegate({'title': 'Parent', 'task': 'Split task', 'model': 'provider/parent'}))
        try:
            self.assertTrue(entered.wait(3))
            self.assertEqual(self.group.active, 2)
            self.assertTrue(self.group.entries[started['id']]['active'])
            release.set()
            until(lambda: self.group.active == 0)
        finally:
            release.set()
        self.assertTrue(any(model == 'provider/parent' and 'Grandchild report' in str(messages[-1]['content'])
                            for model, messages in requests))

    def test_background_completion_resumes_origin_while_another_chat_is_open(self):
        entered, release = threading.Event(), threading.Event()
        class Client:
            backend = 'openrouter'
            def complete(inner, model, messages, definitions, **options):
                if model == 'provider/worker':
                    entered.set()
                    if not release.wait(3): raise RuntimeError('fixture timeout')
                    return {'role': 'assistant', 'content': 'Origin report'}
                if len(messages) == 2:
                    return {'role': 'assistant', 'tool_calls': [call('delegate_task', title='Background', task='Read', model='provider/worker')]}
                return {'role': 'assistant', 'content': 'Origin answer'}
        terminal = Terminal(self.root, 'provider/main', self.store, Client())
        origin = terminal.chat
        origin['title_attempted'] = True
        terminal.draft = 'Delegate'
        terminal.submit()
        try:
            self.assertTrue(entered.wait(3))
            def idle():
                terminal.drain_events()
                return not terminal.busy
            until(idle)
            group = terminal.agent_group
            terminal.create_chat_from_menu()
            current_id = terminal.chat['id']
            release.set()
            until(lambda: group.active == 0)
            def completed():
                terminal.drain_events()
                return (not terminal.session_states[origin['id']].get('busy') and
                        any('Origin report' in str(m.get('content')) for m in origin['messages']))
            until(completed)
            self.assertEqual(terminal.chat['id'], current_id)
            self.assertEqual(terminal.chat['messages'], [])
            self.assertFalse(terminal.busy)
        finally:
            release.set()

    def test_status_summary_is_bounded_but_old_executor_remains_queryable(self):
        identifiers = []
        for index in range(20):
            chat = self.store.new('provider/worker')
            chat.update(parent_id=self.chat['id'], status='reported', title=str(index),
                        messages=[{'role': 'assistant', 'content': 'Progress ' * 500} for _ in range(12)])
            self.group.reserve(chat, self.store)
            self.group.finish(chat['id'], {'status': 'reported'}, publish=False)
            identifiers.append(chat['id'])
        data = json.loads(self.group.status())
        self.assertEqual(data['total_agents'], 20)
        self.assertEqual(len(data['agents']), 6)
        self.assertEqual([item['id'] for item in data['agents']], identifiers[-6:])
        self.assertEqual(json.loads(self.group.status(identifiers[0]))['agents'][0]['id'], identifiers[0])
        self.assertTrue(all(len(item['progress']) <= 3 and all(len(line) <= 400 for line in item['progress'])
                            for item in data['agents']))

    def test_durable_inbox_recovers_without_duplicate_delivery(self):
        inbox = self.group.inbox
        inbox.put({'role': 'user', 'content': 'Nova mensagem'})
        restored = Inbox(self.root, self.chat['id'])
        item = restored.snapshot()[0]
        self.chat['messages'] = [item['message']]
        self.chat['received_messages'] = [item['id']]
        self.group.inbox = restored
        class Client:
            def complete(inner, *args, **options):
                return {'role': 'assistant', 'content': 'Respondido'}
        tools = self.tools(Client())
        run_turn(self.chat, tools.client, tools, self.store, lambda: None)
        self.assertEqual(sum(m['role'] == 'user' for m in self.chat['messages']), 1)
        self.assertEqual(restored.snapshot(), [])

    def test_two_permissions_are_serialized_and_cancelled_requests_do_not_open(self):
        terminal = Terminal(self.root, 'provider/main', self.store, None)
        results = []
        threads = [threading.Thread(target=lambda: results.append(terminal.approve('Pedido'))) for _ in range(2)]
        for thread in threads: thread.start()
        until(lambda: not terminal.events.empty())
        terminal.drain_events()
        self.assertIsNotNone(terminal.approval)
        terminal.handle('y')
        until(lambda: not terminal.events.empty())
        terminal.drain_events()
        self.assertIsNotNone(terminal.approval)
        terminal.handle('n')
        for thread in threads: thread.join(3)
        self.assertEqual(sorted(results), [False, True])

    def test_removed_commands_and_capture_shortcut_do_not_call_the_model(self):
        terminal = Terminal(self.root, 'provider/main', self.store, None)
        for busy in (False, True):
            terminal.busy = busy
            for command in ('$attach x.txt', '$screenshot', '$screnshoot'):
                terminal.draft = command
                terminal.submit()
                self.assertIn('Ctrl+S', terminal.notice)
                self.assertFalse(terminal.chat['messages'])
            with patch.object(terminal, 'capture_attachment') as capture:
                terminal.handle('\x13')
                capture.assert_called_once()
        terminal.completion.update('$')
        self.assertNotIn('attach', terminal.completion.options)
        self.assertNotIn('screenshot', terminal.completion.options)
        terminal.draw(Screen((12, 40)))

    def test_active_grandchild_protects_root_from_expiration_and_deletion(self):
        self.chat['created'] = '2000-01-01T00:00:00+00:00'
        self.store.save(self.chat)
        parent = self.store.new('provider/worker')
        parent.update(parent_id=self.chat['id'], principal_id=self.chat['id'])
        parent_store = ChatStore(self.root)
        parent_store.directory = self.root / '.centaur' / 'agents' / self.chat['id']
        parent_store.save(parent)
        child = self.store.new('provider/worker')
        child.update(parent_id=parent['id'], principal_id=self.chat['id'])
        child_store = ChatStore(self.root)
        child_store.directory = self.root / '.centaur' / 'agents' / parent['id']
        child_store.save(child)
        self.group.registry.set(child['id'], 'running')
        self.assertEqual(self.store.prune(), [])
        with self.assertRaises(ValueError): self.store.delete(self.chat['id'])
        self.group.registry.set(child['id'], 'stopped')
        self.store.delete(self.chat['id'])
        self.assertEqual(self.store.agents(), [])
