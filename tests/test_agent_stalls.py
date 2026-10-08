"""Bound command cleanup, safe live native telemetry and the command/model boundary."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from centaur_cli.history import ChatStore
from centaur_cli.interaction import TurnCancelled
from centaur_cli.native_client import NativeClient
from centaur_cli.sessions import SessionRegistry, native_activity_label
from centaur_cli.subagents import SubagentTools
from centaur_cli.tools import ProjectTools


class AgentStallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_command_cleanup_is_bounded_even_when_exit_is_not_confirmed(self):
        process = Mock(pid=99999)
        process.wait.side_effect = subprocess.TimeoutExpired('PRIVATE', 2)
        with patch('centaur_cli.tools.os.killpg'):
            self.assertFalse(ProjectTools.stop_command(process))
        process.wait.assert_called_once_with(timeout=2)

    def test_command_exit_race_does_not_hide_cancellation(self):
        process = Mock(pid=99999)
        with patch('centaur_cli.tools.os.killpg', side_effect=ProcessLookupError):
            self.assertTrue(ProjectTools.stop_command(process))
        process.wait.assert_called_once_with(timeout=2)

    def test_command_deadline_returns_without_unbounded_cleanup(self):
        process = Mock(pid=99999)
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired('fixture', 2)
        tools = ProjectTools(self.root, lambda _: True)
        with patch('centaur_cli.tools.subprocess.Popen', return_value=process), \
                patch('centaur_cli.tools.time.monotonic', side_effect=[0, 61]), \
                patch('centaur_cli.tools.os.killpg'):
            result = tools.execute('run_command', {'command': 'fixture'})
        self.assertIn('não confirmou saída', result)
        process.wait.assert_called_once_with(timeout=2)

    def test_live_native_state_ignores_private_text_and_heartbeat_does_not_claim_progress(self):
        registry = SessionRegistry(self.root)
        identifier = 'a'*32
        with patch('centaur_cli.sessions.time.time', return_value=1000):
            registry.set(identifier, 'running')
            registry.activity(identifier, 'model')
            registry.native_event(identifier, {'event': 'turn.started', 'warning': 'rede',
                'output_bytes': 20, 'stderr_bytes': 0, 'text': 'PRIVATE'})
        with patch('centaur_cli.sessions.time.time', return_value=1100):
            registry.heartbeat()
            self.assertIn('sem saída há 1m 40s', native_activity_label(self.root, identifier))
        self.assertEqual(registry.records[identifier]['phase_started'], 1000)
        self.assertNotIn('PRIVATE', json.dumps(registry.records))
        with patch('centaur_cli.sessions.time.time', return_value=1101):
            registry.activity(identifier, 'tool:run_command')
            self.assertEqual(native_activity_label(self.root, identifier), '')
            self.assertNotIn('native_last_output', registry.records[identifier])

    def test_native_observer_receives_only_fixed_metadata_and_cannot_stop_success(self):
        with patch('centaur_cli.native_client.shutil.which', return_value=sys.executable):
            client = NativeClient('codex', 'fixture')
        client.timeout, client.idle_timeout = 3, 0
        events = [{'type': 'item.completed', 'item': {'type': 'reasoning', 'text': 'PRIVATE'}},
                  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '{"content":"OK","calls":[]}'}},
                  {'type': 'turn.completed'}]
        code = f'import sys; sys.stdin.read(); print({chr(10).join(map(json.dumps, events))!r},flush=True)'
        snapshots = []
        def observer(event):
            snapshots.append(event)
            raise OSError('Observer unavailable')
        with patch.object(client, 'arguments', return_value=[sys.executable, '-c', code]):
            reply = client.complete('fixture', [], [], on_progress=observer)
        self.assertEqual(reply['content'], 'OK')
        self.assertEqual(snapshots[-1]['event'], 'turn.completed')
        self.assertNotIn('PRIVATE', json.dumps(snapshots))
        self.assertEqual(set(snapshots[-1]), {'event', 'warning', 'output_bytes', 'stderr_bytes',
                                            'recovering', 'recovery_errors', 'recovery_episode'})

    def test_subagent_inherits_effort_and_advertised_fast_without_changing_model(self):
        for supported in (True, False):
            with self.subTest(fast_supported=supported):
                class Client:
                    backend, allows_model_routing, fixed_model = 'codex', False, 'fixture'
                    model_efforts = {'fixture': ['low', 'medium']}
                    def model_catalog(self): return {'fixture': 'Fixture'}
                    def supports_fast(self, model): return supported
                    def complete(inner, model, messages, tools, **options):
                        self.assertEqual(options['effort'], 'low')
                        self.assertEqual(options.get('speed'), 'fast' if supported else None)
                        return {'role': 'assistant', 'content': 'Relatório'}
                parent = ChatStore(self.root).new('fixture')
                tools = SubagentTools(ProjectTools(self.root, lambda _: True), Client(), parent['id'],
                                      lambda _: None, effort='low', speed='fast')
                result = json.loads(tools.delegate({'title': 'Task', 'task': 'Consultar'}))
                child = json.loads(Path(result['history']).read_text())
                self.assertEqual(child['effort'], 'low')
                self.assertEqual(child['speed'], 'fast' if supported else 'standard')

    def test_subagent_other_model_uses_its_advertised_effort(self):
        class Client:
            backend, allows_model_routing, fixed_model = 'codex', False, 'main'
            model_efforts = {'worker': ['low']}
            def model_catalog(self): return {'main': 'Main', 'worker': 'Worker'}
            def complete(inner, model, messages, tools, **options):
                self.assertEqual(model, 'worker')
                self.assertNotIn('effort', options)  # Provider default, not unsupported high.
                return {'role': 'assistant', 'content': 'Relatório'}
        tools = SubagentTools(ProjectTools(self.root, lambda _: True), Client(), 'a'*32,
                              lambda _: None, effort='high')
        result = json.loads(tools.delegate({'title': 'Task', 'task': 'Consultar', 'model': 'worker'}))
        self.assertEqual(result['status'], 'reported')

    def test_command_finishes_then_silent_native_inference_remains_cancelable(self):
        registry = SessionRegistry(self.root)
        marker = self.root / 'executed'
        cancel = threading.Event()
        code = f'from pathlib import Path; p=Path({str(marker)!r}); p.write_text("once")'
        command = shlex.quote(sys.executable) + ' -c ' + shlex.quote(code)
        reply = {'content': 'Executando fixture', 'calls': [{'name': 'run_command', 'arguments': {'command': command}}]}
        output = '\n'.join(map(json.dumps, [
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(reply)}}, {'type': 'turn.completed'}]))
        observations = []
        class Client(NativeClient):
            count = 0
            def complete(inner, *args, **options):
                inner.count += 1
                process_code = ('import sys; sys.stdin.read(); ' + f'print({output!r},flush=True)' if inner.count == 1 else
                    'import sys,time; sys.stdin.read(); print(\'{"type":"turn.started"}\',flush=True); time.sleep(30)')
                if inner.count == 2:
                    def interrupt():
                        observations.extend(dict(record) for record in registry.records.values())
                        cancel.set()
                    timer = threading.Timer(.35, interrupt)
                    timer.start()
                    self.addCleanup(timer.cancel)
                with patch.object(inner, 'arguments', return_value=[sys.executable, '-c', process_code]):
                    return super().complete(*args, **options)
        with patch('centaur_cli.native_client.shutil.which', return_value=sys.executable):
            client = Client('codex', 'fixture')
        client.idle_timeout, client.timeout = 0, 30
        tools = SubagentTools(ProjectTools(self.root, lambda _: True, cancel_event=cancel), client,
                              'a'*32, lambda _: None, registry=registry)
        with self.assertRaises(TurnCancelled):
            tools.delegate({'title': 'Fixture após comando', 'task': 'Consultar'})
        self.assertEqual(marker.read_text(), 'once')
        self.assertTrue(any(record.get('phase') == 'model' and record.get('native_event') == 'turn.started' for record in observations))
        child = ChatStore(self.root).agents()[0]
        self.assertEqual(child['status'], 'cancelled')
        self.assertEqual(registry.state(child['id']), 'stopped')
        self.assertEqual(len([m for m in child['messages'] if m['role'] == 'tool']), 1)
        self.assertTrue(child['messages'][-1]['content'].startswith('Código de saída: 0'))


if __name__ == '__main__':
    unittest.main()
