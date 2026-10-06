import curses
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from centaur_cli.backends import resolve_approval_mode
from centaur_cli.config import load_config, save_config
from centaur_cli.history import ChatStore
from centaur_cli.permissions import ordinary_path, query_command
from centaur_cli.settings import ConfigPicker
from centaur_cli.startup import StartupPicker
from centaur_cli.subagents import SubagentTools
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools
from test_terminal_settings import Screen


class PermissionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.approvals = []

    def tools(self, mode, allow=False):
        return ProjectTools(self.root, lambda action: self.approvals.append(action) or allow,
                            approval_mode=mode)

    def test_three_modes_apply_to_writes_and_general_commands(self):
        for mode in ('ask', 'auto', 'never'):
            tools = self.tools(mode)
            result = tools.execute('write_file', {'path': f'{mode}.txt', 'content': 'new'})
            self.assertEqual((self.root / f'{mode}.txt').exists(), mode != 'ask')
            result = tools.execute('run_command', {'command': f'touch {mode}.command'})
            self.assertEqual((self.root / f'{mode}.command').exists(), mode == 'never')
        self.assertEqual(len(self.approvals), 3)

    def test_auto_queries_never_use_a_shell_or_project_path_executable(self):
        result = self.tools('auto').execute('run_command', {'command': 'pwd'})
        self.assertIn(str(self.root), result)
        self.assertFalse(self.approvals)
        executable = self.root / 'pwd'
        executable.write_text('#!/bin/sh\ntouch hijacked\n')
        executable.chmod(0o755)
        with patch.dict(os.environ, {'PATH': str(self.root) + os.pathsep + os.defpath}):
            result = self.tools('auto').execute('run_command', {'command': 'pwd'})
        self.assertIn(str(self.root), result)
        self.assertFalse((self.root / 'hijacked').exists())

    def test_auto_does_not_trust_shell_syntax_or_tests_and_git_mutations(self):
        commands = ['pwd; touch unexpected', 'pwd && true', 'pwd | cat', 'cat $(pwd)',
                    'cat `pwd`', 'pwd > redirected', 'pwd\ntouch unexpected', 'PATH=x pwd',
                    'python -m unittest', 'npm test', 'npm run build', 'git push', 'git commit -m x',
                    'git reset --hard', 'git clean -fd', 'rm -rf src', 'find . -exec touch bad ;',
                    'rg --pre=touch pattern', 'git -c alias.x=!touch x', './pwd',
                    'cat ../secret', 'cat /etc/passwd', 'cat .env', 'cat --help']
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNone(query_command(self.root, command))
                result = self.tools('auto').execute('run_command', {'command': command})
                self.assertIn('recusada', result)
        self.assertFalse((self.root / 'unexpected').exists())
        self.assertFalse((self.root / 'redirected').exists())

    def test_auto_sensitive_files_links_and_executables_require_review(self):
        (self.root / 'normal').write_text('original')
        (self.root / 'link').symlink_to(self.root / 'normal')
        (self.root / 'executable').write_text('original')
        (self.root / 'executable').chmod(0o755)
        os.link(self.root / 'normal', self.root / 'hardlink')
        tools = self.tools('auto')
        for path in ('.env', '.git/config', '.github/workflows/release.yml', 'secrets/token',
                     'link', 'executable', 'hardlink'):
            self.assertFalse(ordinary_path(self.root, path))
            self.assertIn('recusada', tools.execute('write_file', {'path': path, 'content': 'changed'}))
        self.assertEqual((self.root / 'normal').read_text(), 'original')
        self.assertIsNone(query_command(self.root, 'cat link'))

    def test_never_still_enforces_path_and_credential_guards(self):
        tools = self.tools('never')
        (self.root / 'outside').symlink_to(self.root.parent, target_is_directory=True)
        for path in ('../escape', 'outside/escape'):
            self.assertIn('Erro', tools.execute('write_file', {'path': path, 'content': 'x'}))
        with patch('centaur_cli.tools.credentials_path', return_value=self.root / 'credentials.json'):
            self.assertIn('Credenciais', tools.execute('write_file', {'path': 'credentials.json', 'content': 'x'}))
        self.assertFalse(self.approvals)

    def test_auto_git_queries_disable_fsmonitor_and_other_programs(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        hook = self.root / 'monitor.sh'
        hook.write_text('#!/bin/sh\ntouch monitor-executed\n')
        hook.chmod(0o755)
        subprocess.run(['git', '-C', str(self.root), 'config', 'core.fsmonitor', str(hook)], check=True)
        result = self.tools('auto').execute('run_command', {'command': 'git status --short'})
        self.assertIn('Código de saída: 0', result)
        self.assertFalse((self.root / 'monitor-executed').exists())
        self.assertFalse(self.approvals)

    def test_mode_preferences_and_precedence_are_independent_of_backend(self):
        save_config(self.root, 'codex', 'main', 'high', 'never')
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_approval_mode(self.root), 'never')
        with patch.dict(os.environ, {'CENTAUR_APPROVAL_MODE': 'auto'}, clear=True):
            self.assertEqual(resolve_approval_mode(self.root), 'auto')
            self.assertEqual(resolve_approval_mode(self.root, 'ask'), 'ask')
        save_config(self.root, 'claude', 'sonnet')
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_approval_mode(self.root), 'ask')
        with self.assertRaises(ValueError):
            save_config(self.root, 'claude', 'sonnet', approval_mode='typo')

    def test_startup_and_config_share_mode_choices_and_cancel_keeps_active_mode(self):
        picker = StartupPicker('claude', 'sonnet', 'medium', 'auto')
        for _ in range(3): picker.handle('\n')
        self.assertEqual(picker.page, 'permissions')
        self.assertEqual(picker.options()[picker.selected][0], 'auto')
        picker.handle(curses.KEY_DOWN)
        picker.handle('\n')
        self.assertEqual(picker.approval_mode, 'never')
        terminal = Terminal(self.root, 'main', ChatStore(self.root), None, approval_mode='auto')
        terminal.configure('$config')
        terminal.settings.row = 3
        terminal.handle('\n')
        sibling = ConfigPicker('claude', '', 'default')
        sibling.page = 'permissions'
        self.assertEqual(terminal.settings.options(), sibling.options())
        terminal.handle(curses.KEY_DOWN)
        terminal.handle('\n')
        terminal.handle('\x1b')
        self.assertEqual(terminal.approval_mode, 'auto')
        self.assertEqual(load_config(self.root), {})

    def test_resume_cannot_restore_unrestricted_mode_from_history(self):
        store = ChatStore(self.root)
        old = store.new('main')
        old['approval_mode'] = 'never'
        store.save(old)
        terminal = Terminal(self.root, 'main', store, None, approval_mode='ask')
        terminal.open_chats()
        terminal.handle('\n')
        self.assertEqual(terminal.approval_mode, 'ask')
        self.assertEqual(terminal.chat['approval_mode'], 'ask')

    def test_subagents_inherit_policy_and_do_not_escalate(self):
        for mode in ('ask', 'auto', 'never'):
            base = self.tools(mode)
            client = SimpleNamespace(allows_model_routing=True, backend='openrouter')
            tools = SubagentTools(base, client, 'a' * 32, lambda _: None)
            def execute(chat, client, child, *args):
                self.assertEqual(child.approval_mode, mode)
                child.execute('write_file', {'path': f'{mode}-child.txt', 'content': 'child'})
                chat['messages'].append({'role': 'assistant', 'content': 'Report'})
            with patch('centaur_cli.subagents.run_turn', side_effect=execute):
                tools.delegate({'title': 'task', 'task': 'contract'})
            self.assertEqual((self.root / f'{mode}-child.txt').exists(), mode != 'ask')

    def test_compact_picker_keeps_save_and_never_mode_reachable(self):
        terminal = Terminal(self.root, 'main', ChatStore(self.root), None)
        terminal.configure('$config')
        picker = terminal.settings
        picker.page, picker.selected = 'permissions', 2
        for size in ((24, 100), (18, 40), (12, 40)):
            screen = Screen(size)
            terminal.draw(screen)
            self.assertIn('Sem perguntar', screen.text())
            picker.page, picker.row = 'fields', 4
            terminal.draw(screen)
            self.assertIn('Salvar preferências', screen.text())
            picker.page, picker.selected = 'permissions', 2

    def test_changing_only_mode_preserves_chat_and_its_original_model_effort(self):
        client = SimpleNamespace(backend='openrouter', secrets=())
        terminal = Terminal(self.root, 'main', ChatStore(self.root), client, effort='high')
        terminal.chat['messages'] = [{'role': 'user', 'content': 'Original'}]
        terminal.chat['model'], terminal.chat['effort'] = 'resumed-model', 'low'
        original = terminal.chat['id']
        terminal.store.save(terminal.chat)
        terminal.activate_config('openrouter', 'main', 'high', client, 'auto')
        self.assertEqual(terminal.chat['id'], original)
        self.assertEqual(terminal.chat['model'], 'resumed-model')
        self.assertEqual(terminal.chat['effort'], 'low')
        self.assertEqual(terminal.store.list()[0]['approval_mode'], 'auto')

    def test_history_failure_after_mode_commit_keeps_chat_operational(self):
        client = SimpleNamespace(backend='openrouter', secrets=())
        terminal = Terminal(self.root, 'main', ChatStore(self.root), client)
        terminal.chat['messages'] = [{'role': 'user', 'content': 'Original'}]
        with patch.object(terminal.store, 'save', side_effect=PermissionError('history locked')):
            terminal.activate_config('openrouter', 'main', 'default', client, 'auto')
        self.assertEqual(terminal.approval_mode, 'auto')
        self.assertIn('histórico', terminal.notice)
