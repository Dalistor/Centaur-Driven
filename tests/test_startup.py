import curses
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from centaur_cli.__main__ import main
from centaur_cli.config import load_config, save_config
from centaur_cli.startup import StartupPicker, StartupWizard
from test_terminal_settings import Screen


class StartupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_backend_model_effort_review_sequence_reuses_preferences(self):
        picker = StartupPicker('claude', 'sonnet', 'high')
        self.assertEqual(picker.options()[picker.selected][0], 'claude')
        self.assertEqual(picker.handle('\n'), 'catalog')
        self.assertEqual(picker.page, 'model')
        self.assertEqual(picker.options()[picker.selected][0], 'sonnet')
        picker.handle('\n')
        self.assertEqual(picker.page, 'effort')
        self.assertEqual(picker.options()[picker.selected][0], 'high')
        picker.handle('\n')
        self.assertEqual((picker.page, picker.row), ('fields', 3))
        self.assertEqual(picker.handle('\n'), 'save')

    def test_backend_change_discards_incompatible_model_and_effort(self):
        picker = StartupPicker('openrouter', 'provider/model', 'none')
        picker.handle(curses.KEY_DOWN)
        picker.handle('\n')
        self.assertEqual((picker.backend, picker.model, picker.effort), ('codex', '', 'default'))
        self.assertEqual(picker.page, 'model')
        picker.handle('\x1b')
        self.assertEqual(picker.page, 'backend')
        self.assertEqual(picker.handle('\x1b'), 'cancel')
        self.assertEqual(load_config(self.root), {})

    def test_custom_model_validation_and_back_navigation(self):
        picker = StartupPicker('claude', '', 'default')
        picker.handle('\n')
        picker.handle(curses.KEY_DOWN)
        picker.handle('\n')
        self.assertEqual(picker.page, 'custom')
        picker.query = 'bad model'
        picker.handle('\n')
        self.assertEqual(picker.page, 'custom')
        self.assertTrue(picker.error)
        picker.query = 'sonnet'
        picker.handle('\n')
        self.assertEqual((picker.page, picker.model), ('effort', 'sonnet'))
        picker.handle('\x1b')
        self.assertEqual(picker.page, 'model')

    def test_catalog_limits_effort_and_ignores_stale_backend_visit(self):
        wizard = StartupWizard('openrouter', 'plain', 'high')
        wizard.picker.open_page('model')
        wizard.catalog_request = 2
        wizard.events.put((1, ({'stale': 'old'}, {}, '')))
        wizard.events.put((2, ({'plain': 'No reasoning'}, {'plain': ['default']}, '')))
        wizard.drain_events()
        self.assertNotIn('stale', wizard.picker.catalog)
        self.assertEqual(wizard.picker.effort, 'default')
        wizard.picker.backend = 'claude'
        wizard.events.put((2, ({'wrong-backend': 'old'}, {}, '')))
        wizard.drain_events()
        self.assertNotIn('wrong-backend', wizard.picker.catalog)

    def test_narrow_resize_and_all_pages_preserve_selection_and_explanation(self):
        wizard = StartupWizard('claude', 'sonnet', 'medium')
        for size in ((24, 100), (24, 80), (18, 40), (12, 35)):
            for page in ('backend', 'model', 'effort', 'fields', 'custom'):
                wizard.picker.page = page
                screen = Screen(size)
                wizard.draw(screen)
                self.assertEqual((wizard.picker.backend, wizard.picker.model, wizard.picker.effort),
                                 ('claude', 'sonnet', 'medium'))
                if size[0] >= 18 and size[1] >= 40:
                    self.assertIn('Subagentes', screen.text())
                else:
                    self.assertIn('Amplie', screen.text())

    def run_main(self, wrapper, client):
        with patch('sys.argv', ['centaur', str(self.root)]), \
                patch('sys.stdin.isatty', return_value=True), patch('sys.stdout.isatty', return_value=True), \
                patch.dict('os.environ', {}, clear=True), \
                patch('centaur_cli.__main__.curses.wrapper', side_effect=wrapper), \
                patch('centaur_cli.__main__.create_client', side_effect=client) as factory:
            main()
        return factory

    def test_cancel_never_authenticates_saves_or_creates_chat(self):
        factory = self.run_main(lambda _: None, lambda *args: self.fail('Authentication before choice'))
        factory.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_default_launch_authenticates_only_after_confirmation_and_saves(self):
        connected = SimpleNamespace(backend='claude', secrets=())
        seen = []
        def wrapper(run):
            seen.append(run.__self__)
            if isinstance(run.__self__, StartupWizard):
                self.assertEqual(list(self.root.iterdir()), [])
                return 'claude', 'sonnet', 'medium'
            self.assertEqual(run.__self__.backend, 'claude')
            self.assertEqual(run.__self__.chat['model'], 'sonnet')
            self.assertEqual(run.__self__.chat['effort'], 'medium')
        factory = self.run_main(wrapper, lambda *args: connected)
        factory.assert_called_once_with('claude', 'sonnet')
        self.assertEqual(len(seen), 2)
        self.assertEqual(load_config(self.root), {'backend': 'claude', 'model': 'sonnet', 'effort': 'medium'})

    def test_auth_failure_keeps_preferences_and_allows_another_backend(self):
        save_config(self.root, 'codex', 'old', 'high')
        visits = []
        def wrapper(run):
            owner = run.__self__
            if isinstance(owner, StartupWizard):
                visits.append(owner)
                if len(visits) == 1:
                    self.assertEqual((owner.picker.backend, owner.picker.model), ('codex', 'old'))
                    return 'codex', 'old', 'high'
                self.assertIn('codex login', owner.picker.error)
                self.assertEqual(load_config(self.root)['model'], 'old')
                return 'claude', 'sonnet', 'medium'
            self.assertEqual(owner.backend, 'claude')
        factory = self.run_main(wrapper, [RuntimeError('Execute codex login.'), SimpleNamespace(backend='claude', secrets=())])
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(load_config(self.root)['backend'], 'claude')
