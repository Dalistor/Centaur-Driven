"""Native process/clock regressions; no account, network, paid model or desktop."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from centaur_cli.history import ChatStore
from centaur_cli.interaction import RequestTimeout, TurnCancelled
from centaur_cli.native_client import NativeClient
from centaur_cli.sessions import SessionRegistry, activity_label
from centaur_cli.subagents import SubagentTools
from centaur_cli.tools import ProjectTools


class NativeWatchdogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        with patch('centaur_cli.native_client.shutil.which', return_value=sys.executable):
            self.client = NativeClient('codex', 'fixture')
        self.client.timeout = 5
        self.client.idle_timeout = .8

    def invoke(self, code, **options):
        with patch.object(self.client, 'arguments', return_value=[sys.executable, '-c', code]):
            return self.client.complete('fixture', [], [], **options)

    def default_client(self, backend='codex'):
        with patch.dict(os.environ, {}, clear=True), patch('centaur_cli.native_client.shutil.which', return_value=sys.executable):
            return NativeClient(backend, 'fixture')

    def final_output(self, backend, content='Resposta pública'):
        reply = {'content': content, 'calls': []}
        if backend == 'claude':
            return json.dumps({'type': 'result', 'subtype': 'success', 'structured_output': reply})
        return '\n'.join(map(json.dumps, [
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(reply)}},
            {'type': 'turn.completed'}]))

    def silent_process(self, backend, elapsed):
        output = self.final_output(backend)
        class Process:
            pid, returncode, requests = 99999, 0, 0
            def communicate(inner, input=None, timeout=None):
                inner.requests += 1
                if inner.requests == 1:
                    elapsed[0] += 301  # No output for more than the old five-minute cutoff.
                    raise subprocess.TimeoutExpired('fixture', timeout)
                return output, ''
        return Process()

    def test_default_accepts_final_only_replies_after_five_minutes_in_turns_and_summaries(self):
        for backend in ('codex', 'claude'):
            for summary_timeout in (None, 600):
                with self.subTest(backend=backend, summary_timeout=summary_timeout):
                    client, elapsed = self.default_client(backend), [0]
                    process = self.silent_process(backend, elapsed)
                    with patch('centaur_cli.native_client.time.monotonic', side_effect=lambda: elapsed[0]), \
                            patch('centaur_cli.native_client.subprocess.Popen', return_value=process), \
                            patch('centaur_cli.native_client.os.killpg') as kill:
                        reply = client.complete('fixture', [], [], request_timeout=summary_timeout)
                    self.assertEqual(reply['content'], 'Resposta pública')
                    self.assertEqual(process.requests, 2)
                    kill.assert_not_called()

    def test_default_accepts_a_real_silent_process_until_its_final_reply(self):
        for backend in ('codex', 'claude'):
            with self.subTest(backend=backend):
                client = self.default_client(backend)
                self.assertEqual(client.idle_timeout, 0)
                code = ('import sys,time; sys.stdin.read(); time.sleep(1); '
                        f'print({self.final_output(backend)!r},flush=True)')
                with patch.object(client, 'arguments', return_value=[sys.executable, '-c', code]):
                    reply = client.complete('fixture', [], [])
                self.assertEqual(reply['content'], 'Resposta pública')

    def test_default_subagent_reports_after_long_silence_without_false_failure(self):
        client, elapsed = self.default_client(), [0]
        store = ChatStore(self.root)
        parent = store.new('fixture', backend='codex')
        registry = SessionRegistry(self.root)
        tools = SubagentTools(ProjectTools(self.root, lambda _: True), client,
                              parent['id'], lambda _: None, registry=registry)
        with patch('centaur_cli.native_client.time.monotonic', side_effect=lambda: elapsed[0]), \
                patch('centaur_cli.native_client.subprocess.Popen', return_value=self.silent_process('codex', elapsed)), \
                patch('centaur_cli.native_client.os.killpg') as kill:
            result = json.loads(tools.delegate({'title': 'Fixture silenciosa', 'task': 'Consultar fontes'}))
        self.assertEqual(result['status'], 'reported')
        self.assertEqual(result['report'], 'Resposta pública')
        self.assertEqual(registry.state(result['id']), 'stopped')
        child = next(a for a in store.agents() if a['id'] == result['id'])
        self.assertNotIn('last_error', child)
        kill.assert_not_called()

    def test_silent_native_process_is_stopped_before_overall_deadline(self):
        started = time.monotonic()
        with self.assertRaisesRegex(RuntimeError, 'sem nova saída') as error:
            self.invoke('import sys,time; sys.stdin.read(); time.sleep(30)')
        self.assertLess(time.monotonic() - started, 3)
        self.assertIn('/retry', str(error.exception))
        self.assertIn('Nenhuma ferramenta', str(error.exception))

    def test_growing_output_renews_idle_budget_without_publishing_private_text(self):
        code = '''import sys,time,json
sys.stdin.read()
for i in range(12):
 print(json.dumps({'type':'item.completed','item':{'type':'reasoning','text':'PRIVATE'}}),flush=True)
 time.sleep(.1)
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps({'content':'Final público','calls':[]})}}),flush=True)
print(json.dumps({'type':'turn.completed'}),flush=True)
'''
        reply = self.invoke(code)
        self.assertEqual(reply['content'], 'Final público')
        self.assertNotIn('PRIVATE', json.dumps(reply))

    def test_activity_cannot_extend_the_overall_request_deadline(self):
        code = 'import sys,time; sys.stdin.read()\nwhile True:\n print("tick",flush=True); time.sleep(.05)'
        self.client.timeout = .45
        with self.assertRaisesRegex(RuntimeError, 'tempo limite de 0.45'):
            self.invoke(code)

    def test_disabling_idle_keeps_the_absolute_deadline_and_cancellation(self):
        self.client.idle_timeout = 0
        self.client.timeout = .35
        with self.assertRaisesRegex(RuntimeError, 'tempo limite de 0.35'):
            self.invoke('import time; time.sleep(30)')
        self.client.timeout = 5
        cancel = threading.Event()
        timer = threading.Timer(.15, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)
        with self.assertRaises(TurnCancelled):
            self.invoke('import time; time.sleep(30)', cancel_event=cancel)

    def test_summary_idle_expiry_remains_a_request_timeout(self):
        with self.assertRaisesRegex(RequestTimeout, 'sem nova saída'):
            self.invoke('import time; time.sleep(30)', request_timeout=4)

    def test_cancel_stops_a_silent_process_promptly(self):
        cancel = threading.Event()
        timer = threading.Timer(.15, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)
        with self.assertRaises(TurnCancelled):
            self.invoke('import time; time.sleep(30)', cancel_event=cancel)

    def test_cleanup_is_bounded_with_an_escaped_child_holding_output(self):
        marker = self.root / 'escaped.pid'
        code = ('import subprocess,sys,time\n'
                'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],start_new_session=True)\n'
                f'open({str(marker)!r},"w").write(str(p.pid))\n'
                'time.sleep(30)')
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(RuntimeError, 'sem nova saída'):
                self.invoke(code)
            self.assertLess(time.monotonic() - started, 4)
        finally:
            if marker.exists():
                try:
                    os.kill(int(marker.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_complete_reply_is_not_blocked_by_shutdown_or_inherited_output(self):
        for backend in ('codex', 'claude'):
            for complete, parent_hangs in ((True, False), (False, False), (True, True)):
                with self.subTest(backend=backend, complete=complete, parent_hangs=parent_hangs):
                    marker = self.root / f'{backend}-{complete}-{parent_hangs}.pid'
                    output = self.final_output(backend) if complete else '{"type":"turn.started"}'
                    code = ('import subprocess,sys,json\n'
                            'sys.stdin.read()\n'
                            'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],start_new_session=True)\n'
                            f'open({str(marker)!r},"w").write(str(p.pid))\n'
                            f'print({output!r},flush=True)\n'
                            + ('import time; time.sleep(30)\n' if parent_hangs else ''))
                    client = self.default_client(backend)
                    client.timeout = 5 if parent_hangs else 3
                    started = time.monotonic()
                    try:
                        with patch.object(client, 'arguments', return_value=[sys.executable, '-c', code]):
                            if complete:
                                self.assertEqual(client.complete('fixture', [], [])['content'], 'Resposta pública')
                            else:
                                with self.assertRaises(RuntimeError) as error:
                                    client.complete('fixture', [], [])
                                self.assertNotIn('tempo limite', str(error.exception))
                        self.assertLess(time.monotonic() - started, 5 if parent_hangs else 3)
                    finally:
                        if marker.exists():
                            try:
                                os.kill(int(marker.read_text()), signal.SIGKILL)
                            except ProcessLookupError:
                                pass

    def test_stalled_child_returns_failed_report_and_persists_public_diagnostic(self):
        store = ChatStore(self.root)
        parent = store.new('fixture', backend='codex')
        registry = SessionRegistry(self.root)
        progress = []
        tools = SubagentTools(ProjectTools(self.root, lambda _: True), self.client,
                              parent['id'], progress.append, registry=registry)
        with patch.object(self.client, 'arguments', return_value=[sys.executable, '-c', 'import time; time.sleep(30)']):
            result = json.loads(tools.delegate({'title': 'Fixture lenta', 'task': 'Consultar arquivo'}))
        self.assertEqual(result['status'], 'failed')
        self.assertIn('sem nova saída', result['report'])
        self.assertEqual(registry.state(result['id']), 'stopped')
        child = next(a for a in store.agents() if a['id'] == result['id'])
        self.assertEqual(child['last_error'], result['report'])
        self.assertTrue(any('Retomando coordenador' in notice for notice in progress))

    def test_runtime_heartbeat_does_not_reset_phase_timer_and_input_is_explicit(self):
        registry = SessionRegistry(self.root)
        chat_id = 'a' * 32
        registry.set(chat_id, 'running')
        registry.activity(chat_id, 'model')
        started = registry.records[chat_id]['phase_started']
        with patch('centaur_cli.sessions.time.time', return_value=started + 40):
            registry.heartbeat()
            self.assertIn('Aguardando modelo · 0m 40s', activity_label(self.root, chat_id))
            registry.set(chat_id, 'waiting_input')
            self.assertEqual(activity_label(self.root, chat_id), 'Aguardando input')
            registry.set(chat_id, 'running')
            self.assertIn('0m 00s', activity_label(self.root, chat_id))
            registry.records[chat_id]['phase'] = {'invalid': 'phase'}
            registry._write(registry.records[chat_id])
            self.assertIn('Trabalhando', activity_label(self.root, chat_id))
            registry.set(chat_id, 'stopped')
            self.assertEqual(activity_label(self.root, chat_id), '')

    def test_idle_environment_validation_and_override(self):
        for variable, attribute in (('CENTAUR_NATIVE_IDLE_TIMEOUT', 'idle_timeout'),
                                    ('CENTAUR_NATIVE_RECOVERY_TIMEOUT', 'recovery_timeout')):
            for value in ('-1', '29', '3601', 'nan'):
                with patch.dict(os.environ, {variable: value}), patch('centaur_cli.native_client.shutil.which', return_value=sys.executable):
                    with self.assertRaisesRegex(ValueError, variable):
                        NativeClient('codex')
            for value in ('0', '1800'):
                with patch.dict(os.environ, {variable: value}), patch('centaur_cli.native_client.shutil.which', return_value=sys.executable):
                    self.assertEqual(getattr(NativeClient('codex'), attribute), int(value))
