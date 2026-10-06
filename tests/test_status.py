import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from centaur_cli.agent import run_turn
from centaur_cli.history import ChatStore
from centaur_cli.status import ANALYSIS_INSTRUCTIONS, StatusTools, render_status
from centaur_cli.status_command import main
from centaur_cli.terminal import Terminal


class StatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.put('.centaur/workspace.json', json.dumps({'scopes': {
            'master': {'specs': '.centaur/specs'},
            'api': {'specs': '.centaur/modules/api/specs'},
            'ui': {'specs': '.centaur/modules/ui/specs'}}}))

    def put(self, path, text):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def spec(self, scope, identifier, status='Pendente', parent='—', children='—', dependencies='—'):
        directory = '.centaur/specs' if scope == 'master' else f'.centaur/modules/{scope}/specs'
        self.put(f'{directory}/{identifier}/README.md',
                 f'# Entrega {scope}/{identifier}\n\n**Status:** {status}\n**Spec mestre:** {parent}\n'
                 f'**Specs filhas:** {children}\n**Dependências:** {dependencies}\n'
                 '\n## Tasks\n- [ ] Não é task do checklist\n'
                 '\n## Checklist de conclusão\n- [x] Task 01 — pronta registrada\n- [ ] Task 02 — implementar endpoint\n')

    def test_tree_links_modules_to_master_and_counts_recorded_states(self):
        self.spec('master', '0001', 'Em revisão', children='api/0001, ui/0001')
        self.spec('api', '0001', 'Concluída', parent='master/0001')
        self.spec('ui', '0001', dependencies='api/0001')
        report = render_status(self.root)
        self.assertIn('A implementar: 1 · Em revisão: 1 · Feito: 1', report)
        self.assertIn('    ├── api/0001', report)
        self.assertIn('    └── ui/0001', report)
        self.assertNotIn('\napi/\n', report)
        self.assertIn('Falta: Task 02 — implementar endpoint', report)
        self.assertNotIn('Não é task do checklist', report)
        self.assertIn('Dependências: api/0001', report)
        self.assertIn('checkboxes não são evidência', report)

    def test_cycles_missing_links_and_conflicts_are_visible_without_hiding_specs(self):
        self.spec('master', '0001', parent='api/0001', children='ui/0001, ui/ausente')
        self.spec('api', '0001', parent='master/0001')
        self.spec('ui', '0001', parent='api/0001')
        report = render_status(self.root)
        self.assertIn('ciclo entre specs', report)
        self.assertIn('filha ausente ui/ausente', report)
        self.assertIn('vínculo mestre/filha divergente', report)
        for identifier in ('master/0001', 'api/0001', 'ui/0001'):
            self.assertEqual(report.count(identifier + ' · Entrega'), 1)

    def test_invalid_workspace_does_not_fall_back_to_an_invented_scope(self):
        self.spec('master', '0001')
        self.put('.centaur/workspace.json', '{')
        report = render_status(self.root)
        self.assertIn('Workspace inválido', report)
        self.assertNotIn('Entrega master/0001', report)

    def test_paths_and_symlinks_outside_project_are_rejected(self):
        self.put('.centaur/workspace.json', json.dumps({'scopes': {'master': {'specs': '../'}}}))
        self.assertIn('Aviso: Escopo master', render_status(self.root))
        self.put('.centaur/workspace.json', json.dumps({'scopes': {'master': {'specs': 'linked'}}}))
        (self.root / 'linked').symlink_to(self.root.parent, target_is_directory=True)
        self.assertIn('Aviso: Escopo master', render_status(self.root))

    def test_legacy_and_empty_projects_work_without_configuration(self):
        (self.root / '.centaur/workspace.json').unlink()
        self.assertIn('Nenhuma spec encontrada', render_status(self.root))
        self.put('specs/0001/README.md', '# Legado\n**Status:** Concluída\n')
        self.assertIn('master/0001 · Legado [Concluída]', render_status(self.root))

    def test_terminal_status_is_local_and_invalid_option_does_not_call_ai(self):
        self.spec('master', '0001')
        store = ChatStore(self.root)
        terminal = Terminal(self.root, 'test', store, None)
        terminal.draft = '/status'
        with patch('centaur_cli.terminal.threading.Thread') as thread:
            terminal.submit()
            thread.assert_not_called()
        self.assertFalse(terminal.busy)
        self.assertIn('master/0001', terminal.chat['messages'][-1]['content'])
        terminal.draft = '/status --apply'
        terminal.submit()
        self.assertIn('Uso: /status', terminal.notice)

    def test_standalone_status_needs_neither_key_nor_interactive_terminal(self):
        self.spec('master', '0001')
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch('centaur_cli.status_command.create_client') as credentials:
            main([str(self.root)])
            credentials.assert_not_called()
        self.assertIn('master/0001', output.getvalue())
        self.assertFalse((self.root / '.centaur/chats').exists())

    def test_analysis_rejects_mutating_tools_even_if_model_requests_them(self):
        tools = StatusTools(self.root, lambda _: self.fail('Não deve pedir escrita'))
        calls = []
        class Client:
            def complete(client, model, messages, definitions):
                calls.append((messages, definitions))
                if len(calls) == 1:
                    return {'role': 'assistant', 'content': None, 'tool_calls': [{
                        'id': 'write', 'type': 'function', 'function': {'name': 'write_file',
                        'arguments': json.dumps({'path': 'should-not-exist', 'content': 'oops'})}}]}
                return {'role': 'assistant', 'content': 'Verificação pendente; não alterar o status.'}
        store = ChatStore(self.root)
        chat = store.new('test')
        chat['messages'] = [{'role': 'user', 'content': '/status --ai'}]
        run_turn(chat, Client(), tools, store, lambda: None, ANALYSIS_INSTRUCTIONS)
        self.assertFalse((self.root / 'should-not-exist').exists())
        names = [entry['function']['name'] for entry in calls[0][1]]
        self.assertEqual(set(names), {'read_skill', 'read_file', 'list_files', 'project_status', 'lifecycle_status'})
        self.assertIn('somente leitura', chat['messages'][2]['content'])
        self.assertIn('Uma mestre só pode concluir', calls[0][0][0]['content'])

    def test_analysis_detects_stale_evidence_using_canonical_hashes(self):
        from support import fixture
        fixture(self.root)
        tools = StatusTools(self.root, lambda _: False)
        def projection():
            return ''.join(tools.execute('lifecycle_status', {'start_line': str(line)})
                           for line in range(1, 1000, 200))
        before = projection()
        self.assertIn('"verification": "aprovada"', before)
        source = self.root / 'src/agenda.py'
        source.write_text(source.read_text() + '# fonte mudou\n')
        after = projection()
        self.assertIn('"verification": "desatualizada"', after)
        self.assertNotIn('"verification": "aprovada"', after)

    def test_terminal_ai_status_uses_read_only_tools(self):
        store = ChatStore(self.root)
        terminal = Terminal(self.root, 'test', store, object())
        terminal.chat['messages'] = [{'role': 'user', 'content': '/status --ai'}]
        with patch('centaur_cli.terminal.run_turn') as execute:
            terminal.work(terminal.chat)
        self.assertIsInstance(execute.call_args.args[2], StatusTools)
        self.assertIn(ANALYSIS_INSTRUCTIONS, execute.call_args.args[5])


if __name__ == '__main__':
    unittest.main()
