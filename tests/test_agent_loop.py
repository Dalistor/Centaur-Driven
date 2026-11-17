"""Loop do agente: leituras em paralelo, poda de resultados antigos e texto transmitido."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock

import os
from unittest.mock import patch

from centaur_cli.agent import run_turn, REREAD_NOTE
from centaur_cli.context import active_messages, estimate_tokens, prune_tool_results, record_spend, spend_label, working_window
from centaur_cli.openrouter import ModelReply
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

    def test_large_windows_are_capped_by_the_context_budget(self):
        client = Mock(backend='openrouter', context_windows={'main': 1_000_000, 'small': 32_000, })
        self.assertEqual(working_window(client, 'main'), 150_000)
        self.assertEqual(working_window(client, 'small'), 32_000)
        self.assertIsNone(working_window(client, 'unknown'))
        with patch.dict(os.environ, {'CENTAUR_CONTEXT_BUDGET': '300000'}):
            self.assertEqual(working_window(client, 'main'), 300_000)
        with patch.dict(os.environ, {'CENTAUR_CONTEXT_BUDGET': 'off'}):
            self.assertEqual(working_window(client, 'main'), 1_000_000)
        # ~100k tokens de resultados: longe de 60% de 1M, mas acima de 60% do orçamento.
        self.chat['messages'] = self.long_history(results=34, size=9000)
        self.assertTrue(prune_tool_results(self.chat, client, active_messages(self.chat), []))

    def test_identical_reread_is_replaced_while_the_first_result_is_in_context(self):
        (self.root / 'a.txt').write_text('linha\n' * 300)
        tools = ProjectTools(self.root, lambda _: True, approval_mode='never')
        client = self.client({'role': 'assistant', 'content': None, 'tool_calls': [call('read_file', 'r1', path='a.txt')]},
                             {'role': 'assistant', 'content': None, 'tool_calls': [call('read_file', 'r2', path='a.txt')]},
                             {'role': 'assistant', 'content': None, 'tool_calls': [call('write_file', 'w', path='a.txt', content='novo\n' * 300)]},
                             {'role': 'assistant', 'content': None, 'tool_calls': [call('read_file', 'r3', path='a.txt')]},
                             {'role': 'assistant', 'content': 'Feito'})
        run_turn(self.chat, client, tools, self.store, lambda: None)
        results = {message['tool_call_id']: message['content'] for message in self.chat['messages'] if message['role'] == 'tool'}
        self.assertIn('linha', results['r1'])
        self.assertEqual(results['r2'], REREAD_NOTE)
        self.assertIn('novo', results['r3'])  # O arquivo mudou: a leitura volta inteira.
        # Resultado podado deixa de estar visível: a releitura precisa trazer o conteúdo.
        self.chat['tool_pruning'] = {'through': len(self.chat['messages'])}
        client = self.client({'role': 'assistant', 'content': None, 'tool_calls': [call('read_file', 'r4', path='a.txt')]},
                             {'role': 'assistant', 'content': 'Feito'})
        self.chat['messages'].append({'role': 'user', 'content': 'De novo'})
        run_turn(self.chat, client, tools, self.store, lambda: None)
        self.assertIn('novo', self.chat['messages'][-2]['content'])

    def test_spend_accumulates_provider_counts_per_chat(self):
        record_spend(self.chat, ModelReply({}, 'main', {'prompt_tokens': 1000, 'completion_tokens': 50, 'cost': 0.01,
                                                         'prompt_tokens_details': {'cached_tokens': 800}}))
        record_spend(self.chat, ModelReply({}, 'main', {'prompt_tokens': 3000, 'completion_tokens': 150, 'cached_tokens': 2200}))
        record_spend(self.chat, ModelReply({}, 'main', {}))
        self.assertEqual(self.chat['spend'], {'requests': 2, 'input': 4000, 'cached': 3000, 'output': 200, 'cost': 0.01})
        label = spend_label(self.chat['spend'], [{'requests': 1, 'input': 1000, 'cached': 0, 'output': 10, 'cost': 0}, None])
        self.assertEqual(label, 'Este chat: 3 chamadas · entrada 5k (60% do cache) · saída 210 · US$ 0.01 · inclui 1 subagente(s)')
        self.assertEqual(spend_label(None), '')

    def test_budget_compaction_that_stalls_is_deferred_instead_of_blocking_the_turn(self):
        from centaur_cli.context import CompactionPaused
        from centaur_cli import agent
        # Texto do modelo (não podável) acima de 80% do orçamento, longe do limite real de 1M.
        self.chat['messages'] = [{'role': 'user', 'content': 'Trabalhe'}] + [
            {'role': 'assistant', 'content': 'y' * 9000} for _ in range(45)] + [{'role': 'user', 'content': 'Continue'}]
        tools = ProjectTools(self.root, lambda _: True, approval_mode='never')
        client = self.client({'role': 'assistant', 'content': 'Feito'})
        client.context_windows = {'main': 1_000_000}
        notes = []
        with patch.object(agent, 'compact_chat', side_effect=CompactionPaused('lento')) as compact:
            run_turn(self.chat, client, tools, self.store, lambda: None, progress=notes.append)
            self.assertEqual(compact.call_args.kwargs['time_budget'], agent.SOFT_COMPACT_SECONDS)
            self.assertEqual(self.chat['messages'][-1]['content'], 'Feito')
            self.assertTrue(any('Compactação adiada' in note for note in notes))
            # Sem crescimento relevante, o próximo turno não tenta de novo.
            self.chat['messages'].append({'role': 'user', 'content': 'Mais'})
            client.complete.side_effect = lambda *args, **options: {'role': 'assistant', 'content': 'Ok'}
            run_turn(self.chat, client, tools, self.store, lambda: None)
            self.assertEqual(compact.call_count, 1)
        # Perto do limite real do modelo a compactação continua obrigatória.
        client = self.client({'role': 'assistant', 'content': 'Feito'})
        client.context_windows = {'main': 150_000}
        self.chat.pop('compaction_retry_at', None)
        self.chat['messages'].append({'role': 'user', 'content': 'Outra'})
        with patch.object(agent, 'compact_chat', side_effect=CompactionPaused('lento')):
            with self.assertRaises(CompactionPaused):
                run_turn(self.chat, client, tools, self.store, lambda: None)

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
