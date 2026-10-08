import curses
from io import StringIO
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch

from centaur_cli.appearance import TerminalView, cell_width
from centaur_cli.composer import layout_input
from centaur_cli.history import ChatStore
from centaur_cli.keyboard import KEY_NEWLINE, KEY_IGNORE, KEY_FOCUS_IN, KEY_FOCUS_OUT, PastedText, KeyboardReader, keyboard_protocol, read_key
from centaur_cli.terminal import Terminal
from test_terminal_settings import Screen


class InputScreen:
    def __init__(self, keys): self.keys, self.timeouts = list(keys), []
    def get_wch(self):
        if not self.keys: raise curses.error()
        return self.keys.pop(0)
    def timeout(self, value): self.timeouts.append(value)


class KeyboardTests(unittest.TestCase):
    def test_plain_csi_and_application_arrows_are_not_inserted_as_text(self):
        for prefix in ('\x1b[', '\x1bO'):
            for suffix, expected in (('A', curses.KEY_UP), ('B', curses.KEY_DOWN),
                                     ('C', curses.KEY_RIGHT), ('D', curses.KEY_LEFT),
                                     ('H', curses.KEY_HOME), ('F', curses.KEY_END)):
                self.assertEqual(read_key(InputScreen(prefix + suffix)), expected)
        for name, expected in ((b'kxIN', KEY_FOCUS_IN), (b'kxOUT', KEY_FOCUS_OUT)):
            with patch('centaur_cli.keyboard.curses.keyname', return_value=name):
                self.assertEqual(read_key(InputScreen([591])), expected)

    def test_shift_enter_encodings_ctrl_shortcuts_and_release(self):
        for sequence in ('\x1b[13;2u', '\x1b[13;2:1u', '\x1b[13;2:2u', '\x1b[13;66u', '\x1b[27;2;13~'):
            self.assertEqual(read_key(InputScreen(sequence)), KEY_NEWLINE, sequence)
        for sequence, expected in [('\x1b[13u', '\r'), ('\x1b[13;1u', '\r'),
                                  ('\x1b[99;5u', '\x03'), ('\x1b[27;5;106~', '\n'),
                                  ('\x1b[13;1:2u', KEY_IGNORE), ('\x1b[13;65:2u', KEY_IGNORE),
                                  ('\x1b[13;2:3u', KEY_IGNORE), ('\x1b[1;2D', curses.KEY_SLEFT),
                                  ('\x1b[I', KEY_FOCUS_IN), ('\x1b[O', KEY_FOCUS_OUT)]:
            self.assertEqual(read_key(InputScreen(sequence)), expected, sequence)

    def test_incomplete_protocol_is_not_replayed_as_draft_text(self):
        screen = InputScreen('\x1b[13;')
        with patch('centaur_cli.keyboard.curses.unget_wch') as restore:
            self.assertEqual(read_key(screen, 80), KEY_IGNORE)
        restore.assert_not_called()
        self.assertEqual(screen.timeouts[-1], 80)

    def test_modified_enter_survives_gaps_at_every_boundary(self):
        for sequence in ('\x1b\r', '\x1b[13;2u', '\x1b[27;2;13~'):
            for split in range(1, len(sequence)):
                with self.subTest(sequence=sequence, split=split):
                    reader = KeyboardReader()
                    screen = InputScreen(sequence[:split])
                    with patch('centaur_cli.keyboard.time.monotonic', return_value=10):
                        self.assertEqual(reader.read(screen, 40), KEY_IGNORE)
                    screen.keys.extend(sequence[split:])
                    with patch('centaur_cli.keyboard.time.monotonic', return_value=10.1):
                        self.assertEqual(reader.read(screen, 40), KEY_NEWLINE)
                    self.assertIsNone(reader.escape)
                    self.assertEqual(screen.timeouts[-1], 40)

    def test_standalone_escape_and_expired_protocol_have_bounded_wait(self):
        for prefix, expected in (('\x1b', '\x1b'), ('\x1b[13;', KEY_IGNORE)):
            reader = KeyboardReader()
            screen = InputScreen(prefix)
            with patch('centaur_cli.keyboard.time.monotonic', return_value=10):
                self.assertEqual(reader.read(screen), KEY_IGNORE)
            with patch('centaur_cli.keyboard.time.monotonic', return_value=10.3):
                self.assertEqual(reader.read(screen), expected)
            screen.keys.append('x')
            self.assertEqual(reader.read(screen), 'x')

    def test_resize_cancel_and_damaged_frame_do_not_submit(self):
        reader = KeyboardReader()
        screen = InputScreen(list('\x1b[13;') + [curses.KEY_RESIZE])
        self.assertEqual(reader.read(screen), curses.KEY_RESIZE)
        screen.keys.extend('2u')
        self.assertEqual(reader.read(screen), KEY_NEWLINE)
        screen.keys.extend('\x1b[13;\r')
        self.assertEqual(reader.read(screen), KEY_IGNORE)
        screen.keys.extend('\x1b[13;\x03')
        self.assertEqual(reader.read(screen), '\x03')
        self.assertIsNone(reader.escape)

    def test_multiline_paste_is_atomic_and_continues_across_reads(self):
        reader = KeyboardReader()
        screen = InputScreen('\x1b[200~first\r\nsecond\t')
        self.assertEqual(reader.read(screen), KEY_IGNORE)
        screen.keys.extend(list('third\x1b[201~'))
        self.assertEqual(reader.read(screen), PastedText('first\nsecond    third'))
        self.assertIsNone(reader.paste)
        self.assertEqual(screen.timeouts[-1], 100)

    def test_resize_and_cancel_during_paste(self):
        reader = KeyboardReader()
        screen = InputScreen(list('\x1b[200~abc') + [curses.KEY_RESIZE])
        self.assertEqual(reader.read(screen), curses.KEY_RESIZE)
        screen.keys.append('\x03')
        self.assertEqual(reader.read(screen), '\x03')
        self.assertIsNone(reader.paste)

    def test_keyboard_modes_restore_on_exception_and_skip_redirected_output(self):
        class TTY(StringIO):
            def isatty(self): return True
        stream = TTY()
        with self.assertRaises(RuntimeError):
            with keyboard_protocol(stream): raise RuntimeError('fixture')
        self.assertEqual(stream.getvalue(), '\x1b[>1u\x1b[>4;2m\x1b[?2004h\x1b[?1004h\x1b[?1004l\x1b[?2004l\x1b[>4m\x1b[<1u')
        stream = StringIO()
        with keyboard_protocol(stream): pass
        self.assertEqual(stream.getvalue(), '')


class ComposerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ChatStore(self.root)
        self.terminal = Terminal(self.root, 'model', self.store, None)

    def test_prompt_history_moves_backward_forward_and_restores_empty_or_current_draft(self):
        terminal = self.terminal
        terminal.chat['messages'] = [
            {'role': 'user', 'content': '$spec primeira'},
            {'role': 'assistant', 'content': 'Resposta'},
            {'role': 'user', 'content': 'segunda\nlinha'}]
        original = [dict(m) for m in terminal.chat['messages']]
        for draft in ('', 'rascunho atual'):
            terminal.draft = draft
            terminal.cursor = min(3, len(draft))
            cursor = terminal.cursor
            terminal.handle(curses.KEY_UP)
            self.assertEqual(terminal.draft, 'segunda\nlinha')
            terminal.handle(curses.KEY_UP)
            self.assertEqual(terminal.draft, '$spec primeira')
            terminal.handle(curses.KEY_UP)
            self.assertEqual(terminal.draft, '$spec primeira')
            terminal.handle(curses.KEY_DOWN)
            self.assertEqual(terminal.draft, 'segunda\nlinha')
            terminal.handle(curses.KEY_DOWN)
            self.assertEqual((terminal.draft, terminal.cursor), (draft, cursor))
            self.assertEqual(terminal.chat['messages'], original)
        terminal.draft = ''
        terminal.handle(curses.KEY_UP)
        terminal.handle('!')
        self.assertIsNone(terminal.prompt_history)
        self.assertEqual(terminal.chat['messages'], original)

    def test_soft_wrap_preserves_spaces_wide_characters_and_combining_marks(self):
        text = 'ab  汉e\u0301字end'
        layout = layout_input(text, 6)
        self.assertEqual(''.join(layout.lines), text)
        self.assertTrue(all(cell_width(line) <= 6 for line in layout.lines))
        self.assertEqual(layout.positions[7], layout.positions[6])

    def test_explicit_blank_lines_and_exact_width_keep_insertion_point_visible(self):
        self.assertEqual(layout_input('abc\n\nend\n', 8).lines, ['abc', '', 'end', ''])
        layout = layout_input('abcd', 4)
        self.assertEqual(layout.lines, ['abcd', ''])
        self.assertEqual(layout.positions[-1], (1, 0))

    def test_newline_at_cursor_does_not_submit_or_complete_skill(self):
        terminal = self.terminal
        terminal.draft = 'Execute $ru'
        with patch.object(terminal, 'start_work') as start:
            terminal.handle(KEY_NEWLINE)
            self.assertEqual(terminal.draft, 'Execute $ru\n')
            terminal.cursor = 7
            terminal.handle('\n')
            self.assertEqual(terminal.draft, 'Execute\n $ru\n')
            start.assert_not_called()
        self.assertFalse(terminal.chat['messages'])

    def test_enter_submits_whole_multiline_message_once(self):
        terminal = self.terminal
        terminal.draft = '$config é assunto\nsegunda linha'
        with patch.object(terminal, 'start_work') as start:
            terminal.handle('\r')
            start.assert_called_once()
        self.assertEqual(terminal.chat['messages'][0]['content'], '$config é assunto\nsegunda linha')
        self.assertNotIn('\n', terminal.chat['title'])
        self.assertEqual(terminal.draft, '')

    def test_paste_preserves_content_and_never_confirms_an_approval(self):
        terminal = self.terminal
        terminal.draft = 'prefixsuffix'
        terminal.cursor = 6
        terminal.handle(PastedText('first\nsecond'))
        self.assertEqual(terminal.draft, 'prefixfirst\nsecondsuffix')
        self.assertFalse(terminal.chat['messages'])
        answer = queue.Queue()
        terminal.approval = ('Aprovar?', answer)
        terminal.handle(PastedText('y\n'))
        self.assertTrue(answer.empty())
        self.assertIsNotNone(terminal.approval)

    def test_vertical_movement_remembers_column_across_short_lines(self):
        terminal = self.terminal
        terminal.draft = 'abcdef\nx\nabcdef'
        terminal.handle(curses.KEY_UP)
        self.assertEqual(terminal.cursor, 8)
        terminal.handle(curses.KEY_UP)
        self.assertEqual(terminal.cursor, 6)
        terminal.handle(curses.KEY_DOWN)
        terminal.handle(curses.KEY_DOWN)
        self.assertEqual(terminal.cursor, len(terminal.draft))
        self.assertEqual(terminal.scroll, 0)

    def test_backspace_and_delete_edit_explicit_line_boundaries(self):
        terminal = self.terminal
        terminal.draft = 'first\nsecond'
        terminal.cursor = 6
        terminal.handle(curses.KEY_BACKSPACE)
        self.assertEqual(terminal.draft, 'firstsecond')
        terminal.insert_text('\n')
        terminal.handle(curses.KEY_LEFT)
        terminal.handle(curses.KEY_DC)
        self.assertEqual(terminal.draft, 'firstsecond')

    def test_three_row_bar_grows_and_scrolls_while_preserving_draft_on_resize(self):
        terminal = self.terminal
        view = TerminalView()
        screen = Screen((24, 80))
        view.draw(screen, terminal)
        bars = [row for row, column, text, _ in screen.output if column == 2 and len(text) == 75 and text.isspace()]
        self.assertEqual(bars, [19, 20, 21])
        terminal.draft = '\n'.join(f'linha {i}' for i in range(15))
        expected = terminal.draft
        for size in ((24, 80), (12, 40), (34, 120)):
            screen = Screen(size)
            view.draw(screen, terminal)
            self.assertIn('linha 14', screen.text())
            self.assertIn('↑', screen.text())
            self.assertEqual(terminal.draft, expected)
            self.assertLess(screen.cursor[0], size[0] - 2)
        terminal.handle(curses.KEY_HOME)
        screen = Screen((24, 80))
        view.draw(screen, terminal)
        self.assertIn('linha 0', screen.text())
        self.assertIn('↓', screen.text())
        self.assertEqual(screen.cursor[1], 4)
