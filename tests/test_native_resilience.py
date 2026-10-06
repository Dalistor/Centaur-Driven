import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from centaur_cli.agent import run_turn
from centaur_cli.history import ChatStore
from centaur_cli.native_client import NativeClient, codex_output, decode_reply, process_failure, reply_schema
from centaur_cli.subagents import DELEGATE_TASK
from centaur_cli.terminal import Terminal
from centaur_cli.tools import TOOLS, ProjectTools
from test_terminal_settings import Screen


class NativeResilienceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        with patch('centaur_cli.native_client.shutil.which', return_value='/fake/codex'):
            self.client = NativeClient('codex', 'main')

    def test_typed_multiline_arguments_and_legacy_strings_are_equivalent(self):
        arguments = {'path': 'test.py', 'content': 'print("ação")\nvalue = "\\n"\n'}
        for args in (arguments, json.dumps(arguments)):
            reply = self.client.reply({'content': 'Writing', 'calls': [{'name': 'write_file', 'arguments': args}]}, TOOLS)
            self.assertEqual(json.loads(reply['tool_calls'][0]['function']['arguments']), arguments)
        schema = reply_schema(TOOLS)
        items = schema['properties']['calls']['items']['anyOf']
        write = next(item for item in items if item['properties']['name']['enum'] == ['write_file'])
        self.assertEqual(write['properties']['arguments']['type'], 'object')

    def test_optional_delegate_fields_use_null_in_schema_and_are_omitted_on_wire(self):
        schema = reply_schema([DELEGATE_TASK])
        parameters = schema['properties']['calls']['items']['anyOf'][0]['properties']['arguments']
        self.assertIn('model', parameters['required'])
        self.assertIn({'type': 'null'}, parameters['properties']['model']['anyOf'])
        value = {'content': None, 'calls': [{'name': 'delegate_task', 'arguments': {
            'title': 'task', 'task': 'contract', 'model': None, 'cost_tier': None}}]}
        reply = self.client.reply(value, [DELEGATE_TASK])
        self.assertEqual(json.loads(reply['tool_calls'][0]['function']['arguments']), {'title': 'task', 'task': 'contract'})

    def test_only_complete_fenced_json_is_normalized(self):
        text = json.dumps({'content': 'ação', 'calls': []})
        for value in (text, '\ufeff'+text, '```json\n'+text+'\n```', '```\n'+text+'\n```'):
            self.assertEqual(decode_reply(value)['content'], 'ação')
        for value in ('prefix '+text, text+' trailing', text[:-2]):
            with self.assertRaises(ValueError): decode_reply(value)

    def test_completed_event_fallback_ignores_reasoning_and_partial_events(self):
        value = {'content': 'Public answer', 'calls': []}
        events = [
            {'type': 'item.completed', 'item': {'type': 'reasoning', 'text': 'private'}},
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(value)}},
            {'type': 'turn.completed'}]
        output = '\n'.join(map(json.dumps, events))
        self.assertEqual(codex_output(self.root, output), value)
        for events in (events[:-1], [{'type': 'turn.failed'}], [{'type': 'turn.completed'}]):
            with self.assertRaises(ValueError): codex_output(self.root, '\n'.join(map(json.dumps, events)))

    def test_large_response_is_supported_and_oversized_response_is_explicit(self):
        value = {'content': 'x' * 2_100_000, 'calls': []}
        (self.root / 'reply.json').write_text(json.dumps(value))
        self.assertEqual(len(codex_output(self.root, '')['content']), 2_100_000)
        (self.root / 'reply.json').write_text('x' * 8_000_001)
        with self.assertRaisesRegex(ValueError, '8 MB'): codex_output(self.root, '')

    def test_invalid_batch_executes_no_tools_even_when_first_call_is_valid(self):
        value = {'content': 'Writing', 'calls': [
            {'name': 'write_file', 'arguments': {'path': 'must-not-exist', 'content': 'x'}},
            {'name': 'read_file', 'arguments': {'unexpected': 'path'}}]}
        chat = ChatStore(self.root).new('main')
        chat['messages'] = [{'role': 'user', 'content': 'work'}]
        with patch.object(self.client, 'complete', side_effect=lambda *a, **k: self.client.reply(value, TOOLS)):
            with self.assertRaises(ValueError):
                run_turn(chat, self.client, ProjectTools(self.root, lambda _: True), ChatStore(self.root), lambda: None)
        self.assertFalse((self.root / 'must-not-exist').exists())

    def test_native_error_diagnostics_do_not_echo_private_logs(self):
        for text, hint in [('schema invalid', 'schema'), ('usage limit reached', 'Limite de uso'),
                           ('context window exceeded', 'contexto'), ('unexpected argument', 'opção')]:
            message = process_failure('codex', 1, text + '\nprivate reasoning and account details')
            self.assertIn(hint, message)
            self.assertNotIn('private reasoning', message)

    def test_native_json_failure_reports_the_public_cause_without_private_logs(self):
        output = '\n'.join(map(json.dumps, [
            {'type': 'item.completed', 'item': {'type': 'reasoning', 'text': 'quota PRIVATE'}},
            {'type': 'turn.failed', 'error': {'message': 'context window exceeded ACCOUNT'}}]))
        message = process_failure('codex', 1, '', output)
        self.assertIn('$compact', message)
        self.assertNotIn('ACCOUNT', message)
        self.assertNotIn('PRIVATE', message)
        self.assertNotIn('Limite de uso', message)

    def test_retry_preserves_messages_and_previously_completed_actions(self):
        terminal = Terminal(self.root, 'main', ChatStore(self.root), self.client)
        terminal.chat['messages'] = [
            {'role': 'user', 'content': 'work'},
            {'role': 'assistant', 'tool_calls': [{'id': 'old', 'function': {
                'name': 'run_command', 'arguments': '{"command":"touch repeated"}'}}]},
            {'role': 'tool', 'tool_call_id': 'old', 'content': 'Código de saída: 0\n'}]
        terminal.chat['last_error'] = 'Malformed response'
        before = list(terminal.chat['messages'])
        terminal.draft = '/retry'
        with patch('centaur_cli.terminal.threading.Thread'):
            terminal.submit()
        self.assertEqual(terminal.chat['messages'], before)
        self.assertTrue(terminal.busy)
        with patch.object(self.client, 'complete', return_value={'role': 'assistant', 'content': 'Resumed'}):
            run_turn(terminal.chat, self.client, ProjectTools(self.root, lambda _: True), terminal.store, lambda: None)
        self.assertFalse((self.root / 'repeated').exists())

    def test_error_is_persisted_and_rendered_in_full_and_wide_preserves_draft(self):
        terminal = Terminal(self.root, 'main', ChatStore(self.root), self.client)
        terminal.chat['messages'] = [{'role': 'user', 'content': 'Question'}]
        terminal.chat['last_error'] = 'A long diagnostic ' * 40 + 'END OF DIAGNOSTIC'
        terminal.store.save(terminal.chat)
        self.assertEqual(terminal.store.list()[0]['last_error'], terminal.chat['last_error'])
        self.assertIn('END OF DIAGNOSTIC', '\n'.join(terminal.lines(90)))
        terminal.draft = '/wide'
        terminal.submit()
        self.assertTrue(terminal.wide_chat)
        terminal.draft = 'Draft preserved'
        screen = Screen((30, 180))
        terminal.draw(screen)
        self.assertEqual(terminal.draft, 'Draft preserved')
        self.assertTrue(any(column == 3 for row, column, text, style in screen.output if row == 2))
