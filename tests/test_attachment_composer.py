"""Codex-style clipboard, atomic placeholders and restored drafts."""
import curses
import io
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from centaur_cli import attachments as a
from centaur_cli.clipboard import pasted_paths, clipboard_content, read_command
from centaur_cli.keyboard import PastedText
import test_attachments as attachment_fixtures
from test_terminal_settings import Screen


class AttachmentComposerTests(unittest.TestCase):
    setUp = attachment_fixtures.AttachmentTests.setUp
    text = attachment_fixtures.AttachmentTests.text
    image = attachment_fixtures.AttachmentTests.image
    wait_prepared = attachment_fixtures.AttachmentTests.wait_prepared
    # Inherit only fixtures/helpers, not the base feature tests.
    def test_ctrl_v_image_inserts_at_cursor_and_preserves_message(self):
        image = self.image()
        terminal = self.terminal
        terminal.draft = 'antes depois'
        terminal.cursor = 6
        with patch('centaur_cli.terminal.clipboard_content', return_value=('image', image['data'])):
            terminal.handle('\x16')
            self.wait_prepared()
        self.assertEqual(terminal.draft, 'antes [Imagem #1]depois')
        self.assertEqual(len(terminal.pending_attachments), 1)
        self.assertFalse(terminal.chat['messages'])
        self.assertIsNone(terminal.computer)
        terminal.handle(curses.KEY_LEFT)
        self.assertEqual(terminal.cursor, 6)
        terminal.handle(curses.KEY_DC)
        self.assertEqual(terminal.draft, 'antes depois')
        self.assertFalse(terminal.pending_attachments)

    def test_bracketed_paths_and_copied_uri_list_attach_multiple_files_atomically(self):
        first, second = self.root / 'um arquivo.txt', self.root / 'dois.txt'
        first.write_text('first')
        second.write_text('second')
        self.terminal.draft = 'explique '
        value = f'"{first}" "{second}"'
        self.terminal.handle(PastedText(value))
        self.wait_prepared()
        self.assertEqual(self.terminal.draft, 'explique [Arquivo #1][Arquivo #2]')
        self.assertEqual([item['name'] for item in self.terminal.pending_attachments], [first.name,second.name])
        self.assertEqual(pasted_paths(self.root, first.as_uri()+'\n'+second.as_uri()), [str(first),str(second)])
        self.assertEqual(pasted_paths(self.root, str(first)), [str(first)])
        self.assertIsNone(pasted_paths(self.root, 'file://remotehost/a.png'))
        self.assertIsNone(pasted_paths(self.root, 'explique '+str(second)))
        self.assertIsNone(pasted_paths(self.root, first.as_uri()+'\nfile:///'+'x'*300))

    def test_typed_file_path_while_busy_prepares_then_queues_attachment(self):
        terminal = self.terminal
        source = self.root / 'busy file.txt'
        source.write_text('Attachment while working')
        terminal.busy = True
        terminal.draft = source.as_uri()
        terminal.submit()
        self.wait_prepared()
        self.assertIn('[Arquivo #', terminal.draft)
        self.assertEqual(terminal.chat['messages'], [])
        self.assertFalse(terminal.inbox().snapshot())
        terminal.submit()
        pending = terminal.inbox().snapshot()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]['message']['attachments'][0]['name'], source.name)
        self.assertEqual(terminal.chat['messages'], [])
        self.assertFalse(terminal.pending_attachments)

    def test_normal_paste_remains_literal_and_never_sends(self):
        values = ('um texto\ncom duas linhas', 'texto comum ' * 35, 'á' * 180,
                  'palavra' * 80, '~centaur_missing_user_999999/texto',
                  'file://[endereco-invalido/texto', 'file:///' + 'x' * 300,
                  '"texto com aspas incompletas')
        for value in values:
            for clipboard in (False, True):
                with self.subTest(text=value[:24], clipboard=clipboard):
                    self.terminal.draft = 'antes depois'
                    self.terminal.cursor = 6
                    if clipboard:
                        with patch('centaur_cli.terminal.clipboard_content', return_value=('text', value)):
                            self.terminal.handle('\x16')
                            self.wait_prepared()
                    else:
                        self.terminal.handle(PastedText(value))
                    self.assertEqual(self.terminal.draft, 'antes ' + value + 'depois')
                    self.assertEqual(self.terminal.cursor, 6 + len(value))
                    self.assertIsNone(self.terminal.preparing_attachment)
                    self.assertFalse(self.terminal.chat['messages'])
                    self.assertFalse(self.terminal.pending_attachments)

    def test_backspace_deletes_entire_marker_and_shifts_other_elements(self):
        terminal = self.terminal
        terminal.draft = 'a '
        terminal.add_attachment(self.text('one'))
        terminal.insert_text(' meio ')
        terminal.add_attachment(self.text('two'))
        second = terminal.pending_attachments[-1]
        terminal.cursor = 2 + len('[Arquivo #1]')
        terminal.handle('\x7f')
        self.assertEqual(terminal.draft, 'a  meio [Arquivo #2]')
        self.assertEqual(terminal.pending_attachments, [second])
        terminal.cursor = len(terminal.draft)
        terminal.handle('\x7f')
        self.assertEqual(terminal.draft, 'a  meio ')
        self.assertFalse(terminal.pending_attachments)
        terminal.add_attachment(self.text())
        terminal.handle('\x15')
        self.assertEqual(terminal.draft, '')
        self.assertFalse(terminal.pending_attachments)

    def test_literal_marker_is_not_an_attachment_or_atomic_element(self):
        terminal = self.terminal
        terminal.draft = '[Arquivo #1] literal '
        terminal.add_attachment(self.text())
        self.assertEqual(terminal.pending_attachments[0]['marker'], '[Arquivo #2]')
        terminal.cursor = len('[Arquivo #1]')
        terminal.handle('\x7f')
        self.assertIn('[Arquivo #1 literal', terminal.draft)
        self.assertEqual(len(terminal.pending_attachments), 1)

    def test_edit_during_path_preparation_does_not_replace_newer_input(self):
        source = self.root / 'arquivo.txt'
        source.write_text('snapshot')
        started, release = threading.Event(), threading.Event()
        original = a.prepare_file
        def slow(*args):
            started.set()
            release.wait(2)
            return original(*args)
        with patch('centaur_cli.terminal.prepare_file', side_effect=slow):
            self.terminal.handle(PastedText(str(source)))
            self.assertTrue(started.wait(1))
            self.terminal.insert_text(' changed')
            release.set()
            self.wait_prepared()
        self.assertEqual(self.terminal.draft, str(source)+' changed')
        self.assertFalse(self.terminal.pending_attachments)
        self.assertIn('alterada', self.terminal.notice)

    def test_clipboard_text_late_result_cannot_overwrite_draft(self):
        started, release = threading.Event(), threading.Event()
        def slow(**kwargs):
            started.set(); release.wait(2)
            return 'text', 'clipboard text'
        self.terminal.draft = 'original'
        with patch('centaur_cli.terminal.clipboard_content', side_effect=slow):
            self.terminal.handle('\x16')
            self.assertTrue(started.wait(1))
            self.terminal.insert_text(' changed')
            release.set()
            self.wait_prepared()
        self.assertEqual(self.terminal.draft, 'original changed')

    def test_batch_failure_preserves_paths_without_partial_attachments(self):
        source, binary = self.root / 'good.txt', self.root / 'bad.bin'
        source.write_text('valid')
        binary.write_bytes(b'\0binary')
        value = f'"{source}" "{binary}"'
        self.terminal.handle(PastedText(value))
        self.wait_prepared()
        self.assertEqual(self.terminal.draft, value)
        self.assertFalse(self.terminal.pending_attachments)
        self.assertIn('Erro', self.terminal.notice)

    def test_raw_terminal_drop_requires_preparation_before_send(self):
        source = self.root / 'arquivo.txt'
        source.write_text('attach me')
        self.terminal.draft = str(source)
        with patch.object(self.terminal, 'start_work') as start:
            self.terminal.submit()
            self.wait_prepared()
            self.assertFalse(start.called)
            self.assertIn('[Arquivo #', self.terminal.draft)
            self.terminal.submit()
            self.assertTrue(start.called)

    def test_history_recovers_files_and_down_restores_unsent_draft(self):
        terminal = self.terminal
        terminal.draft = 'original '
        terminal.add_attachment(self.text('sent fact'))
        with patch.object(terminal, 'start_work'):
            terminal.submit()
        sent = terminal.chat['messages'][0]['content']
        terminal.draft = 'unsent '
        terminal.add_attachment(self.text('unsent fact'))
        current = terminal.draft
        terminal.handle(curses.KEY_UP)
        self.assertEqual(terminal.draft, sent)
        self.assertEqual(terminal.pending_attachments[0]['text'], 'sent fact')
        terminal.handle(curses.KEY_DOWN)
        self.assertEqual(terminal.draft, current)
        self.assertEqual(terminal.pending_attachments[0]['text'], 'unsent fact')
        self.assertNotIn('span', terminal.chat['messages'][0]['attachments'][0])
        self.assertEqual(terminal.chat['messages'][0]['content'], sent)

    def test_missing_recalled_copy_keeps_current_prompt_and_pending_files(self):
        terminal = self.terminal
        terminal.add_attachment(self.text('previous'))
        with patch.object(terminal, 'start_work'): terminal.submit()
        copy = a.attachment_directory(self.root, terminal.chat['id']) / terminal.chat['messages'][0]['attachments'][0]['digest']
        copy.unlink()
        terminal.draft = 'still here'
        terminal.handle(curses.KEY_UP)
        self.assertEqual(terminal.draft, 'still here')
        self.assertIn('Erro ao recuperar', terminal.notice)

    def test_chat_switch_restores_text_cursor_and_attachments_in_same_session(self):
        terminal = self.terminal
        terminal.draft = 'draft '
        terminal.add_attachment(self.text())
        original, text, cursor = terminal.chat, terminal.draft, terminal.cursor
        terminal.chat = terminal.new_chat()
        terminal.draft = ''
        self.assertFalse(terminal.pending_attachments)
        terminal.draft = 'other'
        terminal.chat = original
        terminal.draft = ''
        self.assertEqual((terminal.draft,terminal.cursor),(text,cursor))
        self.assertEqual(len(terminal.pending_attachments), 1)

    def test_clipboard_linux_uses_mime_types_and_wayland_reader(self):
        for wayland in ('','wayland-0'):
            with self.subTest(wayland=wayland), patch('centaur_cli.clipboard.sys.platform','linux'), patch.dict(os.environ,{'WAYLAND_DISPLAY':wayland}):
                with patch('centaur_cli.clipboard.read_command', side_effect=[b'image/png\nUTF8_STRING\n',b'png-bytes']) as read:
                    self.assertEqual(clipboard_content(),('image',b'png-bytes'))
                self.assertEqual(read.call_args.args[0][0], 'wl-paste' if wayland else 'xclip')
                self.assertIn('image/png',read.call_args.args[0])
        with patch('centaur_cli.clipboard.sys.platform','linux'), patch.dict(os.environ,{'WAYLAND_DISPLAY':''}), patch('centaur_cli.clipboard.read_command',side_effect=[b'UTF8_STRING\n',b'clipboard text']):
            self.assertEqual(clipboard_content(),('text','clipboard text'))

    def test_clipboard_read_command_bounds_size_and_kills_cancelled_process(self):
        program = self.root / 'reader'
        program.write_text('#!'+sys.executable+'\nimport sys\nsys.stdout.write("x"*1000)\n')
        program.chmod(0o755)
        with self.assertRaisesRegex(ValueError,'limite'):
            read_command([str(program)],20)
        program.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(10)\n')
        cancellation=threading.Event(); cancellation.set()
        started=time.monotonic()
        with self.assertRaisesRegex(RuntimeError,'cancelada'):
            read_command([str(program)],20,cancellation=cancellation)
        self.assertLess(time.monotonic()-started,2)

    def test_inline_markers_remain_in_bounds_after_wrap_and_resize(self):
        terminal = self.terminal
        terminal.draft = '汉字 '*18
        terminal.add_attachment(self.text())
        for size in ((12,40),(16,60),(24,80),(32,120)):
            with self.subTest(size=size):
                screen=Screen(size)
                terminal.draw(screen)
                self.assertIsNotNone(screen.cursor)
        terminal.handle(curses.KEY_LEFT)
        span=terminal.pending_attachments[0]['span']
        self.assertEqual(terminal.cursor,span[0])

    @unittest.skipUnless(os.environ.get('CENTAUR_TEST_DESKTOP')=='1','Clipboard Xvfb opt-in')
    def test_real_x11_clipboard_image_paste(self):
        import subprocess
        image=self.image()
        owner=subprocess.Popen(['xclip','-selection','clipboard','-t','image/png','-i','-quiet'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            owner.stdin.write(image['data']); owner.stdin.close()
            self.addCleanup(lambda: owner.kill() if owner.poll() is None else None)
            kind, data = None, None
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                try:
                    kind,data=clipboard_content()
                    if kind=='image': break
                except RuntimeError: pass
                time.sleep(.05)
            self.assertEqual(kind,'image')
            self.terminal.handle('\x16')
            self.wait_prepared()
            self.assertEqual(len(self.terminal.pending_attachments),1)
            self.assertIn('[Imagem #',self.terminal.draft)
            self.assertFalse(self.terminal.chat['messages'])
        finally:
            if owner.poll() is None: owner.kill()
            owner.wait()

    def test_mac_files_precede_image_data_and_plain_text_falls_back(self):
        with patch('centaur_cli.clipboard.sys.platform','darwin'), patch('centaur_cli.clipboard.mac_file_urls',return_value='file:///tmp/copied.png'):
            self.assertEqual(clipboard_content(),('text','file:///tmp/copied.png'))
        self.image()  # The image-only branch requires the optional dependency.
        with patch('centaur_cli.clipboard.sys.platform','darwin'), patch('centaur_cli.clipboard.mac_file_urls',return_value=''), patch('PIL.ImageGrab.grabclipboard',return_value=None), patch('centaur_cli.clipboard.read_command',return_value=b'plain text'):
            self.assertEqual(clipboard_content(),('text','plain text'))

    def test_local_file_urls_precede_thumbnail_in_linux_clipboard(self):
        with patch('centaur_cli.clipboard.sys.platform','linux'), patch.dict(os.environ,{'WAYLAND_DISPLAY':''}), patch('centaur_cli.clipboard.read_command',side_effect=[b'image/png\ntext/uri-list\n',b'file:///tmp/copied.png']):
            self.assertEqual(clipboard_content(),('text','file:///tmp/copied.png'))

    def test_inserting_inside_marker_keeps_atomic_attachment(self):
        from centaur_cli.composer import replace_input
        terminal = self.terminal
        terminal.add_attachment(self.text())
        terminal._draft, terminal.cursor = replace_input(terminal.draft,terminal.pending_attachments,3,3,' depois')
        self.assertEqual(len(terminal.pending_attachments),1)
        self.assertEqual(terminal.draft,'[Arquivo #1] depois')

    @unittest.skipUnless(sys.platform=='darwin' and os.environ.get('CENTAUR_TEST_MAC_CLIPBOARD')=='1','macOS disposable clipboard opt-in')
    def test_real_mac_file_url_clipboard(self):
        item = self.text()
        path = self.root / item['name']
        path.write_bytes(item['data'])
        import json
        uri = path.as_uri()
        script = 'ObjC.import("AppKit"); function run() { var p=$.NSPasteboard.generalPasteboard; p.clearContents; return p.setStringForType($('+json.dumps(uri)+'),$("public.file-url")); }'
        self.assertEqual(read_command(['osascript','-l','JavaScript','-e',script],1024).strip(),b'true')
        from centaur_cli.clipboard import mac_file_urls
        self.assertEqual(mac_file_urls(),uri)
        self.assertEqual(clipboard_content(),('text',uri))
        self.terminal.handle('\x16'); self.wait_prepared()
        self.assertIn('[Arquivo #',self.terminal.draft)

    @unittest.skipUnless(sys.platform=='darwin' and os.environ.get('CENTAUR_TEST_MAC_CLIPBOARD')=='1','macOS disposable clipboard opt-in')
    def test_real_mac_image_clipboard(self):
        import json
        image = self.image()
        path = self.root / 'paste.png'; path.write_bytes(image['data'])
        script = 'ObjC.import("AppKit"); const p=$.NSPasteboard.generalPasteboard; p.clearContents; p.setDataForType($.NSData.dataWithContentsOfFile($('+json.dumps(str(path))+')),$.NSPasteboardTypePNG);'
        read_command(['osascript','-l','JavaScript','-e',script],1024)
        kind,data = clipboard_content()
        self.assertEqual(kind,'image')
        self.assertTrue(data.startswith(b'\x89PNG'))
        self.terminal.handle('\x16'); self.wait_prepared()
        self.assertIn('[Imagem #',self.terminal.draft)
        self.assertFalse(self.terminal.chat['messages'])
