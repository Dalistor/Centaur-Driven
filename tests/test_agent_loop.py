"""Loop do agente: leituras em paralelo, poda de resultados antigos e texto transmitido."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

from centaur_cli.agent import run_turn
from centaur_cli.context import active_messages, estimate_tokens, prune_tool_results
from centaur_cli.history import ChatStore
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools


def call(name, identifier, **arguments):
    return {'id': identifier, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(arguments)}}


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ChatStore(self.root)
        self.chat = self.store.new('main')
        self.chat['messages'] = [{'role': 'user', 'content': 'Trabalhe'}]

    def client(self, *replies, **attributes):
        replies = list(replies)
        client = Mock(backend='openrouter', secrets=(), supports_cancellation=False, supports_streaming=False,
                      supports_progress=False, context_windows={}, **attributes)
        client.complete.side_effect = lambda *args, **options: replies.pop(0)
        return client

    def test_consecutive_reads_run_together_and_keep_the_order_of_the_batch(self):
        for name in 'abc':
            (self.root / f'{name}.txt').write_text(name)
        tools = ProjectTools(self.root, lambda _: True, approval_mode='never')
        lock, together, active, order = threading.Lock(), threading.Event(), [0], []
        original = tools.execute
        def execute(name, arguments):
            order.append(name)
            if name == 'read_file' and arguments['path'] != 'd.txt':
                with lock:
                    active[0] += 1
                    if active[0] == 3:
                        together.set()
                together.wait(3)  # Só é liberado quando as três leituras estão em andamento juntas.
                with lock:
                    active[0] -= 1
            else:
                self.assertEqual(active[0], 0)  # Gravação e leitura seguinte esperam o lote anterior.
            return original(name, arguments)
        tools.execute = execute
        batch = [call('read_file', 'r1', path='a.txt'), call('read_file', 'r2', path='b.txt'), call('read_file', 'r3', path='c.txt'),
                 call('write_file', 'w', path='d.txt', content='d'), call('read_file', 'r4', path='d.txt')]
        client = self.client({'role': 'assistant', 'content': 'Lendo', 'tool_calls': batch}, {'role': 'assistant', 'content': 'Pronto'})
        run_turn(self.chat, client, tools, self.store, lambda: None)
        self.assertTrue(together.is_set())
        results = [message for message in self.chat['messages'] if message['role'] == 'tool']
        self.assertEqual([message['tool_call_id'] for message in results], ['r1', 'r2', 'r3', 'w', 'r4'])
        self.assertEqual([message['content'] for message in results[:3]], ['1\ta', '1\tb', '1\tc'])
        self.assertEqual(order.index('write_file'), 3)

    def long_history(self, results=12, size=9000):
        messages = [{'role': 'user', 'content': 'Investigue'}]
        for index in range(results):
            messages.append({'role': 'assistant', 'content': None, 'tool_calls': [call('read_file', f'c{index}', path=f'{index}.txt')]})
            messages.append({'role': 'tool', 'tool_call_id': f'c{index}', 'content': f'resultado {index} ' + 'x' * size})
        return messages

    def test_old_bulky_results_leave_the_context_but_not_the_saved_history(self):
        self.chat['messages'] = self.long_history()
        client = Mock(backend='openrouter', context_windows={'main': 50000})
        original = json.dumps(self.chat['messages'])
        before = estimate_tokens(active_messages(self.chat))
        self.assertTrue(prune_tool_results(self.chat, client, active_messages(self.chat), []))
        view = active_messages(self.chat)
        self.assertEqual(json.dumps(self.chat['messages']), original)
        self.assertLess(estimate_tokens(view), before * .7)
        self.assertEqual(len(view), len(self.chat['messages']))
        self.assertTrue(view[2]['content'].startswith('resultado 0 '))
        self.assertIn('resultado antigo omitido', view[2]['content'])
        self.assertEqual(view[-1]['content'], self.chat['messages'][-1]['content'])
        self.assertEqual([message.get('tool_call_id') for message in view], [message.get('tool_call_id') for message in self.chat['messages']])
        # Sem novo volume, a fronteira não se move: o prefixo enviado continua igual para o cache.
        self.assertFalse(prune_tool_results(self.chat, client, active_messages(self.chat), []))

    def test_pruning_waits_for_pressure_and_a_known_window(self):
        self.chat['messages'] = self.long_history(results=3)
        self.assertFalse(prune_tool_results(self.chat, Mock(backend='openrouter', context_windows={'main': 200000}), active_messages(self.chat), []))
        self.chat['messages'] = self.long_history()
        self.assertFalse(prune_tool_results(self.chat, Mock(backend='openrouter', context_windows={}), active_messages(self.chat), []))
        self.assertNotIn('tool_pruning', self.chat)

    def test_turn_prunes_before_the_request_and_sends_the_reduced_view(self):
        self.chat['messages'] = self.long_history() + [{'role': 'user', 'content': 'Continue'}]
        client = self.client({'role': 'assistant', 'content': 'Feito'})
        client.context_windows = {'main': 60000}
        run_turn(self.chat, client, ProjectTools(self.root, lambda _: True), self.store, lambda: None)
        sent = client.complete.call_args.args[1]
        self.assertIn('resultado antigo omitido', sent[3]['content'])
        self.assertEqual(client.complete.call_count, 1)  # Poda não consome uma chamada de resumo.
        self.assertNotIn('compaction', self.chat)
        self.assertNotIn('omitido', self.store.list()[0]['messages'][2]['content'])

    def test_streamed_text_reaches_the_terminal_and_is_replaced_by_the_saved_reply(self):
        seen = []
        tools = ProjectTools(self.root, lambda _: True)
        tools.stream_text = seen.append
        client = self.client({'role': 'assistant', 'content': 'Olá'})
        client.supports_streaming = True
        def complete(model, messages, definitions, **options):
            options['on_delta']('Ol')
            return {'role': 'assistant', 'content': 'Olá'}
        client.complete.side_effect = complete
        run_turn(self.chat, client, tools, self.store, lambda: None)
        self.assertEqual(seen, ['Ol'])
        terminal = Terminal(self.root, 'main', self.store, None)
        terminal.busy = True
        terminal.events.put(('stream', 'Resposta parci'))
        terminal.drain_events()
        self.assertIn('Resposta parci', '\n'.join(terminal.lines(80)))
        terminal.events.put(('refresh', None))
        terminal.drain_events()
        self.assertNotIn('Resposta parci', '\n'.join(terminal.lines(80)))


if __name__ == '__main__':
    unittest.main()
