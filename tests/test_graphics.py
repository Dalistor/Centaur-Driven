import curses
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from centaur_cli.appearance import Palette, TerminalView
from centaur_cli.graphics import DOT_BITS, FRAME_SECONDS, Renderer, SPIN_SECONDS, WelcomeAnimation
from centaur_cli.history import ChatStore
from centaur_cli.terminal import Terminal, read_key
from test_terminal_settings import Screen


class GraphicsTests(unittest.TestCase):
    def test_projection_is_deterministic_bounded_and_visible_through_rotation(self):
        renderer = Renderer()
        for columns, rows in ((36, 16), (26, 10), (1, 1)):
            for progress in (0, .2, .4, .6, .8, 1):
                frame = renderer.frame(columns, rows, progress)
                self.assertEqual(len(frame), rows)
                self.assertTrue(all(len(line) == columns for line in frame))
                self.assertTrue(all(cell.glyph == ' ' or 0x2801 <= ord(cell.glyph) <= 0x28ff
                                    for line in frame for cell in line))
                self.assertTrue(all(0 <= cell.shade <= 15 for line in frame for cell in line))
                if columns > 1:
                    self.assertTrue(any(cell.glyph != ' ' for line in frame for cell in line))
        self.assertEqual(renderer.frame(36, 16), renderer.frame(36, 16, 1))
        self.assertNotEqual(renderer.frame(36, 16, .2), renderer.frame(36, 16, .4))
        self.assertTrue(any(cell.accent for line in renderer.frame(36, 16) for cell in line))
        for size in ((0, 1), (37, 16), (36, 17)):
            with self.assertRaises(ValueError): renderer.frame(*size)

    def test_animation_makes_a_full_turn_and_returns_to_front(self):
        renderer = Renderer()
        for size in ((36, 16), (26, 10)):
            stages = []
            for progress in (0, .35, .5, .65, 1):
                with self.subTest(size=size, progress=progress):
                    frame = renderer.frame(*size, progress)
                    dots = [(x * 2 + dx, y * 4 + dy)
                            for y, row in enumerate(frame) for x, cell in enumerate(row)
                            if cell.glyph != ' '
                            for dy, pair in enumerate(DOT_BITS) for dx, bit in enumerate(pair)
                            if (ord(cell.glyph) - 0x2800) & bit]
                    self.assertTrue(dots)
                    stages.append(dots)
            front, side, back, other_side, final = stages
            self.assertEqual(front, final)
            front_width = max(x for x, _ in front) - min(x for x, _ in front)
            for edge in (side, other_side):
                self.assertLess(max(x for x, _ in edge) - min(x for x, _ in edge), front_width * .5)
            right_tip = [y for x, y in front if x == max(x for x, _ in front)]
            left_tip = [y for x, y in back if x == min(x for x, _ in back)]
            self.assertTrue(all(abs(y - size[1] * 2) <= 3 for y in right_tip + left_tip))

    def test_frame_sampling_is_consistent_within_one_animation_tick(self):
        animation = WelcomeAnimation()
        animation.frame(26, 10, 0)
        with patch.object(animation.renderer, 'frame', wraps=animation.renderer.frame) as render:
            first = animation.frame(26, 10, FRAME_SECONDS * .8)
            second = animation.frame(26, 10, FRAME_SECONDS * 1.1)
        self.assertIs(first, second)
        self.assertEqual(render.call_count, 1)
        self.assertAlmostEqual(render.call_args.args[2], FRAME_SECONDS / SPIN_SECONDS)

    def test_visible_clock_pauses_hidden_and_stops_at_final_pose(self):
        animation = WelcomeAnimation()
        animation.frame(26, 10, 0)
        animation.frame(26, 10, 1)
        self.assertEqual(animation.elapsed, 1)
        animation.pause()
        animation.frame(26, 10, 100)
        self.assertEqual(animation.elapsed, 1)
        animation.frame(26, 10, 101)
        self.assertEqual(animation.elapsed, 2)
        final = animation.frame(26, 10, 110)
        self.assertFalse(animation.active)
        self.assertEqual(animation.elapsed, SPIN_SECONDS)
        with patch.object(animation.renderer, 'frame', side_effect=AssertionError('idle render')):
            self.assertIs(animation.frame(26, 10, 200), final)
        animation.replay()
        self.assertEqual(animation.elapsed, 0)
        self.assertNotEqual(animation.frame(26, 10, 201), final)
        self.assertTrue(animation.active)

    def test_reduced_motion_and_typing_render_stable_final_pose(self):
        animation = WelcomeAnimation()
        first = animation.frame(26, 10, 0, reduced=True)
        self.assertIs(animation.frame(26, 10, 20, reduced=True), first)
        self.assertFalse(animation.active)
        animation.replay()
        self.assertEqual(animation.frame(26, 10, 30, editing=True), first)
        self.assertEqual(animation.frame(26, 10, 31), first)
        self.assertFalse(animation.active)

    def test_monochrome_inherits_default_colors_and_has_readable_shades(self):
        palette = Palette()
        with patch.dict(os.environ, {'NO_COLOR': '1'}), \
                patch('centaur_cli.appearance.curses.has_colors', return_value=True), \
                patch('centaur_cli.appearance.curses.start_color'), \
                patch('centaur_cli.appearance.curses.use_default_colors') as defaults, \
                patch('centaur_cli.appearance.curses.init_pair') as initialize:
            palette.initialize()
        initialize.assert_not_called()
        defaults.assert_called_once()
        self.assertNotEqual(palette.styles[palette.graphic_style(2, False)],
                            palette.styles[palette.graphic_style(14, False)])
        self.assertTrue(palette.styles['selected'] & curses.A_BOLD)
        self.assertFalse(palette.styles['selected'] & curses.A_REVERSE)

    def test_real_view_resizes_preserves_draft_and_pauses_on_other_surfaces(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terminal = Terminal(root, 'test', ChatStore(root), None)
            view = terminal.view
            for size in ((34, 110), (24, 80), (42, 60), (18, 45), (12, 40), (8, 30)):
                screen = Screen(size)
                view.draw(screen, terminal)
                if size[0] == 18:
                    self.assertIn('Digite', screen.text())
            terminal.draft = 'Intenção sem enviar'
            view.draw(Screen((34, 110)), terminal)
            self.assertEqual(terminal.draft, 'Intenção sem enviar')
            self.assertFalse(view.animation.active)
            terminal.draft = ''
            terminal.handle(curses.KEY_F5)
            view.draw(Screen((34, 110)), terminal)
            self.assertTrue(view.animation.active)
            terminal.open_chats()
            view.draw(Screen((34, 110)), terminal)
            self.assertFalse(view.animation.active)
            elapsed = view.animation.elapsed
            terminal.handle(curses.KEY_F5)
            self.assertEqual(view.animation.elapsed, elapsed)

    def test_native_palette_preserves_background_and_slots_on_8_and_256_colors(self):
        for count in (8, 256):
            with self.subTest(colors=count), patch.dict(os.environ, {}, clear=True), \
                    patch('centaur_cli.appearance.curses.has_colors', return_value=True), \
                    patch('centaur_cli.appearance.curses.start_color'), \
                    patch('centaur_cli.appearance.curses.use_default_colors') as defaults, \
                    patch('centaur_cli.appearance.curses.COLORS', count, create=True), \
                    patch('centaur_cli.appearance.curses.COLOR_PAIRS', count, create=True), \
                    patch('centaur_cli.appearance.curses.init_color') as colors, \
                    patch('centaur_cli.appearance.curses.init_pair') as pairs, \
                    patch('centaur_cli.appearance.curses.color_pair', side_effect=lambda pair: pair << 8):
                palette = Palette(); palette.initialize(); palette.restore()
                defaults.assert_called_once()
                colors.assert_not_called()
                self.assertTrue(pairs.call_args_list)
                self.assertTrue(all(call.args[2] == -1 for call in pairs.call_args_list[:4]))
                self.assertEqual(pairs.call_args_list[4].args, (5, 252 if count == 256 else curses.COLOR_WHITE,
                                                              238 if count == 256 else curses.COLOR_BLACK))
                self.assertEqual(pairs.call_args_list[0].args[1], -1)
                self.assertNotEqual(palette.styles['text'], palette.styles['input'])
                self.assertEqual(palette.styles['text'], palette.styles['panel_comment'])
                self.assertNotEqual(palette.styles['panel_comment'], palette.styles['panel_action'])
                self.assertTrue(palette.styles['selected'] & curses.A_BOLD)
                self.assertFalse(any(style & curses.A_REVERSE for style in palette.styles.values()))

    def test_unsupported_default_colors_falls_back_without_painting_background(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch('centaur_cli.appearance.curses.has_colors', return_value=True), \
                patch('centaur_cli.appearance.curses.start_color'), \
                patch('centaur_cli.appearance.curses.use_default_colors', side_effect=curses.error('unsupported')), \
                patch('centaur_cli.appearance.curses.init_color') as colors, \
                patch('centaur_cli.appearance.curses.init_pair') as pairs:
            palette = Palette(); palette.initialize(); palette.restore()
            colors.assert_not_called(); pairs.assert_not_called()
            self.assertEqual(palette.styles['input'], 0)
            self.assertEqual(palette.styles['selected'], curses.A_BOLD)
            self.assertNotEqual(palette.styles['action'], palette.styles['comment'])

    def test_rejected_accent_stays_readable_and_cleanup_survives_errors(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch('centaur_cli.appearance.curses.has_colors', return_value=True), \
                patch('centaur_cli.appearance.curses.start_color'), \
                patch('centaur_cli.appearance.curses.use_default_colors'), \
                patch('centaur_cli.appearance.curses.COLOR_PAIRS', 8, create=True), \
                patch('centaur_cli.appearance.curses.init_pair', side_effect=curses.error('unsupported')):
            palette = Palette(); palette.initialize()
            self.assertEqual(palette.styles['warning'], curses.A_BOLD)
            self.assertEqual(palette.styles['input'], 0)
        with tempfile.TemporaryDirectory() as directory:
            terminal = Terminal(Path(directory), 'test', ChatStore(directory), None)
            with patch.object(terminal, '_run', side_effect=curses.error('fixture')), \
                    patch.object(terminal.view.palette, 'restore') as restore:
                with self.assertRaises(curses.error): terminal.run(None)
            restore.assert_called_once()

    def test_ascii_encoding_retains_readable_static_fallback(self):
        with patch('centaur_cli.appearance.sys.stdout') as output:
            output.encoding = 'ascii'
            view = TerminalView()
            screen = Screen((34, 110))
            view.logo(screen, 5, 5)
            self.assertIn('C E N T A U R', screen.text())
            self.assertTrue(all(ord(char) < 128 for char in screen.text()))
            self.assertFalse(view.animation.active)

    def test_graphics_opt_out_uses_the_static_mark(self):
        with patch.dict(os.environ, {'CENTAUR_GRAPHICS': '0'}):
            view = TerminalView()
            screen = Screen((34, 110))
            view.logo(screen, 5, 5)
            self.assertIn('C E N T A U R', screen.text())
            self.assertFalse(any(0x2800 <= ord(c) <= 0x28ff for c in screen.text()))
            self.assertFalse(view.animation.active)

    def test_escape_decoder_restores_animation_timeout(self):
        class Input:
            def __init__(self): self.keys, self.timeouts = iter('\x1b[1;2D'), []
            def get_wch(self): return next(self.keys)
            def timeout(self, value): self.timeouts.append(value)
        screen = Input()
        self.assertEqual(read_key(screen, 40), curses.KEY_SLEFT)
        self.assertEqual(screen.timeouts, [25, 40])


if __name__ == '__main__': unittest.main()
