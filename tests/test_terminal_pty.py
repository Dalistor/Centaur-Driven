"""Exercise real curses input under a disposable POSIX terminal, without an AI account."""

import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest


CHILD = r'''
import copy, curses, json, sys, os, time
import centaur_cli.terminal as terminal_module
from pathlib import Path
from centaur_cli.history import ChatStore
from centaur_cli.terminal import Terminal
class Client:
    backend='codex'; secrets=(); allows_model_routing=False
    context_windows={'fixture':100000}
    def __init__(self): self.requests=[]
    def model_catalog(self): return {'fixture':'Fixture'}
    def complete(self, model, messages, tools, **options):
        self.requests.append({'messages':copy.deepcopy(messages),'tools':bool(tools)})
        if os.environ.get('CENTAUR_TEST_STEERING') == '1' and len(self.requests) == 1:
            deadline=time.monotonic()+6
            while not (root/'release-model').exists() and time.monotonic()<deadline: time.sleep(.01)
        return {'role':'assistant','content': 'Objetivo preservado, alteracoes e validacao pendentes.' if not tools else 'Mensagem recebida.'}
class RecordingTerminal(Terminal):
    def draw(self, screen):
        super().draw(screen)
        data={'draft':self.draft,'cursor':self.cursor,'busy':self.busy,
              'chat':self.chat,'requests':self.client.requests,'width':self.input_width,'notice':self.notice,
              'pending_attachments':len(self.pending_attachments),
              'inbox': len(self.inboxes[self.chat['id']].snapshot()) if self.chat['id'] in self.inboxes else 0,
              'browser':self.browser, 'preview':(self.agent_preview or {}).get('title'),
              'tree':[c['title'] for c in self.chats],
              'input_hitbox':{k:v for k,v in (self.input_hitbox or {}).items() if k!='layout'},
              'action_style':self.view.palette.styles['action'],'comment_style':self.view.palette.styles['comment']}
        pending=root/'snapshot.tmp'
        pending.write_text(json.dumps(data))
        pending.replace(root/'snapshot.json')
root=Path(sys.argv[1]); client=Client()
terminal_module.clipboard_content=lambda **kwargs: ('text', (root/'fixture com espaço.txt').as_uri())
terminal=RecordingTerminal(root,'fixture',ChatStore(root),client)
terminal.chat['messages']=[{'role':'user' if i%2==0 else 'assistant','content':f'log {i}: '+'details '*150} for i in range(14)]
terminal.chat['title_attempted']=True
if os.environ.get('CENTAUR_TEST_TREE') == '1':
    terminal.chat['title']='Principal PTY'
    terminal.store.save(terminal.chat)
    terminal.worker_context()
    parent=terminal.chat
    for title in ('Executor PTY','Neto PTY'):
        store=ChatStore(root); store.directory=root/'.centaur'/'agents'/parent['id']
        child=store.new('fixture',backend='codex')
        child.update(title=title,parent_id=parent['id'])
        store.save(child); terminal.registry.set(child['id'],'running')
        terminal.registry.activity(child['id'],'model')
        terminal.registry.native_event(child['id'], {'event':'turn.started','warning':'','output_bytes':24,'stderr_bytes':0})
        parent=child
curses.wrapper(terminal.run)
'''


