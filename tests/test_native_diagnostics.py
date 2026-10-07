"""Reproduce native timeouts and terminal events without an authenticated model."""
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from centaur_cli.interaction import RequestTimeout
from centaur_cli.native_client import NativeClient, NativeTrace, codex_output


class NativeDiagnosticTests(unittest.TestCase):
    def client(self, backend='codex'):
        with patch('centaur_cli.native_client.shutil.which', return_value=sys.executable):
            client = NativeClient(backend, 'fixture')
        client.timeout, client.idle_timeout = .4, 0
        return client

    def invoke(self, client, code, **options):
        with patch.object(client, 'arguments', return_value=[sys.executable, '-c', code]):
            return client.complete('fixture', [], [], **options)

    def test_split_utf8_and_json_lines_are_consumed_once_without_item_text(self):
        trace = NativeTrace('codex')
        data = (json.dumps({'type': 'item.completed', 'item': {'type': 'reasoning',
                'text': 'PRIVATE quota ação'}}, ensure_ascii=False) + '\n').encode()
        for size in range(1, len(data) + 1):
            trace.feed(data[:size])
        trace.feed(data)
        self.assertEqual(trace.offset, len(data))
        self.assertEqual(trace.phase, 'item concluído')
        self.assertFalse(trace.failed)
        self.assertEqual(trace.hint, '')
        diagnostic = trace.diagnostic('', 42)
        self.assertNotIn('PRIVATE', diagnostic)
        self.assertNotIn('Limite de uso', diagnostic)

    def test_recoverable_error_does_not_abort_and_cannot_display_secrets(self):
        trace = NativeTrace('codex')
        trace.feed(json.dumps({'type': 'error', 'message': 'stream disconnected; Reconnecting 1/5 TOKEN PRIVATE'}) + '\n')
        self.assertFalse(trace.failed)
        message = trace.diagnostic('', 17)
        self.assertIn('rede/proxy', message)
        self.assertNotIn('TOKEN', message)
        self.assertNotIn('PRIVATE', message)

    def test_terminal_failure_preserves_safe_category_and_does_not_echo_provider_text(self):
        trace = NativeTrace('codex')
        trace.feed(json.dumps({'type': 'turn.failed', 'error': {'message': 'context window exceeded PRIVATE'}}) + '\n')
        self.assertTrue(trace.failed)
        self.assertIn('$compact', trace.hint)
        self.assertNotIn('PRIVATE', trace.diagnostic('', 12))

    def test_malformed_or_unknown_events_cannot_become_public_phase(self):
        trace = NativeTrace('codex')
        trace.feed(b'not-json\n[]\n' + json.dumps({'type': ['PRIVATE']}).encode() + b'\n'
                   + json.dumps({'type': 'PRIVATE'}).encode() + b'\n')
        self.assertEqual(trace.phase, 'nenhum evento completo')
        self.assertFalse(trace.failed)
        self.assertNotIn('PRIVATE', trace.diagnostic('', 0))

    def test_timeout_reports_network_evidence_from_real_process_and_never_executes_calls(self):
        client = self.client()
        events = [{'type': 'turn.started'}, {'type': 'error', 'message': 'stream disconnected SECRET'},
                  {'type': 'item.completed', 'item': {'type': 'agent_message',
                   'text': json.dumps({'content': None, 'calls': [{'name': 'run_command',
                            'arguments': {'command': 'PRIVATE'}}]})}}]
        code = ('import sys,time; sys.stdin.read(); '
                f'print({chr(10).join(map(json.dumps, events))!r},flush=True); '
                'print("Reconnecting 2/5 ACCOUNT",file=sys.stderr,flush=True); time.sleep(30)')
        with self.assertRaisesRegex(RuntimeError, 'tempo limite') as caught:
            self.invoke(client, code)
        message = str(caught.exception)
        self.assertIn('rede/proxy', message)
        self.assertIn('item concluído', message)
        self.assertIn('entrada:', message)
        self.assertIn('Nenhuma chamada pendente', message)
        for private in ('SECRET', 'ACCOUNT', 'PRIVATE', 'run_command'):
            self.assertNotIn(private, message)

    def test_default_1800_second_timeout_keeps_last_event_evidence(self):
        client = self.client()
        client.timeout = 1800
        elapsed = [0]
        class Process:
            pid, returncode = 99999, 0
            def communicate(self, input=None, timeout=None):
                if input is None:
                    return '', ''  # Cleanup after kill.
                elapsed[0] = 1801
                raise subprocess.TimeoutExpired('fixture', timeout,
                    output=b'{"type":"turn.started"}\n', stderr=b'PRIVATE')
        with patch('centaur_cli.native_client.subprocess.Popen', return_value=Process()), \
                patch('centaur_cli.native_client.time.monotonic', side_effect=lambda: elapsed[0]), \
                patch('centaur_cli.native_client.os.killpg'):
            with self.assertRaisesRegex(RuntimeError, 'tempo limite de 1800') as caught:
                client.complete('fixture', [], [])
        self.assertIn('turno iniciado', str(caught.exception))
        self.assertIn('Causa não confirmada', str(caught.exception))
        self.assertNotIn('PRIVATE', str(caught.exception))

    def test_terminal_failure_stops_real_hanging_process_before_deadline(self):
        for backend in ('codex', 'claude'):
            with self.subTest(backend=backend):
                client = self.client(backend)
                client.timeout = 20
                event = ({'type': 'turn.failed', 'error': {'message': 'usage limit PRIVATE'}}
                         if backend == 'codex' else {'type': 'result', 'is_error': True,
                                'subtype': 'error_during_execution', 'result': 'usage limit PRIVATE'})
                code = ('import sys,time; sys.stdin.read(); '
                        f'print({json.dumps(event)!r},flush=True); time.sleep(30)')
                # The second communicate is cleanup, not waiting for the deadline.
                with self.assertRaisesRegex(RuntimeError, 'Limite de uso') as caught:
                    self.invoke(client, code)
                self.assertNotIn('PRIVATE', str(caught.exception))

    def test_reconnect_followed_by_valid_final_reply_is_accepted(self):
        client = self.client()
        client.timeout = 3
        events = [{'type': 'error', 'message': 'stream disconnected; Reconnecting 1/5'},
                  {'type': 'item.completed', 'item': {'type': 'agent_message',
                   'text': json.dumps({'content': 'Recuperou', 'calls': []})}},
                  {'type': 'turn.completed'}]
        code = ('import sys,time; sys.stdin.read(); '
                f'print({json.dumps(events[0])!r},flush=True); time.sleep(.2); '
                f'print({chr(10).join(map(json.dumps, events[1:]))!r},flush=True)')
        self.assertEqual(self.invoke(client, code)['content'], 'Recuperou')

    def test_silent_summary_timeout_keeps_typed_exception_and_unknown_cause(self):
        with self.assertRaises(RequestTimeout) as caught:
            self.invoke(self.client(), 'import sys,time; sys.stdin.read(); time.sleep(30)', request_timeout=.3)
        self.assertIn('Causa não confirmada', str(caught.exception))
        self.assertIn('nenhum evento completo', str(caught.exception))

    def test_partial_final_reply_then_hang_is_never_accepted_as_success(self):
        code = ('import sys,time; sys.stdin.read(); '
                'print(\'{"type":"turn.completed"}\',flush=True); time.sleep(30)')
        with self.assertRaisesRegex(RuntimeError, 'tempo limite') as caught:
            self.invoke(self.client(), code)
        self.assertIn('turno concluído', str(caught.exception))

    def test_final_file_cannot_override_terminal_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'reply.json').write_text(json.dumps({'content': 'Invalid success', 'calls': []}))
            with self.assertRaisesRegex(ValueError, 'interrompeu'):
                codex_output(root, '{"type":"turn.failed"}\n')

    def test_recoverable_error_without_completion_cannot_become_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'resposta final'):
                codex_output(Path(temporary), '{"type":"error","message":"Reconnecting 1/5"}\n')


if __name__ == '__main__':
    unittest.main()
