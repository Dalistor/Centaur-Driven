import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from centaur_cli.agent import run_turn
from centaur_cli.backends import resolve_speed
from centaur_cli.config import save_config, load_config
from centaur_cli.history import ChatStore
from centaur_cli.native_client import NativeClient, claude_output
from centaur_cli.native_usage import (BalanceUnavailable, NativeBalance, QuotaWindow,
                                     codex_balance, claude_windows, native_label, read_codex_balance)
from centaur_cli.openrouter import OpenRouter, ModelReply
from centaur_cli.settings import ConfigPicker
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools
from test_terminal_settings import Screen


class NativeUsageSpeedTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ChatStore(self.root)

    def native(self, backend='codex', model='fast'):
        with patch('centaur_cli.native_client.shutil.which', return_value='/fake/' + backend):
            return NativeClient(backend, model)

    def test_codex_stdio_handshake_reads_only_account_limits_and_cleans_up(self):
        record = self.root / 'rpc.json'
        executable = self.root / 'codex'
        executable.write_text('''#!/usr/bin/env python3
import json, os, sys, time
seen=[]
for line in sys.stdin:
    message=json.loads(line); seen.append(message)
    with open(RECORD,'w') as out: json.dump({'messages':seen,'extra_key':bool(os.environ.get('OPENROUTER_API_KEY'))},out)
    if message['method']=='initialize': print(json.dumps({'id':1,'result':{'userAgent':'private account metadata'}}),flush=True)
    elif message['method']=='account/rateLimits/read':
        print(json.dumps({'id':2,'result':{'rateLimits':{'primary':{'usedPercent':25,'windowDurationMins':300,'resetsAt':2000000000},'secondary':{'usedPercent':80,'windowDurationMins':10080},'credits':{'balance':'12.5','hasCredits':True}}}}),flush=True)
'''.replace('RECORD', repr(str(record))))
        executable.chmod(0o700)
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'private-key'}):
            balance = read_codex_balance(str(executable))
        self.assertEqual([window.remaining for window in balance.windows], [75, 20])
        self.assertEqual([window.label for window in balance.windows], ['5h', '7d'])
        self.assertEqual(float(balance.credits), 12.5)
        saved = json.loads(record.read_text())
        self.assertFalse(saved['extra_key'])
        self.assertEqual([m['method'] for m in saved['messages']], ['initialize', 'initialized', 'account/rateLimits/read'])
        self.assertNotIn('private account metadata', repr(balance))

    def test_quota_unknown_and_invalid_values_are_never_a_fictitious_balance(self):
        with self.assertRaises(BalanceUnavailable): codex_balance({'rateLimits': {}})
        balance = codex_balance({'rateLimits': {'credits': {'hasCredits': False, 'balance': 'NaN'}}})
        self.assertIsNone(balance.credits)
        self.assertEqual(native_label(balance, 'ready', 80)[1], 'warning')
        windows = claude_windows([
            {'rate_limit_info': {'rateLimitType': 'five_hour', 'status': 'allowed'}},
            {'rate_limit_info': {'rateLimitType': 'seven_day', 'status': 'rejected'}}])
        self.assertIsNone(windows['five_hour'].remaining)
        self.assertEqual(windows['seven_day'].remaining, 0)
        balance = NativeBalance('claude', tuple(windows.values()))
        label, _ = native_label(balance, 'ready', 100)
        self.assertNotIn('100%', label)
        self.assertIn('disponível', label)
        self.assertTrue(label.startswith('Claude ~'))

    def test_claude_only_completed_results_supply_calls_and_usage_events_stay_public(self):
        events = [
            {'type': 'assistant', 'message': {'content': [{'type': 'thinking', 'thinking': 'PRIVATE'}],
             'usage': {'input_tokens': 10, 'cache_read_input_tokens': 50, 'cache_creation_input_tokens': 10, 'output_tokens': 5}}},
            {'type': 'rate_limit_event', 'rate_limit_info': {'rateLimitType': 'five_hour', 'status': 'allowed', 'utilization': .25}},
            {'type': 'result', 'subtype': 'success', 'structured_output': {'content': 'Final', 'calls': []},
             'usage': {'input_tokens': 100, 'cache_read_input_tokens': 50, 'cache_creation_input_tokens': 10, 'output_tokens': 20}}]
        output = '\n'.join(map(json.dumps, events))
        result, windows = claude_output(output)
        self.assertEqual(result['structured_output']['content'], 'Final')
        self.assertEqual(windows['five_hour'].remaining, 75)
        self.assertNotIn('PRIVATE', json.dumps(result))
        for text in ('\n'.join(map(json.dumps, events[:-1])), json.dumps({'type':'assistant','structured_output':{'content':'fake','calls':[]}})):
            with self.assertRaises(ValueError): claude_output(text)
        client = self.native('claude', 'sonnet')
        process = SimpleNamespace(returncode=0, communicate=lambda *a, **k: (output, ''))
        with patch('centaur_cli.native_client.subprocess.Popen', return_value=process):
            reply = client.complete('sonnet', [], [])
        self.assertEqual(reply.usage, {'prompt_tokens':160, 'completion_tokens':20})
        self.assertEqual(reply.context_usage, {'prompt_tokens':70})
        self.assertNotIn('context_usage', reply)
        self.assertEqual(client.credits().windows[0].remaining, 75)

    def test_native_fast_capability_keeps_model_effort_and_tool_isolation(self):
        (self.root / 'models_cache.json').write_text(json.dumps({'models': [
            {'slug':'fast','service_tiers':[{'id':'fast'}]},
            {'slug':'legacy','additional_speed_tiers':['fast']}, {'slug':'plain','service_tiers':[]}]}))
        with patch.dict(os.environ, {'CODEX_HOME':str(self.root)}):
            client = self.native()
            client.check_speed('fast', 'fast')
            self.assertTrue(client.supports_fast('legacy'))
            with self.assertRaises(ValueError): client.check_speed('plain', 'fast')
            argv = client.arguments(self.root, 'fast', 'high', speed='fast')
        self.assertIn('service_tier="fast"', argv)
        self.assertEqual(argv[argv.index('--model') + 1], 'fast')
        self.assertIn('model_reasoning_effort="high"', argv)
        self.assertIn('--ignore-user-config', argv)
        self.assertIn('read-only', argv)
        self.assertIn('service_tier="default"', client.arguments(self.root))
        claude = self.native('claude', 'opus')
        with patch('centaur_cli.native_client.subprocess.run', return_value=SimpleNamespace(stdout='2.1.280', returncode=0)):
            claude.check_speed('opus', 'fast')
        argv = claude.arguments(self.root, 'opus', 'high', speed='fast')
        self.assertEqual(json.loads(argv[argv.index('--settings')+1]), {'fastMode':True})
        self.assertEqual(argv[argv.index('--model')+1], 'opus')
        self.assertEqual(argv[argv.index('--tools')+1], '')
        self.assertIn('--safe-mode', argv)
        with patch('centaur_cli.native_client.subprocess.Popen') as start:
            with self.assertRaises(ValueError): claude.complete('sonnet', [], [], speed='fast')
            start.assert_not_called()

    def test_openrouter_fast_uses_announced_tier_and_reports_a_standard_fallback(self):
        client = OpenRouter('key')
        endpoints = io.BytesIO(json.dumps({'data':{'endpoints':[{'service_tier':'priority'}]}}).encode())
        result = io.BytesIO(json.dumps({'choices':[{'message':{'role':'assistant','content':'ok'}}],
                                        'model':'provider/model','service_tier':'default'}).encode())
        with patch('centaur_cli.openrouter.urlopen', side_effect=[endpoints, result]) as request:
            reply = client.complete('provider/model', [], [], speed='fast', effort='high')
        sent = json.loads(request.call_args.args[0].data)
        self.assertEqual(sent['model'], 'provider/model')
        self.assertEqual(sent['service_tier'], 'fast')
        self.assertEqual(sent['reasoning'], {'effort':'high'})
        self.assertEqual(reply.service_tier, 'default')
        self.assertNotIn('service_tier', reply)
        tagged = io.BytesIO(json.dumps({'data': {'endpoints': [
            {'tag': 'anthropic'}, {'tag': 'anthropic/fast'}]}}).encode())
        with patch('centaur_cli.openrouter.urlopen', return_value=tagged):
            self.assertTrue(client.supports_fast('anthropic/claude-opus-5.5'))
        self.assertFalse(client.supports_fast('openrouter/auto'))
        client.speed_support['plain/model'] = False
        with self.assertRaises(ValueError): client.complete('plain/model', [], [], speed='fast')

    def test_config_speed_model_and_effort_return_to_same_chat_and_persist(self):
        client = SimpleNamespace(backend='openrouter', secrets=(), speed_support={'main':True},
                                 check_speed=lambda *a: None)
        terminal = Terminal(self.root, 'main', self.store, client, effort='high')
        terminal.chat.update(title='Meu chat', messages=[{'role':'user','content':'Objetivo'}],
                             last_error='Timeout', compaction={'through':1,'summary':'Objetivo anterior'})
        original = terminal.chat['id']
        terminal.store.save(terminal.chat)
        terminal.configure('$config')
        picker = terminal.settings
        picker.page='speed'
        self.assertEqual([v for v, _ in picker.options()], ['standard','fast'])
        picker.selected=1
        terminal.handle('\r')
        picker.row=len(picker.fields)-1
        class ImmediateThread:
            def __init__(self,target,**kwargs): self.target=target
            def start(self): self.target()
        with patch('centaur_cli.terminal.threading.Thread', ImmediateThread), \
                patch('centaur_cli.terminal.create_client') as create:
            terminal.handle('\r'); terminal.drain_events()
            create.assert_not_called()
        self.assertEqual(terminal.chat['id'], original)
        self.assertEqual(terminal.chat['messages'], [{'role':'user','content':'Objetivo'}])
        self.assertEqual(terminal.chat['title'], 'Meu chat')
        self.assertEqual(terminal.chat['last_error'], 'Timeout')
        self.assertEqual(terminal.chat['speed'], 'fast')
        self.assertEqual(load_config(self.root)['speed'], 'fast')
        self.assertIsNone(terminal.settings)
        terminal.activate_config('openrouter','other','low',client,'auto','standard')
        self.assertEqual(terminal.chat['id'], original)
        self.assertEqual((terminal.chat['model'],terminal.chat['effort'],terminal.chat['speed']), ('other','low','standard'))
        self.assertIn('compaction', terminal.chat)
        self.assertEqual(self.store.list()[0]['id'], original)

    def test_fast_preference_reaches_main_request_and_unknown_models_stay_standard(self):
        for backend, model in [('claude','sonnet'), ('codex','unknown'), ('openrouter','unknown/model')]:
            picker=ConfigPicker(backend,model,'high')
            picker.page='speed'
            self.assertEqual([v for v,_ in picker.options()], ['standard'])
        chat=self.store.new('main'); chat['speed']='fast'
        seen=[]
        class Client:
            def complete(self,*args,**kwargs):
                seen.append(kwargs)
                return ModelReply({'role':'assistant','content':'Done'}, service_tier='priority')
        run_turn(chat,Client(),ProjectTools(self.root,lambda _:False),self.store,lambda:None)
        self.assertEqual(seen,[{'speed':'fast'}])
        self.assertEqual(chat['speed_served'],'priority')
        save_config(self.root,'claude','opus',speed='fast')
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(resolve_speed(self.root,'claude'),'fast')
            self.assertEqual(resolve_speed(self.root,'codex'),'standard')
        with self.assertRaises(ValueError): save_config(self.root,'claude','opus',speed='wrong')

    def test_native_footer_cached_missing_and_stale_states_never_overlap_context(self):
        client=SimpleNamespace(backend='claude',secrets=())
        terminal=Terminal(self.root,'opus',self.store,client,speed='fast')
        terminal.credits=NativeBalance('claude',(QuotaWindow('5h',75),QuotaWindow('7d',30)))
        for size in ((24,80),(12,40),(34,120)):
            screen=Screen(size); terminal.draw(screen)
            footer=[(col,text) for row,col,text,_ in screen.output if row==size[0]-2]
            self.assertEqual(len(footer),2)
            self.assertLessEqual(footer[0][0]+len(footer[0][1]),footer[1][0])
        self.assertIn('Fast',screen.text())
        self.assertIn('após resposta', native_label(None,'awaiting',80,'claude')[0])
        self.assertTrue(native_label(terminal.credits,'error',80)[0].startswith('Claude ~'))
