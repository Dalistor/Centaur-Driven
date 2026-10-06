"""Exercise real curses input under a disposable POSIX terminal, without an AI account."""

import fcntl
import json
import os
from pathlib import Path
import pty
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
import copy, curses, json, sys
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
        return {'role':'assistant','content': 'Objetivo preservado, alteracoes e validacao pendentes.' if not tools else 'Mensagem recebida.'}
class RecordingTerminal(Terminal):
    def draw(self, screen):
        super().draw(screen)
        data={'draft':self.draft,'cursor':self.cursor,'busy':self.busy,
              'chat':self.chat,'requests':self.client.requests,'width':self.input_width,'notice':self.notice,
              'pending_attachments':len(self.pending_attachments),
              'action_style':self.view.palette.styles['action'],'comment_style':self.view.palette.styles['comment']}
        pending=root/'snapshot.tmp'
        pending.write_text(json.dumps(data))
        pending.replace(root/'snapshot.json')
root=Path(sys.argv[1]); client=Client()
terminal=RecordingTerminal(root,'fixture',ChatStore(root),client)
terminal.chat['messages']=[{'role':'user' if i%2==0 else 'assistant','content':f'log {i}: '+'details '*150} for i in range(14)]
terminal.chat['title_attempted']=True
curses.wrapper(terminal.run)
'''


class TerminalPTYTests(unittest.TestCase):
    def test_multiline_protocols_paste_resize_compaction_and_resume_in_real_curses(self):
        for mode in ('color', 'monochrome', 'reduced'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                master, slave = pty.openpty()
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
                env = {**os.environ, 'TERM': 'xterm-256color', 'CENTAUR_GRAPHICS': '0'}
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
                    send('$attach \"fixture com espaço.txt\"\r'.encode())
                    snapshot = wait_for(lambda s: s['pending_attachments'] == 1 and not s['draft'])
                    self.assertEqual(len(snapshot['requests']), requests_before)
                    send(b'examine\r')
                    snapshot = wait_for(lambda s: not s['busy'] and len(s['chat']['messages']) == 20)
                    self.assertEqual(snapshot['pending_attachments'], 0)
                    self.assertIn('fact-from-attachment', json.dumps(snapshot['requests'][-1]['messages']))
                    self.assertIn('attachments', snapshot['chat']['messages'][-2])
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
