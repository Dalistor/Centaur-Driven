import curses
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from centaur_cli.__main__ import main
from centaur_cli.agent import run_turn
from centaur_cli.backends import create_client, resolve_model
from centaur_cli.credits import credit_label
from centaur_cli.history import ChatStore
from centaur_cli.native_client import NativeClient
from centaur_cli.subagents import SubagentTools
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools, TOOLS


class BackendTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def client(self, backend='codex', model='fixed'):
        with patch('centaur_cli.native_client.shutil.which', return_value='/fake/' + backend):
            return NativeClient(backend, model)

    def process(self, client, value):
        class Process:
            pid = 999
            returncode = 0
            def communicate(process, prompt, timeout):
                if client.backend == 'codex':
                    argv = self.fake_start.call_args.args[0]
                    output = Path(argv[argv.index('--output-last-message') + 1])
                    output.write_text(json.dumps(value))
                    return '', ''
                return json.dumps({'subtype': 'success', 'structured_output': value}), ''
        start = patch('centaur_cli.native_client.subprocess.Popen', return_value=Process())
        return start

    def test_native_factory_never_loads_or_configures_openrouter_credentials(self):
        for backend in ('codex', 'claude'):
            with patch('centaur_cli.native_client.shutil.which', return_value='/fake/' + backend), \
                    patch.object(NativeClient, 'check_available'), patch.object(NativeClient, 'check_authentication'), \
                    patch('centaur_cli.backends.CredentialStore') as credentials:
                client = create_client(backend, 'fixed')
            credentials.assert_not_called()
            self.assertFalse(client.allows_model_routing)

    def test_model_environment_is_separate_and_routing_attempts_are_rejected_before_process(self):
        with patch.dict(os.environ, {'OPENROUTER_MODEL': 'provider/other', 'CENTAUR_MODEL': 'fixed'}):
            self.assertEqual(resolve_model('codex'), 'fixed')
            self.assertEqual(resolve_model('openrouter'), 'provider/other')
        client = self.client()
        with patch('centaur_cli.native_client.subprocess.Popen') as start:
            for model, tier in (('provider/other', None), ('fixed', 'low')):
                with self.assertRaises(ValueError):
                    client.complete(model, [], TOOLS, cost_tier=tier)
            start.assert_not_called()

    def test_native_invocations_isolate_builtin_tools_and_forward_only_valid_centaur_calls(self):
        for backend in ('codex', 'claude'):
            client = self.client(backend)
            value = {'content': None, 'calls': [{'name': 'read_file', 'arguments': '{"path":"README.md"}'}]}
            with self.process(client, value) as start:
                # Expose patch mock to the fake process after context entry.
                self.fake_start = start
                reply = client.complete('fixed', [{'role': 'user', 'content': 'Leia README'}], TOOLS)
            self.assertEqual(reply['tool_calls'][0]['function']['name'], 'read_file')
            argv = start.call_args.args[0]
            self.assertEqual(argv[argv.index('--model') + 1], 'fixed')
            self.assertNotEqual(start.call_args.kwargs['cwd'], self.root)
            if backend == 'codex':
                self.assertIn('--ignore-user-config', argv)
                self.assertIn('read-only', argv)
                self.assertIn('multi_agent', argv)
            else:
                self.assertIn('--safe-mode', argv)
                self.assertEqual(argv[argv.index('--tools') + 1], '')
                self.assertIn('--strict-mcp-config', argv)

    def test_invalid_native_reply_cannot_execute_undeclared_tools(self):
        client = self.client('claude')
        value = {'content': 'ok', 'calls': [{'name': 'write_file', 'arguments': '{}'}]}
        with self.process(client, value), self.assertRaises(RuntimeError):
            client.complete('fixed', [], [])

    def test_missing_cli_and_old_cli_fail_without_provider_fallback(self):
        with patch('centaur_cli.native_client.shutil.which', return_value=None), self.assertRaises(RuntimeError):
            NativeClient('codex')
        client = self.client()
        with patch('centaur_cli.native_client.subprocess.run', return_value=subprocess.CompletedProcess([], 0, stdout='old cli')):
            with self.assertRaises(RuntimeError):
                client.check_available()

    def test_missing_authentication_guides_login_without_exposing_account_details(self):
        client = self.client('claude')
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': '', 'CLAUDE_CODE_OAUTH_TOKEN': ''}), \
                patch('centaur_cli.native_client.subprocess.run', return_value=subprocess.CompletedProcess([], 1, stdout='private account metadata')):
            with self.assertRaisesRegex(RuntimeError, 'claude auth login') as error:
                client.check_authentication()
        self.assertNotIn('private account metadata', str(error.exception))

    def test_native_delegation_selects_model_without_changing_parent_or_provider(self):
        for backend in ('codex', 'claude'):
            client = self.client(backend)
            with patch.object(client, 'model_catalog', return_value={'fixed': 'Main', 'fast': 'Simple tasks'}):
                tools = SubagentTools(ProjectTools(self.root, lambda _: False), client, 'a' * 32, lambda _: None)
                properties = tools.definitions[-1]['function']['parameters']['properties']
                self.assertEqual(set(properties), {'title', 'task', 'model'})
                self.assertEqual(properties['model']['enum'], ['fixed', 'fast'])
                for field, value in (('model', 'provider/other'), ('cost_tier', 'low')):
                    output = tools.execute('delegate_task', {'title': 'Task', 'task': 'Contrato', field: value})
                    self.assertIn('Falha ao delegar', output)
                self.assertEqual(tools.count, 0)
                with patch('centaur_cli.subagents.run_turn') as execute:
                    def report(chat, used_client, *args):
                        self.assertIs(used_client, client)
                        self.assertEqual(chat['model'], 'fast')
                        self.assertEqual(chat['backend'], backend)
                        chat['messages'].append({'role': 'assistant', 'content': 'Relatório'})
                    execute.side_effect = report
                    output = json.loads(tools.delegate({'title': 'Task', 'task': 'Contrato', 'model': 'fast'}))
                self.assertEqual(output['requested_model'], 'fast')
                self.assertEqual(client.fixed_model, 'fixed')
                self.assertIsNone(output['cost_tier'])
                self.assertEqual(output['status'], 'reported')

    def test_native_selected_model_reaches_process_arguments(self):
        for backend in ('codex', 'claude'):
            client = self.client(backend)
            with patch.object(client, 'model_catalog', return_value={'fast': 'Simple'}), \
                    self.process(client, {'content': 'ok', 'calls': []}) as start:
                self.fake_start = start
                client.complete('fast', [], [])
            argv = start.call_args.args[0]
            self.assertEqual(argv[argv.index('--model') + 1], 'fast')
            self.assertEqual(client.fixed_model, 'fixed')

    def test_codex_catalog_ignores_hidden_models_and_handles_missing_cache(self):
        with patch.dict(os.environ, {'CODEX_HOME': str(self.root)}):
            client = self.client()
            self.assertEqual(client.model_catalog(), {'fixed': 'Modelo principal configurado'})
            (self.root / 'models_cache.json').write_text(json.dumps({'models': [
                {'slug': 'fast', 'visibility': 'list', 'description': 'Simple'},
                {'slug': 'hidden', 'visibility': 'hide'},
                {'slug': '--bad', 'visibility': 'list'}]}))
            self.assertEqual(set(client.model_catalog()), {'fast', 'fixed'})

    def test_cli_connects_native_without_openrouter_setup(self):
        with patch('sys.argv', ['centaur', '--no-setup', '--backend', 'claude', '--model', 'fixed', str(self.root)]), \
                patch('sys.stdin.isatty', return_value=True), patch('sys.stdout.isatty', return_value=True), \
                patch('centaur_cli.native_client.shutil.which', return_value='/fake/claude'), \
                patch.object(NativeClient, 'check_available'), patch.object(NativeClient, 'check_authentication'), \
                patch('centaur_cli.backends.CredentialStore') as credentials, \
                patch('centaur_cli.__main__.curses.wrapper') as wrapper:
            main()
        credentials.assert_not_called()
        terminal = wrapper.call_args.args[0].__self__
        self.assertEqual(terminal.backend, 'claude')
        self.assertEqual(terminal.chat['backend'], 'claude')

    def test_history_backend_mismatch_is_rejected_and_native_usage_is_independent_of_openrouter(self):
        store = ChatStore(self.root)
        old = store.new('fixed')
        store.save(old)
        terminal = Terminal(self.root, 'fixed', store, self.client())
        terminal.handle(curses.KEY_SLEFT)
        terminal.handle('\n')
        self.assertIn('outro backend', terminal.notice)
        self.assertNotEqual(terminal.chat['id'], old['id'])
        with patch('centaur_cli.terminal.threading.Thread') as thread:
            terminal.request_credits()
            thread.assert_called_once()
        self.assertEqual(terminal.credits_status, 'loading')

    def test_invalid_backend_in_saved_chat_is_ignored(self):
        store = ChatStore(self.root)
        chat = store.new('fixed', backend='codex')
        chat['backend'] = {'invalid': 'provider'}
        store.save(chat)
        self.assertEqual(store.list(), [])

    def test_timeout_kills_native_process_group_without_retry(self):
        client = self.client()
        class Process:
            pid = 999
            def communicate(self, *args, **kwargs):
                if args:
                    raise subprocess.TimeoutExpired('codex', 180)
                return '', ''
        with patch('centaur_cli.native_client.subprocess.Popen', return_value=Process()) as start, \
                patch('centaur_cli.native_client.os.killpg') as kill:
            with self.assertRaisesRegex(RuntimeError, 'tempo limite'):
                client.complete('fixed', [], [])
        kill.assert_called_once()
        self.assertEqual(start.call_count, 1)
