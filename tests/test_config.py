import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from centaur_cli.backends import resolve_selection
from centaur_cli.config import load_config, save_config
from centaur_cli.completion import SkillCompletion
from centaur_cli.history import ChatStore
from centaur_cli.terminal import Terminal


class ConfigTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.client = type('Client', (), {'backend': 'codex', 'secrets': ('secret-token',)})()
        self.terminal = Terminal(self.root, 'main', ChatStore(self.root), self.client)

    def test_backend_switch_creates_chat_persists_preferences_and_keeps_history(self):
        terminal = self.terminal
        terminal.chat['messages'].append({'role': 'user', 'content': 'Old conversation'})
        terminal.store.save(terminal.chat)
        old_id = terminal.chat['id']
        replacement = type('Client', (), {'backend': 'claude'})()
        terminal.draft = '$config claude sonnet'
        with patch('centaur_cli.terminal.create_client', return_value=replacement) as factory:
            terminal.submit()
        factory.assert_called_once_with('claude', 'sonnet', allow_setup=False)
        self.assertEqual(load_config(self.root), {'backend': 'claude', 'model': 'sonnet', 'approval_mode': 'ask'})
        self.assertEqual(terminal.model, 'sonnet')
        self.assertEqual(terminal.chat['backend'], 'claude')
        self.assertNotEqual(terminal.chat['id'], old_id)
        self.assertEqual(terminal.store.list()[0]['id'], old_id)

    def test_failure_or_busy_does_not_change_configuration(self):
        terminal = self.terminal
        terminal.draft = '$config claude'
        with patch('centaur_cli.terminal.create_client', side_effect=RuntimeError('Faça login')):
            terminal.submit()
        self.assertIs(terminal.client, self.client)
        self.assertEqual(load_config(self.root), {})
        self.assertIn('Faça login', terminal.notice)
        terminal.busy = True
        with patch('centaur_cli.terminal.create_client') as factory:
            terminal.submit()
        factory.assert_not_called()

    def test_config_is_local_command_and_autocompleted(self):
        terminal = self.terminal
        terminal.draft = '$config'
        with patch('centaur_cli.terminal.threading.Thread') as thread:
            terminal.submit()
        thread.assert_not_called()
        self.assertEqual(terminal.settings.backend, 'codex')
        self.assertFalse(terminal.chat['messages'])
        completion = SkillCompletion(self.root)
        completion.update('$con')
        self.assertEqual(completion.choose('$con'), '$config ')

    def test_credentials_and_external_paths_are_rejected(self):
        self.terminal.draft = '$config claude secret-token'
        self.terminal.submit()
        self.assertEqual(load_config(self.root), {})
        with self.assertRaises(ValueError):
            save_config(self.root, 'claude', '--unsafe')
        (self.root / '.centaur').mkdir()
        with tempfile.TemporaryDirectory() as outside:
            (self.root / '.centaur/config.json').symlink_to(Path(outside) / 'config.json')
            with self.assertRaises(ValueError):
                save_config(self.root, 'claude', 'sonnet')

    def test_saved_selection_and_explicit_environment_overrides(self):
        save_config(self.root, 'claude', 'sonnet')
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_selection(self.root), ('claude', 'sonnet'))
            self.assertEqual(resolve_selection(self.root, 'codex'), ('codex', ''))
            self.assertEqual(resolve_selection(self.root, model='opus'), ('claude', 'opus'))
        with patch.dict(os.environ, {'CENTAUR_BACKEND': 'codex', 'CENTAUR_MODEL': 'fast'}, clear=True):
            self.assertEqual(resolve_selection(self.root), ('codex', 'fast'))
            self.assertEqual(resolve_selection(self.root, 'claude', 'opus'), ('claude', 'opus'))

    def test_old_backend_credit_events_are_discarded_after_switch(self):
        terminal = self.terminal
        terminal.events.put(('backend_credits', (self.client, ('credits', 'stale balance'))))
        terminal.client = object()
        terminal.drain_events()
        self.assertIsNone(terminal.credits)
