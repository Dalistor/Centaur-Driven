"""Concurrent workers, interaction routing, live menu states and creation-time TTL."""
import curses
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import queue
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from centaur_cli.history import ChatStore
from centaur_cli.interaction import TurnCancelled
from centaur_cli.sessions import read_state, SessionRegistry
from centaur_cli.terminal import Terminal
from test_terminal_settings import Screen


class SessionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ChatStore(self.root)
        self.terminal = Terminal(self.root, 'model', self.store, None)
        self.now = datetime.now(timezone.utc)

    def old_chat(self, hours, store=None):
        store = store or self.store
        chat = store.new('model')
        chat['created'] = (self.now - timedelta(hours=hours)).isoformat()
        store.save(chat)
        return chat

    def wait(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            self.terminal.drain_events()
            time.sleep(.005)
        self.terminal.drain_events()
        self.assertTrue(predicate())

    def test_creation_time_immutable_across_saves_rename_and_title(self):
        chat = self.old_chat(65)
        created = chat['created']
        chat['created'] = self.now.isoformat()
        self.store.save(chat)
        self.assertEqual(chat['created'], created)
        self.store.generated_title(chat['id'], 'Gerado')
        self.store.rename(chat['id'], 'Manual')
        self.assertEqual(self.store.list()[0]['created'], created)
        self.assertEqual(self.store.prune(now=self.now), [chat['id']])

    def test_exact_64h_survives_older_is_deleted_with_private_files(self):
        fresh = self.old_chat(64)
        expired = self.old_chat(64.01)
        directory = self.root / '.centaur' / 'attachments' / expired['id']
        directory.mkdir(parents=True)
        (directory/'copy.txt').write_text('private')
        self.assertEqual(self.store.prune(now=self.now), [expired['id']])
        self.assertFalse(directory.exists())
        self.assertEqual(self.store.list()[0]['id'], fresh['id'])

    def test_legacy_creation_migrates_without_touching_updated(self):
        chat = self.old_chat(65)
        chat.pop('created')
        chat['updated'] = (self.now - timedelta(hours=66)).isoformat()
        self.store.path(chat['id']).write_text(json.dumps(chat))
        migrated = self.store.list()[0]
        self.assertEqual(migrated['created'], chat['updated'])
        self.assertEqual(migrated['updated'], chat['updated'])
        self.assertEqual(self.store.prune(now=self.now), [chat['id']])

    def test_running_and_waiting_protected_then_removed_when_stopped(self):
        registry = SessionRegistry(self.root)
        for state in ('running', 'waiting_input'):
            chat = self.old_chat(65)
            registry.set(chat['id'], state)
            self.assertEqual(read_state(self.root,chat['id']), state)
            self.assertEqual(self.store.prune(now=self.now), [])
            with self.assertRaises(ValueError): self.store.delete(chat['id'])
            registry.set(chat['id'], 'stopped')
            self.assertEqual(self.store.prune(now=self.now), [chat['id']])

    def test_protected_and_invalid_birth_dates_are_preserved(self):
        chat = self.old_chat(66)
        invalid = self.store.new('model')
        invalid['created'] = 'unknown'
        self.store.save(invalid)
        self.assertEqual(self.store.prune([chat['id']], now=self.now), [])
        self.assertEqual(len(self.store.list()), 2)

    def test_dead_stale_and_malformed_states_do_not_report_running(self):
        registry = SessionRegistry(self.root)
        chat = self.old_chat(65)
        registry.set(chat['id'], 'running')
        path = self.root / '.centaur' / 'runtime' / (chat['id']+'.json')
        record = json.loads(path.read_text())
        with patch('centaur_cli.sessions.os.kill', side_effect=ProcessLookupError):
            self.assertEqual(read_state(self.root, chat['id']), 'stopped')
        record['heartbeat'] = time.time() - 121
        path.write_text(json.dumps(record))
        self.assertEqual(read_state(self.root,chat['id']), 'stopped')
        for content in ('[]', '{', '{}', 'null'):
            path.write_text(content)
            self.assertEqual(read_state(self.root,chat['id']), 'stopped')
        self.assertEqual(self.store.prune(now=self.now), [chat['id']])

    def test_heartbeat_refreshes_all_owned_live_sessions(self):
        registry = SessionRegistry(self.root)
        first, second = self.store.new('model'), self.store.new('model')
        registry.set(first['id'], 'running')
        registry.set(second['id'], 'waiting_input')
        before = registry.records[first['id']]['heartbeat']
        with patch('centaur_cli.sessions.time.time', return_value=before + 40): registry.heartbeat()
        self.assertEqual(registry.records[first['id']]['heartbeat'], before + 40)
        self.assertEqual(registry.records[second['id']]['heartbeat'], before + 40)
        self.assertEqual(os.stat(self.root/'.centaur'/'runtime'/(first['id']+'.json')).st_mode & 0o777, 0o600)

    def test_live_child_protects_parent_and_child_even_when_parent_stopped(self):
        parent = self.old_chat(65)
        child_store = ChatStore(self.root)
        child_store.directory = self.root/'.centaur'/'agents'/parent['id']
        child = child_store.new('model')
        child.update(parent_id=parent['id'], created=(self.now-timedelta(hours=65)).isoformat())
        child_store.save(child)
        registry = SessionRegistry(self.root)
        registry.set(child['id'], 'waiting_input')
        self.assertEqual(self.store.prune(now=self.now), [])
        with self.assertRaises(ValueError): self.store.delete(parent['id'])
        self.assertTrue(child_store.path(child['id']).exists())
        registry.set(child['id'], 'stopped')
        self.assertEqual(self.store.prune(now=self.now), [parent['id']])
        self.assertFalse(child_store.directory.exists())
        self.assertEqual(self.store.agents(), [])

    def test_menu_create_switch_and_per_chat_drafts(self):
        terminal = self.terminal
        first = terminal.chat
        terminal.draft = 'rascunho primeiro'
        terminal.open_chats()
        terminal.handle('n')
        second = terminal.chat
        self.assertNotEqual(first['id'], second['id'])
        self.assertFalse(terminal.browser)
        terminal.draft = 'segundo'
        terminal.switch_chat(first)
        self.assertEqual(terminal.draft, 'rascunho primeiro')
        terminal.switch_chat(second)
        self.assertEqual(terminal.draft, 'segundo')
        self.assertEqual(len(self.store.list()), 2)

    def test_saved_selection_restores_model_effort_speed_but_not_permissions(self):
        for backend in ('openrouter', 'codex', 'claude'):
            with self.subTest(backend=backend):
                client = type('Client', (), {'backend': backend})()
                terminal = Terminal(self.root, 'model', self.store, client, effort='low', approval_mode='ask')
                saved = self.store.new('other' if backend == 'openrouter' else 'model', backend)
                saved.update(effort='high', speed='fast', approval_mode='never',
                             messages=[{'role': 'user', 'content': 'Anterior'}])
                self.store.save(saved)
                terminal.open_chats()
                terminal.selected = next(i for i, chat in enumerate(terminal.chats) if chat['id'] == saved['id'])
                terminal.handle_browser('\n')
                self.assertFalse(terminal.browser)
                self.assertEqual((terminal.model, terminal.effort, terminal.speed), (saved['model'], 'high', 'fast'))
                self.assertEqual(terminal.approval_mode, 'ask')
                terminal.create_chat_from_menu()
                self.assertEqual((terminal.chat['model'], terminal.chat['effort'], terminal.chat['speed']),
                                 (saved['model'], 'high', 'fast'))

    def test_two_real_workers_route_questions_approvals_and_cancellation(self):
        terminal = self.terminal
        results = {}
        def run(chat, client, tools, store, emit, instructions, progress):
            progress('atividade ' + chat['title'])
            if chat['title'] == 'primeiro':
                results['first'] = tools.base.ask_user('Qual?', ['A', 'B'])
                chat['messages'].append({'role':'assistant','content':results['first']['answer']})
            else:
                results['second'] = tools.base.approve('Executar?')
                chat['messages'].append({'role':'assistant','content':str(results['second'])})
            store.save(chat)
        first = terminal.chat
        first.update(title='primeiro', title_attempted=True, messages=[{'role':'user','content':'um'}])
        with patch('centaur_cli.terminal.run_turn', side_effect=run):
            terminal.start_work()
            self.wait(lambda: terminal.question is not None)
            terminal.handle(curses.KEY_SLEFT)
            terminal.handle('n')
            second = terminal.chat
            second.update(title='segundo',title_attempted=True,messages=[{'role':'user','content':'dois'}])
            terminal.start_work()
            self.wait(lambda: terminal.approval is not None)
            self.assertEqual(terminal.session_state(first), 'waiting_input')
            self.assertEqual(terminal.session_state(second), 'waiting_input')
            terminal.handle(curses.KEY_SLEFT)
            terminal.selected = next(i for i,c in enumerate(terminal.chats) if c['id'] == first['id'])
            terminal.handle('\n')
            self.assertIsNotNone(terminal.question)
            self.assertIsNone(terminal.approval)
            terminal.handle(curses.KEY_DOWN)
            terminal.handle('\n')
            self.wait(lambda: not terminal.busy)
            self.assertEqual(results['first']['answer'], 'B')
            self.assertTrue(terminal.session_states[second['id']]['busy'])
            self.assertEqual(first['messages'][-1]['content'],'B')
            terminal.switch_chat(second)
            self.assertIsNotNone(terminal.approval)
            terminal.handle('n')
            self.wait(lambda: not terminal.busy)
            self.assertFalse(results['second'])
            self.assertEqual(second['messages'][-1]['content'],'False')
        self.assertEqual(read_state(self.root, first['id']), 'stopped')
        self.assertEqual(read_state(self.root, second['id']), 'stopped')

    def test_cancel_and_done_only_affect_originating_session(self):
        terminal = self.terminal
        first = terminal.chat
        terminal.busy = True
        worker = terminal.worker_context()
        terminal.create_chat_from_menu()
        second = terminal.chat
        terminal.busy = True
        second_worker = terminal.worker_context()
        errors = []
        def await_answer():
            try: worker.ask_user('Qual?', ['A'])
            except TurnCancelled: errors.append('first')
        thread = threading.Thread(target=await_answer)
        thread.start()
        self.wait(lambda: terminal.session_states[first['id']].get('question') is not None)
        self.assertIsNone(terminal.question)
        terminal.switch_chat(first)
        terminal.handle('\x03')
        thread.join(2)
        self.assertEqual(errors,['first'])
        self.assertFalse(second_worker.cancel_event.is_set())
        terminal.switch_chat(second)
        worker.events.put(('done','primeiro terminou'))
        terminal.drain_events()
        self.assertTrue(terminal.busy)
        self.assertNotEqual(terminal.notice, 'primeiro terminou')
        terminal.busy = False

    def test_background_compaction_updates_its_own_chat(self):
        terminal = self.terminal
        first = terminal.chat
        first['messages'] = [{'role':'user','content':'primeiro'}]
        self.store.save(first)
        terminal.busy = True
        worker = terminal.worker_context()
        terminal.create_chat_from_menu()
        second = terminal.chat
        state = {'summary':'resumo','covered':0}
        worker.events.put(('compacted',(first,worker.cancel_event,state,100,30)))
        with patch('centaur_cli.terminal.save_compaction') as save:
            terminal.drain_events()
            self.assertIs(save.call_args.args[0], first)
        self.assertEqual(terminal.chat['id'],second['id'])
        self.assertFalse(terminal.session_states[first['id']]['busy'])
        self.assertNotIn('Contexto compactado', terminal.notice)

    def test_menu_states_and_child_preview_during_pending_input(self):
        terminal = self.terminal
        parent = terminal.chat
        parent['messages'] = [{'role':'user','content':'Pai'}]
        self.store.save(parent)
        terminal.busy = True
        worker = terminal.worker_context()
        worker.events.put(('approval', ('permitir?', queue.Queue())))
        terminal.drain_events()
        child_store = ChatStore(self.root)
        child_store.directory = self.root/'.centaur'/'agents'/parent['id']
        child = child_store.new('model')
        child.update(title='Filho', parent_id=parent['id'], messages=[{'role':'assistant','content':'Trabalho do filho'}])
        child_store.save(child)
        terminal.registry.set(child['id'], 'waiting_input')
        terminal.handle(curses.KEY_SLEFT)
        terminal.handle('\t')
        self.assertEqual(len(terminal.chats),2)
        for size in ((12,40),(24,80),(40,120)):
            terminal.draw(Screen(size))
        terminal.selected = next(i for i,c in enumerate(terminal.chats) if c['id']==child['id'])
        terminal.handle('\n')
        self.assertIn('Trabalho do filho','\n'.join(terminal.lines(50)))
        terminal.handle('\n')
        self.assertFalse(terminal.browser)
        self.assertEqual(terminal.chat['id'],parent['id'])
        self.assertIsNotNone(terminal.approval)

    def test_expired_current_chat_opens_empty_new_chat(self):
        terminal = self.terminal
        terminal.chat = self.old_chat(65)
        terminal.draft = ''
        previous = terminal.chat['id']
        terminal.housekeeping()
        self.assertNotEqual(previous,terminal.chat['id'])
        self.assertEqual(terminal.chat['messages'], [])

    def test_other_process_running_chat_cannot_be_taken_over(self):
        chat = self.old_chat(1)
        SessionRegistry(self.root).set(chat['id'],'running')
        self.terminal.open_chats()
        self.terminal.handle('\n')
        self.assertTrue(self.terminal.browser)
        self.assertIn('outro processo',self.terminal.notice)
        # A remembered idle selection is not ownership of a live runtime.
        self.terminal.session_contexts[chat['id']] = self.terminal.worker_context()
        self.terminal.handle('\n')
        self.assertTrue(self.terminal.browser)
        self.assertIn('outro processo', self.terminal.notice)

    def test_clipboard_control_characters_cannot_enter_composer(self):
        self.terminal.paste_text('a\r\nb\x1b\x03\tc')
        self.assertEqual(self.terminal.draft, 'a\nb    c')

    def test_background_title_and_manual_rename_survive_switch(self):
        terminal = self.terminal
        first = terminal.chat
        self.store.save(first)
        terminal.worker_context()
        terminal.create_chat_from_menu()
        terminal.pending_titles[first['id']] = 'Gerado'
        terminal.apply_titles()
        terminal.switch_chat(first)
        self.assertEqual(terminal.chat['title'],'Gerado')
        self.assertTrue(terminal.rename_chat(terminal.chat,'Manual'))
        terminal.create_chat_from_menu()
        terminal.switch_chat(first)
        self.assertEqual(terminal.chat['title'],'Manual')

    def test_pending_background_worker_blocks_quit_and_capture_stops_on_switch(self):
        from types import SimpleNamespace
        terminal = self.terminal
        first = terminal.chat
        terminal.busy = True
        terminal.worker_context()
        close = unittest.mock.Mock()
        terminal.computer = SimpleNamespace(close=close)
        terminal.create_chat_from_menu()
        close.assert_called_once()
        terminal.draft = '/quit'
        self.assertIsNone(terminal.submit())
        self.assertTrue(terminal.session_states[first['id']]['busy'])
        self.assertIn('sessões',terminal.notice)
        terminal.session_states[first['id']]['busy'] = False
        self.assertEqual(terminal.submit(),'quit')

    def test_background_worker_keeps_client_and_permissions_after_config_changes(self):
        terminal = self.terminal
        original_client = object()
        terminal.client = original_client
        terminal.approval_mode = 'ask'
        first = terminal.chat
        worker = terminal.worker_context()
        terminal.create_chat_from_menu()
        terminal.client = object()
        terminal.approval_mode = 'never'
        self.assertIs(worker.client, original_client)
        self.assertEqual(worker.approval_mode, 'ask')
        terminal.switch_chat(first)
        self.assertIs(terminal.client,original_client)
        self.assertEqual(terminal.approval_mode,'ask')

    def test_rename_from_menu_does_not_answer_pending_parent_question(self):
        from centaur_cli.interaction import QuestionPicker
        terminal = self.terminal
        terminal.question = QuestionPicker('Pendente?', ['A'], queue.Queue())
        other = self.store.new('model'); self.store.save(other)
        terminal.open_chats()
        terminal.handle('r')
        terminal.handle('\x15')
        for char in 'Renomeado': terminal.handle(char)
        screen = Screen((24,80)); terminal.draw(screen)
        self.assertIsNotNone(screen.cursor)
        terminal.handle('\n')
        self.assertIsNone(terminal.rename_target)
        self.assertEqual(self.store.list()[0]['title'],'Renomeado')
        self.assertTrue(terminal.question.answer.empty())
