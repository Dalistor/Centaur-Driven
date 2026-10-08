"""Opt-in real CLI against local Responses SSE; no account or paid inference."""
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from centaur_cli.native_client import BRIDGE_INSTRUCTIONS, NativeClient
from centaur_cli.tools import TOOLS


class CodexProtocolTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('CENTAUR_TEST_CODEX_BINARY'), 'Set CENTAUR_TEST_CODEX_BINARY for the offline real-CLI integration')
    def test_real_cli_uses_bridge_base_instructions_and_returns_typed_calls_without_execution(self):
        captured = []
        text = json.dumps({'content': 'Vou consultar o arquivo.', 'calls': [
            {'name': 'read_file', 'arguments': {'path': 'README.md'}}]})
        item = {'id': 'msg_fixture', 'type': 'message', 'status': 'completed', 'role': 'assistant',
                'content': [{'type': 'output_text', 'text': text, 'annotations': []}]}
        response = {'id': 'resp_fixture', 'object': 'response', 'created_at': 0, 'status': 'completed',
                    'output': [item], 'usage': {'input_tokens': 10, 'output_tokens': 10, 'total_tokens': 20,
                    'input_tokens_details': {'cached_tokens': 0}, 'output_tokens_details': {'reasoning_tokens': 0}}}
        events = [
            {'type': 'response.created', 'response': {**response, 'status': 'in_progress', 'output': []}},
            {'type': 'response.output_item.added', 'output_index': 0,
             'item': {**item, 'status': 'in_progress', 'content': []}},
            {'type': 'response.output_text.delta', 'item_id': item['id'], 'output_index': 0, 'content_index': 0, 'delta': text},
            {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
            {'type': 'response.completed', 'response': response},
        ]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"models":[]}')
            def do_POST(self):
                captured.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                body = ''.join('event: ' + event['type'] + '\ndata: ' + json.dumps(event) + '\n\n'
                               for event in events).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'isolated-cli-home').mkdir()
            binary = str(Path(os.environ['CENTAUR_TEST_CODEX_BINARY']).resolve())
            # CODEX_HOME is the CLI's intended scoped config setting, never a
            # shell workspace variable. The child has no account/auth history.
            environment = {'CODEX_HOME': str(root / 'isolated-cli-home'), 'NO_PROXY': '127.0.0.1,localhost',
                           'OPENAI_API_KEY': '', 'CODEX_API_KEY': '', 'CODEX_ACCESS_TOKEN': ''}
            with patch.dict(os.environ, environment), patch('centaur_cli.native_client.shutil.which', return_value=binary):
                client = NativeClient('codex', 'fixture')
                client.timeout = 10
                arguments = client.arguments
                def local_arguments(*args, **kwargs):
                    argv = arguments(*args, **kwargs)
                    provider = ('model_providers.centaur_fixture={name="fixture",base_url="http://127.0.0.1:'
                                + str(server.server_port) + '/v1",wire_api="responses",requires_openai_auth=false,'
                                'supports_websockets=false,request_max_retries=0,stream_max_retries=0}')
                    return [*argv[:-1], '--config', 'model_provider="centaur_fixture"', '--config', provider, argv[-1]]
                with patch.object(client, 'arguments', side_effect=local_arguments), \
                        patch('centaur_cli.tools.ProjectTools.execute', side_effect=AssertionError('Native inference cannot execute Centaur tools')):
                    reply = client.complete('fixture', [{'role': 'user', 'content': 'Consulte README.md'}],
                                            [tool for tool in TOOLS if tool['function']['name'] == 'read_file'])
            self.assertEqual(len(captured), 1)
            self.assertEqual(captured[0]['instructions'], BRIDGE_INSTRUCTIONS.strip())
            self.assertEqual(reply['content'], 'Vou consultar o arquivo.')
            self.assertEqual(reply['tool_calls'][0]['function']['name'], 'read_file')
            self.assertEqual(json.loads(reply['tool_calls'][0]['function']['arguments']), {'path': 'README.md'})
            self.assertEqual(reply.usage, {'prompt_tokens': 10, 'completion_tokens': 10})


if __name__ == '__main__':
    unittest.main()
