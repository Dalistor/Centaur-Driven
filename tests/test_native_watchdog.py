"""Real local processes; no account, network, paid model or desktop required."""
import json
import os
from pathlib import Path
import signal
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
        for value in ('0', '29', '3601', 'nan'):
            with patch.dict(os.environ, {'CENTAUR_NATIVE_IDLE_TIMEOUT': value}), patch('centaur_cli.native_client.shutil.which', return_value=sys.executable):
                with self.assertRaisesRegex(ValueError, 'CENTAUR_NATIVE_IDLE_TIMEOUT'):
                    NativeClient('codex')
        with patch.dict(os.environ, {'CENTAUR_NATIVE_IDLE_TIMEOUT': '1800'}), patch('centaur_cli.native_client.shutil.which', return_value=sys.executable):
            self.assertEqual(NativeClient('codex').idle_timeout, 1800)
