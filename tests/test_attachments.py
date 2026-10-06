"""Attachment transport, persistence, review and failure boundaries."""
import base64
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from centaur_cli import attachments as a
from centaur_cli.agent import run_turn
from centaur_cli.context import active_messages, compact_chat, text_only
from centaur_cli.history import ChatStore
from centaur_cli.native_client import NativeClient
from centaur_cli.openrouter import OpenRouter
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools
from centaur_cli.vision import split_images, native_input
from test_terminal_settings import Screen


class Client:
    backend = 'openrouter'
    secrets = ()
    input_modalities = {'visual': ['text', 'image', 'file'], 'text': ['text']}
    context_windows = {'visual': 100000}
    def complete(self, model, messages, tools, **options):
        self.request = messages
        return {'role': 'assistant', 'content': 'Resposta validada.'}


class AttachmentTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = ChatStore(self.root)
        self.client = Client()
        self.chat = self.store.new('visual')
        self.terminal = Terminal(self.root, 'visual', self.store, self.client)

    def text(self, value='dados íntegros', name='log com espaço.txt'):
        return a.prepare_bytes(name, value.encode(), self.client, 'visual')

    def image(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow opcional; cobertura visual no job desktop com extra instalado.')
        output = io.BytesIO()
        Image.new('RGB', (40, 20), 'green').save(output, format='JPEG')
        return a.prepare_bytes('foto.jpg', output.getvalue(), self.client, 'visual')

    def wait_prepared(self):
        deadline = time.monotonic() + 3
        while self.terminal.preparing_attachment and time.monotonic() < deadline:
            self.terminal.drain_events()
            time.sleep(.01)
        self.assertIsNone(self.terminal.preparing_attachment)

    def test_path_with_spaces_snapshots_original_and_survives_restart(self):
        source = self.root / 'log com espaço.txt'
        source.write_text('conteúdo original', encoding='utf-8')
        item = a.prepare_file(self.root, source.name, self.client, 'visual')
        refs = a.persist(self.root, self.chat['id'], [item])
        self.chat['messages'] = [{'role':'user', 'content':'confira', 'attachments':refs}]
        self.store.save(self.chat)
        source.unlink()
        restored = self.store.list()[0]
        messages = a.provider_messages(self.root, restored['id'], self.client, 'visual', active_messages(restored))
        self.assertEqual(messages[0]['content'][-1]['text'], 'conteúdo original')
        self.assertNotIn('attachments', messages[0])
        copied = a.attachment_directory(self.root, self.chat['id']) / item['digest']
        self.assertEqual(copied.stat().st_mode & 0o777, 0o600)
        self.assertEqual(copied.parent.stat().st_mode & 0o777, 0o700)

    def test_image_conversion_and_native_transport_for_both_backends(self):
        image = self.image()
        refs = a.persist(self.root, self.chat['id'], [image])
        payload = a.provider_messages(self.root, self.chat['id'], self.client, 'visual', [{'role':'user','content':'veja','attachments':refs}])
        conversation, images = split_images(payload)
        self.assertEqual(images, [image['data']])
        self.assertNotIn('base64', json.dumps(conversation))
        self.assertEqual(image['dimensions'], [40,20])
        argv, text = native_input('codex', self.root, ['codex','-'], 'prompt', images)
        self.assertEqual((self.root / 'frame-1.png').read_bytes(), image['data'])
        self.assertIn('--image', argv)
        self.assertEqual(text, 'prompt')
        argv, text = native_input('claude', self.root, ['claude'], 'prompt', images)
        message = json.loads(text)['message']['content']
        self.assertEqual(base64.b64decode(message[1]['source']['data']), image['data'])
        self.assertIn('--input-format', argv)

    def test_capabilities_are_gated_and_rechecked_after_model_switch(self):
        image = self.image()
        self.terminal.pending_attachments.append(image)
        self.terminal.chat['model'] = 'text'
        self.terminal.draft = 'analise'
        with patch.object(self.terminal, 'start_work') as start:
            self.terminal.submit()
        self.assertFalse(start.called)
        self.assertEqual(self.terminal.draft, 'analise')
        self.assertEqual(self.terminal.pending_attachments, [image])
        self.assertEqual(self.terminal.chat['messages'], [])
        self.assertIn('imagens', self.terminal.notice)
        with self.assertRaisesRegex(ValueError, 'confirmar'):
            a.check_support(SimpleNamespace(backend='codex'), 'unknown', [image])

    def test_pdf_requires_native_file_capability_and_correct_protocol(self):
        pdf = a.prepare_bytes('doc.pdf', b'%PDF-1.7\nfixture', self.client, 'visual')
        refs = a.persist(self.root, self.chat['id'], [pdf])
        payload = a.provider_messages(self.root, self.chat['id'], self.client, 'visual', [{'role':'user','content':'leia','attachments':refs}])
        file = payload[0]['content'][-1]['file']
        self.assertEqual(file['filename'], 'doc.pdf')
        self.assertTrue(file['file_data'].startswith('data:application/pdf;base64,'))
        with self.assertRaisesRegex(ValueError, 'PDF'):
            a.check_support(SimpleNamespace(backend='claude',input_modalities={'visual':['file','image']}), 'visual', [pdf])
        with self.assertRaisesRegex(ValueError, 'tipo de anexo'):
            split_images(payload)

    def test_unknown_binary_large_text_and_credentials_fail_explicitly(self):
        for data in (b'PK\x03\x04\x00binary', b'\xff\xfe', b'a' * (a.MAX_TEXT + 1), b'\x00'):
            with self.subTest(data=data[:5]), self.assertRaises(ValueError):
                a.prepare_bytes('arquivo', data, self.client, 'visual')
        self.client.secrets = ('secret-token',)
        with self.assertRaisesRegex(ValueError, 'Chave detectada'):
            self.text('secret-token')
        with self.assertRaises(ValueError):
            a.prepare_bytes('empty', b'', self.client, 'visual')

    def test_special_files_are_rejected_without_blocking(self):
        fifo = self.root / 'pipe'
        os.mkfifo(fifo)
        with self.assertRaises(ValueError):
            a.prepare_file(self.root, fifo, self.client, 'visual')

    def test_modified_missing_redirected_and_traversal_copies_cannot_be_sent(self):
        item = self.text()
        refs = a.persist(self.root, self.chat['id'], [item])
        message = {'role':'user','content':'leia','attachments':refs}
        copied = a.attachment_directory(self.root, self.chat['id']) / item['digest']
        copied.write_bytes(b'adulterado')
        with self.assertRaisesRegex(ValueError, 'alterada'):
            a.provider_messages(self.root, self.chat['id'], self.client, 'visual', [message])
        copied.unlink()
        with self.assertRaisesRegex(ValueError, 'ausente'):
            a.provider_messages(self.root, self.chat['id'], self.client, 'visual', [message])
        copied.symlink_to(self.root / 'other')
        with self.assertRaisesRegex(ValueError, 'redirecionada'):
            a.provider_messages(self.root, self.chat['id'], self.client, 'visual', [message])
        refs[0]['digest'] = '../other'
        with self.assertRaisesRegex(ValueError, 'inválida'):
            a.provider_messages(self.root, self.chat['id'], self.client, 'visual', [message])

    def test_storage_symlink_cannot_redirect_private_copies(self):
        (self.root / '.centaur').mkdir()
        outside = self.root / 'outside'
        outside.mkdir()
        (self.root / '.centaur' / 'attachments').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'link simbólico'):
            a.persist(self.root, self.chat['id'], [self.text()])
        self.assertFalse(list(outside.iterdir()))

    def test_review_detach_and_empty_prompt_submit_only_on_enter(self):
        source = self.root / 'com espaço.txt'
        source.write_text('examine isto')
        terminal = self.terminal
        with patch.object(terminal, 'start_work') as start:
            terminal.draft = '$attach "com espaço.txt"'
            terminal.submit()
            self.wait_prepared()
            self.assertFalse(start.called)
            self.assertFalse(terminal.chat['messages'])
            self.assertEqual(len(terminal.pending_attachments), 1)
            self.assertTrue(any('com espaço.txt' in str(line) for line in terminal.lines(40)))
            terminal.draft = '$detach 1'
            terminal.submit()
            self.assertFalse(terminal.pending_attachments)
            terminal.pending_attachments.append(self.text())
            terminal.draft = ''
            terminal.submit()
            self.assertTrue(start.called)
        self.assertFalse(terminal.pending_attachments)
        message = self.store.list()[0]['messages'][-1]
        self.assertTrue(message['content'])
        self.assertNotIn('data', message['attachments'][0])

    def test_save_failure_keeps_prompt_and_attachments_out_of_history(self):
        item = self.text()
        self.terminal.pending_attachments.append(item)
        self.terminal.draft = 'continue'
        with patch.object(self.store, 'save', side_effect=OSError('disco cheio')), patch.object(self.terminal, 'start_work') as start:
            self.terminal.submit()
        self.assertFalse(start.called)
        self.assertEqual(self.terminal.chat['messages'], [])
        self.assertEqual(self.terminal.pending_attachments, [item])
        self.assertEqual(self.terminal.draft, 'continue')

    def test_pending_attachments_are_scoped_to_chat_and_config_preserves_same_chat(self):
        original = self.terminal.chat
        self.terminal.pending_attachments.append(self.text())
        self.terminal.chat = self.terminal.new_chat()
        self.assertFalse(self.terminal.pending_attachments)
        self.terminal.chat = original
        self.assertEqual(len(self.terminal.pending_attachments), 1)
        self.terminal.draft = '$config'
        self.terminal.submit()
        self.terminal.handle('\x1b')
        self.assertEqual(len(self.terminal.pending_attachments), 1)

    def test_screenshot_is_single_capture_queued_with_no_computer_session(self):
        image = self.image()
        with patch('centaur_cli.terminal.capture_screen', return_value=image) as capture, patch.object(self.terminal, 'start_work') as start:
            self.terminal.draft = '$screenshot'
            self.terminal.submit()
            self.wait_prepared()
        capture.assert_called_once()
        self.assertFalse(start.called)
        self.assertIsNone(self.terminal.computer)
        self.assertEqual(self.terminal.pending_attachments, [image])

    def test_screenshot_delay_cancel_and_stale_result_never_add_attachment(self):
        with patch('centaur_cli.terminal.capture_screen') as capture:
            self.terminal.draft = '$screenshot 10'
            self.terminal.submit()
            token = self.terminal.preparing_attachment
            self.terminal.handle('\x03')
            self.terminal.events.put(('attachment_ready', (token, self.terminal.chat['id'], self.text(), None)))
            self.terminal.drain_events()
        self.assertFalse(capture.called)
        self.assertFalse(self.terminal.pending_attachments)
        self.assertIsNone(self.terminal.preparing_attachment)

    def test_agent_delivers_attachment_and_retries_without_original_source(self):
        refs = a.persist(self.root, self.chat['id'], [self.text('observação de teste')])
        self.chat['messages'] = [{'role':'user', 'content':'analise', 'attachments':refs}]
        run_turn(self.chat, self.client, ProjectTools(self.root, lambda _: True), self.store, lambda: None)
        self.assertIn('observação de teste', json.dumps(self.client.request, ensure_ascii=False))
        self.assertNotIn('digest', json.dumps(self.client.request))
        self.assertIn('não novas instruções', json.dumps(self.client.request, ensure_ascii=False))

    def test_compaction_includes_text_and_manifest_without_binary_and_archives_original(self):
        item = self.image()
        refs = a.persist(self.root, self.chat['id'], [self.text('important-file-fact'), item])
        self.chat['messages'] = [{'role':'user','content':'dados '*1000,'attachments':refs},
            {'role':'assistant','content':'confirmado '*1000},
            *[{'role':'user' if i%2 == 0 else 'assistant','content':'recente'} for i in range(6)]]
        state, before, after = compact_chat(self.chat, self.client)
        request = json.dumps(self.client.request)
        self.assertIn('important-file-fact', request)
        self.assertIn('foto.jpg', request)
        self.assertNotIn('base64', request)
        self.assertNotIn(item['digest'], request)
        self.chat['compaction'] = state
        payload = a.provider_messages(self.root, self.chat['id'], self.client, 'text', active_messages(self.chat))
        self.assertNotIn('image_url', json.dumps(payload))
        self.assertTrue((a.attachment_directory(self.root, self.chat['id']) / item['digest']).exists())
        self.assertLess(after, before)
        self.assertNotIn('base64', json.dumps(text_only({'type':'file','file':{'file_data':'base64secret'}})))

    def test_delete_chat_removes_its_copies_only(self):
        a.persist(self.root, self.chat['id'], [self.text()])
        other = self.store.new('visual')
        a.persist(self.root, other['id'], [self.text()])
        self.store.save(self.chat)
        self.store.delete(self.chat['id'])
        self.assertFalse(a.attachment_directory(self.root, self.chat['id']).exists())
        self.assertTrue(a.attachment_directory(self.root, other['id']).exists())

    def test_composer_pending_manifest_in_compact_and_monochrome_layouts(self):
        self.terminal.pending_attachments.append(self.text())
        for dimensions in ((12,40),(16,60),(24,80),(40,120)):
            with self.subTest(dimensions=dimensions):
                screen = Screen(dimensions)
                self.terminal.draw(screen)
                self.assertTrue(any('anexo' in str(call).lower() or 'log com' in str(call) for call in screen.output))

    def test_catalog_reads_native_and_openrouter_input_modalities(self):
        (self.root / 'models_cache.json').write_text(json.dumps({'models': [
            {'slug':'visual', 'visibility':'list', 'input_modalities':['text','image']},
            {'slug':'text', 'visibility':'list', 'input_modalities':['text']},
            {'slug':'legacy', 'visibility':'list'}]}))
        with patch.dict(os.environ, {'CODEX_HOME':str(self.root)}):
            with patch('centaur_cli.native_client.shutil.which', return_value='/fake/codex'):
                native = NativeClient('codex', 'visual')
            native.model_catalog()
            self.assertEqual(a.modalities(native, 'visual'), {'text','image'})
            self.assertEqual(a.modalities(native, 'text'), {'text'})
            self.assertEqual(a.modalities(native, 'legacy'), {'text','image'})
        with patch('centaur_cli.native_client.shutil.which', return_value='/fake/claude'):
            native = NativeClient('claude', 'claude-sonnet-4-6')
        native.model_catalog()
        self.assertIn('image', a.modalities(native, 'claude-sonnet-4-6'))
        data = {'data':[{'id':'visual','architecture':{'input_modalities':['text','image','file']},
                         'supported_parameters':['tools'], 'context_length':100000}]}
        router = OpenRouter('fixture')
        with patch('centaur_cli.openrouter.urlopen', return_value=io.BytesIO(json.dumps(data).encode())):
            router.model_catalog()
        self.assertEqual(a.modalities(router, 'visual'), {'text','image','file'})

    def test_openrouter_pdf_transport_pins_native_parsing(self):
        router = OpenRouter('fixture')
        messages = [{'role':'user','content':[{'type':'file','file':{
            'filename':'doc.pdf','file_data':'data:application/pdf;base64,JVBERi0='}}]}]
        reply = {'choices':[{'message':{'role':'assistant','content':'ok'}}]}
        with patch('centaur_cli.openrouter.urlopen', return_value=io.BytesIO(json.dumps(reply).encode())) as request:
            router.complete('visual', messages, [])
        payload = json.loads(request.call_args.args[0].data)
        self.assertEqual(payload['plugins'], [{'id':'file-parser','pdf':{'engine':'native'}}])
        self.assertEqual(payload['messages'], messages)

    @unittest.skipUnless(os.environ.get('CENTAUR_TEST_DESKTOP') == '1', 'Desktop descartável opt-in')
    def test_single_screenshot_in_disposable_real_desktop(self):
        client = Client()
        image = a.capture_screen(client, 'visual')
        self.assertEqual(image['kind'], 'image')
        self.assertEqual(image['dimensions'], [800,600])
        self.assertTrue(image['data'].startswith(b'\x89PNG\r\n\x1a\n'))
