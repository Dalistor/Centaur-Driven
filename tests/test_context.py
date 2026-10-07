import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from centaur_cli.agent import project_prompt, run_turn
from centaur_cli.context import active_messages, compact_chat, context_label, estimate_tokens, record_context, auto_compaction_needed, save_compaction_progress, save_compaction, CompactionPaused
from centaur_cli.history import ChatStore
from centaur_cli.interaction import TurnCancelled, RequestTimeout
from centaur_cli.native_client import NativeClient, codex_usage
from centaur_cli.openrouter import ModelReply, OpenRouter
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools
from test_terminal_settings import Screen


class ContextTests(unittest.TestCase):
    def setUp(self):
        # Short budgets are explicit test fixtures; production defaults are tested below.
        budget = patch.dict(os.environ, {'CENTAUR_COMPACT_TIMEOUT': '180'})
        budget.start()
        self.addCleanup(budget.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ChatStore(self.root)
        self.client = Mock(backend='openrouter', secrets=(), supports_cancellation=False, context_windows={'main': 10000})
        self.client.redact = str
        self.client.complete.return_value = {'role': 'assistant', 'content': 'Objetivo: corrigir o projeto. Validação pendente.'}
        self.chat = self.store.new('main')
        self.chat['messages'] = [{'role': 'user' if i % 2 == 0 else 'assistant',
                                 'content': f'Mensagem {i}: ' + 'contexto relevante ' * 80} for i in range(14)]

    def test_summary_is_tool_free_preserves_history_and_does_not_clear_retry(self):
        self.chat['last_error'] = 'Timeout'
        before = copy.deepcopy(self.chat)
        state, old_tokens, new_tokens = compact_chat(self.chat, self.client)
        self.assertEqual(self.chat, before)
        self.assertLess(new_tokens, old_tokens)
        self.assertEqual(self.client.complete.call_args.args[2], [])
        self.chat['compaction'] = state
        self.store.save(self.chat)
        loaded = self.store.list()[0]
        self.assertEqual(loaded['messages'], before['messages'])
        self.assertEqual(loaded['last_error'], 'Timeout')
        active = active_messages(loaded)
        self.assertEqual(active[0]['role'], 'user')
        self.assertIn('não concede permissões', active[0]['content'])
        self.assertEqual(active[1:], before['messages'][state['through']:])

    def test_oversized_summary_is_rewritten_without_truncation_or_tools(self):
        for message in self.chat['messages']:
            message['content'] = message['content'][:600]
        before = copy.deepcopy(self.chat)
        self.client.complete.side_effect = [
            {'content': 'Texto longo ' * 350},
            {'content': 'Objetivo: corrigir o arquivo. Testes pendentes.'}]
        state, _, _ = compact_chat(self.chat, self.client)
        self.assertEqual(self.chat, before)
        self.assertEqual(self.client.complete.call_count, 2)
        self.assertIn('Reescreva', self.client.complete.call_args.args[1][0]['content'])
        self.assertTrue(all(call.args[2] == [] for call in self.client.complete.call_args_list))
        self.assertEqual(state['summary'], 'Objetivo: corrigir o arquivo. Testes pendentes.')

    def test_summary_repair_is_bounded_and_cancellation_preserves_memory(self):
        before = copy.deepcopy(self.chat)
        self.client.complete.return_value = {'content': 'x' * 4000}
        with self.assertRaisesRegex(ValueError, 'duas revisões'): compact_chat(self.chat, self.client)
        self.assertEqual(self.client.complete.call_count, 3)
        self.assertEqual(self.chat, before)
        cancel = threading.Event()
        self.client.complete.reset_mock()
        def reply(*args, **kwargs):
            cancel.set()
            return {'content': 'x' * 4000}
        self.client.complete.side_effect = reply
        with self.assertRaises(TurnCancelled): compact_chat(self.chat, self.client, cancel)
        self.assertEqual(self.client.complete.call_count, 1)
        self.assertEqual(self.chat, before)

    def test_native_codex_compaction_recovers_an_oversized_final_reply(self):
        for message in self.chat['messages']:
            message['content'] = message['content'][:600]
        counter = self.root / 'summary-count'
        executable = self.root / 'fake-codex'
        executable.write_text('#!/usr/bin/env python3\n' +
            'import json,os,sys\nfrom pathlib import Path\n' +
            f'counter=Path({str(counter)!r})\n' +
            'count=int(counter.read_text()) if counter.exists() else 0\n' +
            'counter.write_text(str(count+1))\n' +
            'schema=json.loads(Path(sys.argv[sys.argv.index("--output-schema")+1]).read_text())\n' +
            'assert schema["properties"]["calls"]["maxItems"]==0\n' +
            'assert "OPENROUTER_API_KEY" not in os.environ\n' +
            'sys.stdin.read()\n' +
            'value={"content":"x"*4000 if count==0 else "Objetivo preservado; validar testes.","calls":[]}\n' +
            'Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps(value))\n' +
            'print(json.dumps({"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":20}}))\n')
        executable.chmod(0o700)
        with patch('centaur_cli.native_client.shutil.which', return_value=str(executable)):
            client = NativeClient('codex', 'main')
        client.context_windows = {'main': 10000}
        original = copy.deepcopy(self.chat)
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'must-not-reach-native'}):
            state, _, _ = compact_chat(self.chat, client)
        self.assertEqual(counter.read_text(), '2')
        self.assertEqual(state['summary'], 'Objetivo preservado; validar testes.')
        self.assertEqual(self.chat, original)

    def test_auto_compaction_precedes_main_request_and_preserves_history(self):
        original = copy.deepcopy(self.chat['messages'])
        self.client.complete.side_effect = lambda model, messages, tools, **options: ModelReply(
            {'role': 'assistant', 'content': 'Memória: objetivo e testes pendentes.' if not tools else 'Resposta final'})
        notices = []
        run_turn(self.chat, self.client, ProjectTools(self.root, lambda _: True), self.store, lambda: None, progress=notices.append)
        calls = self.client.complete.call_args_list
        self.assertFalse(calls[0].args[2])
        self.assertTrue(calls[-1].args[2])
        self.assertIn('Resumo de mensagens anteriores', calls[-1].args[1][1]['content'])
        self.assertEqual(self.chat['messages'][:-1], original)
        self.assertEqual(self.store.list()[0]['compaction'], self.chat['compaction'])
        self.assertIn('automaticamente', notices[0])

    def test_auto_compaction_does_not_invent_limits_or_loop_on_recent_messages(self):
        payload = [{'role': 'user', 'content': 'x' * 30000}]
        self.assertTrue(auto_compaction_needed(self.chat, self.client, payload, []))
        with patch.dict(os.environ, {'CENTAUR_AUTOCOMPACT': '0'}):
            self.assertFalse(auto_compaction_needed(self.chat, self.client, payload, []))
        self.client.context_windows = {}
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(auto_compaction_needed(self.chat, self.client, payload, []))
        self.client.context_windows = {'main': 10000}
        self.chat['messages'] = self.chat['messages'][-6:]
        self.assertFalse(auto_compaction_needed(self.chat, self.client, payload, []))

    def test_auto_failure_keeps_memory_and_does_not_run_main_request(self):
        original = copy.deepcopy(self.chat)
        self.client.complete.side_effect = RuntimeError('falha de resumo')
        with self.assertRaisesRegex(RuntimeError, 'automática falhou'):
            run_turn(self.chat, self.client, ProjectTools(self.root, lambda _: True), self.store, lambda: None)
        self.assertEqual(self.chat, original)
        self.assertTrue(all(call.args[2] == [] for call in self.client.complete.call_args_list))

    def test_boundary_never_splits_assistant_tool_batch_and_keeps_pending_calls(self):
        call = lambda ident: {'id': ident, 'function': {'name': 'report_progress', 'arguments': '{"message":"ok"}'}}
        self.chat['messages'][7] = {'role': 'assistant', 'tool_calls': [call('a'), call('b')]}
        self.chat['messages'][8] = {'role': 'tool', 'tool_call_id': 'a', 'content': 'ok'}
        self.chat['messages'][9] = {'role': 'tool', 'tool_call_id': 'b', 'content': 'ok'}
        state, _, _ = compact_chat(self.chat, self.client)
        self.assertEqual(state['through'], 7)
        self.chat['messages'][3] = {'role': 'assistant', 'tool_calls': [call('pending')]}
        state, _, _ = compact_chat(self.chat, self.client)
        self.assertEqual(state['through'], 3)

    def test_repeat_compaction_includes_previous_memory_and_only_new_prefix(self):
        state, _, _ = compact_chat(self.chat, self.client)
        self.chat['compaction'] = state
        self.chat['messages'].extend(copy.deepcopy(self.chat['messages'][-6:]))
        self.client.complete.reset_mock()
        next_state, _, _ = compact_chat(self.chat, self.client)
        sent = self.client.complete.call_args.args[1][1]['content']
        self.assertIn(state['summary'], sent)
        self.assertNotIn('Mensagem 0:', sent)
        self.assertGreater(next_state['through'], state['through'])

    def test_short_invalid_non_reducing_and_failed_summaries_preserve_existing_memory(self):
        self.chat['compaction'] = {'through': 2, 'summary': 'Memória anterior'}
        before = copy.deepcopy(self.chat)
        for reply in ({'content': ''}, {'content': 'x' * 10000},
                      {'content': 'ok', 'tool_calls': [{'id': 'unsafe'}]}):
            self.client.complete.return_value = reply
            with self.assertRaises(ValueError): compact_chat(self.chat, self.client)
            self.assertEqual(self.chat, before)
        self.client.complete.side_effect = RuntimeError('backend indisponível')
        with self.assertRaises(RuntimeError): compact_chat(self.chat, self.client)
        self.assertEqual(self.chat, before)
        self.chat['messages'] = self.chat['messages'][:5]
        with self.assertRaisesRegex(ValueError, 'Conversa curta'): compact_chat(self.chat, self.client)
        self.chat['messages'] = [{'role': 'user', 'content': 'a'}] * 9
        self.chat.pop('compaction')
        self.client.complete.side_effect = None
        self.client.complete.return_value = {'content': 'Resumo longo ' * 15}
        with self.assertRaisesRegex(ValueError, 'não reduziu'): compact_chat(self.chat, self.client)

    def test_cancel_before_call_and_after_reply_leaves_memory_unchanged(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(TurnCancelled): compact_chat(self.chat, self.client, cancel)
        self.client.complete.assert_not_called()
        cancel.clear()
        before = copy.deepcopy(self.chat)
        def answer(*args, **kwargs):
            cancel.set()
            return {'content': 'Resumo válido'}
        self.client.complete.side_effect = answer
        with self.assertRaises(TurnCancelled): compact_chat(self.chat, self.client, cancel)
        self.assertEqual(self.chat, before)

    def test_large_context_is_summarized_in_chunks_without_base64_or_tools(self):
        self.chat['messages'][0]['reasoning'] = 'PRIVATE_REASONING'
        self.chat['messages'][0]['content'] = [
            {'type': 'text', 'text': 'Requisito ' * 7000},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,SECRET_IMAGE_BYTES'}}]
        state, _, _ = compact_chat(self.chat, self.client)
        self.assertGreater(self.client.complete.call_count, 2)
        for call in self.client.complete.call_args_list:
            sent = call.args[1][1]['content']
            self.assertNotIn('SECRET_IMAGE_BYTES', sent)
            self.assertNotIn('PRIVATE_REASONING', sent)
            self.assertLess(len(sent), 13000)
            self.assertEqual(call.args[2], [])
        self.assertTrue(state['summary'])

    def test_compaction_progress_reaches_each_fragment_and_uses_advertised_low_effort(self):
        self.chat['effort'] = 'xhigh'
        self.client.model_efforts = {'main': ['default', 'low', 'xhigh']}
        notices = []
        original = copy.deepcopy(self.chat)
        state, _, _ = compact_chat(self.chat, self.client, progress=notices.append)
        count = self.client.complete.call_count
        self.assertEqual(len(notices), count)
        self.assertIn(f'fragmento {count}/{count}', notices[-1])
        self.assertTrue(all(call.kwargs['effort'] == 'low' for call in self.client.complete.call_args_list))
        self.assertEqual(self.chat, original)
        self.assertTrue(state['summary'])

    def test_large_known_window_avoids_excess_small_summary_requests(self):
        self.client.context_windows = {'main': 200000}
        self.chat['messages'] = [{'role': 'user' if index % 2 == 0 else 'assistant',
                                 'content': f'Parte {index}: ' + 'contexto ' * 2000} for index in range(24)]
        original = copy.deepcopy(self.chat['messages'])
        compact_chat(self.chat, self.client)
        self.assertLessEqual(self.client.complete.call_count, 7)
        self.assertTrue(all(len(json.loads(call.args[1][1]['content'])['fragmento']) <= 48000
                            for call in self.client.complete.call_args_list))
        self.assertEqual(self.chat['messages'], original)
        self.assertTrue(all(call.args[2] == [] for call in self.client.complete.call_args_list))

    def test_resume_uses_summary_and_keeps_results_without_reexecuting_actions(self):
        self.chat['messages'][-2:] = [
            {'role': 'assistant', 'tool_calls': [{'id': 'done', 'function': {
                'name': 'run_command', 'arguments': '{"command":"touch duplicate"}'}}]},
            {'role': 'tool', 'tool_call_id': 'done', 'content': 'Código de saída: 0\n'}]
        state, _, _ = compact_chat(self.chat, self.client)
        self.chat['compaction'] = state
        before = copy.deepcopy(self.chat['messages'])
        self.client.complete.return_value = ModelReply({'role': 'assistant', 'content': 'Continuando'}, 'main',
                                                      {'prompt_tokens': 1200, 'completion_tokens': 20})
        run_turn(self.chat, self.client, ProjectTools(self.root, lambda _: True), self.store, lambda: None)
        sent = self.client.complete.call_args.args[1]
        self.assertEqual(sent[1:], active_messages({**self.chat, 'messages': before}))
        self.assertFalse((self.root / 'duplicate').exists())
        self.assertEqual(self.chat['messages'][:-1], before)
        self.assertEqual(self.chat['context_usage']['used'], 1220)
        self.assertTrue(self.chat['context_usage']['provider_count'])

    def test_timeout_stops_large_compaction_and_resume_skips_saved_fragments(self):
        self.client.context_windows = {'main': 200000}
        self.client.supports_request_timeout = True
        self.chat['messages'][0]['content'] = 'histórico importante ' * 55000
        original = copy.deepcopy(self.chat['messages'])
        elapsed = [0]
        def reply(*args, **kwargs):
            elapsed[0] += 90
            return {'content': 'Objetivos, decisões e validações preservados.'}
        self.client.complete.side_effect = reply
        checkpoint = lambda pending: save_compaction_progress(self.chat, self.store, pending)
        with patch('centaur_cli.context.time.monotonic', side_effect=lambda: elapsed[0]):
            with self.assertRaisesRegex(RuntimeError, 'limite de 180s'):
                compact_chat(self.chat, self.client, checkpoint=checkpoint)
        self.assertEqual(self.client.complete.call_count, 2)
        pending = self.store.list()[0]['compaction_pending']
        self.assertEqual(pending['offset'], 96000)
        self.assertNotIn('compaction', self.chat)
        self.assertEqual(active_messages(self.chat), original)
        self.chat = self.store.list()[0]  # Survives restarting the terminal.
        self.client.complete.reset_mock()
        self.client.complete.side_effect = None
        notices = []
        state, _, _ = compact_chat(self.chat, self.client, progress=notices.append,
            checkpoint=lambda pending: save_compaction_progress(self.chat, self.store, pending))
        self.assertIn('fragmento 3/', notices[0])
        self.assertEqual(json.loads(self.client.complete.call_args_list[0].args[1][1]['content'])['resumo_anterior'],
                         pending['summary'])
        save_compaction(self.chat, self.store, state)
        self.assertNotIn('compaction_pending', self.store.list()[0])
        self.assertEqual(self.chat['messages'], original)

    def test_failed_fragment_resumes_after_checkpoint_and_new_messages(self):
        original = copy.deepcopy(self.chat['messages'])
        self.client.complete.side_effect = [{'content': 'Memória validada.'}, RuntimeError('provedor indisponível')]
        with self.assertRaisesRegex(RuntimeError, 'fragmento 2/'):
            compact_chat(self.chat, self.client,
                checkpoint=lambda pending: save_compaction_progress(self.chat, self.store, pending))
        pending = copy.deepcopy(self.chat['compaction_pending'])
        self.chat['messages'].append({'role': 'user', 'content': 'Novo requisito; não descartar.'})
        self.client.complete.reset_mock()
        self.client.complete.side_effect = None
        state, _, _ = compact_chat(self.chat, self.client)
        self.assertEqual(state['through'], pending['through'])
        self.assertNotIn('Mensagem 0:', self.client.complete.call_args.args[1][1]['content'])
        self.assertEqual(self.chat['messages'][:-1], original)
        self.assertIn('Novo requisito', active_messages({**self.chat, 'compaction': state})[-1]['content'])

    def test_changed_history_or_model_invalidates_saved_summary(self):
        self.client.complete.side_effect = [{'content': 'Memória validada.'}, RuntimeError('offline')]
        with self.assertRaises(RuntimeError):
            compact_chat(self.chat, self.client,
                checkpoint=lambda pending: save_compaction_progress(self.chat, self.store, pending))
        pending = copy.deepcopy(self.chat['compaction_pending'])
        for change in ('history', 'model'):
            chat = copy.deepcopy(self.chat)
            chat['compaction_pending'] = pending
            if change == 'history': chat['messages'][0]['content'] = 'Requisito corrigido.'
            else: chat['model'] = 'other'
            self.client.complete.reset_mock()
            self.client.complete.side_effect = None
            notices = []
            compact_chat(chat, self.client, progress=notices.append)
            self.assertIn('fragmento 1/', notices[0])
            first = json.loads(self.client.complete.call_args_list[0].args[1][1]['content'])
            self.assertEqual(first['resumo_anterior'], '')
            self.assertIn(chat['messages'][0]['content'][:30], first['fragmento'])

    def test_checkpoint_write_failure_and_cancel_never_apply_partial_memory(self):
        original = copy.deepcopy(self.chat)
        pending = {'summary': 'rascunho'}
        with patch.object(self.store, 'save', side_effect=OSError('disco cheio')):
            with self.assertRaises(OSError): save_compaction_progress(self.chat, self.store, pending)
        self.assertEqual(self.chat, original)
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(TurnCancelled): save_compaction_progress(self.chat, self.store, pending, cancel)
        self.assertEqual(self.chat, original)

    def test_summary_repair_shares_deadline_and_requests_use_remaining_budget(self):
        self.client.supports_request_timeout = True
        elapsed = [0]
        def reply(*args, **kwargs):
            elapsed[0] += 80
            return {'content': 'x' * 4000}
        self.client.complete.side_effect = reply
        with patch('centaur_cli.context.time.monotonic', side_effect=lambda: elapsed[0]):
            with self.assertRaises(ValueError): compact_chat(self.chat, self.client)
        self.assertEqual([call.kwargs['request_timeout'] for call in self.client.complete.call_args_list], [180, 100, 20])
        self.assertNotIn('compaction', self.chat)

    def test_invalid_timeout_does_not_call_provider_or_change_history(self):
        original = copy.deepcopy(self.chat)
        for value in ('0', '29', '3601', 'forever'):
            with patch.dict(os.environ, {'CENTAUR_COMPACT_TIMEOUT': value}):
                with self.assertRaisesRegex(ValueError, 'CENTAUR_COMPACT_TIMEOUT'):
                    compact_chat(self.chat, self.client)
        self.client.complete.assert_not_called()
        self.assertEqual(self.chat, original)

    def test_slow_first_fragment_shrinks_and_finishes_without_losing_material(self):
        original = copy.deepcopy(self.chat)
        sent = []
        def reply(model, messages, tools, **options):
            data = json.loads(messages[1]['content'])
            sent.append(data['fragmento'])
            if len(sent) == 1: raise RequestTimeout('Codex demorou')
            return {'content': 'Requisitos e pendências preservados.'}
        self.client.complete.side_effect = reply
        notices = []
        state, _, _ = compact_chat(self.chat, self.client, progress=notices.append)
        self.assertEqual(len(sent[1]), len(sent[0]) // 2)
        self.assertTrue(any('reduzindo' in notice for notice in notices))
        source = json.dumps([{key: value for key, value in message.items()
            if key in ('role', 'content', 'tool_calls', 'tool_call_id')}
            for message in self.chat['messages'][:state['through']]], ensure_ascii=False)
        self.assertEqual(''.join(sent[1:]), source)
        self.assertEqual(self.chat, original)

    def test_repeated_native_timeouts_save_smaller_first_fragment_for_restart(self):
        elapsed = [0]
        def timeout(*args, **options):
            elapsed[0] += 90
            raise RequestTimeout('Codex demorou')
        self.client.complete.side_effect = timeout
        self.client.supports_request_timeout = True
        with patch('centaur_cli.context.time.monotonic', side_effect=lambda: elapsed[0]):
            with self.assertRaisesRegex(RuntimeError, 'limite de 180s'):
                compact_chat(self.chat, self.client,
                    checkpoint=lambda pending: save_compaction_progress(self.chat, self.store, pending))
        pending = self.store.list()[0]['compaction_pending']
        self.assertEqual(pending['offset'], 0)
        self.assertEqual(pending['chunk_size'], 3000)
        self.assertEqual(pending['summary'], '')
        self.assertEqual(self.client.complete.call_count, 2)
        self.client.complete.reset_mock()
        self.client.complete.side_effect = None
        compact_chat(self.store.list()[0], self.client)
        self.assertEqual(len(json.loads(self.client.complete.call_args_list[0].args[1][1]['content'])['fragmento']), 3000)

    def test_auto_failure_saves_progress_without_running_main_request(self):
        original = copy.deepcopy(self.chat['messages'])
        self.client.complete.side_effect = [{'content': 'Objetivos e validações.'}, RuntimeError('offline')]
        with self.assertRaisesRegex(RuntimeError, 'automática falhou'):
            run_turn(self.chat, self.client, ProjectTools(self.root, lambda _: True), self.store, lambda: None)
        self.assertGreater(self.store.list()[0]['compaction_pending']['offset'], 0)
        self.assertNotIn('compaction', self.chat)
        self.assertEqual(self.chat['messages'], original)
        self.assertTrue(all(call.args[2] == [] for call in self.client.complete.call_args_list))

    def test_non_reducing_final_summary_is_not_cached_as_completed_work(self):
        self.chat['messages'] = [{'role': 'user', 'content': 'a'}] * 9
        self.client.complete.return_value = {'content': 'Resumo longo ' * 15}
        original = copy.deepcopy(self.chat)
        with self.assertRaisesRegex(ValueError, 'não reduziu'):
            compact_chat(self.chat, self.client,
                checkpoint=lambda pending: save_compaction_progress(self.chat, self.store, pending))
        self.assertEqual(self.chat, original)
        self.assertEqual(self.store.list(), [])

    def test_budget_returns_safe_prefix_instead_of_failing_completed_work(self):
        self.client.context_windows = {'main': 200000}
        self.chat['messages'] = [{'role': 'user' if i % 2 == 0 else 'assistant',
            'content': f'Parte {i}: ' + 'contexto ' * 2000} for i in range(24)]
        original = copy.deepcopy(self.chat['messages'])
        elapsed = [0]
        def reply(*args, **options):
            elapsed[0] += 90
            return {'content': 'Objetivos, decisões e pendências.'}
        self.client.complete.side_effect = reply
        with patch('centaur_cli.context.time.monotonic', side_effect=lambda: elapsed[0]):
            state, before, after = compact_chat(self.chat, self.client,
                checkpoint=lambda pending: save_compaction_progress(self.chat, self.store, pending))
        self.assertEqual(self.client.complete.call_count, 2)
        self.assertTrue(state['partial'])
        self.assertGreater(state['through'], 0)
        self.assertLess(state['through'], len(original) - 6)
        self.assertLess(after, before)
        self.assertEqual(active_messages({**self.chat, 'compaction': state})[1:], original[state['through']:])
        save_compaction(self.chat, self.store, state)
        self.assertEqual(self.chat['messages'], original)
        self.assertNotIn('compaction_pending', self.chat)
        self.client.complete.reset_mock()
        self.client.complete.side_effect = None
        compact_chat(self.chat, self.client)
        self.assertNotIn('Parte 0:', self.client.complete.call_args_list[0].args[1][1]['content'])

    def test_partial_summary_keeps_whole_tool_batch_even_when_results_span_chunks(self):
        self.client.context_windows = {'main': 200000}
        self.chat['messages'] = [{'role': 'user', 'content': 'Objetivo: ' + 'x' * 18000},
            {'role': 'assistant', 'content': 'Consultar arquivos', 'tool_calls': [
                {'id': 'a', 'function': {'name': 'read_file', 'arguments': '{"path":"a"}'}},
                {'id': 'b', 'function': {'name': 'read_file', 'arguments': '{"path":"b"}'}}]},
            {'role': 'tool', 'tool_call_id': 'a', 'content': 'y' * 60000},
            {'role': 'tool', 'tool_call_id': 'b', 'content': 'z' * 60000},
            *copy.deepcopy(self.chat['messages'][-6:])]
        elapsed = [0]
        def reply(*args, **options):
            elapsed[0] += 180
            return {'content': 'Objetivo preservado; consultas registradas, confira resultados.'}
        self.client.complete.side_effect = reply
        with patch('centaur_cli.context.time.monotonic', side_effect=lambda: elapsed[0]):
            state, _, _ = compact_chat(self.chat, self.client)
        self.assertEqual(state['through'], 1)
        active = active_messages({**self.chat, 'compaction': state})
        self.assertEqual(active[1]['role'], 'assistant')
        self.assertEqual([entry['tool_call_id'] for entry in active[2:4]], ['a', 'b'])

    def test_auto_stops_when_sufficient_space_is_recovered_and_continues_turn(self):
        self.client.context_windows = {'main': 140000}
        self.chat['messages'] = [{'role': 'user' if i % 2 == 0 else 'assistant',
            'content': f'Mensagem {i}: ' + 'x' * 9000} for i in range(40)]
        original = copy.deepcopy(self.chat['messages'])
        self.client.complete.side_effect = lambda model, messages, tools, **options: ModelReply(
            {'role': 'assistant', 'content': 'Memória preservada.' if not tools else 'Continuando o pedido.'})
        run_turn(self.chat, self.client, ProjectTools(self.root, lambda _: True), self.store, lambda: None)
        self.assertTrue(self.chat['compaction']['partial'])
        self.assertLess(self.chat['compaction']['through'], len(original) - 6)
        self.assertEqual(self.chat['messages'][:-1], original)
        self.assertTrue(self.client.complete.call_args.args[2])
        self.assertLess(self.client.complete.call_count, 8)  # Full old prefix takes seven calls, plus the main turn.

    def test_pause_is_not_wrapped_as_auto_failure_and_terminal_can_retry_it(self):
        before = copy.deepcopy(self.chat)
        with patch('centaur_cli.agent.compact_chat', side_effect=CompactionPaused('Compactação pausada; use $compact.')):
            with self.assertRaises(CompactionPaused):
                run_turn(self.chat, self.client, ProjectTools(self.root, lambda _: True), self.store, lambda: None)
        self.assertEqual(self.chat, before)
        terminal = Terminal(self.root, 'main', self.store, self.client)
        terminal.chat = self.chat
        terminal.busy = True
        with patch('centaur_cli.terminal.run_turn', side_effect=CompactionPaused('Compactação pausada; use $compact.')):
            terminal.work(self.chat)
        terminal.drain_events()
        self.assertFalse(terminal.busy)
        self.assertIn('turn_paused', self.store.list()[0])
        self.assertNotIn('last_error', self.chat)
        self.assertNotIn('! Erro', '\n'.join(terminal.lines(80)))
        self.assertIn('Turno pausado', '\n'.join(terminal.lines(80)))
        terminal.draft = '/retry'
        with patch('centaur_cli.terminal.threading.Thread') as thread:
            terminal.submit()
        thread.return_value.start.assert_called_once()
        self.assertNotIn('turn_paused', self.chat)

    def test_legacy_budget_error_is_shown_as_previous_pause_without_losing_retry(self):
        terminal = Terminal(self.root, 'main', self.store, self.client)
        terminal.chat['last_error'] = ('Compactação automática falhou; histórico preservado. '
            'Compactação atingiu o limite de 180s. Use $compact.')
        terminal.busy = True
        terminal.notice = 'Compactando contexto · fragmento 19/26'
        output = '\n'.join(terminal.lines(80))
        self.assertIn('Compactação anterior pausada', output)
        self.assertNotIn('! Erro', output)
        self.assertIn('last_error', terminal.chat)

    def test_partial_compaction_with_insufficient_space_pauses_before_main_request(self):
        original = copy.deepcopy(self.chat['messages'])
        state = {'through': 1, 'summary': 'Memória validada.', 'partial': True}
        with patch('centaur_cli.agent.compact_chat', return_value=(state, 20000, 19000)):
            with self.assertRaises(CompactionPaused):
                run_turn(self.chat, self.client, ProjectTools(self.root, lambda _: True), self.store, lambda: None)
        self.assertEqual(self.store.list()[0]['compaction'], state)
        self.assertEqual(self.chat['messages'], original)
        self.client.complete.assert_not_called()

    def test_safe_prefix_boundary_accounts_for_secret_redaction(self):
        self.client.context_windows = {'main': 200000}
        self.client.redact = lambda value: value.replace('long-secret-value', '[OCULTO]')
        self.chat['messages'] = [{'role': 'user', 'content': 'long-secret-value ' * 4000},
            {'role': 'assistant', 'content': 'x' * 100000},
            *copy.deepcopy(self.chat['messages'][-6:])]
        elapsed = [0]
        def reply(*args, **options):
            elapsed[0] += 180
            return {'content': 'Objetivo e requisitos preservados.'}
        self.client.complete.side_effect = reply
        with patch('centaur_cli.context.time.monotonic', side_effect=lambda: elapsed[0]):
            state, _, _ = compact_chat(self.chat, self.client)
        self.assertEqual(state['through'], 1)
        self.assertNotIn('long-secret-value', self.client.complete.call_args.args[1][1]['content'])
        self.assertEqual(active_messages({**self.chat, 'compaction': state})[1], self.chat['messages'][1])

    def test_saved_progress_can_already_satisfy_auto_target_without_another_request(self):
        self.client.context_windows = {'main': 200000}
        self.chat['messages'] = [{'role': 'user' if i % 2 == 0 else 'assistant',
            'content': 'x' * 16000} for i in range(24)]
        self.client.complete.side_effect = [{'content': 'Memória preservada.'}, RuntimeError('offline')]
        with self.assertRaises(RuntimeError):
            compact_chat(self.chat, self.client,
                checkpoint=lambda pending: save_compaction_progress(self.chat, self.store, pending))
        self.client.complete.reset_mock()
        target = estimate_tokens(active_messages(self.chat)) - 5000
        state, before, after = compact_chat(self.chat, self.client, target_tokens=target)
        self.assertTrue(state['partial'])
        self.assertLess(after, before)
        self.client.complete.assert_not_called()

    def test_paused_turn_does_not_leave_terminal_busy_when_disk_save_fails(self):
        terminal = Terminal(self.root, 'main', self.store, self.client)
        terminal.busy = True
        with patch('centaur_cli.terminal.run_turn', side_effect=CompactionPaused('Compactação pausada.')), \
                patch.object(self.store, 'save', side_effect=OSError('disco cheio')):
            terminal.work(terminal.chat)
        terminal.drain_events()
        self.assertFalse(terminal.busy)
        self.assertIn('Não foi possível salvar a pausa', terminal.notice)

    def test_bar_uses_current_usage_and_marks_estimates_and_unknown_limits(self):
        record_context(self.chat, self.client, active_messages(self.chat), [],
                       ModelReply({}, 'main', {'prompt_tokens': 2500, 'completion_tokens': 500}))
        label, style = context_label(self.chat, self.client, 80)
        self.assertIn('~70% livre', label)
        self.assertEqual(style, 'green')
        self.chat['messages'].append({'role': 'tool', 'content': 'x' * 27000})
        self.assertIn('~0%', context_label(self.chat, self.client, 80)[0])
        self.assertEqual(context_label(self.chat, self.client, 80)[1], 'warning')
        self.client.context_windows = {}
        self.assertIn('limite desconhecido', context_label(self.chat, self.client, 80)[0])
        self.assertNotIn('%', context_label(self.chat, self.client, 80)[0])
        with patch.dict(os.environ, {'CENTAUR_CONTEXT_WINDOW': '20000'}):
            self.assertIn('%', context_label(self.chat, self.client, 80)[0])
        with patch.dict(os.environ, {'CENTAUR_CONTEXT_WINDOW': 'invalid'}):
            self.assertNotIn('%', context_label(self.chat, self.client, 80)[0])

    def test_terminal_command_commits_only_valid_uncancelled_saved_metadata(self):
        terminal = Terminal(self.root, 'main', self.store, self.client)
        terminal.chat = self.chat
        terminal.draft = '$compact'
        terminal.completion.update('$comp')
        self.assertEqual(terminal.completion.options, ['compact'])
        before = copy.deepcopy(self.chat)
        with patch('centaur_cli.terminal.threading.Thread') as thread:
            terminal.submit()
            self.assertTrue(terminal.busy)
            thread.assert_called_once()
        terminal.compact(self.chat, self.client, terminal.cancel_event)
        terminal.drain_events()
        self.assertFalse(terminal.busy)
        self.assertEqual(self.chat['messages'], before['messages'])
        self.assertIn('compaction', self.store.list()[0])
        state_before = copy.deepcopy(self.chat['compaction'])
        terminal.events.put(('compacted', (self.chat, terminal.cancel_event, {'summary': 'new', 'through': 4}, 100, 50)))
        terminal.cancel_event.set()
        terminal.drain_events()
        self.assertEqual(self.chat['compaction'], state_before)
        terminal.cancel_event.clear()
        terminal.events.put(('compacted', (self.chat, terminal.cancel_event, {'summary': 'new', 'through': 4}, 100, 50)))
        with patch.object(self.store, 'save', side_effect=OSError('disk full')): terminal.drain_events()
        self.assertEqual(self.chat['compaction'], state_before)
        self.assertIn('Erro ao salvar', terminal.notice)

    def test_footer_does_not_overlap_context_and_credit_on_resize(self):
        terminal = Terminal(self.root, 'main', self.store, self.client)
        terminal.chat = self.chat
        for size in ((24, 80), (12, 40), (34, 120)):
            screen = Screen(size)
            terminal.draw(screen)
            entries = [(col, text) for row, col, text, _ in screen.output if row == size[0] - 2]
            context, credits = entries
            self.assertIn('Ctx', context[1]) if size[1] < 80 else self.assertTrue(context[1].startswith(('Ctx', 'Contexto')))
            self.assertLessEqual(context[0] + len(context[1]), credits[0])
            self.assertEqual(credits[0] + len(credits[1]), size[1] - 3)
        self.assertIn('$compact é um comando local', project_prompt(self.root))

    def test_openrouter_carries_usage_and_catalog_window_outside_api_message(self):
        client = OpenRouter('secret')
        catalog = {'data': [{'id': 'main', 'context_length': 10000, 'supported_parameters': ['tools']}]}
        with patch('centaur_cli.openrouter.urlopen', return_value=io.BytesIO(json.dumps(catalog).encode())):
            client.model_catalog()
        self.assertEqual(client.context_windows['main'], 10000)
        payload = {'choices': [{'message': {'role': 'assistant', 'content': 'Resposta'}}], 'model': 'main',
                   'usage': {'prompt_tokens': 100, 'completion_tokens': 20}}
        with patch('centaur_cli.openrouter.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
            reply = client.complete('main', [], [])
        self.assertEqual(reply.usage, payload['usage'])
        self.assertNotIn('usage', reply)


class NativeContextTests(unittest.TestCase):
    def client(self):
        with patch('centaur_cli.native_client.shutil.which', return_value='/fake/codex'):
            return NativeClient('codex', 'main')

    def test_timeout_default_override_validation_and_process_cleanup(self):
        with patch.dict(os.environ, {}, clear=True): self.assertEqual(self.client().timeout, 1800)
        with patch.dict(os.environ, {'CENTAUR_NATIVE_TIMEOUT': '900'}): client = self.client()
        self.assertEqual(client.timeout, 900)
        for value in ('no', '0', '29', '3601'):
            with patch.dict(os.environ, {'CENTAUR_NATIVE_TIMEOUT': value}):
                with self.assertRaisesRegex(ValueError, '30 a 3600'): self.client()
        process = Mock(pid=999)
        process.communicate.side_effect = [subprocess.TimeoutExpired('codex', 900), ('', '')]
        with patch('centaur_cli.native_client.subprocess.Popen', return_value=process), \
                patch('centaur_cli.native_client.os.killpg') as kill:
            with self.assertRaisesRegex(RuntimeError, '900 segundos'): client.complete('main', [], [])
        self.assertEqual(process.communicate.call_args_list[0].kwargs['timeout'], 900)
        kill.assert_called_once()

    def test_codex_cache_limits_and_public_usage_exclude_private_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, 'models_cache.json').write_text(json.dumps({'models': [
                {'slug': 'main', 'visibility': 'list', 'context_window': 200000,
                 'supported_reasoning_levels': [{'effort': 'low'}, {'effort': 'high'}]},
                {'slug': 'max', 'visibility': 'list', 'context_window': None, 'max_context_window': 400000}]}))
            with patch.dict(os.environ, {'CODEX_HOME': temporary}):
                client = self.client()
                client.model_catalog()
            self.assertEqual(client.context_windows, {'main': 200000, 'max': 400000})
            self.assertEqual(client.model_efforts['main'], ['default', 'low', 'high'])
            self.assertEqual(client.model_efforts['max'], ['default'])
        output = '\n'.join(map(json.dumps, [{'type': 'item.completed', 'item': {'type': 'reasoning', 'text': 'private'}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 100, 'cached_input_tokens': 80, 'output_tokens': 30}}]))
        self.assertEqual(codex_usage(output), {'prompt_tokens': 100, 'completion_tokens': 30})
        self.assertEqual(codex_usage('invalid\n{"type":"turn.completed","usage":null}'), {'prompt_tokens': None, 'completion_tokens': None})

    def test_summary_timeout_kills_real_native_process_without_changing_chat_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary, 'slow-codex')
            executable.write_text('#!/usr/bin/env python3\nimport sys,time\nsys.stdin.read()\ntime.sleep(30)\n')
            executable.chmod(0o700)
            with patch('centaur_cli.native_client.shutil.which', return_value=str(executable)):
                client = NativeClient('codex', 'main')
            original_timeout = client.timeout
            with self.assertRaisesRegex(RuntimeError, 'requisição de resumo'):
                client.complete('main', [], [], request_timeout=0.1, cancel_event=threading.Event())
            self.assertEqual(client.timeout, original_timeout)
            for value in (0, -1, True, '90', float('nan')):
                with self.assertRaises(ValueError): client.complete('main', [], [], request_timeout=value)

    def test_openrouter_summary_timeout_does_not_extend_normal_network_timeout(self):
        client = OpenRouter('fake-key')
        payload = {'choices': [{'message': {'content': 'Memória'}}]}
        with patch('centaur_cli.openrouter.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())) as request:
            client.complete('main', [], [], request_timeout=12.5)
        self.assertEqual(request.call_args.kwargs['timeout'], 12.5)
        with patch('centaur_cli.openrouter.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())) as request:
            client.complete('main', [], [])
        self.assertEqual(request.call_args.kwargs['timeout'], 1800)
