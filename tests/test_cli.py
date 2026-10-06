import curses
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from centaur_cli.agent import run_turn
from centaur_cli.history import ChatStore
from centaur_cli.openrouter import OpenRouter
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools
from centaur_cli import skill_catalog


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = ChatStore(self.root)

    def test_history_survives_restart_and_is_scoped_to_folder(self):
        chat = self.store.new('test/model')
        chat['messages'] = [{'role': 'user', 'content': 'Olá'}]
        self.store.save(chat)
        self.assertEqual(ChatStore(self.root).list()[0]['messages'], chat['messages'])
        self.assertEqual(ChatStore(self.root / 'other').list(), [])
        self.assertEqual(len(list(self.store.directory.glob('*.json'))), 1)
        self.assertEqual(list(self.store.directory.glob('*.tmp')), [])

    def test_corrupt_history_does_not_hide_valid_chats(self):
        self.store.save(self.store.new('test'))
        (self.store.directory / 'broken.json').write_text('{')
        self.assertEqual(len(self.store.list()), 1)

    def test_left_opens_chats_and_enter_resumes_selected_conversation(self):
        first = self.store.new('model/first')
        first['title'] = 'Primeiro'
        self.store.save(first)
        second = self.store.new('model/second')
        second['title'] = 'Segundo'
        self.store.save(second)
        terminal = Terminal(self.root, 'default', self.store, None)
        terminal.draft = 'rascunho'
        terminal.handle(curses.KEY_LEFT)
        self.assertTrue(terminal.browser)
        self.assertEqual(len(terminal.chats), 2)
        terminal.handle(curses.KEY_DOWN)
        terminal.handle('\n')
        self.assertFalse(terminal.browser)
        self.assertEqual(terminal.chat['id'], first['id'])
        self.assertEqual(terminal.chat['model'], 'model/first')

    def test_chat_switch_is_blocked_during_request(self):
        self.store.save(self.store.new('test'))
        terminal = Terminal(self.root, 'test', self.store, None)
        current = terminal.chat['id']
        terminal.busy = True
        terminal.handle(curses.KEY_LEFT)
        terminal.handle('\n')
        self.assertEqual(terminal.chat['id'], current)

    def test_delete_removes_selected_chat_from_disk_and_preserves_other_chat(self):
        first = self.store.new('first')
        self.store.save(first)
        second = self.store.new('second')
        self.store.save(second)
        terminal = Terminal(self.root, 'test', self.store, None)
        terminal.handle(curses.KEY_LEFT)
        terminal.handle(curses.KEY_DOWN)
        terminal.handle(curses.KEY_DC)
        self.assertTrue(terminal.browser)
        self.assertEqual([chat['id'] for chat in ChatStore(self.root).list()], [second['id']])
        self.assertFalse((self.store.directory / (first['id'] + '.json')).exists())
        self.assertEqual(terminal.selected, 0)
        terminal.handle('\n')
        self.assertEqual(terminal.chat['id'], second['id'])

    def test_delete_current_chat_starts_new_chat_without_restoring_deleted_history(self):
        terminal = Terminal(self.root, 'test', self.store, None)
        previous = terminal.chat['id']
        terminal.chat['messages'].append({'role': 'user', 'content': 'Anterior'})
        self.store.save(terminal.chat)
        terminal.handle(curses.KEY_LEFT)
        terminal.handle(curses.KEY_DC)
        self.assertNotEqual(terminal.chat['id'], previous)
        self.assertEqual(terminal.chat['messages'], [])
        self.assertEqual(self.store.list(), [])
        self.assertEqual(terminal.selected, 0)
        terminal.handle(curses.KEY_DC)
        self.assertEqual(self.store.list(), [])

    def test_delete_active_chat_is_blocked_but_other_chat_can_be_deleted(self):
        terminal = Terminal(self.root, 'test', self.store, None)
        self.store.save(terminal.chat)
        terminal.busy = True
        terminal.handle(curses.KEY_LEFT)
        terminal.handle(curses.KEY_DC)
        self.assertEqual(len(self.store.list()), 1)
        other = self.store.new('other')
        self.store.save(other)
        terminal.handle(curses.KEY_LEFT)
        terminal.handle(curses.KEY_DC)
        self.assertEqual([chat['id'] for chat in self.store.list()], [terminal.chat['id']])

    def test_delete_failure_preserves_selection_and_history(self):
        self.store.save(self.store.new('test'))
        terminal = Terminal(self.root, 'test', self.store, None)
        terminal.handle(curses.KEY_LEFT)
        with patch.object(self.store, 'delete', side_effect=PermissionError('negado')):
            terminal.handle(curses.KEY_DC)
        self.assertEqual(len(terminal.chats), 1)
        self.assertEqual(len(self.store.list()), 1)
        self.assertIn('Não foi possível', terminal.notice)

    def test_delete_rejects_paths_outside_chat_store(self):
        with self.assertRaises(ValueError):
            self.store.delete('../outside')

    def test_tools_reject_traversal_and_symlinks_outside_folder(self):
        tools = ProjectTools(self.root, lambda _: True)
        self.assertIn('Erro', tools.execute('read_file', {'path': '../secret'}))
        (self.root / 'outside').symlink_to(self.root.parent, target_is_directory=True)
        self.assertIn('Erro', tools.execute('write_file', {'path': 'outside/secret', 'content': 'x'}))

    def test_bundled_skills_can_be_read_from_an_unrelated_project(self):
        tools = ProjectTools(self.root, lambda _: False)
        entry = tools.execute('read_skill', {'path': 'spec/SKILL.md', 'start_line': '1'})
        self.assertIn('name: spec', entry)
        reference = tools.execute('read_skill', {'path': 'graphify/references/lifecycle.md', 'start_line': '1'})
        self.assertNotIn('Erro na ferramenta', reference)
        self.assertIn('linhas 1–', reference)
        continuation = tools.execute('read_skill', {'path': 'spec/SKILL.md', 'start_line': '201'})
        self.assertIn('linhas 201–', continuation)
        self.assertNotEqual(entry, continuation)
        self.assertEqual(len(skill_catalog.names()), 12)

    def test_internal_memory_is_readable_but_not_a_public_skill(self):
        self.assertNotIn('memory', skill_catalog.names())
        tools = ProjectTools(self.root, lambda _: False)
        entry = tools.execute('read_skill', {'path': '_internal/memory/SKILL.md', 'start_line': '1'})
        self.assertIn('visibility: internal', entry)
        self.assertIn('dependencies: ai-memory', entry)
        reference = tools.execute('read_skill', {'path': '_internal/memory/references/contract.md', 'start_line': '1'})
        self.assertNotIn('Erro na ferramenta', reference)
        self.assertIn('linhas 1–', reference)
        self.assertIn('Erro', tools.execute('read_skill', {'path': 'memory/SKILL.md', 'start_line': '1'}))

    def test_skill_reader_cannot_escape_catalog(self):
        tools = ProjectTools(self.root, lambda _: False)
        self.assertIn('Erro', tools.execute('read_skill', {'path': '../credentials.py', 'start_line': '1'}))
        self.assertIn('Erro', tools.execute('read_skill', {'path': 'spec/SKILL.md', 'start_line': '0'}))

    def test_write_refusal_preserves_file(self):
        target = self.root / 'example.txt'
        target.write_text('original')
        tools = ProjectTools(self.root, lambda _: False)
        self.assertIn('recusada', tools.execute('write_file', {'path': 'example.txt', 'content': 'changed'}))
        self.assertEqual(target.read_text(), 'original')

    def test_approved_write_is_visible_to_read_tool(self):
        tools = ProjectTools(self.root, lambda _: True)
        tools.execute('write_file', {'path': 'src/example.txt', 'content': 'Olá'})
        self.assertEqual(tools.execute('read_file', {'path': 'src/example.txt'}), 'Olá')

    def test_shell_requires_approval(self):
        tools = ProjectTools(self.root, lambda _: False)
        self.assertIn('recusada', tools.execute('run_command', {'command': 'touch blocked'}))
        self.assertFalse((self.root / 'blocked').exists())
        tools.approve = lambda _: True
        result = tools.execute('run_command', {'command': 'pwd'})
        self.assertIn(str(self.root), result)

    def test_agent_completes_tool_round_trip_and_saves_response(self):
        (self.root / 'example.txt').write_text('contents')
        responses = [
            {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'call-1', 'type': 'function', 'function': {
                    'name': 'read_file', 'arguments': '{"path":"example.txt"}'}}]},
            {'role': 'assistant', 'content': 'Arquivo consultado.'}]
        requests = []
        class Client:
            def complete(self, model, messages, tools):
                requests.append(list(messages))
                return responses.pop(0)
        chat = self.store.new('test')
        chat['messages'].append({'role': 'user', 'content': 'Leia o arquivo'})
        run_turn(chat, Client(), ProjectTools(self.root, lambda _: False), self.store, lambda: None)
        self.assertEqual(requests[1][-1]['tool_call_id'], 'call-1')
        self.assertEqual(requests[1][-1]['content'], 'contents')
        self.assertEqual(self.store.list()[0]['messages'][-1]['content'], 'Arquivo consultado.')

    def test_interrupted_tool_is_not_reexecuted_on_resume(self):
        chat = self.store.new('test')
        chat['messages'] = [
            {'role': 'assistant', 'tool_calls': [{'id': 'interrupted', 'function': {
                'name': 'run_command', 'arguments': '{"command":"touch repeated"}'}}]},
            {'role': 'user', 'content': 'Continue'}]
        class Client:
            def complete(inner, model, messages, tools):
                self.assertEqual(messages[-2]['role'], 'tool')
                self.assertEqual(messages[-1]['role'], 'user')
                return {'role': 'assistant', 'content': 'Retomado.'}
        run_turn(chat, Client(), ProjectTools(self.root, lambda _: True), self.store, lambda: None)
        self.assertFalse((self.root / 'repeated').exists())

    def test_openrouter_sends_auth_model_and_tools(self):
        from io import BytesIO
        response = BytesIO(json.dumps({'choices': [{'message': {
            'role': 'assistant', 'content': 'Olá'}}]}).encode())
        with patch('centaur_cli.openrouter.urlopen', return_value=response) as request:
            message = OpenRouter('fake-key').complete('test/model', [{'role': 'user', 'content': 'Oi'}], [])
        sent = request.call_args.args[0]
        self.assertEqual(sent.get_header('Authorization'), 'Bearer fake-key')
        self.assertEqual(json.loads(sent.data)['model'], 'test/model')
        self.assertEqual(message['content'], 'Olá')

    def test_openrouter_error_is_reported(self):
        from io import BytesIO
        with patch('centaur_cli.openrouter.urlopen', return_value=BytesIO(b'{"error":"no credit"}')):
            with self.assertRaisesRegex(RuntimeError, 'recusou'):
                OpenRouter('fake').complete('test', [], [])


if __name__ == '__main__':
    unittest.main()
