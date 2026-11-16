"""Display virtual: contrato com display simulado e fluxo real opt-out quando Xvfb/xdotool existem."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from centaur_cli import computer
from centaur_cli.computer import ComputerSession, DISPLAYS
from centaur_cli.computer_access import ComputerControl, DesktopLease

try:
    from PIL import Image, features
except ImportError:
    Image = None


class FakeDisplay:
    name, size, xdotool, authority = ':42', (1280, 800), 'xdotool', '/private/Xauthority'
    environment = {'DISPLAY': ':42', 'XAUTHORITY': '/private/Xauthority'}
    prefix = 'env DISPLAY=:42 XAUTHORITY=/private/Xauthority'
    def __init__(self): self.alive, self.closed = True, False
    def grab(self): return self.size, bytes(self.size[0] * self.size[1] * 3)
    def close(self): self.alive, self.closed = False, True


@unittest.skipUnless(Image, 'Requer Pillow')
class VirtualContractTests(unittest.TestCase):
    def setUp(self):
        self.prompts, self.commands, self.displays = [], [], []
        def factory():
            self.displays.append(FakeDisplay())
            return self.displays[-1]
        def desktop():
            raise AssertionError('O desktop real não pode ser aberto por uma autorização virtual.')
        self.answer = True
        self.session = ComputerSession(lambda prompt: self.prompts.append(prompt) or self.answer, backend_factory=desktop,
                                       display_factory=factory, interval=60, settle_timeout=0)
        self.addCleanup(lambda: DISPLAYS.destroy(self.session.display_key))
        self.addCleanup(self.session.close)
        def run(arguments, **options):
            self.commands.append((arguments[1:], options.get('input'), options['env']['DISPLAY']))
            return subprocess.CompletedProcess(arguments, 0, '', '')
        patcher = patch.object(computer.subprocess, 'run', run)
        patcher.start()
        self.addCleanup(patcher.stop)

    def start(self):
        return self.session.execute('computer_start', {'purpose': 'Testar formulário', 'display': 'virtual'})

    def act(self, name='computer_action', **arguments):
        self.session.observation_messages()
        self.commands.clear()
        return self.session.execute(name, dict(frame_id=self.session.reference.identifier, x=200, y=35, **arguments))

    def test_virtual_consent_is_explicit_reused_and_does_not_open_the_real_desktop(self):
        result = self.start()
        self.assertIn('env DISPLAY=:42 XAUTHORITY=/private/Xauthority', result)
        self.assertTrue(self.prompts[0].startswith('DISPLAY VIRTUAL'))
        self.assertIn('NÃO são vistos', self.prompts[0])
        self.assertIn('display virtual', self.session.observation_messages()[0]['content'][0]['text'])
        self.start()
        self.assertEqual(len(self.prompts), 1)
        self.assertEqual(len(self.displays), 1)  # O mesmo display é retomado.
        self.answer = False
        self.assertIn('recusada', self.session.execute('computer_start', {'purpose': 'Desktop real'}))
        self.assertTrue(self.prompts[1].startswith('COMPUTER USE'))
        self.assertIn('display deve ser', str(self.failure('computer_start', purpose='x', display='janela')))

    def failure(self, name, **arguments):
        with self.assertRaises(ValueError) as caught:
            self.session.execute(name, arguments)
        return caught.exception

    def test_actions_become_xdotool_input_on_the_virtual_display_only(self):
        self.start()
        self.act(action='right_click')
        self.assertEqual(self.commands, [(['mousemove', '200', '35'], None, ':42'), (['click', '3'], None, ':42')])
        self.act(action='keypress', keys=['control', 'a'])
        self.assertEqual(self.commands[-1][0], ['key', 'ctrl+a'])
        self.act(action='keypress', keys=['F5'])
        self.assertEqual(self.commands[-1][0], ['key', 'F5'])
        self.act(action='scroll', amount=-3)
        self.assertEqual(self.commands[-1][0], ['click', '--repeat', '3', '--delay', '20', '5'])
        self.act(action='drag', end_x=280, end_y=115)
        self.assertEqual(self.commands[1][0], ['mousedown', '1'])
        self.assertEqual(self.commands[-2][0], ['mousemove', '280', '115'])
        self.assertEqual(self.commands[-1][0], ['mouseup', '1'])
        self.act('computer_batch', steps=[{'action': 'type_text', 'text': 'Olá'}, {'action': 'keypress', 'keys': ['enter']}])
        self.assertEqual([command[:2] for command in self.commands[1:]],
                         [(['click', '1'], None), (['type', '--delay', '60', '--file', '-'], 'Olá'), (['key', 'Return'], None)])

    def test_chat_scope_persists_without_taking_the_desktop_lock_and_revoke_closes_the_display(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        chat, lock = 'a' * 32, Path(folder.name) / 'desktop.lock'
        other = DesktopLease(lock)
        other.acquire()  # Outro processo controla o desktop real.
        self.addCleanup(other.release)
        control = ComputerControl(folder.name, chat, lease=DesktopLease(lock))
        session = ComputerSession(lambda prompt: self.prompts.append(prompt) or self.answer, control=control, chat_id=chat,
                                  display_factory=FakeDisplay, interval=60, settle_timeout=0)
        self.addCleanup(lambda: DISPLAYS.destroy(chat))
        self.addCleanup(session.close)
        self.assertIn('display virtual :42', session.execute('computer_start', {'purpose': 'Teste', 'display': 'virtual'}))
        self.assertTrue(session.active)
        self.assertTrue(control.permissions.granted(chat, 'virtual'))
        self.assertFalse(control.permissions.granted(chat))
        display = DISPLAYS.find(chat)
        self.answer = False  # O desktop real pede autorização própria.
        self.assertIn('recusada', session.execute('computer_start', {'purpose': 'Desktop'}))
        self.assertTrue(self.prompts[-1].startswith('COMPUTER USE'))
        self.assertFalse(control.permissions.granted(chat))
        self.assertTrue(display.alive)
        control.revoke(chat)
        self.assertTrue(display.closed)
        self.assertFalse(control.permissions.granted(chat, 'virtual'))

    def test_display_survives_pauses_and_ends_with_stop(self):
        self.start()
        display = self.displays[0]
        self.session.suspend()
        self.session.close()
        self.assertTrue(display.alive)
        self.assertIs(DISPLAYS.find(self.session.display_key), display)
        self.start()
        self.assertIn('display virtual e suas aplicações encerrados', self.session.execute('computer_stop', {}))
        self.assertTrue(display.closed)
        self.assertIsNone(DISPLAYS.find(self.session.display_key))
        self.assertEqual(self.session.observation_messages(), [])


APP = '''import sys, tkinter as tk
root = tk.Tk(); root.geometry('400x200+0+0')
entry = tk.Entry(root, font=('Sans', 16)); entry.pack(pady=20)
tk.Button(root, text='Enviar', font=('Sans', 16),
          command=lambda: open(sys.argv[1], 'w', encoding='utf-8').write(entry.get())).pack(pady=40)
root.mainloop()
'''


def real_display_available():
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False
    return bool(Image and features.check('xcb') and sys.platform.startswith('linux')
                and shutil.which('Xvfb') and shutil.which('xdotool'))


@unittest.skipUnless(real_display_available() and os.environ.get('CENTAUR_SKIP_VIRTUAL') != '1',
                     'Requer Linux com Xvfb, xdotool, Tk e Pillow com XCB')
class VirtualDisplayTests(unittest.TestCase):
    def test_real_private_display_receives_typed_text_and_click_then_is_destroyed(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        output = Path(folder.name) / 'resultado.txt'
        session = ComputerSession(lambda prompt: True, interval=60, settle_timeout=0.4)
        self.addCleanup(lambda: DISPLAYS.destroy(session.display_key))
        self.addCleanup(session.close)
        session.execute('computer_start', {'purpose': 'Fluxo real em display descartável', 'display': 'virtual'})
        display = DISPLAYS.find(session.display_key)
        self.assertEqual(os.stat(display.authority).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(display.directory).st_mode & 0o777, 0o700)
        outsider = subprocess.run([display.xdotool, 'getmouselocation'], capture_output=True,
                                  env={**os.environ, 'DISPLAY': display.name, 'XAUTHORITY': os.devnull})
        self.assertNotEqual(outsider.returncode, 0)  # Sem o cookie privado não há acesso.
        app = subprocess.Popen([sys.executable, '-c', APP, str(output)], env={**os.environ, **display.environment},
                               stderr=subprocess.DEVNULL)
        self.addCleanup(app.kill)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:  # Espera a janela cinza substituir o fundo preto.
            session.observation_messages()
            if session.frames[-1].image.getpixel((390, 190)) != (0, 0, 0):
                break
            time.sleep(0.2)
        else:
            self.fail('A janela não apareceu no display virtual.')
        before = os.environ.get('XAUTHORITY')
        session.execute('computer_batch', {'frame_id': session.reference.identifier, 'x': 200, 'y': 35,
                                           'steps': [{'action': 'type_text', 'text': 'Olá, ação'}]})
        session.observation_messages()
        session.execute('computer_action', {'action': 'click', 'frame_id': session.reference.identifier, 'x': 200, 'y': 130})
        deadline = time.monotonic() + 5
        while not output.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(output.read_text(encoding='utf-8'), 'Olá, ação')
        self.assertEqual(os.environ.get('XAUTHORITY'), before)
        session.execute('computer_stop', {})
        self.assertFalse(display.alive)
        self.assertFalse(os.path.exists(display.directory))
        self.assertIsNotNone(app.wait(timeout=5))
