"""Desfazer alterações de arquivo, plano visível e hooks do usuário."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from centaur_cli.checkpoints import Checkpoints
from centaur_cli.conversation import tool_activity
from centaur_cli.history import ChatStore
from centaur_cli.hooks import load_hooks
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools


class Base(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name, 'project').resolve()
        self.root.mkdir()
        self.config = Path(temporary.name, 'config')
        environment = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.config)})
        environment.start()
        self.addCleanup(environment.stop)

    def tools(self, **options):
        return ProjectTools(self.root, lambda _: True, approval_mode='never', **options)


class CheckpointTests(Base):
    def turn(self, name, chat_id='a' * 32):
        tools, checkpoints = self.tools(), Checkpoints(self.root, chat_id)
        tools.before_change = lambda path: checkpoints.record(path, name)
        return tools

    def test_rewind_restores_each_turn_to_its_first_state_newest_first(self):
        (self.root / 'kept.txt').write_text('original\n')
        first = self.turn('one')
        first.execute('edit_file', {'path': 'kept.txt', 'old_string': 'original', 'new_string': 'primeira'})
        first.execute('write_file', {'path': 'kept.txt', 'content': 'segunda\n'})
        first.execute('write_file', {'path': 'new/created.txt', 'content': 'novo\n'})
        second = self.turn('two')
        second.execute('write_file', {'path': 'kept.txt', 'content': 'terceira\n'})
        checkpoints = Checkpoints(self.root, 'a' * 32)
        self.assertEqual(checkpoints.rewind(), (['kept.txt'], []))
        self.assertEqual((self.root / 'kept.txt').read_text(), 'segunda\n')
        self.assertTrue((self.root / 'new/created.txt').exists())
        restored, skipped = checkpoints.rewind()
        self.assertEqual((sorted(restored), skipped), (['kept.txt', 'new/created.txt (removido)'], []))
        self.assertEqual((self.root / 'kept.txt').read_text(), 'original\n')
        self.assertFalse((self.root / 'new/created.txt').exists())
        self.assertEqual(checkpoints.rewind(), ([], []))

    def test_refused_changes_are_not_recorded_and_other_chats_are_untouched(self):
        (self.root / 'a.txt').write_text('a\n')
        tools, checkpoints = ProjectTools(self.root, lambda _: False), Checkpoints(self.root, 'a' * 32)
        tools.before_change = lambda path: checkpoints.record(path, 'one')
        tools.execute('write_file', {'path': 'a.txt', 'content': 'b\n'})
        self.assertEqual(checkpoints.rewind(), ([], []))
        self.turn('one', 'b' * 32).execute('write_file', {'path': 'a.txt', 'content': 'b\n'})
        self.assertEqual(checkpoints.rewind(), ([], []))
        self.assertEqual((self.root / 'a.txt').read_text(), 'b\n')

    def test_terminal_rewind_restores_files_and_tells_the_model(self):
        store = ChatStore(self.root)
        terminal = Terminal(self.root, 'provider/main', store, None)
        (self.root / 'a.txt').write_text('antes\n')
        self.turn('one', terminal.chat['id']).execute('write_file', {'path': 'a.txt', 'content': 'depois\n'})
        terminal.draft = '/rewind'
        terminal.submit()
        self.assertEqual((self.root / 'a.txt').read_text(), 'antes\n')
        self.assertIn('a.txt', terminal.chat['messages'][-1]['content'])
        self.assertIn('releia', terminal.chat['messages'][-1]['content'])
        terminal.draft = '/rewind'
        terminal.submit()
        self.assertIn('Nenhuma alteração', terminal.notice)
        self.assertEqual(len(terminal.chat['messages']), 2)
        store.save(terminal.chat)
        self.turn('two', terminal.chat['id']).execute('write_file', {'path': 'a.txt', 'content': 'x\n'})
        store.delete(terminal.chat['id'])
        self.assertFalse((self.root / '.centaur/checkpoints' / terminal.chat['id']).exists())


class PlanTests(Base):
    def test_plan_is_validated_and_rendered_for_model_and_transcript(self):
        steps = [{'step': 'Ler o módulo', 'status': 'completed'}, {'step': 'Corrigir a falha', 'status': 'in_progress'},
                 {'step': 'Rodar os testes', 'status': 'pending'}]
        result = self.tools().execute('update_plan', {'steps': steps})
        self.assertEqual(result, 'Plano · 1/3 concluídas\n✓ Ler o módulo\n▸ Corrigir a falha\n○ Rodar os testes')
        call = {'function': {'name': 'update_plan', 'arguments': json.dumps({'steps': steps})}}
        self.assertEqual(tool_activity(call, result), result)
        self.assertEqual(tool_activity(call), '○ Atualizando plano')
        self.assertIn('Erro', self.tools().execute('update_plan', {'steps': [{'step': 'x', 'status': 'done'}]}))
        self.assertIn('Erro', self.tools().execute('update_plan', {'steps': []}))


class HookTests(Base):
    def configure(self, hooks, mode=0o600):
        self.config.joinpath('centaur').mkdir(parents=True, exist_ok=True)
        path = self.config / 'centaur' / 'hooks.json'
        path.write_text(json.dumps({'hooks': hooks}))
        path.chmod(mode)

    def test_before_hook_blocks_with_code_two_and_receives_the_call(self):
        self.configure([{'event': 'before_tool', 'tools': 'write_file|edit_file',
                         'command': 'cat > "$CENTAUR_PROJECT/seen.json"; case "$CENTAUR_TOOL_PATH" in *.lock) echo "arquivo gerado"; exit 2;; esac'}])
        tools = self.tools()
        self.assertEqual(tools.execute('write_file', {'path': 'deps.lock', 'content': 'x'}), 'Bloqueado por hook do usuário: arquivo gerado')
        self.assertFalse((self.root / 'deps.lock').exists())
        seen = json.loads((self.root / 'seen.json').read_text())
        self.assertEqual((seen['event'], seen['tool'], seen['arguments']['path']), ('before_tool', 'write_file', 'deps.lock'))
        self.assertIn('gravado', tools.execute('write_file', {'path': 'ok.txt', 'content': 'x'}))
        (self.root / 'seen.json').unlink()
        self.assertEqual(tools.execute('read_file', {'path': 'ok.txt'}), '1\tx')
        self.assertFalse((self.root / 'seen.json').exists())

    def test_after_hook_failure_is_appended_to_the_result_and_success_is_silent(self):
        self.configure([{'event': 'after_tool', 'tools': 'write_file', 'command': 'grep -q proibido "$CENTAUR_TOOL_PATH" && { echo "lint: termo proibido"; exit 1; }; echo ok'}])
        tools = self.tools()
        self.assertIn('[Hook após write_file (código 1): lint: termo proibido]', tools.execute('write_file', {'path': 'a.txt', 'content': 'proibido'}))
        self.assertNotIn('Hook', tools.execute('write_file', {'path': 'b.txt', 'content': 'limpo'}))

    def test_hooks_are_scoped_by_project_and_secrets_stay_out_of_their_environment(self):
        self.configure([{'event': 'after_tool', 'command': 'echo outro; exit 1', 'project': str(self.root.parent / 'other')},
                        {'event': 'after_tool', 'command': 'echo "chave=$OPENROUTER_API_KEY"; exit 1', 'project': str(self.root)}])
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'segredo'}):
            result = self.tools().execute('list_files', {'path': '.'})
        self.assertIn('chave=]', result)
        self.assertNotIn('outro', result)

    def test_invalid_or_writable_configuration_disables_hooks_and_says_so_once(self):
        self.configure([{'event': 'sometimes', 'command': 'exit 2'}])
        tools = self.tools()
        self.assertIn('Hooks desativados', tools.execute('list_files', {'path': '.'}))
        self.assertNotIn('Hooks desativados', tools.execute('list_files', {'path': '.'}))
        self.configure([{'event': 'before_tool', 'command': 'exit 2'}], mode=0o666)
        self.assertEqual(load_hooks(self.root)[0], [])
        self.assertIn('sem escrita', load_hooks(self.root)[1])
        self.assertEqual(load_hooks(self.root.parent / 'missing')[1], load_hooks(self.root)[1])
        (self.config / 'centaur' / 'hooks.json').unlink()
        self.assertEqual(load_hooks(self.root), ([], None))

    def test_model_tools_cannot_reach_the_hook_configuration(self):
        self.configure([])
        relative = os.path.relpath(self.config / 'centaur' / 'hooks.json', self.root)
        self.assertIn('Erro', self.tools().execute('write_file', {'path': relative, 'content': '{}'}))
        self.assertEqual(json.loads((self.config / 'centaur' / 'hooks.json').read_text()), {'hooks': []})


if __name__ == '__main__':
    unittest.main()
