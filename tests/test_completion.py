import curses
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from centaur_cli.agent import project_prompt
from centaur_cli.completion import SkillCompletion
from centaur_cli.history import ChatStore
from centaur_cli.skill_catalog import additional_names
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools


class CompletionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.terminal = Terminal(self.root, 'test', ChatStore(self.root), None)

    def put(self, path, body):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding='utf-8')

    def type(self, text):
        for char in text:
            self.terminal.handle(char)

    def test_dollar_filters_centaur_skills_and_enter_only_inserts(self):
        self.type('Execute $ru')
        completion = self.terminal.completion
        completion.update(self.terminal.draft)
        self.assertEqual(completion.options, ['run'])
        with patch('centaur_cli.terminal.threading.Thread') as thread:
            self.terminal.handle('\n')
            thread.assert_not_called()
        self.assertEqual(self.terminal.draft, 'Execute $run ')
        self.assertFalse(self.terminal.chat['messages'])

    def test_arrows_select_tab_inserts_and_escape_allows_literal_text(self):
        self.type('$')
        self.terminal.handle(curses.KEY_DOWN)
        choice = self.terminal.completion.options[1]
        self.terminal.handle('\t')
        self.assertEqual(self.terminal.draft, '$' + choice + ' ')
        self.terminal.draft = '$run'
        self.terminal.handle('\x1b')
        self.terminal.completion.update(self.terminal.draft)
        self.assertFalse(self.terminal.completion.visible)
        self.type(' texto')
        self.assertEqual(self.terminal.draft, '$run texto')

    def test_at_only_lists_complete_project_skills_and_reads_their_resources(self):
        self.put('.centaur/skills/custom/SKILL.md', 'Instruções adicionais')
        self.put('.centaur/skills/custom/references/guide.md', 'Guia adicional')
        self.put('.centaur/skills/incomplete/notes.md', 'não é skill')
        self.put('.agents/skills/elsewhere/SKILL.md', 'outro cliente')
        self.type('Use @cu')
        self.terminal.handle('\t')
        self.assertEqual(self.terminal.draft, 'Use @custom ')
        self.assertEqual(additional_names(self.root), ['custom'])
        tools = ProjectTools(self.root, lambda _: False)
        self.assertIn('Instruções adicionais', tools.execute('read_skill', {'path': '@custom/SKILL.md', 'start_line': '1'}))
        self.assertIn('Guia adicional', tools.execute('read_skill', {'path': '@custom/references/guide.md', 'start_line': '1'}))
        self.assertIn('custom', project_prompt(self.root))

    def test_same_name_keeps_centaur_and_additional_skills_separate(self):
        self.put('.centaur/skills/run/SKILL.md', 'Meu run adicional')
        tools = ProjectTools(self.root, lambda _: False)
        self.assertIn('Meu run adicional', tools.execute('read_skill', {'path': '@run/SKILL.md', 'start_line': '1'}))
        self.assertNotIn('Meu run adicional', tools.execute('read_skill', {'path': 'run/SKILL.md', 'start_line': '1'}))

    def test_subskills_are_not_suggested_and_nonmention_tokens_do_not_open_popup(self):
        completion = SkillCompletion(self.root)
        completion.update('$')
        self.assertNotIn('memory', completion.options)
        for draft in ('mail@example.com', 'echo$PATH', 'Use $run agora', '@ausente'):
            completion.update(draft)
            self.assertFalse(completion.visible)

    def test_additional_resources_cannot_escape_skill_or_project(self):
        self.put('.centaur/skills/custom/SKILL.md', 'custom')
        self.put('.centaur/skills/other/SKILL.md', 'other')
        tools = ProjectTools(self.root, lambda _: False)
        self.assertIn('Erro', tools.execute('read_skill', {'path': '@custom/../other/SKILL.md', 'start_line': '1'}))
        (self.root / '.centaur/skills/external').symlink_to(self.root.parent, target_is_directory=True)
        self.assertNotIn('external', additional_names(self.root))
        (self.root / '.centaur/skills/custom/references').symlink_to(self.root.parent, target_is_directory=True)
        self.assertIn('Erro', tools.execute('read_skill', {'path': '@custom/references/file', 'start_line': '1'}))

    def test_chat_navigation_still_works_while_completion_is_open(self):
        self.type('$')
        self.terminal.handle(curses.KEY_SLEFT)
        self.assertTrue(self.terminal.browser)
        self.terminal.handle('\x1b')
        self.assertFalse(self.terminal.browser)
        self.assertEqual(self.terminal.draft, '$')

    def test_dismissal_is_reset_after_editing_the_draft(self):
        completion = SkillCompletion(self.root)
        completion.update('$run')
        completion.dismiss('$run')
        completion.update('$run')
        self.assertFalse(completion.visible)
        completion.update('')
        completion.update('$run')
        self.assertTrue(completion.visible)

    def test_filter_change_and_backspace_refresh_choices(self):
        self.type('$ru')
        self.terminal.handle(curses.KEY_BACKSPACE)
        self.terminal.completion.update(self.terminal.draft)
        self.assertEqual(self.terminal.completion.options, ['run'])
        self.terminal.handle('\x15')
        self.type('$sp')
        self.terminal.completion.update(self.terminal.draft)
        self.assertEqual(self.terminal.completion.options, ['spec'])


if __name__ == '__main__':
    unittest.main()
