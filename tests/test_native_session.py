"""Sessão persistente do Claude com ferramentas via MCP, exercitada com um CLI de fixture."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from datetime import date

from centaur_cli import models, native_session
from centaur_cli.agent import run_turn
from centaur_cli.history import ChatStore
from centaur_cli.interaction import TurnCancelled
from centaur_cli.native_client import NativeClient
from centaur_cli.tools import ProjectTools

# Fala o mesmo protocolo do CLI real: stream-json em stdin/stdout e cliente MCP do servidor configurado.
FAKE_CLI = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, time
arguments = sys.argv[1:]
if '--mcp-config' not in arguments:
    sys.exit(9)
server = json.loads(arguments[arguments.index('--mcp-config') + 1])['mcpServers']['centaur']
log = open(os.environ['FAKE_LOG'], 'a')
bridge = subprocess.Popen([server['command'], *server['args']], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
counter = [0]
def rpc(method, params):
    counter[0] += 1
    bridge.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': counter[0], 'method': method, 'params': params}) + '\n')
    bridge.stdin.flush()
    return json.loads(bridge.stdout.readline())['result']
rpc('initialize', {'protocolVersion': '2025-06-18'})
names = [tool['name'] for tool in rpc('tools/list', {})['tools']]
def emit(value):
    sys.stdout.write(json.dumps(value) + '\n'); sys.stdout.flush()
def assistant(blocks):
    emit({'type': 'assistant', 'message': {'content': blocks, 'usage': {'input_tokens': 5, 'cache_read_input_tokens': 100 * received, 'cache_creation_input_tokens': 0}}})
def call(name, arguments):
    assistant([{'type': 'tool_use', 'id': 'toolu', 'name': 'mcp__centaur__' + name, 'input': arguments}])
    return rpc('tools/call', {'name': name, 'arguments': arguments})['content'][0]['text']
def final(text):
    emit({'type': 'stream_event', 'event': {'type': 'message_start'}})
    emit({'type': 'stream_event', 'event': {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': text[:4]}}})
    assistant([{'type': 'text', 'text': text}])
    emit({'type': 'result', 'subtype': 'success', 'is_error': False, 'result': text, 'usage': {'input_tokens': 5, 'output_tokens': 7},
          'modelUsage': {'claude-fixture-9': {'contextWindow': 123000, 'maxOutputTokens': 4000}}})
emit({'type': 'system', 'subtype': 'init', 'tools': names, 'model': 'claude-fixture-9'})
received = 0
for line in sys.stdin:
    received += 1
    text = json.loads(line)['message']['content'][0]['text']
    log.write(json.dumps({'pid': os.getpid(), 'text': text, 'system': open(arguments[arguments.index('--system-prompt-file') + 1]).read()[:40]}) + '\n'); log.flush()
    if text.startswith('morra'):
        sys.exit(3)
    if text.startswith('espere'):
        time.sleep(60)
    if 'leia' in text:
        assistant([{'type': 'text', 'text': 'Vou ler e registrar.'}])
        content = call('read_file', {'path': 'a.txt'})
        written = call('write_file', {'path': 'b.txt', 'content': 'copiado'})
        final(f'{received}|{content}|{written}')
    elif 'inválida' in text:
        final(f'{received}|' + call('read_file', {'path': 5}))
    else:
        final(f'{received}|eco:{text[:30]}')
'''


class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.addCleanup(native_session.close_all)
        self.root = Path(temporary.name, 'project')
        self.root.mkdir()
        (self.root / 'a.txt').write_text('alfa')
        cli = Path(temporary.name, 'claude')
        cli.write_text(FAKE_CLI.replace('#!/usr/bin/env python3', '#!' + sys.executable))
        cli.chmod(0o700)
        self.log = Path(temporary.name, 'log.jsonl')
        self.log.touch()
        environment = patch.dict(os.environ, {'FAKE_LOG': str(self.log), 'XDG_CONFIG_HOME': str(Path(temporary.name, 'config'))})
        environment.start()
        self.addCleanup(environment.stop)
        with patch('centaur_cli.native_client.shutil.which', return_value=str(cli)):
            self.client = NativeClient('claude', 'fixture')
        self.client.session_mode = True
        self.store = ChatStore(self.root)
        self.chat = self.store.new('fixture', backend='claude')
        self.approvals = []
        self.tools = ProjectTools(self.root, lambda action: self.approvals.append(action) or True)

    def received(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def turn(self, text, tools=None):
        self.chat['messages'].append({'role': 'user', 'content': text})
        run_turn(self.chat, self.client, tools or self.tools, self.store, lambda: None)
        return self.chat['messages'][-1]['content']

    def test_tools_run_in_centaur_and_the_native_conversation_persists_between_turns(self):
        seen = []
        self.tools.stream_text = seen.append
        self.assertEqual(self.turn('leia o arquivo'), '1|1\talfa|Arquivo gravado. 1 linhas em b.txt.')
        self.assertEqual((self.root / 'b.txt').read_text(), 'copiado')
        self.assertEqual(len(self.approvals), 1)  # A permissão continua sendo do Centaur.
        roles = [(message['role'], bool(message.get('tool_calls'))) for message in self.chat['messages']]
        self.assertEqual(roles, [('user', False), ('assistant', True), ('tool', False), ('assistant', True), ('tool', False), ('assistant', False)])
        self.assertEqual(self.chat['messages'][1]['content'], 'Vou ler e registrar.')
        self.assertEqual(seen, ['1|1\t'])
        self.assertEqual(self.turn('e agora?'), '2|eco:e agora?')
        log = self.received()
        self.assertEqual([entry['text'] for entry in log], ['leia o arquivo', 'e agora?'])  # Só o que mudou é enviado.
        self.assertEqual(len({entry['pid'] for entry in log}), 1)
        self.assertTrue(log[0]['system'].startswith('Você é Centaur'))
        self.assertEqual(self.chat['context_usage']['provider_count'], True)
        # O CLI disse qual modelo atendeu o alias e sua janela: o chat e o seletor passam a saber.
        self.assertEqual(self.chat['models_used'][-1], 'claude-fixture-9')
        self.assertEqual((self.client.context_windows['fixture'], self.client.context_windows['claude-fixture-9']), (123000, 123000))
        self.assertEqual(models.load_learned('claude')['fixture'], {'id': 'claude-fixture-9', 'context': 123000, 'output': 4000, 'seen': date.today().isoformat()})

    def test_diverged_history_restarts_the_session_with_the_saved_conversation(self):
        self.turn('primeira')
        self.chat['messages'][:] = [{'role': 'user', 'content': 'Resumo de mensagens anteriores: algo'}]
        self.assertEqual(self.turn('continue')[:6], '1|eco:')
        log = self.received()
        self.assertEqual(len({entry['pid'] for entry in log}), 2)
        self.assertIn('histórico anterior', log[1]['text'])
        self.assertIn('Resumo de mensagens anteriores', log[1]['text'])
        self.assertIn('continue', log[1]['text'])
        self.assertEqual(len(native_session.SESSIONS), 1)

    def test_invalid_call_is_answered_to_the_model_without_executing_anything(self):
        reply = self.turn('chamada inválida')
        self.assertIn('Chamada inválida', reply)
        self.assertIn('Nenhuma ferramenta', reply)
        self.assertEqual([message['role'] for message in self.chat['messages']], ['user', 'assistant'])

    def test_cancelling_kills_the_session_and_the_next_turn_starts_clean(self):
        cancel = threading.Event()
        tools = ProjectTools(self.root, lambda _: True, cancel_event=cancel)
        threading.Timer(.5, cancel.set).start()
        started = time.monotonic()
        with self.assertRaises(TurnCancelled):
            self.turn('espere', tools)
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(native_session.SESSIONS, [])
        self.assertEqual(self.turn('de novo')[:2], '1|')
        self.assertIn('espere', self.received()[-1]['text'])  # A sessão nova recebe o histórico salvo.

    def test_cli_that_dies_before_answering_falls_back_to_one_call_per_step(self):
        # A fixture recusa (código 9) a invocação sem MCP: é o caminho de uma chamada por etapa.
        for expected_mode in (True, False):
            with self.assertRaisesRegex(RuntimeError, 'claude encerrou com código'):
                self.client.complete('fixture', [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'morra'}], self.tools.definitions)
            self.assertEqual(self.client.session_mode, expected_mode)
        self.assertEqual(len(self.received()), 2)
        self.assertEqual(native_session.SESSIONS, [])

    def test_session_is_only_enabled_when_the_installed_cli_advertises_the_flags(self):
        base = '--model --safe-mode --tools --json-schema --strict-mcp-config --no-session-persistence '
        for text, expected in ((base, False), (base + ' '.join(native_session.REQUIRED_FLAGS), True)):
            with patch('centaur_cli.native_client.subprocess.run', return_value=unittest.mock.Mock(returncode=0, stdout=text)):
                self.client.check_available()
            self.assertEqual(self.client.session_mode, expected)
        with patch('centaur_cli.native_client.subprocess.run', return_value=unittest.mock.Mock(returncode=0, stdout=base + ' '.join(native_session.REQUIRED_FLAGS))), \
                patch.dict(os.environ, {'CENTAUR_NATIVE_SESSION': '0'}):
            self.client.check_available()
        self.assertFalse(self.client.session_mode)


if __name__ == '__main__':
    unittest.main()
