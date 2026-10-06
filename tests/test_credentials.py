import contextlib
import getpass
import io
import json
import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from centaur_cli.__main__ import main
from centaur_cli.credentials import CredentialStore
from centaur_cli.history import ChatStore
from centaur_cli.openrouter import OpenRouter
from centaur_cli.setup import configure_key
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = CredentialStore(self.root / 'config/centaur/credentials.json')
        self.key = 'sk-or-v1-synthetic-test-secret'

    def test_persistence_has_private_permissions_and_does_not_create_project_history(self):
        self.assertIsNone(self.store.load())
        self.store.save(self.key)
        self.assertEqual(CredentialStore(self.store.path).load(), self.key)
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.store.path.parent.stat().st_mode & 0o777, 0o700)
        self.assertFalse((self.root / '.centaur').exists())
        self.assertEqual(list(self.store.path.parent.glob('*.tmp')), [])

    def test_malformed_credentials_trigger_setup_without_printing_content(self):
        self.store.path.parent.mkdir(parents=True)
        self.store.path.write_text('{broken')
        self.assertIsNone(self.store.load())

    def test_symlink_credentials_are_not_read(self):
        target = self.root / 'secret'
        target.write_text(self.key)
        self.store.path.parent.mkdir(parents=True)
        self.store.path.symlink_to(target)
        with self.assertRaises(OSError):
            self.store.load()

    def test_wizard_validates_before_saving_and_does_not_display_key(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch('builtins.input', return_value=''), \
                patch('centaur_cli.setup.webbrowser.open', return_value=True) as browser, \
                patch('centaur_cli.setup.getpass.getpass', return_value=self.key), \
                patch.object(OpenRouter, 'validate_key') as validate:
            self.assertEqual(configure_key(self.store), self.key)
        browser.assert_called_once_with('https://openrouter.ai/settings/keys')
        validate.assert_called_once()
        self.assertEqual(self.store.load(), self.key)
        self.assertNotIn(self.key, output.getvalue())

    def test_rejected_key_is_not_saved_and_user_can_retry(self):
        with contextlib.redirect_stdout(io.StringIO()), patch('builtins.input', return_value='n'), \
                patch('centaur_cli.setup.getpass.getpass', side_effect=['rejected', self.key]), \
                patch.object(OpenRouter, 'validate_key', side_effect=[RuntimeError('Chave recusada.'), None]):
            configure_key(self.store)
        self.assertEqual(self.store.load(), self.key)

    def test_empty_input_cancels_without_writing(self):
        with contextlib.redirect_stdout(io.StringIO()), patch('builtins.input', return_value='n'), \
                patch('centaur_cli.setup.getpass.getpass', return_value=''):
            with self.assertRaisesRegex(RuntimeError, 'cancelada'):
                configure_key(self.store)
        self.assertFalse(self.store.path.exists())

    def test_echo_fallback_is_blocked(self):
        def unsafe_input(_):
            warnings.warn('Echo enabled', getpass.GetPassWarning)
            return self.key
        with contextlib.redirect_stdout(io.StringIO()), patch('builtins.input', return_value='n'), \
                patch('centaur_cli.setup.getpass.getpass', side_effect=unsafe_input):
            with self.assertRaisesRegex(RuntimeError, 'entrada oculta'):
                configure_key(self.store)
        self.assertFalse(self.store.path.exists())

    def test_api_validation_uses_only_key_endpoint_and_handles_401_without_secret(self):
        with patch('centaur_cli.openrouter.urlopen', return_value=io.BytesIO(b'{"data":{}}')) as request:
            OpenRouter(self.key).validate_key()
        sent = request.call_args.args[0]
        self.assertEqual(sent.full_url, 'https://openrouter.ai/api/v1/key')
        self.assertEqual(sent.get_method(), 'GET')
        self.assertIsNone(sent.data)
        self.assertEqual(sent.get_header('Authorization'), 'Bearer ' + self.key)
        error = HTTPError(sent.full_url, 401, self.key, {}, None)
        with patch('centaur_cli.openrouter.urlopen', side_effect=error):
            with self.assertRaisesRegex(RuntimeError, 'Chave recusada') as caught:
                OpenRouter(self.key).validate_key()
        self.assertNotIn(self.key, str(caught.exception))

    def test_key_cannot_enter_chat_history(self):
        history = ChatStore(self.root)
        terminal = Terminal(self.root, 'test', history, OpenRouter(self.key))
        terminal.draft = 'Minha chave: ' + self.key
        terminal.submit()
        self.assertEqual(terminal.draft, '')
        self.assertEqual(terminal.chat['messages'], [])
        self.assertEqual(history.list(), [])

    def test_file_and_command_outputs_redact_key_and_child_environment_does_not_inherit_it(self):
        (self.root / 'sample').write_text(self.key)
        tools = ProjectTools(self.root, lambda _: True, self.key)
        self.assertEqual(tools.execute('read_file', {'path': 'sample'}), '[CHAVE OCULTA]')
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': self.key}):
            result = tools.execute('run_command', {'command': 'printenv OPENROUTER_API_KEY'})
        self.assertNotIn(self.key, result)
        self.assertIn('Código de saída: 1', result)

    def test_credentials_file_is_blocked_even_when_project_root_contains_configuration(self):
        self.store.save(self.key)
        tools = ProjectTools(self.root, lambda _: True, self.key)
        with patch('centaur_cli.tools.credentials_path', return_value=self.store.path):
            output = tools.execute('read_file', {'path': 'config/centaur/credentials.json'})
        self.assertIn('não podem ser acessadas', output)
        self.assertNotIn(self.key, output)

    def test_api_payload_and_response_cannot_include_credential(self):
        response = io.BytesIO(json.dumps({'choices': [{'message': {
            'role': 'assistant', 'content': self.key}}]}).encode())
        with patch('centaur_cli.openrouter.urlopen', return_value=response) as request:
            result = OpenRouter(self.key).complete('test', [{'role': 'user', 'content': self.key}], [])
        self.assertNotIn(self.key, request.call_args.args[0].data.decode())
        self.assertEqual(result['content'], '[CHAVE OCULTA]')

    def test_first_launch_configures_key_and_next_launch_reuses_it(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': ''}), \
                patch('sys.argv', ['centaur', str(self.root)]), \
                patch('sys.stdin.isatty', return_value=True), patch('sys.stdout.isatty', return_value=True), \
                patch('centaur_cli.backends.CredentialStore', return_value=self.store), \
                patch('centaur_cli.__main__.curses.wrapper') as terminal, \
                patch('centaur_cli.backends.configure_key') as configure:
            def setup(store):
                store.save(self.key)
                return self.key
            configure.side_effect = setup
            main()
            main()
        configure.assert_called_once_with(self.store)
        self.assertEqual(terminal.call_count, 2)

    def test_environment_key_takes_priority_without_being_persisted(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': self.key}), \
                patch('sys.argv', ['centaur', str(self.root)]), \
                patch('sys.stdin.isatty', return_value=True), patch('sys.stdout.isatty', return_value=True), \
                patch('centaur_cli.backends.CredentialStore', return_value=self.store), \
                patch('centaur_cli.__main__.curses.wrapper') as terminal, \
                patch('centaur_cli.backends.configure_key') as configure:
            main()
        configure.assert_not_called()
        self.assertFalse(self.store.path.exists())
        self.assertEqual(terminal.call_args.args[0].__self__.client.api_key, self.key)


if __name__ == '__main__':
    unittest.main()
