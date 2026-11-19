import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from centaur_cli import skill_catalog
from centaur_cli.agent import project_prompt, run_turn
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

    def test_explore_mode_is_read_only_with_a_short_prompt_and_no_project_instructions(self):
        (self.root / 'AGENTS.md').write_text('REGRA-DO-PROJETO ' * 200, encoding='utf-8')
        requests = []
        class Client:
            def complete(inner, model, messages, tools, **options):
                requests.append((model, list(messages), tools, options))
                return ModelReply({'role': 'assistant', 'content': 'Achado em app.py:3.'}, 'provider/fast')
        base = ProjectTools(self.root, lambda _: True, ask_user=lambda question, options: 'x')
        tools = SubagentTools(base, Client(), self.parent_id, lambda _: None)
        result = json.loads(tools.execute('delegate_task', {'title': 'Onde fica X', 'task': 'Localize X.', 'mode': 'explore'}))
        self.assertEqual((result['status'], result['mode'], result['cost_tier']), ('reported', 'explore', 'low'))
        names = [tool['function']['name'] for tool in requests[0][2]]
        self.assertEqual(sorted(names), ['command_output', 'glob', 'grep', 'list_files', 'read_file', 'read_skill',
                                         'run_command', 'submit_report'])
        system = requests[0][1][0]['content']
        self.assertNotIn('REGRA-DO-PROJETO', system)
        self.assertIn('AGENTS.md e não foram carregadas', system)
        self.assertIn('até 400 palavras', system)
        self.assertLess(len(system), len(project_prompt(self.root)) / 3)
        # Uma task comum continua com o prompt completo e as ferramentas de gravação.
        requests.clear()
        tools.execute('delegate_task', {'title': 'Task', 'task': 'Trabalho'})
        self.assertIn('REGRA-DO-PROJETO', requests[0][1][0]['content'])
        self.assertIn('write_file', [tool['function']['name'] for tool in requests[0][2]])
        self.assertIn('Falha ao delegar task', tools.execute('delegate_task', {'title': 'T', 'task': 'x', 'mode': 'write'}))

    def test_explore_executor_cannot_write_or_delegate_even_if_it_asks(self):
        base = ProjectTools(self.root, lambda _: True, approval_mode='never')
        base.definitions = [entry for entry in base.definitions if entry['function']['name'] in ('read_file', 'grep')]
        base.owned = [[]]
        reader = SubagentTools(base, Mock(allows_model_routing=True), self.parent_id, lambda _: None, executor=True, explore=True)
        for name, arguments in (('write_file', {'path': 'a.txt', 'content': 'x'}), ('delegate_task', {'title': 't', 'task': 'x'})):
            self.assertIn('somente leitura', reader.execute(name, arguments))
        self.assertFalse((self.root / 'a.txt').exists())
        self.assertIn('fora dos arquivos de posse', base.execute('write_file', {'path': 'a.txt', 'content': 'x'}))

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
        self.assertIn('delegate_task', [tool['function']['name'] for tool in requests[0][2]])
        history = json.loads(Path(result['history']).read_text())
        self.assertEqual(history['parent_id'], self.parent_id)
        self.assertEqual(history['status'], 'reported')
        self.assertEqual(ChatStore(self.root).list(), [])
        self.assertTrue(any('provider/coding-model' in notice for notice in progress))
        self.assertEqual(result['changed'], {'files': 1, 'lines': 1})
        self.assertNotIn('review_note', result)
        self.assertTrue(base.turn_acted)  # O principal confere o trabalho delegado ao encerrar.

    def test_large_delivery_is_flagged_for_the_coordinator_to_review_in_parts(self):
        replies = [ModelReply({'role': 'assistant', 'content': None, 'tool_calls': [{
            'id': 'write', 'type': 'function', 'function': {'name': 'write_file', 'arguments': json.dumps(
                {'path': 'big.py', 'content': ''.join(f'x{n} = {n}\n' for n in range(450))})}}]}, 'm'),
            ModelReply({'role': 'assistant', 'content': 'Pronto.'}, 'm')]
        class Client:
            def complete(inner, *args, **options): return replies.pop(0)
        tools = SubagentTools(ProjectTools(self.root, lambda _: True, approval_mode='never'), Client(), self.parent_id, lambda _: None)
        result = json.loads(tools.execute('delegate_task', {'title': 'master/0002 — Task 01', 'task': 'Crie big.py.', 'cost_tier': 'low'}))
        self.assertEqual(result['changed'], {'files': 1, 'lines': 450})
        self.assertIn('Entrega grande: ~450 linhas', result['review_note'])

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

    def test_executor_structured_report_reaches_the_coordinator_and_the_principal_has_no_such_tool(self):
        class Client:
            def complete(inner, model, messages, tools, **options):
                self.assertIn('submit_report', [entry['function']['name'] for entry in tools])
                if messages[-1]['role'] == 'user':
                    return {'role': 'assistant', 'content': None, 'tool_calls': [{
                        'id': 'report', 'type': 'function', 'function': {'name': 'submit_report', 'arguments': json.dumps({
                            'summary': 'CI cobre staging', 'files': ['ci.yml'], 'checks': ['actionlint · passou'], 'pending': ['deploy']})}}]}
                return ModelReply({'role': 'assistant', 'content': 'Relatório livre'}, 'provider/chosen')
        tools = SubagentTools(ProjectTools(self.root, lambda _: False), Client(), self.parent_id, lambda _: None)
        self.assertNotIn('submit_report', [entry['function']['name'] for entry in tools.definitions])
        self.assertIn('desconhecida', tools.execute('submit_report', {'summary': 'x'}))
        result = json.loads(tools.execute('delegate_task', {'title': 'Task', 'task': 'Ajustar CI'}))
        self.assertEqual(result['report'], 'Relatório livre')
        self.assertEqual(result['structured'], {'summary': 'CI cobre staging', 'files': ['ci.yml'], 'checks': ['actionlint · passou'],
                                                'pending': ['deploy'], 'blockers': []})

    def test_review_delegation_carries_the_git_diff_and_rejects_unsafe_refs(self):
        git = lambda *arguments: subprocess.run(['git', '-C', str(self.root), *arguments], check=True, capture_output=True)
        git('init', '-q')
        (self.root / 'app.py').write_text('valor = 1\n')
        (self.root / 'other.py').write_text('outro = 1\n')
        git('add', '.')
        git('-c', 'user.name=t', '-c', 'user.email=t@example.invalid', 'commit', '-q', '-m', 'base')
        (self.root / 'app.py').write_text('valor = 2\n')
        (self.root / 'other.py').write_text('outro = 2\n')
        (self.root / 'novo.py').write_text('novo = 1\n')
        seen = []
        class Client:
            def complete(inner, model, messages, tools, **options):
                seen.append(messages[1]['content'])
                return ModelReply({'role': 'assistant', 'content': 'Sem achados'}, 'provider/chosen')
        tools = SubagentTools(ProjectTools(self.root, lambda _: False), Client(), self.parent_id, lambda _: None)
        tools.execute('delegate_task', {'title': 'Revisão', 'task': 'Revise a onda 1', 'diff': {'base': 'HEAD', 'paths': ['app.py', 'novo.py']}})
        self.assertTrue(seen[0].startswith('Revise a onda 1\n\n[Anexado pelo harness: git diff HEAD -- app.py novo.py.'))
        self.assertIn('+valor = 2', seen[0])
        self.assertNotIn('outro = 2', seen[0])
        self.assertIn('não rastreados (não aparecem no diff; leia-os): novo.py', seen[0])
        for unsafe in ({'base': '--output=/tmp/x'}, {'base': 'HEAD', 'paths': ['../fora']}, {'base': 'HEAD', 'paths': ['-p']}, {'base': 'ref-inexistente'}):
            self.assertIn('Falha ao delegar task', tools.execute('delegate_task', {'title': 'Revisão', 'task': 'x', 'diff': unsafe}))
        self.assertEqual(len(seen), 1)

    def test_project_skill_is_read_before_the_packaged_one_and_says_so(self):
        folder = self.root / '.centaur/skills/run'
        (folder / 'references').mkdir(parents=True)
        (folder / 'SKILL.md').write_text('name: run\nFluxo local')
        (folder / 'references/guide.md').write_text('Guia local')
        (self.root / '.centaur/skills/ponytail').mkdir()
        (self.root / '.centaur/skills/ponytail/SKILL.md').write_text('name: ponytail\nSó no projeto')
        tools = ProjectTools(self.root, lambda _: False)
        read = lambda path: tools.execute('read_skill', {'path': path, 'start_line': '1'})
        self.assertIn('Fluxo local', read('run/SKILL.md'))
        self.assertIn('do projeto (.centaur/skills/run), no lugar da skill do CLI', read('run/SKILL.md').splitlines()[0])
        self.assertIn('Guia local', read('run/references/guide.md'))
        self.assertIn('Fluxo local', read('@run/SKILL.md'))
        self.assertIn('Só no projeto', read('ponytail/SKILL.md'))
        self.assertNotIn('no lugar', read('ponytail/SKILL.md').splitlines()[0])
        self.assertTrue(read('spec/SKILL.md').startswith('Skill: spec/SKILL.md | linhas'))  # Sem cópia local, vale o pacote.
        self.assertIn('Erro', read('run/../../../secret'))
        self.assertEqual(skill_catalog.local_overrides(self.root), ['run'])
        prompt = project_prompt(self.root)
        self.assertIn('substituem as do CLI nesta pasta: run.', prompt)

    def test_local_clean_code_dependency_is_readable_but_cannot_escape_its_directory(self):
        folder = self.root / '.centaur/skills/clean-code'
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text('name: clean-code\nInstruções locais')
        tools = ProjectTools(self.root, lambda _: False)
        self.assertIn('Instruções locais', tools.execute('read_skill', {'path': 'clean-code/SKILL.md', 'start_line': '1'}))
        self.assertIn('Erro', tools.execute('read_skill', {'path': 'clean-code/../../../secret', 'start_line': '1'}))


if __name__ == '__main__':
    unittest.main()
