import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from centaur_cli import login
from centaur_cli.history import ChatStore
from centaur_cli.login import LoginRequired
from centaur_cli.native_client import NativeClient, process_error
from centaur_cli.terminal import Terminal

# Diagnósticos reais dos CLIs sem credencial (Claude Code 2.1, Codex 0.162).
CLAUDE_LOGGED_OUT = json.dumps({'type': 'result', 'subtype': 'success', 'is_error': True,
                                'result': 'Not logged in · Please run /login'})
CODEX_LOGGED_OUT = '\n'.join(json.dumps(event) for event in (
    {'type': 'error', 'message': 'Reconnecting... 5/5 (unexpected status 401 Unauthorized: Missing bearer or basic '
                                 'authentication in header, url: https://api.openai.com/v1/responses)'},
    {'type': 'turn.failed', 'error': {'message': 'unexpected status 401 Unauthorized: Missing bearer or basic '
                                                 'authentication in header'}}))


class LoginDetectionTests(unittest.TestCase):
    def test_logged_out_diagnostics_of_both_clis_ask_for_login(self):
        for backend, output in (('claude', CLAUDE_LOGGED_OUT), ('codex', CODEX_LOGGED_OUT)):
            with patch('centaur_cli.login.logged_in', side_effect=AssertionError('o diagnóstico já basta')):
                error = process_error(backend, '/bin/' + backend, 1, '', output)
            self.assertIsInstance(error, LoginRequired)
            self.assertEqual(error.backend, backend)
            self.assertIn(login.command_text(backend), str(error))
        self.assertTrue(login.mentions_logout('OAuth token has expired. Please obtain a new token.'))

    def test_other_failures_keep_their_own_diagnosis(self):
        with patch('centaur_cli.login.logged_in', side_effect=AssertionError('falha já classificada')):
            for text in ('rate limit reached', 'stream disconnected before completion', 'context window exceeded'):
                error = process_error('codex', '/bin/codex', 1, text)
                self.assertNotIsInstance(error, LoginRequired)
                self.assertIn('codex encerrou com código 1', str(error))

    def test_unexplained_failure_asks_the_cli_whether_it_is_still_logged_in(self):
        for state, expected in ((False, True), (True, False), (None, False)):
            with patch('centaur_cli.login.logged_in', return_value=state):
                error = process_error('claude', '/bin/claude', 1, 'something broke')
            self.assertEqual(isinstance(error, LoginRequired), expected)

    def test_startup_check_raises_login_required(self):
        with patch('centaur_cli.native_client.shutil.which', return_value='/bin/claude'), \
                patch('centaur_cli.models.load_quota', return_value={}), patch('centaur_cli.models.load_learned', return_value={}):
            client = NativeClient('claude', 'sonnet')
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': '', 'CLAUDE_CODE_OAUTH_TOKEN': ''}), \
                patch('centaur_cli.login.subprocess.run', return_value=subprocess.CompletedProcess([], 1, stdout='{"loggedIn": false}')):
            with self.assertRaises(LoginRequired):
                client.check_authentication()

    def test_sign_in_runs_the_official_login_and_confirms_with_status(self):
        calls = []
        def run(arguments, **options):
            calls.append(arguments)
            return subprocess.CompletedProcess(arguments, 0, stdout='')
        output = io.StringIO()
        with patch('centaur_cli.login.subprocess.run', side_effect=run):
            self.assertTrue(login.sign_in('codex', '/bin/codex', output))
        self.assertEqual(calls, [['/bin/codex', 'login'], ['/bin/codex', 'login', 'status']])
        self.assertIn('codex login', output.getvalue())
        with patch('centaur_cli.login.subprocess.run', return_value=subprocess.CompletedProcess([], 1)):
            self.assertFalse(login.sign_in('claude', '/bin/claude', io.StringIO()))
        with patch('centaur_cli.login.subprocess.run', side_effect=KeyboardInterrupt):
            self.assertFalse(login.sign_in('claude', '/bin/claude', io.StringIO()))


class TerminalLoginTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.terminal = Terminal(self.root, 'main', ChatStore(self.root), None)
        self.terminal.chat['last_error'] = 'claude não autenticado'
        self.terminal.start_work = MagicMock()
        self.terminal.configure_mouse = MagicMock()
        for name in ('def_prog_mode', 'endwin', 'reset_prog_mode', 'raw', 'nonl'):
            patcher = patch('centaur_cli.terminal.curses.' + name)
            patcher.start()
            self.addCleanup(patcher.stop)

    def request(self):
        self.terminal.events.put(('login', ('claude', self.terminal.chat['id'])))
        self.terminal.drain_events()
        self.assertEqual(self.terminal.login_request, ('claude', self.terminal.chat['id']))

    def test_successful_login_resumes_the_failed_turn(self):
        self.request()
        with patch('centaur_cli.terminal.shutil.which', return_value='/bin/claude'), \
                patch('centaur_cli.terminal.login.sign_in', return_value=True) as sign_in:
            self.terminal.sign_in(MagicMock())
        sign_in.assert_called_once_with('claude', '/bin/claude')
        self.terminal.start_work.assert_called_once()
        self.assertNotIn('last_error', self.terminal.chat)
        self.assertIsNone(self.terminal.login_request)
        # Recusa logo depois de um login confirmado não reabre o login em laço.
        self.terminal.chat['last_error'] = 'claude não autenticado'
        self.request()
        with patch('centaur_cli.terminal.login.sign_in', side_effect=AssertionError('sem laço')):
            self.terminal.sign_in(MagicMock())
        self.assertIn('/retry', self.terminal.notice)
        self.terminal.start_work.assert_called_once()

    def test_cancelled_login_keeps_the_turn_for_retry(self):
        self.request()
        with patch('centaur_cli.terminal.shutil.which', return_value='/bin/claude'), \
                patch('centaur_cli.terminal.login.sign_in', return_value=False):
            self.terminal.sign_in(MagicMock())
        self.terminal.start_work.assert_not_called()
        self.assertIn('last_error', self.terminal.chat)
        self.assertIn('claude auth login', self.terminal.notice)


if __name__ == '__main__':
    unittest.main()
