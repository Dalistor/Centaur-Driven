import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from centaur_cli.openrouter import OpenRouter
from centaur_cli.interaction import RequestTimeout
from centaur_cli.interaction import TurnCancelled
from centaur_cli.agent import run_turn
from centaur_cli.history import ChatStore
from centaur_cli.tools import ProjectTools, TOOLS


class OpenRouterTests(unittest.TestCase):
    def setUp(self):
        self.client = OpenRouter('chat-secret', 'credits-secret')

    def reply(self):
        return io.BytesIO(json.dumps({'model': 'provider/selected', 'choices': [
            {'message': {'role': 'assistant', 'content': 'Olá'}}]}).encode())

    def error(self, code, message):
        return HTTPError('https://openrouter.ai/api/v1/chat/completions', code,
                         'API error', {}, io.BytesIO(json.dumps(
                             {'error': {'code': code, 'message': message}}).encode()))

    def test_missing_account_default_uses_auto_router_once(self):
        messages = [{'role': 'user', 'content': 'Olá'}]
        with patch('centaur_cli.openrouter.urlopen', side_effect=[
                self.error(400, 'No models provided'), self.reply()]) as request:
            reply = self.client.complete('', messages, [], session_id='chat', effort='high')
        first, second = [json.loads(call.args[0].data) for call in request.call_args_list]
        self.assertNotIn('model', first)
        self.assertEqual(second, {**first, 'model': 'openrouter/auto'})
        self.assertEqual(reply.model, 'provider/selected')

    def test_account_default_is_preserved_when_available(self):
        with patch('centaur_cli.openrouter.urlopen', return_value=self.reply()) as request:
            self.client.complete('', [], [])
        self.assertEqual(request.call_count, 1)
        self.assertNotIn('model', json.loads(request.call_args.args[0].data))

    def test_explicit_model_and_other_errors_never_switch_models(self):
        for model, code, message in [('provider/fixed', 400, 'No models provided'),
                                     ('', 400, 'Unsupported effort'),
                                     ('', 402, 'Insufficient credits')]:
            with self.subTest(model=model, code=code), patch(
                    'centaur_cli.openrouter.urlopen', side_effect=self.error(code, message)) as request:
                with self.assertRaisesRegex(RuntimeError, message):
                    self.client.complete(model, [], [])
                self.assertEqual(request.call_count, 1)

    def test_auto_router_failure_is_not_retried(self):
        with patch('centaur_cli.openrouter.urlopen', side_effect=[
                self.error(400, 'No models provided'), self.error(400, 'No models provided')]) as request:
            with self.assertRaisesRegex(RuntimeError, 'No models provided'):
                self.client.complete('', [], [])
        self.assertEqual(request.call_count, 2)

    def test_api_errors_show_status_and_redact_credentials(self):
        for status in (401, 402, 404, 429, 502):
            with self.subTest(status=status), patch('centaur_cli.openrouter.urlopen', side_effect=
                    self.error(status, 'Denied chat-secret credits-secret\n\x1b[31m')):
                with self.assertRaises(RuntimeError) as caught:
                    self.client.complete('provider/fixed', [], [])
            message = str(caught.exception)
            self.assertIn(f'HTTP {status}', message)
            self.assertIn('Denied', message)
            self.assertNotIn('chat-secret', message)
            self.assertNotIn('credits-secret', message)
            self.assertNotIn('\x1b', message)
            self.assertNotIn('\n', message)

    def test_non_json_http_error_keeps_status(self):
        error = HTTPError('https://openrouter.ai', 502, 'Bad Gateway', {}, io.BytesIO(b'<html>error</html>'))
        with patch('centaur_cli.openrouter.urlopen', side_effect=error):
            with self.assertRaisesRegex(RuntimeError, 'HTTP 502'):
                self.client.complete('provider/fixed', [], [])

    def test_success_status_with_api_error_includes_reason(self):
        response = io.BytesIO(b'{"error":{"code":429,"message":"Rate limit exceeded"}}')
        with patch('centaur_cli.openrouter.urlopen', return_value=response):
            with self.assertRaisesRegex(RuntimeError, '429.*Rate limit exceeded'):
                self.client.complete('provider/fixed', [], [])

    def test_connection_error_preserves_redacted_reason_without_retry(self):
        with patch('centaur_cli.openrouter.urlopen', side_effect=URLError(
                'DNS failure chat-secret')) as request:
            with self.assertRaisesRegex(RuntimeError, 'DNS failure') as caught:
                self.client.complete('provider/fixed', [], [])
        self.assertNotIn('chat-secret', str(caught.exception))
        self.assertEqual(request.call_count, 1)

    def test_provider_error_with_partial_content_is_reported_as_failure(self):
        response = io.BytesIO(json.dumps({'choices': [{
            'message': {'role': 'assistant', 'content': 'partial'},
            'error': {'code': 502, 'message': 'Provider disconnected'}}]}).encode())
        with patch('centaur_cli.openrouter.urlopen', return_value=response):
            with self.assertRaisesRegex(RuntimeError, '502.*Provider disconnected'):
                self.client.complete('provider/fixed', [], [])

    def test_timeouts_are_distinct_from_connection_errors(self):
        for error in (TimeoutError('timed out'), URLError(TimeoutError('timed out'))):
            with self.subTest(error=error), patch('centaur_cli.openrouter.urlopen', side_effect=error) as request:
                with self.assertRaisesRegex(RequestTimeout, 'Tempo limite'):
                    self.client.complete('provider/fixed', [], [])
                self.assertEqual(request.call_count, 1)
                self.assertEqual(request.call_args.kwargs['timeout'], self.client.timeout)

    def response(self, message):
        return io.BytesIO(json.dumps({'model': 'provider/selected', 'choices': [
            {'finish_reason': 'tool_calls', 'message': message}]}).encode())

    def call(self, name, arguments, identifier='call'):
        return {'id': identifier, 'type': 'function', 'function': {
            'name': name, 'arguments': json.dumps(arguments)}}

    def test_invalid_batch_is_corrected_without_executing_or_recording_it(self):
        invalid = {'role': 'assistant', 'content': 'Ação inválida', 'tool_calls': [
            self.call('write_file', {'path': 'must-not-exist', 'content': 'x'}, 'bad-write'),
            self.call('read_skill', {'path': 'spec/SKILL.md', 'start_line': 1}, 'bad-read')]}
        corrected = {'role': 'assistant', 'content': 'Verificando', 'tool_calls': [
            self.call('read_file', {'path': 'existing.txt'}, 'good-read')]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'existing.txt').write_text('Conteúdo existente')
            store = ChatStore(root)
            chat = store.new('provider/fixed')
            chat['messages'] = [
                {'role': 'user', 'content': 'Melhore as telas'},
                {'role': 'assistant', 'content': 'Vou confirmar o escopo', 'tool_calls': [
                    self.call('ask_user', {'question': 'Qual escopo?', 'options': ['Todas as telas']}, 'scope')]},
                {'role': 'tool', 'tool_call_id': 'scope', 'content': json.dumps({
                    'status': 'answered', 'answer': 'Todas as telas'})}]
            tools = ProjectTools(root, lambda _: True, approval_mode='never', ask_user=lambda *args: None)
            with patch('centaur_cli.openrouter.urlopen', side_effect=[
                    self.response(invalid), self.response(corrected), self.reply()]) as request:
                run_turn(chat, self.client, tools, store, lambda: None)
            self.assertFalse((root / 'must-not-exist').exists())
            self.assertEqual(request.call_count, 3)
            sent = [json.loads(call.args[0].data) for call in request.call_args_list]
            self.assertEqual(sent[0]['model'], sent[1]['model'])
            self.assertEqual(sent[0]['tools'], sent[1]['tools'])
            self.assertEqual(sent[1]['messages'][:-1], sent[0]['messages'])
            self.assertIn('read_skill', sent[1]['messages'][-1]['content'])
            self.assertIn('Nenhuma ferramenta', sent[1]['messages'][-1]['content'])
            history = store.list()[0]['messages']
            self.assertNotIn('bad-write', json.dumps(history))
            self.assertNotIn('Aviso local do Centaur', json.dumps(history))
            self.assertEqual([m['tool_call_id'] for m in history if m['role'] == 'tool'], ['scope', 'good-read'])

    def test_invalid_reply_gets_only_one_correction_attempt(self):
        message = {'role': 'assistant', 'content': None, 'tool_calls': [
            self.call('read_file', {'path': 4})]}
        with patch('centaur_cli.openrouter.urlopen', side_effect=[
                self.response(message), self.response(message)]) as request:
            with self.assertRaisesRegex(RuntimeError, 'read_file:.*tipos'):
                self.client.complete('provider/fixed', [], TOOLS)
        self.assertEqual(request.call_count, 2)

    def test_malformed_json_unknown_tool_and_duplicate_ids_are_rejected_before_correction(self):
        cases = [
            {'id': 'bad', 'type': 'function', 'function': {'name': 'read_file', 'arguments': '{"path":'}},
            self.call('unavailable', {}),
            self.call('read_file', {'unexpected': 'x'}),
            self.call('read_file', {'path': 'x'}, 'duplicate')]
        for invalid in cases:
            calls = [self.call('read_file', {'path': 'x'}, 'duplicate'), invalid]
            message = {'role': 'assistant', 'content': None, 'tool_calls': calls}
            with self.subTest(invalid=invalid), patch('centaur_cli.openrouter.urlopen', side_effect=[
                    self.response(message), self.reply()]) as request:
                result = self.client.complete('provider/fixed', [], TOOLS)
            self.assertEqual(result['content'], 'Olá')
            self.assertNotIn('tool_calls', result)
            self.assertEqual(request.call_count, 2)

    def test_correction_respects_total_timeout(self):
        invalid = {'role': 'assistant', 'content': None}
        with patch('centaur_cli.openrouter.time.monotonic', side_effect=[0, 11]), patch(
                'centaur_cli.openrouter.urlopen', return_value=self.response(invalid)) as request:
            with self.assertRaises(RequestTimeout):
                self.client.complete('provider/fixed', [], [], request_timeout=10)
        self.assertEqual(request.call_count, 1)

    def test_cancel_before_correction_does_not_send_another_request(self):
        cancel = threading.Event()
        def invalid_reply(*args):
            cancel.set()
            return {'choices': [{'message': {'role': 'assistant', 'content': None}}]}
        with patch.object(self.client, 'request_json', side_effect=invalid_reply) as request:
            with self.assertRaises(TurnCancelled):
                self.client.complete('provider/fixed', [], [], cancel_event=cancel)
        self.assertEqual(request.call_count, 1)

    def test_envelope_errors_include_reason_without_automatic_correction(self):
        with patch('centaur_cli.openrouter.urlopen', return_value=io.BytesIO(b'{"choices":[]}')) as request:
            with self.assertRaisesRegex(RuntimeError, 'Resposta inválida.*list index out of range'):
                self.client.complete('provider/fixed', [], [])
        self.assertEqual(request.call_count, 1)


if __name__ == '__main__':
    unittest.main()