class TerminalPTYTests(unittest.TestCase):
    def test_steering_during_model_wait_preserves_multiline_and_narrow_terminal(self):
        for mode in ('color', 'monochrome', 'reduced'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                master, slave = pty.openpty()
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 100, 0, 0))
                env = {**os.environ, 'TERM': 'xterm-256color', 'CENTAUR_GRAPHICS': '0',
                       'CENTAUR_TEST_STEERING': '1', 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
                if mode == 'monochrome': env['NO_COLOR'] = '1'
                if mode == 'reduced': env['CENTAUR_REDUCED_MOTION'] = '1'
                process = subprocess.Popen([sys.executable, '-c', CHILD, temporary], stdin=slave, stdout=slave, stderr=slave, env=env)
                os.close(slave)
                transcript = bytearray()
                def wait_for(predicate, timeout=5):
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        if select.select([master], [], [], .02)[0]:
                            try: transcript.extend(os.read(master, 65536))
                            except OSError: pass
                        try:
                            snapshot = json.loads((root / 'snapshot.json').read_text())
                            if predicate(snapshot): return snapshot
                        except (OSError, ValueError): pass
                        if process.poll() is not None: break
                    self.fail('Steering PTY state missing: ' + transcript.decode(errors='replace')[-1000:])
                try:
                    wait_for(lambda s: s['width'] > 0)
                    os.write(master, b'Original request\r')
                    wait_for(lambda s: s['busy'] and len(s['requests']) == 1)
                    os.write(master, b'New direction\nKeep the child working\r')
                    snapshot = wait_for(lambda s: s['inbox'] == 1 and s['draft'] == '')
                    self.assertEqual(len(snapshot['requests']), 1)
                    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 12, 40, 0, 0))
                    process.send_signal(signal.SIGWINCH)
                    wait_for(lambda s: s['width'] < 40 and s['inbox'] == 1)
                    (root/'release-model').touch()
                    snapshot = wait_for(lambda s: not s['busy'] and len(s['requests']) == 2 and s['inbox'] == 0)
                    users = [m['content'] for m in snapshot['chat']['messages'] if m['role'] == 'user']
                    self.assertEqual(users[-2:], ['Original request', 'New direction\nKeep the child working'])
                    self.assertEqual(snapshot['requests'][-1]['messages'][-1]['content'], users[-1])
                    os.write(master, b'\x11')
                    deadline = time.monotonic() + 3
                    while process.poll() is None and time.monotonic() < deadline:
                        if select.select([master], [], [], .03)[0]:
                            try: transcript.extend(os.read(master, 65536))
                            except OSError: pass
                    self.assertEqual(process.poll(), 0)
                finally:
                    if process.poll() is None:
                        process.kill(); process.wait(timeout=3)
                    os.close(master)

    def test_recursive_agent_menu_preview_return_and_resize_in_real_curses(self):
        for mode in ('color', 'monochrome', 'reduced'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                master, slave = pty.openpty()
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 34, 160, 0, 0))
                env = {**os.environ, 'TERM': 'xterm-256color', 'CENTAUR_GRAPHICS': '0', 'CENTAUR_TEST_TREE': '1',
                       'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
                if mode == 'monochrome': env['NO_COLOR'] = '1'
                if mode == 'reduced': env['CENTAUR_REDUCED_MOTION'] = '1'
                process = subprocess.Popen([sys.executable, '-c', CHILD, temporary], stdin=slave, stdout=slave, stderr=slave, env=env)
                os.close(slave)
                transcript = bytearray()
                def wait_for(predicate, timeout=6):
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        if select.select([master], [], [], .03)[0]:
                            try: transcript.extend(os.read(master, 65536))
                            except OSError: pass
                        try:
                            snapshot = json.loads((root / 'snapshot.json').read_text())
                            if predicate(snapshot): return snapshot
                        except (OSError, ValueError): pass
                        if process.poll() is not None: break
                    self.fail('Tree terminal state missing: ' + transcript.decode(errors='replace')[-1000:])
                try:
                    wait_for(lambda s: s['width'] > 0)
                    os.write(master, b'/chats\r')
                    wait_for(lambda s: s['browser'])
                    os.write(master, b'\t')
                    wait_for(lambda s: s['tree'] == ['Principal PTY', 'Executor PTY', 'Neto PTY'])
                    os.write(master, b'\x1b[B\x1b[B\r')
                    wait_for(lambda s: s['preview'] == 'Neto PTY')
                    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 12, 40, 0, 0))
                    process.send_signal(signal.SIGWINCH)
                    wait_for(lambda s: s['width'] < 40 and s['preview'] == 'Neto PTY')
                    os.write(master, b'\r')
                    wait_for(lambda s: not s['browser'] and not s['preview'] and s['chat']['title'] == 'Principal PTY')
                    self.assertIn('PRINCIPAL'.encode(), transcript)
                    self.assertIn('└─↳'.encode(), transcript)
                    os.write(master, b'\x11')
                    deadline = time.monotonic() + 6
                    while process.poll() is None and time.monotonic() < deadline:
                        if select.select([master], [], [], .03)[0]:
                            try: transcript.extend(os.read(master, 65536))
                            except OSError: pass
                    self.assertEqual(process.poll(), 0)
                finally:
                    if process.poll() is None: process.kill(); process.wait()
                    os.close(master)

    def test_multiline_protocols_paste_resize_compaction_and_resume_in_real_curses(self):
        for mode in ('color', 'monochrome', 'reduced', 'legacy'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                master, slave = pty.openpty()
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
                env = {**os.environ, 'TERM': 'xterm-color' if mode == 'legacy' else 'xterm-256color', 'CENTAUR_GRAPHICS': '0'}
                if mode == 'monochrome': env['NO_COLOR'] = '1'
                if mode == 'reduced': env['CENTAUR_REDUCED_MOTION'] = '1'
                env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
                process = subprocess.Popen([sys.executable, '-c', CHILD, temporary],
                                           stdin=slave, stdout=slave, stderr=slave, env=env)
                os.close(slave)
                transcript = bytearray()
                def wait_for(predicate, timeout=6):
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        if select.select([master], [], [], .03)[0]:
                            try: transcript.extend(os.read(master, 65536))
                            except OSError: pass
                        try:
                            snapshot = json.loads((root / 'snapshot.json').read_text())
                            if predicate(snapshot): return snapshot
                        except (OSError, ValueError): pass
                        if process.poll() is not None: break
                    self.fail('Terminal did not reach expected state: ' + transcript.decode(errors='replace')[-1000:])
                def send(value): os.write(master, value)
                try:
                    snapshot = wait_for(lambda s: s['width'] == 73)
                    self.assertNotEqual(snapshot['action_style'], snapshot['comment_style'])
                    text = 'abc ' * 30
                    send(text.encode() + b'\x1b[13;2u' + b'segunda\nterceira\x1b[27;2;13~quarta')
                    expected = text + '\nsegunda\nterceira\nquarta'
                    wait_for(lambda s: s['draft'] == expected)
                    send(b'\x1b[200~\ncolada\r\ncom quebra\x1b[201~')
                    expected += '\ncolada\ncom quebra'
                    snapshot = wait_for(lambda s: s['draft'] == expected)
                    self.assertFalse(snapshot['requests'])
                    box = snapshot['input_hitbox']
                    x, y = box['text_left'] + 3, box['top']
                    # Behave like an emulator: old macOS curses requests X10,
                    # modern ncurses explicitly negotiates SGR coordinates.
                    if re.search(rb'\x1b\[\?[0-9;]*\b1006\b[0-9;]*h', transcript):
                        send(f'\x1b[<0;{x+1};{y+1}M\x1b[<0;{x+1};{y+1}m'.encode())
                    else:
                        send(b'\x1b[M'+bytes((32,x+33,y+33)))
                        send(b'\x1b[M'+bytes((35,x+33,y+33)))
                    snapshot = wait_for(lambda s: s['cursor'] == 3)
                    self.assertEqual(snapshot['draft'], expected)
                    self.assertFalse(snapshot['requests'])
                    send(b'!')
                    expected = expected[:3] + '!' + expected[3:]
                    snapshot = wait_for(lambda s: s['draft'] == expected and s['cursor'] == 4)
                    cursor = snapshot['cursor']
                    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 12, 40, 0, 0))
                    process.send_signal(signal.SIGWINCH)
                    snapshot = wait_for(lambda s: s['width'] == 33)
                    self.assertEqual(snapshot['draft'], expected)
                    self.assertEqual(snapshot['cursor'], cursor)
                    send(b'\r')
                    snapshot = wait_for(lambda s: not s['busy'] and len(s['requests']) == 1)
                    self.assertEqual(snapshot['requests'][0]['messages'][-1]['content'], expected)
                    send(b'$compact\r')
                    snapshot = wait_for(lambda s: not s['busy'] and 'compaction' in s['chat'])
                    self.assertTrue(all(not request['tools'] for request in snapshot['requests'][1:]))
                    self.assertEqual(len(snapshot['chat']['messages']), 16)
                    send(b'continue\r')
                    snapshot = wait_for(lambda s: not s['busy'] and len(s['chat']['messages']) == 18)
                    self.assertIn('Resumo de mensagens anteriores', snapshot['requests'][-1]['messages'][1]['content'])
                    self.assertTrue((root / '.centaur/chats' / (snapshot['chat']['id'] + '.json')).is_file())
                    send(b'\x1b[A')
                    wait_for(lambda s: s['draft'] == 'continue')
                    send(b'\x1bOA')
                    wait_for(lambda s: s['draft'] == expected)
                    send(b'\x1b[B')
                    wait_for(lambda s: s['draft'] == 'continue')
                    send(b'\x1bOB')
                    wait_for(lambda s: s['draft'] == '')
                    attachment = root / 'fixture com espaço.txt'
                    attachment.write_text('fact-from-attachment', encoding='utf-8')
                    requests_before = len(snapshot['requests'])
                    send(b'\x1b[200~' + str(attachment).encode() + b'\x1b[201~')
                    snapshot = wait_for(lambda s: s['pending_attachments'] == 1 and '[Arquivo #' in s['draft'])
                    self.assertEqual(len(snapshot['requests']), requests_before)
                    send(b'\x7f')
                    wait_for(lambda s: not s['pending_attachments'] and not s['draft'])
                    send(b'\x16')
                    wait_for(lambda s: s['pending_attachments'] == 1 and '[Arquivo #' in s['draft'])
                    send(b'examine\r')
                    snapshot = wait_for(lambda s: not s['busy'] and len(s['chat']['messages']) == 20)
                    self.assertEqual(snapshot['pending_attachments'], 0)
                    self.assertIn('fact-from-attachment', json.dumps(snapshot['requests'][-1]['messages']))
                    self.assertIn('attachments', snapshot['chat']['messages'][-2])
                    send(b'\x1b[A')
                    wait_for(lambda s: s['pending_attachments'] == 1 and 'examine' in s['draft'])
                    send(b'\x1b[B')
                    wait_for(lambda s: not s['pending_attachments'] and not s['draft'])
                    self.assertIn(b'\x1b[?2004h', transcript)
                    send(b'\x11')
                    # BSD PTYs have smaller output buffers: consume curses teardown
                    # while waiting, just as a real terminal emulator would.
                    deadline = time.monotonic() + 6
                    while process.poll() is None and time.monotonic() < deadline:
                        if select.select([master], [], [], .03)[0]:
                            try: transcript.extend(os.read(master, 65536))
                            except OSError: pass
                    self.assertIsNotNone(process.poll(), 'Terminal did not exit after Ctrl+Q')
                    self.assertEqual(process.returncode, 0)
                finally:
                    if process.poll() is None: process.kill(); process.wait()
                    os.close(master)
