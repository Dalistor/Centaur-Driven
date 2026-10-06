import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from centaur_cli.agent import run_turn
from centaur_cli.history import ChatStore
from centaur_cli.openrouter import ModelReply, OpenRouter
from centaur_cli.subagents import SubagentTools
from centaur_cli.tools import ProjectTools


class SubagentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.parent_id = 'a' * 32

    def test_auto_router_sends_cost_tier_session_and_preserves_actual_model_separately(self):
        response = io.BytesIO(json.dumps({'model': 'provider/selected', 'choices': [
            {'message': {'role': 'assistant', 'content': 'Relatório'}}]}).encode())
        with patch('centaur_cli.openrouter.urlopen', return_value=response) as request:
            reply = OpenRouter('secret').complete('openrouter/auto', [], [],
                                                cost_tier='high', session_id='task-session')
        payload = json.loads(request.call_args.args[0].data)
        self.assertEqual(payload['plugins'], [{'id': 'auto-router', 'cost_tier': 'high'}])
        self.assertEqual(payload['session_id'], 'task-session')
        self.assertTrue(payload['provider']['require_parameters'])
        self.assertEqual(reply.model, 'provider/selected')
        self.assertNotIn('model', reply)

    def test_beta_router_uses_its_own_plugin_and_fixed_model_has_no_router_plugin(self):
        for model, plugin in [('openrouter/auto-beta', 'auto-beta-router'), ('provider/fixed', None)]:
            response = io.BytesIO(b'{"choices":[{"message":{"role":"assistant","content":"OK"}}]}')
            with patch('centaur_cli.openrouter.urlopen', return_value=response) as request:
                OpenRouter('secret').complete(model, [], [], cost_tier='medium', session_id='task')
            payload = json.loads(request.call_args.args[0].data)
            if plugin:
                self.assertEqual(payload['plugins'][0]['id'], plugin)
            else:
                self.assertNotIn('plugins', payload)

    def test_subagent_has_own_context_uses_tools_and_returns_actual_model_report(self):
        approvals, requests, progress = [], [], []
        class Client:
            def complete(inner, model, messages, tools, **options):
                requests.append((model, list(messages), tools, options))
                if len(requests) == 1:
                    return ModelReply({'role': 'assistant', 'content': None, 'tool_calls': [{
                        'id': 'write', 'type': 'function', 'function': {
                            'name': 'write_file', 'arguments': json.dumps({'path': 'task.txt', 'content': 'feito'})}}]},
                        'provider/coding-model')
                return ModelReply({'role': 'assistant', 'content': 'Arquivo criado, validação pendente.'},
                                  'provider/coding-model')
        base = ProjectTools(self.root, lambda text: approvals.append(text) or True)
        tools = SubagentTools(base, Client(), self.parent_id, progress.append)
        result = json.loads(tools.execute('delegate_task', {
            'title': 'master/0001 — Task 01', 'task': 'Edite somente task.txt. Aceite: arquivo com feito.',
            'cost_tier': 'high'}))
        self.assertEqual(result['status'], 'reported')
        self.assertEqual(result['models_used'], ['provider/coding-model'])
        self.assertEqual((self.root / 'task.txt').read_text(), 'feito')
        self.assertIn('Subagente master/0001', approvals[0])
        self.assertEqual(requests[0][0], 'openrouter/auto')
        self.assertEqual(requests[0][3]['cost_tier'], 'high')
        self.assertEqual(requests[0][3]['session_id'], result['id'])
        self.assertEqual([message['role'] for message in requests[0][1]], ['system', 'user'])
        self.assertNotIn('delegate_task', [tool['function']['name'] for tool in requests[0][2]])
        history = json.loads(Path(result['history']).read_text())
        self.assertEqual(history['parent_id'], self.parent_id)
        self.assertEqual(history['status'], 'reported')
        self.assertEqual(ChatStore(self.root).list(), [])
        self.assertTrue(any('provider/coding-model' in notice for notice in progress))

    def test_different_tasks_get_different_sessions_and_can_choose_different_models(self):
        calls = []
        class Client:
            def complete(inner, model, messages, tools, **options):
                calls.append(options)
                return ModelReply({'role': 'assistant', 'content': 'Relatório'},
                                  'provider/' + options['cost_tier'])
        tools = SubagentTools(ProjectTools(self.root, lambda _: False), Client(), self.parent_id, lambda _: None)
        first = json.loads(tools.execute('delegate_task', {'title': 'Leitura', 'task': 'Consultar fontes', 'cost_tier': 'low'}))
        second = json.loads(tools.execute('delegate_task', {'title': 'Correção', 'task': 'Investigar bug', 'cost_tier': 'high'}))
        self.assertNotEqual(calls[0]['session_id'], calls[1]['session_id'])
        self.assertNotEqual(first['models_used'], second['models_used'])

    def test_tier_limit_rejects_task_before_api_call(self):
        class Client:
            def complete(inner, *args, **kwargs):
                self.fail('API não deveria ser chamada')
        tools = SubagentTools(ProjectTools(self.root, lambda _: False), Client(), self.parent_id,
                              lambda _: None, max_tier='medium')
        result = tools.execute('delegate_task', {'title': 'Task', 'task': 'Trabalho', 'cost_tier': 'high'})
        self.assertIn('máximo medium', result)
        self.assertFalse((self.root / '.centaur/agents').exists())

    def test_failed_child_preserves_history_and_does_not_claim_success(self):
        class Client:
            def complete(inner, *args, **kwargs):
                raise RuntimeError('Falha com secret')
        tools = SubagentTools(ProjectTools(self.root, lambda _: False, 'secret'), Client(),
                              self.parent_id, lambda _: None)
        result = json.loads(tools.execute('delegate_task', {'title': 'Task', 'task': 'Trabalho'}))
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('secret', result['report'])
        self.assertEqual(json.loads(Path(result['history']).read_text())['status'], 'failed')

    def test_subagent_write_refusal_keeps_file_unchanged(self):
        (self.root / 'task.txt').write_text('original')
        class Client:
            def complete(inner, model, messages, tools, **options):
                if messages[-1]['role'] == 'user':
                    return {'role': 'assistant', 'content': None, 'tool_calls': [{
                        'id': 'write', 'type': 'function', 'function': {'name': 'write_file',
                        'arguments': '{"path":"task.txt","content":"alterado"}'}}]}
                self.assertIn('recusada', messages[-1]['content'])
                return {'role': 'assistant', 'content': 'Alteração recusada; task pendente.'}
        tools = SubagentTools(ProjectTools(self.root, lambda _: False), Client(),
                              self.parent_id, lambda _: None)
        result = json.loads(tools.execute('delegate_task', {'title': 'Task', 'task': 'Edite task.txt'}))
        self.assertEqual((self.root / 'task.txt').read_text(), 'original')
        self.assertIn('pendente', result['report'])

    def test_explicit_task_model_is_preserved(self):
        calls = []
        class Client:
            def complete(inner, model, messages, tools, **options):
                calls.append(model)
                return ModelReply({'role': 'assistant', 'content': 'Relatório'}, model)
        tools = SubagentTools(ProjectTools(self.root, lambda _: False), Client(),
                              self.parent_id, lambda _: None)
        tools.execute('delegate_task', {'title': 'Task', 'task': 'Modelo autorizado pela task',
                                       'model': 'provider/explicit'})
        self.assertEqual(calls, ['provider/explicit'])

    def test_coordinator_receives_child_report_and_keeps_its_original_model(self):
        class Client:
            def complete(inner, model, messages, tools, **options):
                if model == 'openrouter/auto':
                    return ModelReply({'role': 'assistant', 'content': 'Relatório da task'}, 'provider/chosen')
                if messages[-1]['role'] == 'user':
                    return {'role': 'assistant', 'content': None, 'tool_calls': [{
                        'id': 'delegate', 'type': 'function', 'function': {'name': 'delegate_task',
                        'arguments': json.dumps({'title': 'Task 01', 'task': 'Consultar fontes'})}}]}
                self.assertIn('Relatório da task', messages[-1]['content'])
                return {'role': 'assistant', 'content': 'Conferir evidências antes de consolidar.'}
        store = ChatStore(self.root)
        chat = store.new('provider/coordinator')
        chat['messages'].append({'role': 'user', 'content': '/run master/0001'})
        client = Client()
        tools = SubagentTools(ProjectTools(self.root, lambda _: False), client, chat['id'], lambda _: None)
        run_turn(chat, client, tools, store, lambda: None)
        self.assertEqual(chat['model'], 'provider/coordinator')
        self.assertEqual(len(store.list()), 1)
        self.assertIn('Conferir evidências', chat['messages'][-1]['content'])

    def test_local_clean_code_dependency_is_readable_but_cannot_escape_its_directory(self):
        folder = self.root / '.centaur/skills/clean-code'
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text('name: clean-code\nInstruções locais')
        tools = ProjectTools(self.root, lambda _: False)
        self.assertIn('Instruções locais', tools.execute('read_skill', {'path': 'clean-code/SKILL.md', 'start_line': '1'}))
        self.assertIn('Erro', tools.execute('read_skill', {'path': 'clean-code/../../../secret', 'start_line': '1'}))


if __name__ == '__main__':
    unittest.main()
