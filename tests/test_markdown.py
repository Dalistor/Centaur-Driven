"""Markdown da conversa: o que a tela mostra e quais trechos recebem estilo."""
import curses
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from centaur_cli import keyboard
from centaur_cli.appearance import cell_width
from centaur_cli.history import ChatStore
from centaur_cli.keyboard import KEY_NEWLINE, KeyboardReader
from centaur_cli.markdown import render
from centaur_cli.terminal import Terminal
from test_terminal_settings import Screen


def marked(line, style):
    return [line[begin:end] for begin, end, mark in line.spans if mark == style]


class MarkdownTests(unittest.TestCase):
    def test_emphasis_loses_its_markers_and_keeps_a_style_across_wrapping(self):
        lines = render('Revisei os **quatro repositórios** e o `deploy.yml` com *cuidado*, veja [a doc](https://x.dev/a).', 34)
        text = ' '.join(lines)
        self.assertNotIn('*', text)
        self.assertNotIn('`', text)
        self.assertEqual(' '.join(part for line in lines for part in marked(line, 'strong')), 'quatro repositórios')
        self.assertEqual([part for line in lines for part in marked(line, 'code')], ['deploy.yml'])
        self.assertEqual(' '.join(part for line in lines for part in marked(line, 'link')), 'a doc')
        self.assertIn('(https://x.dev/a)', text)
        self.assertTrue(all(cell_width(line) <= 34 for line in lines))
        # O que não é ênfase fica como foi escrito.
        literal = ' '.join(render('snake_case_name, 2 * 3 * 4 e \\*escapado\\* com caminho a_b/c_d.py', 80))
        self.assertEqual(literal, 'snake_case_name, 2 * 3 * 4 e *escapado* com caminho a_b/c_d.py')

    def test_headings_lists_quotes_and_rules_become_terminal_blocks(self):
        lines = render('## Situação\n\n1. Primeiro item bem comprido que precisa quebrar\n   - sub item\n- [x] feito\n- [ ] falta\n> nota\n---', 30)
        self.assertEqual(lines[0], 'Situação')
        self.assertEqual(marked(lines[0], 'heading'), ['Situação'])
        self.assertEqual(lines[2], '1. Primeiro item bem comprido')
        self.assertEqual(lines[3], '   que precisa quebrar')  # Continuação alinhada ao texto do item.
        self.assertIn('   • sub item', lines)
        self.assertIn('☑ feito', lines)
        self.assertIn('☐ falta', lines)
        self.assertIn('▎ nota', lines)
        self.assertEqual((lines[-1], lines[-1].style), ('─' * 30, 'line'))

    def test_table_is_drawn_with_borders_aligned_columns_and_wrapped_cells(self):
        source = ('| Área | Estado | Evidência |\n|---|:---:|---:|\n'
                  '| CI | **Pronto** | Os quatro rodam testes, build e `actionlint` |\n| Deploy | Ausente | a \\| b |')
        lines = render(source, 44)
        self.assertEqual(len({cell_width(line) for line in lines}), 1)  # Todas as linhas fecham na mesma coluna.
        self.assertLessEqual(cell_width(lines[0]), 44)
        self.assertTrue(lines[0].startswith('┌') and lines[-1].startswith('└'))
        self.assertEqual(marked(lines[1], 'strong'), ['Área', 'Estado', 'Evidência'])
        body = '\n'.join(lines)
        self.assertNotIn('|', body.replace('a | b', ''))
        self.assertNotIn('---', body)
        self.assertIn('a | b', body)  # Separador escapado é conteúdo.
        self.assertEqual([part for line in lines for part in marked(line, 'code')], ['actionlint'])
        self.assertEqual([part for line in lines for part in marked(line, 'strong')][3:], ['Pronto'])
        centered = next(line for line in lines if 'Ausente' in line).split('│')[2]
        self.assertLessEqual(abs(len(centered) - len(centered.lstrip()) - (len(centered) - len(centered.rstrip()))), 1)
        self.assertTrue(next(line for line in lines if 'a | b' in line).split('│')[3].endswith('a | b '))  # Alinhada à direita.
        # Sem largura para colunas, cada linha vira "Cabeçalho: valor".
        narrow = render(source, 18)
        self.assertIn('Área: CI', narrow)
        self.assertTrue(all(cell_width(line) <= 18 for line in narrow))

    def test_code_block_is_literal_and_cut_instead_of_reflowed(self):
        lines = render('```python\nif a  and  b:  # **não é negrito**\n    return "x" * 40\n```\ndepois', 24)
        self.assertEqual((lines[0], lines[0].style), ('  python', 'muted'))
        code = [line for line in lines if line.style == 'code']
        self.assertEqual(''.join(line[2:] for line in code), 'if a  and  b:  # **não é negrito**    return "x" * 40')
        self.assertTrue(all(not line.spans and cell_width(line) <= 24 for line in code))
        self.assertEqual(lines[-1], 'depois')
        # Bloco ainda aberto (resposta em transmissão) não derruba a renderização.
        self.assertEqual([line.style for line in render('```\nparcial', 20)], ['code'])

    def test_sent_message_keeps_line_breaks_and_formatting_in_the_chat(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        terminal = Terminal(Path(temporary.name), 'model', ChatStore(temporary.name), None)
        terminal.chat['messages'] = [{'role': 'user', 'content': 'Faça **isto**:\n- passo `um`\n\nfim'},
                                     {'role': 'assistant', 'content': '# Título\n| a | b |\n|---|---|\n| 1 | 2 |'}]
        lines = terminal.lines(40)
        user = [line for line in lines if line.style == 'user']
        self.assertEqual([str(line) for line in user], ['› Faça isto:', '› • passo um', '›', '› fim'])
        self.assertEqual((marked(user[0], 'strong'), marked(user[1], 'code')), (['isto'], ['um']))
        self.assertIn('│ 1 │ 2 │', lines)
        screen = Screen((40, 60))
        terminal.view.palette.styles.update(strong=201, code=202, line=203)
        with patch('centaur_cli.appearance.curses.curs_set'):
            terminal.draw(screen)
        drawn = {(text, style) for _, _, text, style in screen.output}
        self.assertTrue({('isto', 201), ('um', 202), ('│', 203)} <= drawn)


class NewlineKeyTests(unittest.TestCase):
    class OneKey:
        def __init__(self, key): self.key = key
        def get_wch(self): return self.key
        def timeout(self, value): pass

    def test_enter_with_shift_held_is_a_line_break_where_the_terminal_cannot_tell(self):
        with patch.object(keyboard.SHIFT, 'held', return_value=True):
            self.assertEqual(KeyboardReader().read(self.OneKey('\r'), 100), KEY_NEWLINE)
            self.assertEqual(KeyboardReader().read(self.OneKey('a'), 100), 'a')
        with patch.object(keyboard.SHIFT, 'held', return_value=False):
            self.assertEqual(KeyboardReader().read(self.OneKey('\r'), 100), '\r')

    def test_probe_reads_the_shift_keys_from_the_keymap_and_is_off_outside_a_local_x11_session(self):
        probe = keyboard.ShiftProbe()
        self.assertFalse(probe.held())  # Desligada até a sessão interativa começar.
        probe.enabled, probe.ready, probe.codes, probe.display = True, True, (50, 62), 1
        class Buffer: raw = bytes(32)
        class Library:
            def XQueryKeymap(self, display, buffer): return 1
        probe.library, probe.buffer = Library(), Buffer()
        self.assertFalse(probe.held())
        pressed = bytearray(32); pressed[62 >> 3] |= 1 << (62 & 7)
        probe.buffer = type('Pressed', (), {'raw': bytes(pressed)})()
        self.assertTrue(probe.held())
        for environment in ({'DISPLAY': ''}, {'DISPLAY': ':0', 'WAYLAND_DISPLAY': 'wayland-0'},
                            {'DISPLAY': ':0', 'SSH_CONNECTION': '1 2 3 4'}, {'DISPLAY': ':0', 'CENTAUR_SHIFT_PROBE': '0'}):
            with patch.dict('os.environ', environment), patch('ctypes.CDLL', side_effect=AssertionError('não deve abrir o X11')):
                clean = {key: value for key, value in __import__('os').environ.items()
                         if key not in ('WAYLAND_DISPLAY', 'SSH_CONNECTION', 'CENTAUR_SHIFT_PROBE', 'XDG_SESSION_TYPE') or key in environment}
                with patch.dict('os.environ', clean, clear=True):
                    outside = keyboard.ShiftProbe()
                    outside.enabled = True
                    self.assertFalse(outside.held(), environment)

    def test_backslash_before_enter_breaks_the_line_instead_of_sending(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        terminal = Terminal(Path(temporary.name), 'model', ChatStore(temporary.name), None)
        terminal.draft, terminal.cursor = 'primeira\\', 9
        with patch.object(terminal, 'submit') as submit:
            terminal.handle('\r')
            submit.assert_not_called()
            self.assertEqual((terminal.draft, terminal.cursor), ('primeira\n', 9))
            terminal.handle('\r')
            submit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
