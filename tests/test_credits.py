import io
import json
import contextlib
import os
import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from centaur_cli.appearance import TerminalView
from centaur_cli.credentials import CredentialStore
from centaur_cli.credits import CreditBalance, credit_label
from centaur_cli.history import ChatStore
from centaur_cli.openrouter import OpenRouter
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools
from centaur_cli.setup import configure_key


class CreditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.client = OpenRouter('chat-secret', 'management-secret')

    def response(self, data):
        return io.BytesIO(json.dumps({'data': data}).encode())

    def test_account_remaining_is_total_purchased_minus_usage(self):
        with patch('centaur_cli.openrouter.urlopen', return_value=self.response(
                {'total_credits': 100.5, 'total_usage': 25.75})) as request:
            balance = self.client.credits()
        sent = request.call_args.args[0]
        self.assertEqual(sent.full_url, 'https://openrouter.ai/api/v1/credits')
        self.assertEqual(sent.get_header('Authorization'), 'Bearer management-secret')
        self.assertEqual(balance.scope, 'account')
        self.assertEqual(balance.remaining, Decimal('74.75'))

    def test_regular_key_uses_its_own_limit_without_claiming_account_balance(self):
        with patch('centaur_cli.openrouter.urlopen', return_value=self.response(
                {'limit': 10, 'limit_remaining': 7})) as request:
            balance = OpenRouter('chat-secret').credits()
        self.assertTrue(request.call_args.args[0].full_url.endswith('/key'))
        label, _ = credit_label(balance, 'ready', 80)
        self.assertIn('Limite chave', label)
        self.assertNotIn('conta', label.lower())
        self.assertIn('US$ 7.00', label)

    def test_unlimited_key_does_not_invent_a_remaining_account_balance(self):
        with patch('centaur_cli.openrouter.urlopen', return_value=self.response({'limit': None})):
            balance = OpenRouter('chat-secret').credits()
        self.assertIsNone(balance.remaining)
        self.assertIsNone(balance.fraction)
        self.assertIn('sem limite', credit_label(balance, 'ready', 80)[0])

    def test_zero_credit_and_overspending_show_empty_bar(self):
        for data in ({'total_credits': 0, 'total_usage': 0},
                     {'total_credits': 10, 'total_usage': 11}):
            with patch('centaur_cli.openrouter.urlopen', return_value=self.response(data)):
                balance = self.client.credits()
            self.assertEqual(balance.remaining, 0)
            self.assertEqual(balance.fraction, 0)
            label, style = credit_label(balance, 'ready', 80)
            self.assertIn('░' * 10, label)
            self.assertEqual(style, 'warning')

    def test_nonfinite_response_is_rejected(self):
        with patch('centaur_cli.openrouter.urlopen', return_value=self.response(
                {'total_credits': 'NaN', 'total_usage': 0})):
            with self.assertRaises(RuntimeError):
                self.client.credits()

    def test_forbidden_response_does_not_expose_management_key(self):
        error = HTTPError('https://openrouter.ai/api/v1/credits', 403, 'management-secret', {}, None)
        with patch('centaur_cli.openrouter.urlopen', side_effect=error):
            with self.assertRaisesRegex(RuntimeError, 'gerenciamento') as caught:
                self.client.credits()
        self.assertNotIn('management-secret', str(caught.exception))

    def test_bar_shrinks_in_narrow_terminal_and_marks_stale_values(self):
        balance = CreditBalance('account', Decimal(10), Decimal(5))
        wide, _ = credit_label(balance, 'ready', 110)
        narrow, _ = credit_label(balance, 'error', 40)
        self.assertEqual(wide.count('█') + wide.count('░'), 10)
        self.assertEqual(narrow.count('█') + narrow.count('░'), 5)
        self.assertIn('~US$', narrow)
        self.assertIn('indisponível', credit_label(None, 'error', 40)[0])

    def test_management_key_persistence_preserves_chat_key_and_private_permissions(self):
        store = CredentialStore(self.root / 'config/credentials.json')
        store.save('chat-secret')
        store.save_credits_key('management-secret')
        store.save('new-chat-secret')
        self.assertEqual(store.load(), 'new-chat-secret')
        self.assertEqual(store.load_credits_key(), 'management-secret')
        self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)

    def test_management_key_wizard_uses_credits_endpoint_and_hidden_input(self):
        store = CredentialStore(self.root / 'config/credentials.json')
        store.save('chat-secret')
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch('builtins.input', return_value='n'), \
                patch('centaur_cli.setup.getpass.getpass', return_value='management-secret'), \
                patch('centaur_cli.openrouter.urlopen', return_value=self.response(
                    {'total_credits': 10, 'total_usage': 3})) as request:
            configure_key(store, purpose='credits')
        self.assertTrue(request.call_args.args[0].full_url.endswith('/credits'))
        self.assertEqual(store.load(), 'chat-secret')
        self.assertEqual(store.load_credits_key(), 'management-secret')
        self.assertNotIn('management-secret', output.getvalue())

    def test_credit_commands_stay_local_and_identify_required_credential(self):
        terminal = Terminal(self.root, '', ChatStore(self.root), OpenRouter('chat-secret'))
        terminal.draft = '/credits'
        terminal.submit()
        self.assertIn('limite da chave', terminal.notice)
        self.assertIn('$config', terminal.notice)
        self.assertTrue(terminal.credits_dirty)
        terminal.draft = '/credits configure'
        self.assertEqual(terminal.submit(), 'configure_credits')
        self.assertEqual(terminal.draft, '')
        self.assertEqual(terminal.chat['messages'], [])
        terminal.client = self.client
        terminal.draft = '/credits'
        terminal.submit()
        self.assertIn('saldo da conta', terminal.notice)
        self.assertNotIn('configure', terminal.notice)

    def test_in_app_registration_preserves_chat_and_discards_old_credit_results(self):
        old_client = OpenRouter('chat-secret')
        old_client.model_efforts = {'example/model': ['default', 'high']}
        terminal = Terminal(self.root, 'example/model', ChatStore(self.root), old_client)
        chat = terminal.chat
        terminal.credits_inflight = True
        terminal.events.put(('backend_credits', (old_client, ('credits',
            CreditBalance('key', Decimal(50), Decimal(49))))))
        screen = Mock()
        with patch('centaur_cli.terminal.curses') as curses, \
                patch('centaur_cli.terminal.configure_key', return_value='management-secret') as wizard:
            terminal.configure_credits(screen)
        self.assertEqual(wizard.call_args.kwargs, {'purpose': 'credits'})
        curses.endwin.assert_called_once()
        curses.reset_prog_mode.assert_called_once()
        screen.clearok.assert_called_once_with(True)
        self.assertIs(terminal.chat, chat)
        self.assertEqual(terminal.model, 'example/model')
        self.assertEqual(terminal.client.api_key, 'chat-secret')
        self.assertEqual(terminal.client.credits_key, 'management-secret')
        self.assertEqual(terminal.client.model_efforts, old_client.model_efforts)
        self.assertTrue(terminal.credits_dirty)
        self.assertFalse(terminal.credits_inflight)
        terminal.drain_events()
        self.assertIsNone(terminal.credits)
        with patch('centaur_cli.openrouter.urlopen', return_value=self.response(
                {'total_credits': 20, 'total_usage': 3.25})):
            terminal.fetch_credits(terminal.client)
        terminal.drain_events()
        self.assertIn('Saldo conta', credit_label(terminal.credits, terminal.credits_status, 110)[0])
        self.assertEqual(terminal.credits.remaining, Decimal('16.75'))

    def test_cancelled_registration_restores_terminal_and_existing_balance(self):
        terminal = Terminal(self.root, '', ChatStore(self.root), self.client)
        balance = CreditBalance('account', Decimal(10), Decimal(5))
        terminal.credits = balance
        terminal.credits_status = 'ready'
        with patch('centaur_cli.terminal.curses') as curses, \
                patch('centaur_cli.terminal.configure_key', side_effect=RuntimeError('Configuração cancelada.')):
            terminal.configure_credits(Mock())
        curses.reset_prog_mode.assert_called_once()
        self.assertIs(terminal.client, self.client)
        self.assertEqual(terminal.credits, balance)
        self.assertEqual(terminal.credits_status, 'ready')
        self.assertIn('cancelada', terminal.notice)

    def test_registration_is_not_started_during_work_or_for_native_backend(self):
        terminal = Terminal(self.root, '', ChatStore(self.root), self.client)
        terminal.draft = '/credits configure'
        terminal.busy = True
        self.assertIsNone(terminal.submit())
        self.assertEqual(terminal.draft, '/credits configure')
        terminal.busy = False
        terminal.backend = 'codex'
        self.assertIsNone(terminal.submit())
        self.assertIn('backend OpenRouter', terminal.notice)
        self.assertEqual(terminal.chat['messages'], [])

    def test_management_secret_is_blocked_from_chat_and_tool_outputs(self):
        terminal = Terminal(self.root, '', ChatStore(self.root), self.client)
        terminal.draft = 'management-secret'
        terminal.submit()
        self.assertEqual(terminal.chat['messages'], [])
        (self.root / 'sample').write_text('management-secret')
        tools = ProjectTools(self.root, lambda _: True, protected_keys=self.client.secrets)
        self.assertEqual(tools.execute('read_file', {'path': 'sample'}), '[CHAVE OCULTA]')
        with patch.dict(os.environ, {'OPENROUTER_CREDITS_KEY': 'management-secret'}):
            result = tools.execute('run_command', {'command': 'printenv OPENROUTER_CREDITS_KEY'})
        self.assertIn('Código de saída: 1', result)
        self.assertNotIn('management-secret', result)

    def test_polling_does_not_block_input_or_duplicate_requests(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        balance = CreditBalance('account', Decimal(10), Decimal(5))
        def delayed():
            started.set()
            release.wait(3)
            return balance
        terminal = Terminal(self.root, '', ChatStore(self.root), self.client)
        with patch.object(self.client, 'credits', side_effect=delayed) as request:
            terminal.request_credits()
            self.assertTrue(started.wait(1))
            terminal.handle('a')
            terminal.request_credits()
            self.assertEqual(terminal.draft, 'a')
            request.assert_called_once()
            release.set()

    def test_failed_refresh_retains_last_balance_and_success_can_replace_it(self):
        terminal = Terminal(self.root, '', ChatStore(self.root), self.client)
        balance = CreditBalance('account', Decimal(10), Decimal(5))
        terminal.events.put(('credits', balance))
        terminal.drain_events()
        terminal.events.put(('credits_error', None))
        terminal.drain_events()
        self.assertEqual(terminal.credits, balance)
        self.assertEqual(terminal.credits_status, 'error')
        terminal.events.put(('done', 'Pronto.'))
        terminal.drain_events()
        self.assertTrue(terminal.credits_dirty)

    def test_credit_bar_moves_with_window_size_and_preserves_draft(self):
        class Screen:
            def __init__(inner):
                inner.size = (34, 110)
                inner.output = []
            def getmaxyx(inner): return inner.size
            def bkgd(inner, *args): pass
            def erase(inner): inner.output.clear()
            def refresh(inner): pass
            def move(inner, *args): pass
            def addnstr(inner, row, column, text, length, style):
                inner.output.append((row, column, text[:length]))
        terminal = Terminal(self.root, '', ChatStore(self.root), self.client)
        terminal.credits = CreditBalance('account', Decimal(10), Decimal(5))
        terminal.credits_status = 'ready'
        terminal.draft = 'rascunho preservado'
        screen = Screen()
        view = TerminalView()
        for size in ((34, 110), (24, 80), (18, 45), (34, 110)):
            screen.size = size
            view.draw(screen, terminal)
            row, column, label = next(item for item in screen.output if 'conta' in item[2].lower() and 'US$' in item[2])
            self.assertEqual(row, size[0] - 2)
            self.assertEqual(column + len(label), size[1] - 3)
            self.assertEqual(terminal.draft, 'rascunho preservado')


if __name__ == '__main__':
    unittest.main()
