import curses
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from centaur_cli.agent import run_turn
from centaur_cli.appearance import TerminalView, cell_width, fit_cells
from centaur_cli.backends import resolve_effort
from centaur_cli.config import load_config, save_config
from centaur_cli.history import ChatStore
from centaur_cli.native_client import NativeClient
from centaur_cli.openrouter import OpenRouter
from centaur_cli.settings import ConfigPicker
from centaur_cli.terminal import Terminal, read_key
from centaur_cli.tools import ProjectTools


class Screen:
    def __init__(self, size):
        self.size, self.output, self.cursor = size, [], None
    def getmaxyx(self): return self.size
    def bkgd(self, *args): pass
    def erase(self): self.output.clear()
    def refresh(self): pass
    def move(self, row, column):
        assert 0 <= row < self.size[0] and 0 <= column < self.size[1]
        self.cursor = (row, column)
    def addnstr(self, row, column, text, length, style):
        assert 0 <= row < self.size[0] and 0 <= column < self.size[1]
        assert column + cell_width(text[:length]) < self.size[1]
        self.output.append((row, column, text[:length], style))
    def text(self): return '\n'.join(entry[2] for entry in self.output)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = ChatStore(self.root)
        self.terminal = Terminal(self.root, 'provider/main', self.store, None, effort='high')

    def test_shift_left_and_plain_left_editing_are_distinct(self):
        terminal = self.terminal
        terminal.draft = 'abcd'
        terminal.handle(curses.KEY_LEFT)
        terminal.handle('X')
        self.assertEqual(terminal.draft, 'abcXd')
        self.assertFalse(terminal.browser)
        terminal.handle(curses.KEY_HOME)
        terminal.handle(curses.KEY_DC)
        self.assertEqual(terminal.draft, 'bcXd')
        terminal.handle(curses.KEY_END)
        terminal.handle(curses.KEY_BACKSPACE)
        self.assertEqual(terminal.draft, 'bcX')
        terminal.handle(curses.KEY_SLEFT)
        terminal.handle('\x1b')
        self.assertEqual(terminal.draft, 'bcX')

    def test_shift_left_fallback_preserves_escape_and_unrelated_keys(self):
        class InputScreen:
            def __init__(self, keys): self.keys, self.timeouts = list(keys), []
            def get_wch(self):
                if not self.keys: raise curses.error()
                return self.keys.pop(0)
            def timeout(self, value): self.timeouts.append(value)
        screen = InputScreen('\x1b[1;2D')
        self.assertEqual(read_key(screen), curses.KEY_SLEFT)
        self.assertEqual(screen.timeouts, [25, 100])
        with patch('centaur_cli.terminal.curses.unget_wch') as restore:
            self.assertEqual(read_key(InputScreen('\x1bX')), '\x1b')
            restore.assert_called_once_with('X')
        self.assertEqual(read_key(InputScreen('\x1b')), '\x1b')

    def test_wide_text_viewport_keeps_the_cursor_content_visible(self):
        terminal = self.terminal
        terminal.draft = '汉' * 25 + 'END'
        screen = Screen((24, 40))
        TerminalView().draw(screen, terminal)
        line = next(entry[2] for entry in screen.output if entry[:2] == (21, 4))
        self.assertTrue(line.endswith('END'))
        self.assertEqual(screen.cursor, (21, 4 + cell_width(line)))

    def test_custom_model_reconciles_unsupported_effort(self):
        picker = ConfigPicker('openrouter', 'deep', 'high')
        picker.model_efforts = {'deep': ['default', 'high'], 'plain': ['default']}
        picker.page, picker.query = 'custom', 'plain'
        picker.handle('\n')
        self.assertEqual((picker.model, picker.effort), ('plain', 'default'))

    def test_chats_command_is_an_alternative_shortcut(self):
        self.terminal.draft = '/chats'
        self.terminal.submit()
        self.assertTrue(self.terminal.browser)
        self.assertFalse(self.terminal.chat['messages'])

    def test_rename_survives_restart_and_preserves_id_model_and_messages(self):
        chat = self.terminal.chat
        chat['messages'] = [{'role': 'user', 'content': 'Antes'}]
        self.store.save(chat)
        self.terminal.open_chats()
        self.terminal.handle('r')
        self.terminal.handle('\x15')
        for char in 'Arquitetura': self.terminal.handle(char)
        self.terminal.handle('\n')
        renamed = ChatStore(self.root).list()[0]
        self.assertEqual(renamed['id'], chat['id'])
        self.assertEqual(renamed['model'], chat['model'])
        self.assertEqual(renamed['messages'], chat['messages'])
        self.assertEqual(renamed['title'], 'Arquitetura')
        self.assertIsNone(self.terminal.rename_target)
        self.assertEqual(self.terminal.chat['title'], 'Arquitetura')

    def test_rename_cancel_failure_and_busy_preserve_history(self):
        terminal = self.terminal
        self.store.save(terminal.chat)
        terminal.begin_rename(terminal.chat)
        terminal.handle('\x15')
        terminal.handle('\n')
        self.assertIsNotNone(terminal.rename_target)
        self.assertIn('1 a 80', terminal.notice)
        terminal.handle('\x1b')
        self.assertEqual(self.store.list()[0]['title'], 'Novo chat')
        with patch.object(self.store, 'rename', side_effect=PermissionError('negado')):
            self.assertFalse(terminal.rename_chat(terminal.chat, 'Novo nome'))
        terminal.busy = True
        terminal.begin_rename(terminal.chat)
        self.assertIsNone(terminal.rename_target)
        self.assertEqual(self.store.list()[0]['title'], 'Novo chat')

    def test_rename_does_not_overwrite_newer_disk_messages(self):
        chat = self.store.new('test')
        self.store.save(chat)
        newer = dict(chat, messages=[{'role': 'user', 'content': 'Mais recente'}])
        self.store.save(newer)
        renamed = self.store.rename(chat['id'], 'Título')
        self.assertEqual(renamed['messages'], newer['messages'])
        for title in ('', 'a' * 81, 'quebra\nlinha', '\x1bcontrole'):
            with self.assertRaises(ValueError): self.store.rename(chat['id'], title)
        with self.assertRaises(ValueError): self.store.rename('../escape', 'Título')

    def test_manual_novo_chat_title_is_not_replaced_on_submit(self):
        terminal = self.terminal
        self.store.save(terminal.chat)
        terminal.rename_chat(terminal.chat, 'Novo chat')
        terminal.draft = 'Primeira mensagem'
        with patch('centaur_cli.terminal.threading.Thread'):
            terminal.submit()
        self.assertEqual(terminal.chat['title'], 'Novo chat')

    def test_picker_cancel_does_not_write_configuration_or_history(self):
        terminal = self.terminal
        terminal.configure('$config')
        terminal.handle('\n')
        terminal.handle(curses.KEY_DOWN)
        terminal.handle('\n')
        self.assertEqual(terminal.settings.backend, 'codex')
        terminal.handle('\x1b')
        self.assertIsNone(terminal.settings)
        self.assertEqual(load_config(self.root), {})
        self.assertEqual(self.store.list(), [])

    def test_picker_custom_model_effort_and_invalid_input(self):
        picker = ConfigPicker('claude', 'sonnet', 'default')
        picker.row = 1
        picker.handle('\n')
        picker.selected = 1
        picker.handle('\n')
        picker.query = '--unsafe'
        picker.handle('\n')
        self.assertEqual(picker.page, 'custom')
        self.assertTrue(picker.error)
        picker.query = 'opus'
        picker.handle('\n')
        self.assertEqual(picker.model, 'opus')
        picker.row = 2
        picker.handle('\n')
        self.assertNotIn('none', [value for value, label in picker.options()])
        picker.selected = 3
        picker.handle('\n')
        self.assertEqual(picker.effort, 'high')

    def test_search_is_local_and_can_be_cleared(self):
        picker = ConfigPicker('openrouter', '', 'default')
        picker.catalog = {'a/fast': '', 'b/deep': ''}
        picker.row = 1
        picker.handle('\n')
        picker.handle('f')
        self.assertEqual([value for value, _ in picker.options()], ['', None, 'a/fast'])
        picker.handle('\x15')
        self.assertEqual(len(picker.options()), 4)

    def test_async_apply_success_and_failure_keep_original_chat_until_saved(self):
        terminal = self.terminal
        original = terminal.chat['id']
        self.store.save(terminal.chat)
        terminal.configure('$config')
        picker = terminal.settings
        picker.row, picker.effort = 3, 'low'
        class ImmediateThread:
            def __init__(self, target, **kwargs): self.target = target
            def start(self): self.target()
        client = type('Client', (), {'backend': 'openrouter'})()
        with patch('centaur_cli.terminal.threading.Thread', ImmediateThread), \
                patch('centaur_cli.terminal.create_client', return_value=client), \
                patch('centaur_cli.terminal.save_config', side_effect=PermissionError('negado')):
            terminal.handle('\n')
            self.assertEqual(terminal.chat['id'], original)
            terminal.drain_events()
        self.assertIs(terminal.settings, picker)
        self.assertIn('negado', picker.error)
        self.assertFalse(picker.pending)
        with patch('centaur_cli.terminal.threading.Thread', ImmediateThread), \
                patch('centaur_cli.terminal.create_client', return_value=client):
            terminal.handle('\n')
            terminal.drain_events()
        self.assertIsNone(terminal.settings)
        self.assertEqual(load_config(self.root)['effort'], 'low')
        self.assertEqual(terminal.chat['effort'], 'low')
        self.assertNotEqual(terminal.chat['id'], original)
        self.assertEqual(self.store.list()[0]['id'], original)

    def test_public_catalog_does_not_require_credentials_when_switching_backends(self):
        terminal = self.terminal
        terminal.backend = 'codex'
        terminal.configure('$config')
        terminal.settings.backend, terminal.settings.page = 'openrouter', 'model'
        class ImmediateThread:
            def __init__(self, target, **kwargs): self.target = target
            def start(self): self.target()
        response = BytesIO(b'{"data":[{"id":"public/model","supported_parameters":["tools"]}]}')
        with patch('centaur_cli.terminal.threading.Thread', ImmediateThread), \
                patch('centaur_cli.openrouter.urlopen', return_value=response) as request:
            terminal.load_catalog(terminal.settings)
            terminal.drain_events()
        self.assertNotIn('Authorization', dict(request.call_args.args[0].header_items()))
        self.assertIn('public/model', terminal.settings.catalog)

    def test_status_analysis_uses_saved_effort_without_write_tools(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from centaur_cli.status_command import main as status_main
        save_config(self.root, 'openrouter', 'provider/main', 'high')
        requests = []
        class Client:
            backend, secrets = 'openrouter', ()
            def complete(self, model, messages, definitions, **options):
                requests.append((definitions, options))
                return {'role': 'assistant', 'content': 'Somente leitura'}
        with patch('centaur_cli.status_command.create_client', return_value=Client()), \
                patch.dict(os.environ, {}, clear=True), redirect_stdout(StringIO()):
            status_main([str(self.root), '--ai'])
        self.assertEqual(requests[0][1], {'effort': 'high'})
        self.assertNotIn('write_file', [entry['function']['name'] for entry in requests[0][0]])

    def test_closed_picker_ignores_delayed_catalog(self):
        terminal = self.terminal
        terminal.configure('$config')
        old = terminal.settings
        terminal.settings = None
        terminal.events.put(('catalog', (old, 'openrouter', ({'late': ''}, {}, ''))))
        terminal.drain_events()
        self.assertNotIn('late', old.catalog)

    def test_effort_defaults_are_backward_compatible_and_overrides_are_explicit(self):
        save_config(self.root, 'codex', 'main')
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_effort(self.root, 'codex'), 'default')
        save_config(self.root, 'codex', 'main', 'high')
        with patch.dict(os.environ, {'CENTAUR_EFFORT': 'low'}, clear=True):
            self.assertEqual(resolve_effort(self.root, 'codex'), 'low')
            self.assertEqual(resolve_effort(self.root, 'codex', 'medium'), 'medium')
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_effort(self.root, 'claude'), 'default')
        with self.assertRaises(ValueError): save_config(self.root, 'claude', 'sonnet', 'none')

    def test_saved_effort_reaches_actual_model_request(self):
        chat = self.store.new('main')
        chat['effort'] = 'high'
        class Client:
            def complete(self, model, messages, tools, *, effort):
                assert effort == 'high'
                return {'role': 'assistant', 'content': 'Pronto'}
        run_turn(chat, Client(), ProjectTools(self.root, lambda _: False), self.store, lambda: None)
        self.assertEqual(self.store.list()[0]['effort'], 'high')

    def test_openrouter_payload_and_default_omission(self):
        for effort in ('high', 'default'):
            response = BytesIO(b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}')
            with patch('centaur_cli.openrouter.urlopen', return_value=response) as request:
                OpenRouter('fake').complete('main', [], [], effort=effort)
            payload = json.loads(request.call_args.args[0].data)
            if effort == 'high': self.assertEqual(payload['reasoning'], {'effort': 'high'})
            else: self.assertNotIn('reasoning', payload)

    def test_live_catalog_filters_models_and_effort_by_capability(self):
        data = {'data': [
            {'id': 'plain', 'supported_parameters': ['tools']},
            {'id': 'deep', 'supported_parameters': ['tools'],
             'reasoning': {'supported_efforts': ['none', 'low', 'high'], 'mandatory': True}},
            {'id': 'no-tools', 'supported_parameters': []}]}
        client = OpenRouter('fake')
        with patch('centaur_cli.openrouter.urlopen', return_value=BytesIO(json.dumps(data).encode())):
            catalog = client.model_catalog()
        self.assertEqual(set(catalog), {'plain', 'deep'})
        self.assertEqual(client.model_efforts['plain'], ['default'])
        picker = ConfigPicker('openrouter', 'deep', 'high')
        picker.model_efforts = client.model_efforts
        picker.page = 'effort'
        self.assertEqual([value for value, _ in picker.options()], ['default', 'low', 'high'])
        with self.assertRaises(ValueError): client.complete('plain', [], [], effort='high')

    def test_native_effort_arguments_preserve_isolation(self):
        for backend in ('codex', 'claude'):
            with patch('centaur_cli.native_client.shutil.which', return_value='/fake/' + backend):
                client = NativeClient(backend, 'main')
            args = client.arguments(self.root, effort='high')
            if backend == 'codex':
                self.assertIn('model_reasoning_effort="high"', args)
                self.assertIn('--ignore-user-config', args)
                self.assertEqual(args[-1], '-')
            else:
                self.assertEqual(args[args.index('--effort') + 1], 'high')
                self.assertIn('--safe-mode', args)

    def test_native_picker_uses_advertised_model_efforts(self):
        with patch.dict(os.environ, {'CODEX_HOME': str(self.root)}):
            (self.root / 'models_cache.json').write_text(json.dumps({'models': [
                {'slug': 'main', 'visibility': 'list', 'supported_reasoning_levels': [
                    {'effort': 'low'}, {'effort': 'high'}, {'effort': 'max'}]}]}))
            picker = ConfigPicker('codex', 'main', 'default')
        picker.page = 'effort'
        self.assertEqual([value for value, _ in picker.options()], ['default', 'low', 'high', 'max'])

    def test_layout_states_and_resize_preserve_focus_draft_and_selection(self):
        terminal = self.terminal
        terminal.draft = '消息😀 rascunho muito longo ' * 10
        terminal.cursor = 8
        self.store.save(terminal.chat)
        view = TerminalView()
        for size in ((34, 110), (24, 80), (18, 45), (12, 40)):
            screen = Screen(size)
            view.draw(screen, terminal)
            original = terminal.draft
            terminal.open_chats()
            view.draw(screen, terminal)
            terminal.browser = False
            terminal.configure('$config')
            for page in ('fields', 'model', 'effort', 'custom'):
                terminal.settings.page = page
                view.draw(screen, terminal)
            terminal.settings = None
            terminal.draft = original
            terminal.begin_rename(terminal.chat)
            view.draw(screen, terminal)
            self.assertEqual(terminal.draft, original)
            terminal.rename_target = None
        self.assertEqual(fit_cells('汉字abc', 5), '汉字a')

    def test_activity_moves_and_reduced_motion_is_static(self):
        view = TerminalView()
        self.terminal.busy_started = 0
        with patch('centaur_cli.appearance.time.monotonic', return_value=10):
            first = view.activity(self.terminal, 'Aguardando')
        with patch('centaur_cli.appearance.time.monotonic', return_value=10.13):
            second = view.activity(self.terminal, 'Aguardando')
        self.assertNotEqual(first[0], second[0])
        with patch.dict(os.environ, {'CENTAUR_REDUCED_MOTION': '1'}):
            self.assertTrue(view.activity(self.terminal, 'Aguardando').startswith('•'))


if __name__ == '__main__': unittest.main()
