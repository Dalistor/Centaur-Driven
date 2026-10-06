"""Teste opt-in em desktop descartável: nunca executar no display do usuário.

CENTAUR_TEST_DESKTOP=1 xvfb-run -a -s '-screen 0 800x600x24' python -m unittest discover -s tests -p test_computer_desktop.py
"""

import base64
import io
import os
import threading
import time
import unittest
from unittest.mock import patch

from centaur_cli.computer import ComputerSession


@unittest.skipUnless(os.environ.get('CENTAUR_TEST_DESKTOP') == '1', 'Requer desktop Xvfb descartável e extra computer')
class DesktopTests(unittest.TestCase):
    def test_zoom_buttons_drag_scroll_and_delayed_visual_update(self):
        from Xlib import X, display
        from PIL import Image
        connection = display.Display()
        self.addCleanup(connection.close)
        root = connection.screen().root
        window = root.create_window(40, 40, 250, 150, 0, connection.screen().root_depth,
                                    X.InputOutput, X.CopyFromParent, background_pixel=0x123456,
                                    event_mask=X.ButtonPressMask | X.ButtonReleaseMask | X.PointerMotionMask)
        window.map()
        self.addCleanup(window.destroy)
        root.warp_pointer(400, 300)
        connection.sync()
        permissions = []
        session = ComputerSession(lambda prompt: permissions.append(prompt) or True)
        self.addCleanup(session.close)
        session.start('Validação de zoom e input em desktop descartável')
        session.observation_messages()
        session.execute('computer_observe', {'region': [40, 40, 250, 150], 'frame_id': session.reference.identifier})

        def action(name, **args):
            session.observation_messages()
            result = session.execute('computer_action', dict(action=name, x=20, y=20,
                frame_id=session.reference.identifier, **args))
            connection.sync()
            events = []
            while connection.pending_events(): events.append(connection.next_event())
            return result, events

        _, events = action('right_click')
        self.assertTrue(any(e.type == X.ButtonPress and e.detail == 3 and (e.root_x, e.root_y) == (60, 60) for e in events))
        self.assertEqual(session.frames[-1].image.size, (250, 150))
        _, events = action('middle_click')
        self.assertTrue(any(e.type == X.ButtonPress and e.detail == 2 for e in events))
        _, events = action('triple_click')
        self.assertEqual(sum(e.type == X.ButtonPress and e.detail == 1 for e in events), 3)
        _, events = action('drag', end_x=100, end_y=100)
        self.assertTrue(any(e.type == X.ButtonRelease and e.detail == 1 and (e.root_x, e.root_y) == (140, 140) for e in events))
        self.assertFalse(root.query_pointer().mask & X.Button1Mask)
        _, events = action('scroll', amount=2, direction='horizontal')
        self.assertEqual(sum(e.type == X.ButtonPress and e.detail == 7 for e in events), 2)

        # A real delayed repaint must be visible after the bounded settle step.
        session.observation_messages()
        reference = session.reference.identifier
        def repaint():
            app = display.Display()
            try:
                target = app.create_resource_object('window', window.id)
                target.change_attributes(background_pixel=0xabcdef)
                target.clear_area()
                app.sync()
            finally:
                app.close()
        timer = threading.Timer(0.2, repaint)
        self.addCleanup(timer.cancel)
        original = session.backend.perform
        def perform(*args):
            original(*args)
            timer.start()
        with patch.object(session.backend, 'perform', side_effect=perform):
            result = session.execute('computer_action', {'action': 'click', 'frame_id': reference, 'x': 20, 'y': 20})
        timer.join(2)
        self.assertIn('estável', result)
        self.assertEqual(session.frames[-1].image.getpixel((20, 20)), (0xab, 0xcd, 0xef))
        messages = session.observation_messages()
        url = messages[0]['content'][-1]['image_url']['url']
        decoded = Image.open(io.BytesIO(base64.b64decode(url.split(',', 1)[1])))
        self.assertEqual(decoded.getpixel((20, 20)), (0xab, 0xcd, 0xef))
        self.assertEqual(len(permissions), 7)
        # Mutating only the destination must block a drag before mouse-down.
        connection.sync()
        while connection.pending_events(): connection.next_event()
        reference = session.reference.identifier
        gc = window.create_gc(foreground=0xff0000)
        window.fill_rectangle(gc, 90, 90, 20, 20)
        connection.sync()
        with self.assertRaisesRegex(ValueError, 'alvo mudou'):
            session.execute('computer_action', {'action': 'drag', 'frame_id': reference,
                'x': 20, 'y': 20, 'end_x': 100, 'end_y': 100})
        self.assertFalse(root.query_pointer().mask & X.Button1Mask)
        self.assertEqual(len(permissions), 8)

    def test_real_capture_click_keyboard_target_change_and_failsafe(self):
        from Xlib import X, XK, display
        from PIL import Image
        connection = display.Display()
        self.addCleanup(connection.close)
        root = connection.screen().root
        window = root.create_window(40, 40, 250, 150, 0, connection.screen().root_depth,
                                    X.InputOutput, X.CopyFromParent,
                                    background_pixel=0x123456,
                                    event_mask=X.ButtonPressMask | X.KeyPressMask)
        window.map()
        window.set_input_focus(X.RevertToParent, X.CurrentTime)
        root.warp_pointer(400, 300)
        connection.sync()
        permissions = []
        session = ComputerSession(lambda prompt: permissions.append(prompt) or True)
        self.addCleanup(session.close)
        session.start('Validar somente desktop Xvfb descartável')
        messages = session.observation_messages()
        image_url = messages[0]['content'][-1]['image_url']['url']
        image = Image.open(io.BytesIO(base64.b64decode(image_url.split(',', 1)[1])))
        self.assertEqual(image.getpixel((60, 60)), (0x12, 0x34, 0x56))
        reference = session.reference[0]
        session.execute('computer_action', {'action': 'click', 'frame_id': reference, 'x': 60, 'y': 60})
        connection.sync()
        events = []
        while connection.pending_events(): events.append(connection.next_event())
        self.assertTrue(any(event.type == X.ButtonPress and event.detail == 1 for event in events))
        session.observation_messages()
        session.execute('computer_action', {'action': 'type_text', 'frame_id': session.reference[0], 'x': 60, 'y': 60, 'text': 'abc'})
        connection.sync()
        typed = []
        while connection.pending_events():
            event = connection.next_event()
            if event.type == X.KeyPress:
                typed.append(XK.keysym_to_string(connection.keycode_to_keysym(event.detail, 0)))
        self.assertEqual(typed, ['a', 'b', 'c'])
        self.assertEqual(len(permissions), 3)
        session.observation_messages()
        reference = session.reference[0]
        window.change_attributes(background_pixel=0xffee00)
        window.clear_area()
        connection.sync()
        with self.assertRaisesRegex(ValueError, 'alvo mudou'):
            session.execute('computer_action', {'action': 'click', 'frame_id': reference, 'x': 60, 'y': 60})
        root.warp_pointer(0, 0)
        connection.sync()
        session.thread.join(2)
        self.assertFalse(session.active)
        self.assertEqual(list(session.frames), [])
