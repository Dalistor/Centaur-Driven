"""Computer use contracts without importing optional desktop dependencies."""

import threading
import time
import unittest
from unittest.mock import patch

from centaur_cli.computer import ComputerSession, Desktop


class Image:
    def __init__(self, size=(3200, 2000), content=b'static'):
        self.size, self.content = size, content
    @property
    def width(self): return self.size[0]
    @property
    def height(self): return self.size[1]
    def convert(self, mode): return self
    def thumbnail(self, bound):
        ratio = min(1, bound[0] / self.width, bound[1] / self.height)
        self.size = tuple(round(value * ratio) for value in self.size)
    def crop(self, box):
        return Image((box[2] - box[0], box[3] - box[1]), self.content)
    def save(self, output, format):
        output.write(b'\x89PNG\r\n\x1a\n' + self.content + str(self.size).encode())


class Backend:
    input_size = (3200, 2000)
    def __init__(self): self.actions = []
    def capture(self): return Image(self.input_size)
    def perform(self, action, x, y, args): self.actions.append((action, x, y, args))


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.backend, self.prompts = Backend(), []
        self.session = ComputerSession(lambda prompt: self.prompts.append(prompt) or True,
                                       backend_factory=lambda: self.backend, interval=60, settle_timeout=0)
        self.addCleanup(self.session.close)
        # Real PIL pixel comparisons are covered by the opt-in desktop test.
        targets = patch.object(self.session, 'validate_targets')
        targets.start()
        self.addCleanup(targets.stop)
        self.session.start('Teste de contrato')
        self.session.observation_messages()

    def action(self, action='click', **args):
        return self.session.execute('computer_action', dict(action=action,
            frame_id=self.session.reference.identifier, x=20, y=30, **args))

    def test_static_frames_deduplicated_but_latest_id_is_used(self):
        for _ in range(5): self.session.capture()
        messages = self.session.observation_messages()
        images = [item for item in messages[0]['content'] if item['type'] == 'image_url']
        self.assertEqual(len(images), 1)
        self.assertIn(f'frame_id={self.session.reference.identifier}', messages[0]['content'][-2]['text'])
        self.assertIn('Autorização deste chat', messages[0]['content'][0]['text'])

    def test_changed_frames_preserved_in_order_without_reencoding(self):
        with patch.object(self.backend, 'capture', side_effect=[Image(content=b'A'), Image(content=b'B'), Image(content=b'C')]):
            self.session.capture()
            self.session.capture()
            messages = self.session.observation_messages()
        metadata = [item['text'] for item in messages[0]['content'][1:] if item['type'] == 'text']
        self.assertEqual(len(metadata), 3)
        self.assertEqual([int(text.split(',')[0].split('=')[1]) for text in metadata],
                         sorted(frame.identifier for frame in self.session.frames))

    def test_zoom_maps_click_and_drag_back_to_desktop_then_restores(self):
        self.session.execute('computer_observe', {'region': [100, 50, 400, 300],
            'frame_id': self.session.reference.identifier})
        self.session.observation_messages()
        self.assertEqual(self.session.reference.box, (200, 100, 800, 600))
        self.assertEqual(self.session.reference.image.size, (800, 600))
        self.action('drag', end_x=500, end_y=400)
        action, x, y, args = self.backend.actions[-1]
        self.assertEqual((action, x, y, args['end_x'], args['end_y']), ('drag', 220, 130, 700, 500))
        self.session.execute('computer_observe', {})
        self.session.observation_messages()
        self.assertEqual(self.session.reference.box, (0, 0, 3200, 2000))
        self.assertEqual(self.session.reference.image.size, (1600, 1000))

    def test_invalid_regions_and_waits_do_not_change_view_or_request_permission(self):
        for region in ([True, 0, 2, 2], [-1, 0, 2, 2], [0, 0, 0, 2], [1599, 0, 2, 2], [1, 2], 'wrong'):
            with self.assertRaises(ValueError):
                self.session.execute('computer_observe', {'region': region, 'frame_id': self.session.reference.identifier})
        for value in (True, -1, 11, 0.2):
            with self.assertRaises(ValueError):
                self.session.execute('computer_observe', {'wait_seconds': value})
        with self.assertRaises(ValueError):
            self.session.execute('computer_observe', {'region': [0, 0, 10, 10], 'frame_id': -1})
        self.assertIsNone(self.session.view_box)
        self.assertEqual(len(self.prompts), 1)
        self.assertEqual(self.backend.actions, [])

    def test_new_actions_share_the_initial_chat_authorization(self):
        for action, args in [('right_click', {}), ('middle_click', {}), ('triple_click', {}),
                             ('scroll', {'amount': -3, 'direction': 'horizontal'}),
                             ('keypress', {'keys': ['Control', 'F5']})]:
            self.session.observation_messages()
            self.action(action, **args)
        self.assertEqual(len(self.prompts), 1)
        self.assertEqual(self.backend.actions[-1][3]['keys'], ['ctrl', 'f5'])
        self.assertEqual(self.backend.actions[-2][3]['direction'], 'horizontal')

    def test_invalid_drag_keyboard_and_direction_never_prompt_or_move(self):
        for action, args in [('drag', {'end_x': True, 'end_y': 1}), ('drag', {'end_x': 1600, 'end_y': 1}),
                             ('keypress', {'keys': ['ctrl', 'control']}), ('keypress', {'keys': ['bad']}),
                             ('scroll', {'amount': 1, 'direction': 'diagonal'})]:
            with self.assertRaises(ValueError): self.action(action, **args)
        self.assertEqual(len(self.prompts), 1)
        self.assertEqual(self.backend.actions, [])

    def test_resolution_change_even_with_same_thumbnail_rejects_input(self):
        self.backend.input_size = (6400, 4000)
        with self.assertRaisesRegex(ValueError, 'resolução mudou'): self.action()
        self.assertEqual(self.backend.actions, [])
        self.assertIsNone(self.session.reference)

    def test_restart_does_not_let_old_worker_clear_new_session(self):
        old_worker = self.session.thread
        old_token = self.session.stop_event
        with self.session.lock:
            self.session.start('Nova autorização')
            self.assertIsNot(self.session.stop_event, old_token)
        old_worker.join(1)
        self.assertFalse(old_worker.is_alive())
        self.assertTrue(self.session.active)
        self.assertIs(self.session.backend, self.backend)

    def test_reference_replaced_before_input_cannot_act(self):
        def progress(notice):
            self.session.observe({})
            self.session.observation_messages()
        self.session.emit = progress
        with self.assertRaisesRegex(ValueError, 'Referência mudou'): self.action()
        self.assertEqual(self.backend.actions, [])

    def test_capture_failure_preserves_diagnostic_after_close(self):
        self.session.failure = 'Captura interrompida'
        self.session.close()
        with self.assertRaisesRegex(RuntimeError, 'Captura interrompida'): self.session.check()
        self.assertIn('autorização do chat foi preservada', self.session.observation_messages()[0]['content'])

    def test_old_operation_cannot_close_a_replacement_session(self):
        token = self.session.stop_event
        self.session.start('Outra sessão')
        self.session.close(token)
        self.assertTrue(self.session.active)
        self.assertIs(self.session.backend, self.backend)

    def test_wait_can_be_cancelled_without_extending_authorization(self):
        deadline = self.session.deadline
        timer = threading.Timer(0.03, self.session.close)
        timer.start()
        self.addCleanup(timer.cancel)
        started = time.monotonic()
        with self.assertRaises(ValueError): self.session.execute('computer_observe', {'wait_seconds': 10})
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertEqual(self.session.deadline, deadline)
        self.assertEqual(len(self.prompts), 1)

    def test_settling_reports_stability_separately_from_task_success(self):
        self.session.settle_timeout = 0.2
        with patch.object(self.session, 'wait'):
            result = self.action()
        self.assertIn('estável', result)
        self.assertIn('não confirma o sucesso', result)

    def test_changing_screen_hits_bounded_settle_timeout_without_replaying(self):
        self.session.settle_timeout = 0.03
        counter = iter(range(100000))
        with patch.object(self.backend, 'capture', side_effect=lambda: Image(content=str(next(counter)).encode())), patch.object(self.session, 'wait'):
            result = self.action()
        self.assertIn('Prazo de estabilização', result)
        self.assertEqual(len(self.backend.actions), 1)
        self.assertIsNone(self.session.reference)


