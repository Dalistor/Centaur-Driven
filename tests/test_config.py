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
        self.assertEqual(load_config(self.root), {'backend': 'claude', 'model': 'sonnet', 'approval_mode': 'ask', 'speed': 'standard', 'setup_complete': True})
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

    def test_updated_selection_survives_navigation_without_mutating_old_worker(self):
        for backend in ('openrouter', 'codex', 'claude'):
            with self.subTest(backend=backend):
                original = type('Client', (), {'backend': backend})()
                replacement = type('Client', (), {'backend': backend})()
                terminal = Terminal(self.root, 'main', ChatStore(self.root), original,
                                    effort='high', approval_mode='ask')
                chat = terminal.chat
                chat['messages'] = [{'role': 'user', 'content': 'Preservar conversa'}]
                worker = terminal.worker_context()
                with patch.object(terminal, 'request_context_catalog'):
                    terminal.activate_config(backend, 'other', 'low', replacement, 'never', 'fast')
                terminal.create_chat_from_menu()
                terminal.switch_chat(chat)
                self.assertIs(terminal.client, replacement)
                self.assertEqual((terminal.model, terminal.effort, terminal.speed, terminal.approval_mode),
                                 ('other', 'low', 'fast', 'never'))
                self.assertEqual(terminal.chat['messages'], [{'role': 'user', 'content': 'Preservar conversa'}])
                self.assertIs(worker.client, original)
                self.assertEqual((worker.model, worker.effort, worker.approval_mode), ('main', 'high', 'ask'))

    def test_backend_roundtrip_restores_idle_sessions_and_discards_stale_credits(self):
        terminal = self.terminal
        first = terminal.chat
        terminal.store.save(first)
        terminal.create_chat_from_menu()
        second = terminal.chat
        replacement = type('Client', (), {'backend': 'claude'})()
        with patch.object(terminal, 'request_context_catalog'):
            terminal.activate_config('claude', 'sonnet', 'low', replacement, 'auto', 'standard')
        third = terminal.chat
        terminal.credits = 'Claude balance'
        terminal.credits_inflight = True
        terminal.events.put(('backend_credits', (replacement, ('credits', 'late Claude balance'))))
        terminal.open_chats()
        terminal.selected = next(i for i, chat in enumerate(terminal.chats) if chat['id'] == first['id'])
        terminal.handle_browser('\n')
        self.assertFalse(terminal.browser)
        self.assertIs(terminal.client, self.client)
        self.assertEqual((terminal.backend, terminal.model), ('codex', 'main'))
        self.assertIsNone(terminal.credits)
        self.assertFalse(terminal.credits_inflight)
        terminal.drain_events()
        self.assertIsNone(terminal.credits)
        terminal.switch_chat(second)
        self.assertIs(terminal.client, self.client)
        terminal.switch_chat(third)
        self.assertIs(terminal.client, replacement)
        self.assertEqual((terminal.backend, terminal.model, terminal.effort, terminal.approval_mode),
                         ('claude', 'sonnet', 'low', 'auto'))
