"""Exercise actual adapters across root, child and grandchild boundaries."""
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from centaur_cli.agent import run_turn
from centaur_cli.agent_runtime import AgentGroup
from centaur_cli.attachments import provider_messages
from centaur_cli.context import compact_chat
from centaur_cli.history import ChatStore
from centaur_cli.interaction import TurnCancelled
from centaur_cli.inbox import Inbox
from centaur_cli.native_client import NativeClient, codex_output
from centaur_cli.openrouter import OpenRouter
from centaur_cli.sessions import SessionRegistry
from centaur_cli.subagents import SubagentTools
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools, TOOLS


# Executed as a real process for Codex/Claude; OpenRouter uses the same plan via HTTP.
ENGINE = '''import json, sys, time

def answer(messages, model):
    first = next(m['content'] for m in messages if m['role'] == 'user')
    if messages[0]['content'].startswith('Resuma o histórico'):
        return {'content':'Resumo: objetivo preservado; validar os arquivos atuais.', 'calls':[]}
    if len(messages) == 2:
        if first == 'steer':
            return {'content':'Writing', 'calls':[
                {'name':'write_file','arguments':{'path':'first.txt','content':'first'}},
                {'name':'write_file','arguments':{'path':'old.txt','content':'old'}}]}
        if first in ('root', 'child'):
            task = 'child' if first == 'root' else 'grandchild'
            selected = 'worker' if first == 'root' else 'grand'
            if '/' in model: selected = 'provider/' + selected
            return {'content':'Delegando ' + task, 'calls':[{'name':'delegate_task',
                'arguments':{'title':task,'task':task,'model':selected}}]}
        if first == 'grandchild':
            return {'content':'Gravando arquivo', 'calls':[{'name':'write_file',
                'arguments':{'path':'result.txt','content':model}}]}
    return {'content':'Relatório ' + first, 'calls':[]}

if __name__ == '__main__':
    prompt = sys.stdin.read()
    data = json.loads(prompt[prompt.index('\\n{"conversation"') + 1:])
    if any(m.get('content') == 'hang' for m in data['conversation']):
        time.sleep(30)
    argv = sys.argv
    model = argv[argv.index('--model')+1]
    value = answer(data['conversation'], model)
    if '--output-last-message' in argv:
        path = argv[argv.index('--output-last-message')+1]
        with open(path,'w') as file: json.dump(value,file)
        print(json.dumps({'type':'turn.started'}))
        print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':5}}))
    else:
        print(json.dumps({'type':'result','subtype':'success','structured_output':value,
                         'usage':{'input_tokens':10,'output_tokens':5}}))
'''


class BackendFlowTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.engine = self.root / 'engine'
        self.engine.write_text('#!' + os.sys.executable + '\n' + ENGINE)
        self.engine.chmod(0o700)
        scope = {}
        exec(ENGINE, scope)
        self.answer = scope['answer']

    def native(self, backend):
        with patch('centaur_cli.native_client.shutil.which', return_value=str(self.engine)):
            client = NativeClient(backend, 'main')
        client.model_catalog = lambda: {'main':'Principal','worker':'Filho','grand':'Neto'}
        return client

    def http(self, request, **kwargs):
        data = json.loads(request.data)
        value = self.answer(data['messages'], data['model'])
        message = {'role':'assistant','content':value['content']}
        if value['calls']:
            message['tool_calls'] = [{'id':str(i), 'type':'function', 'function':{
                'name':call['name'],'arguments':json.dumps(call['arguments'])}}
                for i, call in enumerate(value['calls'])]
        return io.BytesIO(json.dumps({'model':data['model'], 'choices':[{'message':message}]}).encode())

    def test_recursive_execution_and_reports_through_each_real_adapter(self):
        for backend in ('openrouter', 'codex', 'claude'):
            with self.subTest(backend=backend):
                root = self.root / backend
                root.mkdir()
                store = ChatStore(root)
                model = 'provider/main' if backend == 'openrouter' else 'main'
                chat = store.new(model, backend)
                chat['messages'] = [{'role':'user','content':'root'}]
                cancel = threading.Event()
                registry = SessionRegistry(root)
                group = AgentGroup(root, chat['id'], cancel, registry=registry)
                client = OpenRouter('secret') if backend == 'openrouter' else self.native(backend)
                client.model_efforts = {model: ['default', 'high'],
                    'provider/worker' if backend == 'openrouter' else 'worker': ['default', 'low']}
                client.supports_fast = lambda selected: selected == model
                if backend == 'claude': client.fast_version_checked = True
                chat.update(effort='high', speed='fast')
                tools = SubagentTools(ProjectTools(root, lambda _:True, approval_mode='never', cancel_event=cancel),
                    client, chat['id'], lambda _:None, group=group, registry=registry, background=True,
                    effort='high', speed='fast')
                import subprocess
                transports = []
                original = subprocess.Popen
                def start(argv, **options):
                    transports.append(argv)
                    return original(argv, **options)
                def http(request, **options):
                    transports.append(json.loads(request.data))
                    return self.http(request, **options)
                with patch('centaur_cli.openrouter.urlopen', side_effect=http), \
                        patch('centaur_cli.native_client.subprocess.Popen', side_effect=start):
                    run_turn(chat, client, tools, store, lambda:None)
                    deadline = time.monotonic()+8
                    while group.active and time.monotonic()<deadline: time.sleep(.01)
                    self.assertEqual(group.active, 0)
                    self.assertEqual(len(group.entries), 2)
                    run_turn(chat, client, tools, store, lambda:None)
                entries = list(group.entries.values())
                self.assertTrue(all(e['chat']['status']=='reported' for e in entries))
                child, grand = sorted(entries, key=lambda e:e['chat']['title'])
                self.assertEqual(child['chat']['parent_id'], chat['id'])
                self.assertEqual(grand['chat']['parent_id'], child['chat']['id'])
                self.assertTrue(all(e['chat']['backend']==backend for e in entries))
                self.assertEqual((root/'result.txt').read_text(), 'provider/grand' if backend=='openrouter' else 'grand')
                self.assertTrue(any(m.get('agent_source')==grand['chat']['id'] for m in child['chat']['messages']))
                self.assertEqual(len([m for m in chat['messages'] if m.get('agent_kind')=='report']),2)
                self.assertEqual(group.receive(chat['id']), [])
                self.assertTrue(all(registry.state(e['chat']['id'])=='stopped' for e in entries))
                self.assertEqual(chat['model'], model)
                for entry in entries:
                    self.assertEqual((entry['chat']['effort'], entry['chat']['speed']), ('default', 'standard'))
                    self.assertEqual(entry['chat']['approval_mode'], 'never')
                for request in transports:
                    if backend == 'openrouter':
                        if request['model'] == model:
                            self.assertEqual(request['reasoning']['effort'], 'high')
                            self.assertEqual(request['service_tier'], 'fast')
                        else:
                            self.assertNotIn('reasoning', request)
                            self.assertNotIn('service_tier', request)
                            self.assertNotEqual(request['session_id'], chat['id'])
                    elif request[request.index('--model') + 1] == 'main':
                        self.assertIn('model_reasoning_effort="high"' if backend == 'codex' else '--effort', request)
                    else:
                        self.assertNotIn('--effort', request)
                        self.assertFalse(any('model_reasoning_effort=' in flag for flag in request))

    def test_configured_chat_roundtrip_executes_with_selected_adapter_and_delegates(self):
        for backend in ('openrouter', 'codex', 'claude'):
            with self.subTest(backend=backend):
                root = self.root / backend
                root.mkdir()
                store = ChatStore(root)
                model = 'provider/main' if backend == 'openrouter' else 'main'
                original = OpenRouter('secret') if backend == 'openrouter' else self.native(backend)
                replacement = OpenRouter('secret') if backend == 'openrouter' else self.native(backend)
                selected = 'provider/worker' if backend == 'openrouter' else 'worker'
                if backend != 'openrouter': replacement.fixed_model = selected
                terminal = Terminal(root, model, store, original, approval_mode='never')
                first = terminal.chat
                first.update(messages=[{'role': 'user', 'content': 'root'}], title_attempted=True)
                old_worker = terminal.worker_context()
                with patch.object(terminal, 'request_context_catalog'):
                    terminal.activate_config(backend, selected, 'high', replacement, 'never', 'standard')
                terminal.create_chat_from_menu()
                terminal.switch_chat(first)
                self.assertIs(terminal.client, replacement)
                self.assertIs(old_worker.client, original)
                with patch('centaur_cli.openrouter.urlopen', side_effect=self.http):
                    terminal.start_work()
                    deadline = time.monotonic() + 8
                    while (terminal.busy or terminal.agent_group.active
                           or terminal.agent_group.receive(first['id']) or not terminal.events.empty()) \
                            and time.monotonic() < deadline:
                        terminal.drain_events()
                        time.sleep(.01)
                    terminal.drain_events()
                self.assertFalse(terminal.busy)
                self.assertEqual(terminal.agent_group.active, 0)
                self.assertNotIn('last_error', first)
                self.assertEqual((first['model'], terminal.model), (selected, selected))
                self.assertEqual(len(terminal.agent_group.entries), 2)
                self.assertTrue(all(entry['chat']['status'] == 'reported'
                                    for entry in terminal.agent_group.entries.values()))
                self.assertEqual((root / 'result.txt').read_text(),
                                 'provider/grand' if backend == 'openrouter' else 'grand')

    def test_background_inference_keeps_its_client_and_cancel_scope_across_chats(self):
        import subprocess
        for backend in ('openrouter', 'codex', 'claude'):
            with self.subTest(backend=backend):
                root = self.root / backend
                root.mkdir()
                original = OpenRouter('secret') if backend == 'openrouter' else self.native(backend)
                replacement = OpenRouter('secret') if backend == 'openrouter' else self.native(backend)
                model = 'provider/main' if backend == 'openrouter' else 'main'
                terminal = Terminal(root, model, ChatStore(root), original, approval_mode='never')
                first = terminal.chat
                first.update(messages=[{'role': 'user', 'content': 'hang'}], title_attempted=True)
                entered, release = threading.Event(), threading.Event()
                start_process = subprocess.Popen
                def start(*args, **options):
                    process = start_process(*args, **options)
                    entered.set()
                    return process
                def http(request, **options):
                    if any(message.get('content') == 'hang' for message in json.loads(request.data)['messages']):
                        entered.set()
                        release.wait(8)
                        return io.BytesIO(b'{"choices":[{"message":{"role":"assistant","content":"Late"}}]}')
                    return self.http(request, **options)
                with patch('centaur_cli.openrouter.urlopen', side_effect=http), \
                        patch('centaur_cli.native_client.subprocess.Popen', side_effect=start), \
                        patch.object(terminal, 'request_context_catalog'):
                    terminal.start_work()
                    try:
                        self.assertTrue(entered.wait(2))
                        terminal.create_chat_from_menu()
                        second = terminal.chat
                        second.update(messages=[{'role': 'user', 'content': 'root'}], title_attempted=True)
                        terminal.activate_config(backend, model, 'default', replacement, 'never', 'standard')
                        terminal.start_work()
                        deadline = time.monotonic() + 8
                        while (terminal.busy or terminal.agent_group.active
                               or terminal.agent_group.receive(second['id']) or not terminal.events.empty()) \
                                and time.monotonic() < deadline:
                            terminal.drain_events()
                            time.sleep(.01)
                        self.assertFalse(terminal.busy)
                        self.assertEqual(terminal.agent_group.active, 0)
                        self.assertTrue(terminal.session_states[first['id']]['busy'])
                        second_cancel = terminal.cancel_event
                        terminal.switch_chat(first)
                        self.assertIs(terminal.client, original)
                        terminal.cancel_work()
                        deadline = time.monotonic() + 3
                        while terminal.busy and time.monotonic() < deadline:
                            terminal.drain_events()
                            time.sleep(.01)
                        self.assertFalse(terminal.busy)
                        self.assertFalse(second_cancel.is_set())
                        terminal.switch_chat(second)
                        self.assertIs(terminal.client, replacement)
                        self.assertNotIn('last_error', second)
                        self.assertEqual(len(terminal.agent_group.entries), 2)
                    finally:
                        terminal.session_states[first['id']]['cancel_event'].set()
                        release.set()

    def test_compaction_through_each_real_adapter_is_tool_free(self):
        for backend in ('openrouter','codex','claude'):
            with self.subTest(backend=backend):
                client = OpenRouter('secret') if backend=='openrouter' else self.native(backend)
                model = 'provider/main' if backend=='openrouter' else 'main'
                chat = ChatStore(self.root).new(model, backend)
                chat['messages'] = [{'role':'user' if i%2==0 else 'assistant','content':'Historical data '*100} for i in range(16)]
                with patch('centaur_cli.openrouter.urlopen', side_effect=self.http):
                    state, before, after = compact_chat(chat, client, threading.Event())
                self.assertLess(after, before)
                self.assertEqual(state['through'],10)
                self.assertEqual(len(chat['messages']),16)

    def test_steering_between_actions_on_each_adapter_preserves_current_write(self):
        for backend in ('openrouter','codex','claude'):
            with self.subTest(backend=backend):
                root=self.root/backend; root.mkdir()
                store=ChatStore(root); model='provider/main' if backend=='openrouter' else 'main'
                chat=store.new(model,backend); chat['messages']=[{'role':'user','content':'steer'}]
                inbox=Inbox(root,chat['id']); cancel=threading.Event()
                group=AgentGroup(root,chat['id'],cancel,inbox=inbox)
                client=OpenRouter('secret') if backend=='openrouter' else self.native(backend)
                base=ProjectTools(root,lambda _:True,cancel_event=cancel)
                execute=base.execute
                def action(name,args):
                    value=execute(name,args)
                    inbox.put({'role':'user','content':'new direction'})
                    return value
                base.execute=action
                tools=SubagentTools(base,client,chat['id'],lambda _:None,group=group,background=True)
                with patch('centaur_cli.openrouter.urlopen',side_effect=self.http):
                    run_turn(chat,client,tools,store,lambda:None)
                self.assertEqual((root/'first.txt').read_text(),'first')
                self.assertFalse((root/'old.txt').exists())
                self.assertEqual(inbox.snapshot(),[])
                results=[m for m in chat['messages'] if m['role']=='tool']
                self.assertEqual(len(results),2)
                self.assertIn('Não executada',results[1]['content'])
                self.assertEqual([m['content'] for m in chat['messages'] if m['role']=='user'],['steer','new direction'])

    def test_running_child_cancels_and_releases_slot_on_each_backend(self):
        import subprocess
        for backend in ('openrouter','codex','claude'):
            with self.subTest(backend=backend):
                entered, release, cancel=(threading.Event() for _ in range(3))
                root=self.root/backend; root.mkdir()
                model='provider/main' if backend=='openrouter' else 'main'
                client=OpenRouter('secret') if backend=='openrouter' else self.native(backend)
                tools=SubagentTools(ProjectTools(root,lambda _:True,cancel_event=cancel),client,'a'*32,lambda _:None,background=True)
                processes=[]; original=subprocess.Popen
                def start(*args,**kwargs):
                    process=original(*args,**kwargs); processes.append(process); entered.set(); return process
                def http(request,**kwargs):
                    entered.set(); release.wait(3)
                    return io.BytesIO(b'{"choices":[{"message":{"role":"assistant","content":"Late"}}]}')
                with patch('centaur_cli.openrouter.urlopen',side_effect=http), patch('centaur_cli.native_client.subprocess.Popen',side_effect=start):
                    result=json.loads(tools.delegate({'title':'Hanging','task':'hang','model':'provider/worker' if backend=='openrouter' else 'worker'}))
                    self.assertTrue(entered.wait(2)); cancel.set()
                    deadline=time.monotonic()+3
                    while tools.group.active and time.monotonic()<deadline: time.sleep(.01)
                    release.set()
                    self.assertEqual(tools.group.active,0)
                child=tools.group.entries[result['id']]['chat']
                self.assertEqual(child['status'],'cancelled')
                self.assertTrue(all(p.poll() is not None for p in processes))

    def test_cancel_before_request_starts_no_transport_on_any_backend(self):
        for backend in ('openrouter','codex','claude'):
            with self.subTest(backend=backend):
                client = OpenRouter('secret') if backend=='openrouter' else self.native(backend)
                model = 'provider/main' if backend=='openrouter' else 'main'
                cancel = threading.Event(); cancel.set()
                with patch('centaur_cli.openrouter.urlopen') as http, patch('centaur_cli.native_client.subprocess.Popen') as process:
                    with self.assertRaises(TurnCancelled): client.complete(model, [], TOOLS, cancel_event=cancel)
                    http.assert_not_called(); process.assert_not_called()

    def test_openrouter_cancel_during_read_ignores_late_tool_response(self):
        entered, release, finished, cancel = (threading.Event() for _ in range(4))
        class Response(io.BytesIO):
            def read(inner, *args):
                entered.set(); release.wait(3)
                return super().read(*args)
            def close(inner):
                super().close(); finished.set()
        value = {'choices':[{'message':{'role':'assistant','content':'Late','tool_calls':[
            {'id':'late','type':'function','function':{'name':'write_file','arguments':'{"path":"late.txt","content":"wrong"}'}}]}}]}
        response = Response(json.dumps(value).encode())
        client = OpenRouter('secret'); errors=[]
        with patch('centaur_cli.openrouter.urlopen', return_value=response) as http:
            worker = threading.Thread(target=lambda:self.capture_error(errors, lambda:client.complete('provider/main', [], TOOLS, cancel_event=cancel)))
            worker.start(); self.assertTrue(entered.wait(2)); cancel.set(); worker.join(1)
            self.assertFalse(worker.is_alive()); self.assertIsInstance(errors[0],TurnCancelled)
            release.set(); self.assertTrue(finished.wait(2)); http.assert_called_once()
        self.assertFalse((self.root/'late.txt').exists())
        self.assertTrue(client.pending_requests.acquire(blocking=False)); client.pending_requests.release()

    def test_openrouter_transport_thread_failure_returns_capacity(self):
        client=OpenRouter('secret')
        for target in ('centaur_cli.openrouter.threading.Thread','centaur_cli.openrouter.threading.Thread.start'):
            with self.subTest(target=target), patch(target,side_effect=RuntimeError('thread unavailable')):
                with self.assertRaises(RuntimeError): client.request_json(None,30,threading.Event())
            acquired=[]
            while client.pending_requests.acquire(blocking=False): acquired.append(True)
            self.assertEqual(len(acquired),8)
            for _ in acquired: client.pending_requests.release()

    @staticmethod
    def capture_error(errors, callback):
        try: callback()
        except Exception as error: errors.append(error)

    def test_openrouter_invalid_second_call_prevents_first_write(self):
        valid = {'id':'1','type':'function','function':{'name':'write_file','arguments':'{"path":"bad.txt","content":"x"}'}}
        invalids = [
            {'id':'2','type':'function','function':{'name':'read_file','arguments':'{"path":4}'}},
            dict(valid),
            {'id':'2','type':'function','function':{'name':'undeclared','arguments':'{}'}},
            {'id':'2','type':'function','function':{'name':'read_file','arguments':'{"path":"x","unknown":null}'}},
            {'id':'2','type':'function','function':{'name':'read_file','arguments':'{"path":'}}]
        for invalid in invalids:
            message = {'role':'assistant','content':'Work','tool_calls':[valid,invalid]}
            value = {'choices':[{'message':message}]}
            response = io.BytesIO(json.dumps(value).encode())
            chat = ChatStore(self.root).new('provider/main'); chat['messages']=[{'role':'user','content':'Work'}]
            with patch('centaur_cli.openrouter.urlopen', return_value=response):
                with self.assertRaises(RuntimeError): run_turn(chat, OpenRouter('secret'), ProjectTools(self.root,lambda _:True), ChatStore(self.root),lambda:None)
            self.assertFalse((self.root/'bad.txt').exists())

    def test_openrouter_truncated_reply_is_not_accepted(self):
        for reason in ('length','content_filter','error'):
            with self.subTest(reason=reason):
                response = io.BytesIO(json.dumps({'choices':[{'finish_reason':reason,'message':{'role':'assistant','content':'Half answer'}}]}).encode())
                with patch('centaur_cli.openrouter.urlopen', return_value=response), self.assertRaisesRegex(RuntimeError,'não concluiu'):
                    OpenRouter('secret').complete('provider/main',[],[])

    def test_openrouter_reasoning_blocks_survive_protocol_replay_without_local_metadata(self):
        details=[{'type':'reasoning.encrypted','data':'opaque','signature':'signature'}]
        response=io.BytesIO(json.dumps({'choices':[{'message':{'role':'assistant','content':'Public','reasoning':'PRIVATE','reasoning_details':details}}]}).encode())
        client=OpenRouter('secret')
        with patch('centaur_cli.openrouter.urlopen',return_value=response): reply=client.complete('provider/main',[],[])
        self.assertNotIn('reasoning',reply)
        replay=provider_messages(self.root,'a'*32,client,'provider/main',[reply])[0]
        self.assertEqual(replay['reasoning_details'],details)

    def test_native_empty_completion_is_not_success(self):
        for backend in ('codex','claude'):
            for content in (None,'','  '):
                with self.subTest(backend=backend,content=content), self.assertRaisesRegex(ValueError,'vazia'):
                    self.native(backend).reply({'content':content,'calls':[]},[])

    def test_codex_cached_effort_mismatch_is_rejected_before_process(self):
        client=self.native('codex'); client.model_efforts={'main':['default','low','high']}
        with patch('centaur_cli.native_client.subprocess.Popen') as start:
            with self.assertRaisesRegex(ValueError,'effort'):
                client.complete('main',[],[],effort='max')
            start.assert_not_called()

    def test_native_unexpected_pipe_failure_cleans_process(self):
        for backend in ('codex','claude'):
            with self.subTest(backend=backend):
                client=self.native(backend)
                class Process:
                    def communicate(self,*a,**k): raise OSError('pipe failed')
                process=Process()
                with patch('centaur_cli.native_client.subprocess.Popen',return_value=process), patch.object(client,'stop_process') as stop:
                    with self.assertRaisesRegex(RuntimeError,'resposta local'):
                        client.complete('main',[],[])
                    stop.assert_called_once_with(process)

    def test_native_fast_completed_output_cannot_bypass_size_limit(self):
        for backend in ('codex','claude'):
            with self.subTest(backend=backend):
                client=self.native(backend)
                class Process:
                    returncode=0
                    def communicate(self,*a,**k): return 'x'*8_000_001,''
                with patch('centaur_cli.native_client.subprocess.Popen',return_value=Process()):
                    with self.assertRaisesRegex(RuntimeError,'excedeu'):
                        client.complete('main',[],[])

    def test_codex_unfinished_turn_cannot_use_partial_final_file(self):
        (self.root/'reply.json').write_text('{"content":"Partial","calls":[]}')
        for events in ([{'type':'turn.started'}], [{'type':'turn.completed'},{'type':'turn.started'}]):
            with self.assertRaisesRegex(ValueError,'não concluiu'):
                codex_output(self.root,'\n'.join(map(json.dumps,events)))

    def test_subagent_report_save_failure_always_releases_slot(self):
        for backend in ('openrouter','codex','claude'):
            with self.subTest(backend=backend):
                client = OpenRouter('secret') if backend=='openrouter' else self.native(backend)
                parent = ChatStore(self.root).new('provider/main' if backend=='openrouter' else 'main', backend)
                tools = SubagentTools(ProjectTools(self.root,lambda _:True),client,parent['id'],lambda _:None)
                child = ChatStore(self.root).new(parent['model'],backend)
                child.update(title='Child', parent_id=parent['id'], status='running')
                store=ChatStore(self.root); tools.group.reserve(child,store)
                with patch('centaur_cli.subagents.run_turn',side_effect=lambda chat,*a,**k:chat['messages'].append({'role':'assistant','content':'Report'})), patch.object(store,'save',side_effect=ValueError('redirected storage')):
                    result=json.loads(tools.run_child(child,store,'Child','Task','medium' if backend=='openrouter' else None,parent['model']))
                self.assertEqual(tools.group.active,0)
                self.assertEqual(result['status'],'failed')

    def test_failed_thread_and_failed_checkpoint_do_not_leak_slot(self):
        tools=SubagentTools(ProjectTools(self.root,lambda _:True),OpenRouter('secret'),'a'*32,lambda _:None,background=True)
        original=ChatStore.save; attempts=[]
        def save(store,chat):
            attempts.append(chat['status'])
            if chat['status']=='failed': raise ValueError('storage redirected')
            return original(store,chat)
        with patch('centaur_cli.subagents.threading.Thread.start',side_effect=RuntimeError('thread failed')), patch.object(ChatStore,'save',save):
            with self.assertRaises(ValueError): tools.delegate({'title':'T','task':'Contract'})
        self.assertEqual(attempts,['running','failed']); self.assertEqual(tools.group.active,0)

    def test_thread_construction_failure_always_releases_reservation(self):
        tools=SubagentTools(ProjectTools(self.root,lambda _:True),OpenRouter('secret'),'a'*32,lambda _:None,background=True)
        with patch('centaur_cli.subagents.threading.Thread',side_effect=RuntimeError('thread allocation failed')):
            with self.assertRaises(RuntimeError): tools.delegate({'title':'T','task':'Contract'})
        self.assertEqual(tools.group.active,0)

    def test_executor_wait_does_not_wait_for_itself(self):
        group=AgentGroup(self.root,'a'*32,threading.Event())
        child=ChatStore(self.root).new('provider/main'); child.update(parent_id='a'*32,status='running')
        group.reserve(child,ChatStore(self.root))
        started=time.monotonic(); group.wait(child['id'],1)
        self.assertLess(time.monotonic()-started,.2)

    def test_grandchild_question_changes_its_state_without_overwriting_parent(self):
        registry=SessionRegistry(self.root); states=[]
        original=registry.set
        def state(identifier,value):
            states.append((identifier,value)); return original(identifier,value)
        registry.set=state
        base=ProjectTools(self.root,lambda _:True,ask_user=lambda q,o:{'status':'answered','answer':'yes'})
        tools=SubagentTools(base,OpenRouter('secret'),'a'*32,lambda _:None,registry=registry)
        def execute(chat,client,child_tools,*args):
            if chat['title']=='Child':
                child_tools.delegate({'title':'Grand','task':'Question'})
            else:
                child_tools.base.ask_user('Which?',[])
            chat['messages'].append({'role':'assistant','content':'Report'})
        with patch('centaur_cli.subagents.run_turn',side_effect=execute):
            child_id=json.loads(tools.delegate({'title':'Child','task':'Task'}))['id']
        grand_id=next(identifier for identifier in tools.group.entries if identifier!=child_id)
        self.assertNotIn((child_id,'waiting_input'),states)
        self.assertIn((grand_id,'waiting_input'),states)

    def test_registry_failure_does_not_leave_running_executor(self):
        registry=SessionRegistry(self.root)
        tools=SubagentTools(ProjectTools(self.root,lambda _:True),OpenRouter('secret'),'a'*32,lambda _:None,registry=registry)
        with patch.object(registry,'set',side_effect=OSError('runtime unavailable')), patch('centaur_cli.subagents.run_turn',side_effect=lambda chat,*a,**k:chat['messages'].append({'role':'assistant','content':'Report'})):
            result=json.loads(tools.delegate({'title':'Child','task':'Task'}))
        self.assertEqual(tools.group.active,0)
        self.assertEqual(result['status'],'reported')


if __name__=='__main__': unittest.main()
