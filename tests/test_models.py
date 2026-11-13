"""Seleção de modelo: o que cada opção é, o que o provedor serve e a abertura visual."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from centaur_cli import models
from centaur_cli.graphics import DOT_BITS, GLINT_START, REVEAL_SECONDS, Renderer, SPIN_SECONDS, WelcomeAnimation
from centaur_cli.history import ChatStore
from centaur_cli.native_client import NativeClient
from centaur_cli.settings import ConfigPicker
from centaur_cli.startup import StartupWizard
from centaur_cli.terminal import Terminal
from test_terminal_settings import Screen

CATALOG = [
    {'id': 'anthropic/claude-sonnet-5.5', 'name': 'Anthropic: Claude Sonnet 5.5', 'context_length': 1000000,
     'pricing': {'prompt': '0.000003', 'completion': '0.000015'}, 'supported_parameters': ['tools', 'reasoning'],
     'architecture': {'input_modalities': ['text', 'image', 'file']}, 'top_provider': {'max_completion_tokens': 64000}},
    {'id': 'vendor/small:free', 'name': 'Small Free', 'context_length': 32768, 'pricing': {'prompt': '0', 'completion': '0'},
     'supported_parameters': ['tools']},
    {'id': 'vendor/odd', 'pricing': {'prompt': 'n/a'}, 'context_length': None, 'supported_parameters': ['tools']},
]


class ModelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name, 'project')
        self.root.mkdir()
        environment = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(Path(temporary.name, 'config'))})
        environment.start()
        self.addCleanup(environment.stop)

    def picker(self):
        picker = ConfigPicker('openrouter', '', 'default')
        picker.update_catalog('openrouter', {entry['id']: entry.get('name', entry['id']) for entry in CATALOG}, {}, '',
                              {entry['id']: models.openrouter_details(entry) for entry in CATALOG})
        picker.page = 'model'
        return picker

    def test_catalog_entries_say_name_context_and_price_without_inventing_missing_data(self):
        picker = self.picker()
        self.assertEqual(picker.summary('anthropic/claude-sonnet-5.5'), 'Anthropic: Claude Sonnet 5.5 · 1M ctx · $3/$15')
        self.assertEqual(picker.summary('vendor/small:free'), 'Small Free · 33k ctx · grátis')
        self.assertEqual(picker.summary('vendor/odd'), 'vendor/odd')
        self.assertEqual(picker.detail('anthropic/claude-sonnet-5.5'), [
            ('Modelo', 'Anthropic: Claude Sonnet 5.5'), ('Limites', '1M de contexto · até 64k de saída'),
            ('Preço', 'entrada $3 · saída $15 por 1M de tokens (US$)'), ('Aceita', 'imagens · PDF · raciocínio ajustável')])
        self.assertNotIn('Preço', dict(picker.detail('vendor/odd')))
        self.assertIn('fora do Centaur', dict(picker.detail(''))['Modelo'])
        picker.model = 'anthropic/claude-sonnet-5.5'
        self.assertEqual(picker.values[1], 'anthropic/claude-sonnet-5.5 · Anthropic: Claude Sonnet 5.5 · 1M ctx · $3/$15')
        self.assertEqual((models.price_label('0.00000025'), models.price_label(None), models.tokens_label(200000)), ('$0.25', '', '200k'))

    def test_filter_matches_the_id_or_the_public_name(self):
        picker = self.picker()
        picker.query = 'sonnet 5'
        self.assertEqual([value for value, _ in picker.options()][2:], ['anthropic/claude-sonnet-5.5'])
        picker.query = 'SMALL:'
        self.assertEqual([value for value, _ in picker.options()][2:], ['vendor/small:free'])

    def test_model_page_shows_summaries_and_keeps_the_choices_visible_on_short_screens(self):
        wizard = StartupWizard('openrouter', 'anthropic/claude-sonnet-5.5', 'default')
        wizard.picker.update_catalog('openrouter', {entry['id']: '' for entry in CATALOG}, {}, '',
                                     {entry['id']: models.openrouter_details(entry) for entry in CATALOG})
        wizard.picker.open_page('model')
        tall, short = Screen((34, 120)), Screen((20, 80))
        wizard.draw(tall)
        wizard.draw(short)
        self.assertIn('Anthropic: Claude Sonnet 5.5 · 1M ctx · $3/$15', tall.text())
        self.assertIn('entrada $3 · saída $15 por 1M de tokens', tall.text())
        self.assertIn('● Modelo', tall.text())
        for value in ('Padrão do provedor', 'Modelo personalizado', 'vendor/small:free', 'openrouter/auto'):
            self.assertIn(value, short.text())

    def test_claude_aliases_show_the_exact_model_once_the_cli_reported_it(self):
        picker = ConfigPicker('claude', 'sonnet', 'default')
        self.assertEqual([value for value, _ in picker.options()], ['', None, 'fable', 'opus', 'sonnet', 'haiku'])
        self.assertIn('após a primeira resposta', dict(picker.detail('sonnet'))['Servido'])
        with patch('centaur_cli.native_client.shutil.which', return_value='/fake/claude'):
            client = NativeClient('claude', 'sonnet')
        self.assertEqual(client.context_windows, {})
        client.learn('sonnet', 'claude-sonnet-5-5', 1000000, 128000)
        client.learn('', 'claude-fable-5-2', 1000000, None)
        client.learn('sonnet', 'x' * 200)
        self.assertEqual(client.context_windows['claude-sonnet-5-5'], 1000000)
        picker = ConfigPicker('claude', 'sonnet', 'default')
        self.assertEqual(picker.summary('sonnet'), 'claude-sonnet-5-5 · 1M ctx')
        self.assertEqual(picker.summary(''), 'claude-fable-5-2')
        self.assertTrue(dict(picker.detail('sonnet'))['Servido'].startswith('claude-sonnet-5-5 · visto em '))
        self.assertEqual(dict(picker.detail('sonnet'))['Limites'], '1M de contexto · até 128k de saída')
        self.assertIn('claude-fable-5-2', dict(picker.detail(''))['Servido'])
        with patch('centaur_cli.native_client.shutil.which', return_value='/fake/claude'):
            self.assertEqual(NativeClient('claude', 'sonnet').context_windows['sonnet'], 1000000)
        self.assertEqual(stat_mode := os.stat(models.learned_path()).st_mode & 0o077, 0, stat_mode)

    CLI_MODELS = [
        {'value': 'default', 'resolvedModel': 'claude-fable-5-2', 'displayName': 'Default (recommended)', 'description': 'Fable 5.2'},
        {'value': 'opus', 'resolvedModel': 'claude-opus-5-5', 'displayName': 'Opus 5.5', 'description': 'For complex work',
         'supportsEffort': True, 'supportedEffortLevels': ['low', 'high'], 'supportsFastMode': True},
        {'value': 'claude-haiku-4-5-20251001', 'resolvedModel': 'claude-haiku-4-5-20251001', 'displayName': 'Haiku 4.5', 'description': 'Fastest'},
        {'value': 7}, 'lixo']

    def fake_cli(self, body):
        cli = self.root / 'claude'
        cli.write_text('#!' + __import__('sys').executable + '\nimport json, sys\n' + body)
        cli.chmod(0o700)
        return str(cli)

    def test_claude_list_comes_from_the_cli_with_exact_versions_and_is_remembered(self):
        cli = self.fake_cli(
            'request = json.loads(sys.stdin.readline())\n'
            'assert request["request"]["subtype"] == "initialize" and "--tools" in sys.argv\n'
            'print(json.dumps({"type": "system"}), flush=True)\n'
            f'print(json.dumps({{"type": "control_response", "response": {{"response": {{"models": {self.CLI_MODELS!r}}}}}}}), flush=True)\n'
            'sys.stdin.read()\n')
        entries = models.refresh_claude(cli)
        self.assertEqual([entry['value'] for entry in entries], ['default', 'opus', 'claude-haiku-4-5-20251001'])
        picker = ConfigPicker('claude', 'opus', 'high')  # Abertura seguinte: a lista guardada já aparece.
        self.assertEqual([value for value, _ in picker.options()], ['', None, 'opus', 'claude-haiku-4-5-20251001'])
        self.assertEqual(picker.summary('opus'), 'Opus 5.5 · claude-opus-5-5')
        self.assertEqual(picker.summary(''), 'Fable 5.2 · claude-fable-5-2')
        self.assertEqual(picker.summary('claude-haiku-4-5-20251001'), 'Haiku 4.5')
        self.assertEqual(picker.values[1], 'opus · Opus 5.5 · claude-opus-5-5')
        detail = dict(picker.detail('opus'))
        self.assertEqual((detail['Modelo'], detail['Servido']), ('Opus 5.5 · For complex work', 'claude-opus-5-5'))
        self.assertEqual(detail['Aceita'], 'imagens · effort low/high · modo rápido')
        self.assertIn('claude-fable-5-2', dict(picker.detail(''))['Servido'])
        picker.page = 'effort'
        self.assertEqual([value for value, _ in picker.options()], ['default', 'low', 'high'])
        picker.model = 'claude-haiku-4-5-20251001'
        self.assertEqual([value for value, _ in picker.options()], ['default'])
        models.remember('claude', 'opus', 'claude-opus-5-5', 1000000, 128000)
        self.assertEqual(ConfigPicker('claude', 'opus', 'high').summary('opus'), 'Opus 5.5 · claude-opus-5-5 · 1M ctx')

    def test_unresponsive_or_missing_cli_keeps_the_known_aliases(self):
        for cli in (self.fake_cli('sys.exit(3)\n'), self.fake_cli('print("{nope", flush=True)\n'), str(self.root / 'absent')):
            with self.assertRaises(RuntimeError):
                models.refresh_claude(cli)
        self.assertEqual(models.cached_claude(), [])
        wizard = StartupWizard('claude', 'sonnet', 'default')
        wizard.catalog_request, wizard.catalog_backend = 1, 'claude'
        wizard.picker.open_page('model')
        wizard.events.put((1, ({}, {}, 'Lista do Claude Code indisponível; mostrando os aliases conhecidos.')))
        wizard.drain_events()
        self.assertEqual([value for value, _ in wizard.picker.options()], ['', None, 'fable', 'opus', 'sonnet', 'haiku'])
        self.assertIn('indisponível', wizard.picker.catalog_status)
        catalog, efforts, details = models.claude_catalog(self.CLI_MODELS[:3])
        wizard.events.put((1, (catalog, efforts, '', details)))
        wizard.drain_events()
        self.assertEqual(wizard.picker.summary('opus'), 'Opus 5.5 · claude-opus-5-5')
        self.assertIn('claude-haiku-4-5-20251001', wizard.picker.catalog)
        wizard.picker.backend = 'openrouter'
        wizard.events.put((1, ({'stale': 'x'}, {}, '')))
        wizard.drain_events()
        self.assertNotIn('stale', wizard.picker.catalog)

    def test_learned_file_that_is_corrupt_or_linked_is_ignored(self):
        path = models.learned_path()
        path.parent.mkdir(parents=True)
        path.write_text('{nope')
        self.assertEqual(models.load_learned('claude'), {})
        models.remember('claude', 'opus', 'claude-opus-5-5', 200000)
        self.assertEqual(models.load_learned('claude')['opus']['context'], 200000)
        target = path.with_name('other.json')
        target.write_text(json.dumps({'claude': {'opus': {'id': 'forged'}}}))
        path.unlink()
        path.symlink_to(target)
        self.assertEqual(models.load_learned('claude'), {})

    def test_chat_header_names_the_model_that_actually_answered(self):
        terminal = Terminal(self.root, 'sonnet', ChatStore(self.root), None)
        terminal.backend = 'claude'
        screen = Screen((30, 150))
        terminal.view.draw(screen, terminal)
        self.assertIn('claude · sonnet', screen.text())
        self.assertNotIn('→', screen.text())
        terminal.chat['models_used'] = ['claude-sonnet-5-5']
        terminal.view.draw(screen, terminal)
        self.assertIn('claude · sonnet → claude-sonnet-5-5', screen.text())


def dots(frame):
    return {(x * 2 + dx, y * 4 + dy) for y, row in enumerate(frame) for x, cell in enumerate(row) if cell.glyph != ' '
            for dy, pair in enumerate(DOT_BITS) for dx, bit in enumerate(pair) if (ord(cell.glyph) - 0x2800) & bit}


class OpeningTests(unittest.TestCase):
    def test_mark_is_drawn_from_the_tails_to_the_tip_and_ends_as_the_static_pose(self):
        renderer = Renderer()
        final = dots(renderer.frame(36, 16))
        self.assertEqual(dots(renderer.frame(36, 16, 0, reveal=0)), set())
        widths = []
        for reveal in (.25, .5, .75):
            partial = dots(renderer.frame(36, 16, 0, reveal=reveal))
            self.assertTrue(partial and partial < final)
            widths.append(max(x for x, _ in partial))
        self.assertEqual(widths, sorted(widths))
        self.assertLess(widths[0], max(x for x, _ in final) * .5)
        self.assertEqual(dots(renderer.frame(36, 16, 0, reveal=1)), final)

    def test_highlight_changes_light_but_never_the_shape(self):
        renderer = Renderer()
        plain, lit = renderer.frame(36, 16), renderer.frame(36, 16, glint=0.0)
        self.assertEqual(dots(plain), dots(lit))
        self.assertGreater(sum(cell.shade for row in lit for cell in row), sum(cell.shade for row in plain for cell in row))
        self.assertEqual(renderer.frame(36, 16, glint=9.0), plain)

    def test_sequence_reveals_then_glints_then_rests_and_companions_follow_the_clock(self):
        animation = WelcomeAnimation()
        calls = []
        original = animation.renderer.frame
        animation.renderer.frame = lambda *args, **options: calls.append(options) or original(*args, **options)
        animation.frame(26, 10, 0)
        self.assertEqual((calls[-1]['reveal'], calls[-1]['glint']), (0.0, None))
        self.assertEqual((animation.staged(.7, 1.2), animation.staged(2.1)), (0.0, 0.0))
        animation.frame(26, 10, REVEAL_SECONDS / 2)
        self.assertTrue(0 < calls[-1]['reveal'] < 1)
        animation.frame(26, 10, REVEAL_SECONDS + .2)
        self.assertEqual((calls[-1]['reveal'], calls[-1]['glint']), (1.0, None))
        self.assertTrue(0 < animation.staged(.7, 1.2) < 1)
        animation.frame(26, 10, SPIN_SECONDS * (GLINT_START + .1))
        self.assertTrue(-1.5 < calls[-1]['glint'] < 1.5)
        self.assertEqual(animation.staged(2.1), 1.0)
        final = animation.frame(26, 10, SPIN_SECONDS + 1)
        self.assertEqual((calls[-1]['reveal'], calls[-1]['glint']), (1.0, None))
        self.assertEqual(final, Renderer().frame(26, 10))
        self.assertEqual((animation.active, animation.staged(.7, 1.2)), (False, 1.0))

    def test_reduced_motion_shows_everything_at_once(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'CENTAUR_REDUCED_MOTION': '1'}):
            terminal = Terminal(Path(directory), 'test', ChatStore(directory), None)
            screen = Screen((34, 110))
            terminal.view.draw(screen, terminal)
            for text in ('C E N T A U R', 'HUMAN INTENT. AMPLIFIED.', 'Centaur CLI', '$spec', '$config'):
                self.assertIn(text, screen.text())
            self.assertFalse(terminal.view.animation.active)

    def test_startup_screen_carries_the_mark_and_the_chat_does_not_replay_it(self):
        self.addCleanup(setattr, WelcomeAnimation, 'opening_played', False)
        wizard = StartupWizard('claude', 'sonnet', 'default')
        large, small = Screen((32, 120)), Screen((20, 80))
        # A abertura ocupa a tela sozinha, sem as escolhas, e cabe também em terminais menores.
        self.assertTrue(wizard.draw_opening(large))
        self.assertTrue(wizard.view.animation.active)
        self.assertNotIn('Conexão', large.text())
        self.assertNotIn('Backend', large.text())
        self.assertTrue(wizard.draw_opening(small))
        self.assertFalse(wizard.draw_opening(Screen((12, 40))))
        with patch.dict(os.environ, {'CENTAUR_GRAPHICS': '0'}):
            self.assertFalse(wizard.draw_opening(large))
        wizard.end_opening()
        self.assertTrue(wizard.played and not wizard.opening)
        # Depois dela, a marca fica parada ao lado das escolhas.
        wizard.draw(large)
        self.assertFalse(wizard.view.animation.active)
        self.assertTrue(any(0x2800 < ord(char) <= 0x28ff for char in large.text()))
        self.assertIn('● Conexão', large.text())
        self.assertIn('○ Modelo', large.text())
        wizard.draw(small)
        self.assertFalse(any(0x2800 < ord(char) <= 0x28ff for char in small.text()))
        for key in '\r\r\r\r\r':
            wizard.picker.handle(key)
        self.assertEqual(wizard.picker.page, 'fields')
        wizard.draw(large)
        self.assertIn('● Revisão', large.text())
        self.assertEqual(WelcomeAnimation().elapsed, 0.0)
        WelcomeAnimation.opening_played = True
        with tempfile.TemporaryDirectory() as directory:
            terminal = Terminal(Path(directory), 'test', ChatStore(directory), None)
            terminal.view.draw(Screen((34, 110)), terminal)
            self.assertFalse(terminal.view.animation.active)
            terminal.view.animation.replay()
            terminal.view.draw(Screen((34, 110)), terminal)
            self.assertTrue(terminal.view.animation.active)


if __name__ == '__main__':
    unittest.main()
