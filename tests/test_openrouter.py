import io
import json
from pathlib import Path
import tempfile
import threading
import time
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
        self.client.retry_delays = ()  # Uma tentativa; a repetição tem testes próprios.

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


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.client = OpenRouter('chat-secret')
        self.client.retry_delays = (0, 0)

    def body(self, value):
        return io.BytesIO(json.dumps(value).encode())

    def ok(self):
        return self.body({'model': 'provider/selected', 'choices': [{'message': {'role': 'assistant', 'content': 'Olá'}}]})

    def http(self, code, headers=None):
        return HTTPError('https://openrouter.ai/api/v1/chat/completions', code, 'API error', headers or {},
                         io.BytesIO(json.dumps({'error': {'code': code, 'message': 'Sobrecarga'}}).encode()))

    def stream(self, *events, done=True):
        response = io.BytesIO(b''.join(
            (event if isinstance(event, bytes) else b'data: ' + json.dumps(event).encode()) + b'\n\n' for event in events)
            + (b'data: [DONE]\n\n' if done else b''))
        response.headers = {'Content-Type': 'text/event-stream; charset=utf-8'}
        return response

    def test_transient_failures_are_retried_and_the_reply_is_used(self):
        failures = [self.http(429), URLError('connection reset'), self.body({'error': {'code': 502, 'message': 'Provider'}})]
        for failure in failures:
            with self.subTest(failure=failure), patch('centaur_cli.openrouter.urlopen', side_effect=[failure, self.ok()]) as request:
                self.assertEqual(self.client.complete('provider/fixed', [], [])['content'], 'Olá')
                self.assertEqual(request.call_count, 2)

    def test_retries_are_bounded_and_permanent_errors_are_not_repeated(self):
        with patch('centaur_cli.openrouter.urlopen', side_effect=[self.http(503), self.http(503), self.http(503)]) as request:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 503: Sobrecarga'):
                self.client.complete('provider/fixed', [], [])
        self.assertEqual(request.call_count, 3)
        for failure in (self.http(401), self.http(402), URLError(TimeoutError('timed out'))):
            with self.subTest(failure=failure), patch('centaur_cli.openrouter.urlopen', side_effect=[failure, self.ok()]) as request:
                with self.assertRaises((RuntimeError, RequestTimeout)):
                    self.client.complete('provider/fixed', [], [])
                self.assertEqual(request.call_count, 1)

    def test_retry_wait_is_cancellable_and_never_exceeds_the_request_deadline(self):
        cancel = threading.Event()
        self.client.retry_delays = (30,)
        threading.Timer(.2, cancel.set).start()
        with patch.object(self.client, 'request_json', side_effect=URLError('reset')) as request:
            with self.assertRaises(TurnCancelled):
                self.client.complete('provider/fixed', [], [], cancel_event=cancel)
        self.assertEqual(request.call_count, 1)
        with patch('centaur_cli.openrouter.urlopen', side_effect=[self.http(503), self.ok()]) as request:
            with self.assertRaises(RequestTimeout):
                self.client.complete('provider/fixed', [], [], request_timeout=5)
        self.assertEqual(request.call_count, 1)

    def test_stream_is_assembled_into_the_same_validated_reply(self):
        seen = []
        events = [b': OPENROUTER PROCESSING',
                  {'model': 'provider/selected', 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': 'Vou '}}]},
                  {'choices': [{'index': 0, 'delta': {'content': 'ler.', 'reasoning_details': [
                      {'type': 'reasoning.text', 'index': 0, 'text': 'pen'}]}}]},
                  {'choices': [{'index': 0, 'delta': {'reasoning_details': [
                      {'type': 'reasoning.text', 'index': 0, 'text': 'sando', 'signature': None}]}}]},
                  {'choices': [{'index': 0, 'delta': {'reasoning_details': [
                      {'type': 'reasoning.text', 'index': 0, 'signature': 'assinatura'}]}}]},
                  {'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': 0, 'id': 'a', 'type': 'function',
                      'function': {'name': 'read_file', 'arguments': '{"pa'}}]}}]},
                  {'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': 0, 'function': {'arguments': 'th":"x.py"}'}},
                      {'index': 1, 'id': 'b', 'function': {'name': 'list_files', 'arguments': '{"path":"."}'}}]}}]},
                  {'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'delta': {}}],
                   'usage': {'prompt_tokens': 12, 'completion_tokens': 5}}]
        with patch('centaur_cli.openrouter.urlopen', return_value=self.stream(*events)) as request:
            reply = self.client.complete('provider/fixed', [], TOOLS, on_delta=seen.append)
        self.assertIs(json.loads(request.call_args.args[0].data)['stream'], True)
        self.assertEqual(reply['content'], 'Vou ler.')
        self.assertEqual(seen[-1], 'Vou ler.')
        self.assertEqual([(call['id'], call['function']['name'], json.loads(call['function']['arguments'])) for call in reply['tool_calls']],
                         [('a', 'read_file', {'path': 'x.py'}), ('b', 'list_files', {'path': '.'})])
        self.assertEqual(reply['reasoning_details'], [{'type': 'reasoning.text', 'index': 0, 'text': 'pensando', 'signature': 'assinatura'}])
        self.assertEqual((reply.model, reply.usage['prompt_tokens']), ('provider/selected', 12))

    def test_interrupted_or_failed_stream_never_yields_a_partial_reply(self):
        partial = {'choices': [{'index': 0, 'delta': {'content': 'Metade', 'tool_calls': [
            {'index': 0, 'id': 'a', 'function': {'name': 'write_file', 'arguments': '{"path":"x","content":"y"}'}}]}}]}
        self.client.retry_delays = ()
        with patch('centaur_cli.openrouter.urlopen', return_value=self.stream(partial, done=False)):
            with self.assertRaisesRegex(RuntimeError, 'Falha de conexão.*Nenhuma ferramenta'):
                self.client.complete('provider/fixed', [], TOOLS)
        failed = {'error': {'code': 400, 'message': 'Provider refused'}, 'choices': [{'index': 0, 'finish_reason': 'error', 'delta': {}}]}
        with patch('centaur_cli.openrouter.urlopen', return_value=self.stream(partial, failed)):
            with self.assertRaisesRegex(RuntimeError, 'Provider refused'):
                self.client.complete('provider/fixed', [], TOOLS)
        self.client.retry_delays = (0,)
        seen = []
        final = {'choices': [{'index': 0, 'finish_reason': 'stop', 'delta': {'content': 'Inteira'}}]}
        with patch('centaur_cli.openrouter.urlopen', side_effect=[self.stream(partial, done=False), self.stream(final)]):
            self.assertEqual(self.client.complete('provider/fixed', [], TOOLS, on_delta=seen.append)['content'], 'Inteira')
        self.assertEqual(seen, ['Metade', '', 'Inteira'])

    def test_cancelled_stream_stops_reading_and_closes_the_connection(self):
        cancel, entered = threading.Event(), threading.Event()
        class Stream(io.BytesIO):
            headers = {'Content-Type': 'text/event-stream'}
            consumed = 0
            def __next__(inner):
                inner.consumed += 1
                entered.set()
                time.sleep(.05)
                return b'data: ' + json.dumps({'choices': [{'index': 0, 'delta': {'content': 'x'}}]}).encode() + b'\n'
        response = Stream()
        errors = []
        def run():
            try:
                self.client.complete('provider/fixed', [], TOOLS, cancel_event=cancel)
            except Exception as error:
                errors.append(error)
        with patch('centaur_cli.openrouter.urlopen', return_value=response):
            worker = threading.Thread(target=run)
            worker.start()
            self.assertTrue(entered.wait(2))
            cancel.set()
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertIsInstance(errors[0], TurnCancelled)
            deadline = time.monotonic() + 2
            while not response.closed and time.monotonic() < deadline:
                time.sleep(.01)
        self.assertTrue(response.closed)
        self.assertLess(response.consumed, 20)

    def test_anthropic_requests_mark_the_prompt_for_caching_and_fall_back_when_refused(self):
        with patch('centaur_cli.openrouter.urlopen', return_value=self.ok()) as request:
            self.client.complete('anthropic/claude-sonnet', [{'role': 'user', 'content': 'Olá'}], [])
        self.assertEqual(json.loads(request.call_args.args[0].data)['cache_control'], {'type': 'ephemeral'})
        with patch('centaur_cli.openrouter.urlopen', return_value=self.ok()) as request:
            self.client.complete('openai/gpt', [{'role': 'user', 'content': 'Olá'}], [])
        self.assertNotIn('cache_control', json.loads(request.call_args.args[0].data))
        with patch('centaur_cli.openrouter.urlopen', side_effect=[self.http(400), self.ok()]) as request:
            self.assertEqual(self.client.complete('anthropic/claude-sonnet', [], [])['content'], 'Olá')
        self.assertNotIn('cache_control', json.loads(request.call_args.args[0].data))
        self.assertFalse(self.client.cache)
        self.client.cache = True
        with patch('centaur_cli.openrouter.urlopen', side_effect=[self.http(400), self.http(400)]) as request:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 400'):
                self.client.complete('anthropic/claude-sonnet', [], [])
        self.assertTrue(self.client.cache)


if __name__ == '__main__':
    unittest.main()
