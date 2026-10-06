"""Teste opt-in em desktop descartável: nunca executar no display do usuário.

CENTAUR_TEST_DESKTOP=1 xvfb-run -a python -m unittest discover -s tests -p test_computer_desktop.py
"""

import base64
import io
import os
import time
import unittest

from centaur_cli.computer import ComputerSession


@unittest.skipUnless(os.environ.get('CENTAUR_TEST_DESKTOP') == '1', 'Requer desktop Xvfb descartável e extra computer')
class DesktopTests(unittest.TestCase):
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