class Gui:
    FAILSAFE = True
    def __init__(self): self.calls = []
    def moveTo(self, *args, **kwargs): self.calls.append(('move', args))
    def mouseDown(self): self.calls.append(('down',))
    def mouseUp(self): self.calls.append(('up', self.FAILSAFE))
    def keyDown(self, key): self.calls.append(('keyDown', key))
    def keyUp(self, key): self.calls.append(('keyUp', key, self.FAILSAFE))
    def click(self, **kwargs): self.calls.append(('click', kwargs))
    def write(self, text, **kwargs): self.calls.append(('write', text))


class InputCleanupTests(unittest.TestCase):
    def setUp(self):
        self.desktop = Desktop.__new__(Desktop)
        self.desktop.gui = Gui()
        self.desktop.check_cancelled = lambda: None

    def test_drag_failure_releases_mouse_and_restores_failsafe(self):
        with patch.object(self.desktop.gui, 'moveTo', side_effect=[None, RuntimeError('fail-safe')]):
            with self.assertRaises(RuntimeError):
                self.desktop.perform('drag', 2, 2, {'end_x': 4, 'end_y': 4})
        self.assertEqual(self.desktop.gui.calls[-1], ('up', False))
        self.assertTrue(self.desktop.gui.FAILSAFE)

    def test_hotkey_failure_releases_all_keys_even_when_one_release_fails(self):
        calls = []
        def release(key):
            calls.append(key)
            if key == 's': raise RuntimeError('OS release error')
        with patch.object(self.desktop.gui, 'keyUp', side_effect=release):
            with self.assertRaises(RuntimeError): self.desktop.hotkey(['ctrl', 'shift', 's'])
        self.assertEqual(calls, ['s', 'shift', 'ctrl'])
        self.assertTrue(self.desktop.gui.FAILSAFE)

    def test_long_typing_checks_cancellation_between_chunks(self):
        def check():
            if any(call[0] == 'write' for call in self.desktop.gui.calls): raise ValueError('cancelled')
        self.desktop.check_cancelled = check
        with self.assertRaises(ValueError): self.desktop.perform('type_text', 2, 2, {'text': 'x' * 4000})
        typed = [call[1] for call in self.desktop.gui.calls if call[0] == 'write']
        self.assertEqual(typed, ['x' * 50])
