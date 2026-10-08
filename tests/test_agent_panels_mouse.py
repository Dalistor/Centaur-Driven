"""Live child execution cards and cell-aware, non-submitting mouse editing."""
import curses
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from unittest.mock import patch

from centaur_cli.composer import layout_input
from centaur_cli.history import ChatStore
from centaur_cli.interaction import QuestionPicker, TurnCancelled
from centaur_cli.subagents import SubagentTools
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools
from test_terminal_settings import Screen


class AgentPanelMouseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ChatStore(self.root)
        self.terminal = Terminal(self.root, 'main', self.store, None)
        self.terminal.mouse_enabled = True  # Existing click tests exercise the opt-in mode.
        self.terminal.chat['messages'] = [{'role':'user', 'content':'Coordenar tarefas'}]
        self.store.save(self.terminal.chat)

    def test_native_selection_is_default_and_late_mouse_events_do_not_edit(self):
        with patch.dict(os.environ, {}, clear=True):
            terminal = Terminal(self.root, 'main', self.store, None)
        self.assertFalse(terminal.mouse_enabled)
        terminal.draft, terminal.cursor = 'Texto preservado', 8
        terminal.question = QuestionPicker('Qual?', ['A','B'], queue.Queue())
        with patch('centaur_cli.terminal.curses.getmouse') as read:
            terminal.handle(curses.KEY_MOUSE)
        read.assert_not_called()
        self.assertEqual((terminal.draft, terminal.cursor), ('Texto preservado', 8))
        self.assertTrue(terminal.question.answer.empty())

    def test_mouse_toggle_preserves_draft_scroll_and_pending_input(self):
        terminal = self.terminal
        terminal.mouse_enabled = False
        terminal.draft, terminal.cursor, terminal.scroll = '漢字 é', 3, 5
        terminal.question = QuestionPicker('Qual?', ['A','B'], queue.Queue())
        terminal.busy = True
        with patch('centaur_cli.terminal.curses.mousemask', side_effect=lambda mask: (mask, 0)) as mask, \
                patch('centaur_cli.terminal.curses.mouseinterval'):
            terminal.handle(curses.KEY_F6)
            self.assertTrue(terminal.mouse_enabled)
            self.assertIn('Shift+arraste', terminal.notice)
            terminal.handle(curses.KEY_F6)
            self.assertFalse(terminal.mouse_enabled)
            self.assertEqual(mask.call_args.args, (0,))
        self.assertEqual((terminal.draft, terminal.cursor, terminal.scroll), ('漢字 é', 3, 5))
        self.assertTrue(terminal.question.answer.empty())
        self.assertTrue(terminal.busy)
        self.assertFalse(terminal.cancel_event.is_set())

    def test_mouse_opt_in_and_unavailable_terminal_fall_back_to_selection(self):
        with patch.dict(os.environ, {'CENTAUR_MOUSE':'1'}):
            terminal = Terminal(self.root, 'main', self.store, None)
        self.assertTrue(terminal.mouse_enabled)
        for result in ((0, 0), curses.error('unsupported')):
            with patch('centaur_cli.terminal.curses.mousemask', side_effect=result if isinstance(result, Exception) else None,
                       return_value=result):
                terminal.configure_mouse(True)
                self.assertFalse(terminal.mouse_enabled)
                terminal.handle(curses.KEY_F6)
                self.assertIn('indisponíveis', terminal.notice)

    def test_copy_notice_uses_the_emulator_shortcut_for_the_platform(self):
        from centaur_cli.appearance import selection_notice
        for platform, shortcut in (('linux', 'Ctrl+Shift+C'), ('darwin', 'Cmd+C')):
            with self.subTest(platform=platform), patch('centaur_cli.appearance.sys.platform', platform):
                self.assertIn(shortcut, selection_notice(False))
                self.assertIn('Shift+arraste', selection_notice(True))

    def child(self, title='Task leitura', state='running', parent=None):
        store = ChatStore(self.root)
        parent = parent or self.terminal.chat
        store.directory = self.root/'.centaur'/'agents'/parent['id']
        child = store.new('provider/worker')
        child.update(parent_id=parent['id'], title=title, messages=[{'role':'user','content':'Consultar fontes'}])
        store.save(child)
        self.terminal.registry.set(child['id'], state)
        return child, store

    def draw(self, size=(32,160)):
        self.terminal.refresh_agents()
        screen = Screen(size)
        self.terminal.draw(screen)
        return screen

    def click(self, x, y, state=None):
        state = curses.BUTTON1_PRESSED if state is None else state
        with patch('centaur_cli.terminal.curses.getmouse', return_value=(0,x,y,0,state)):
            self.terminal.handle(curses.KEY_MOUSE)

    def test_cards_show_public_execution_refresh_and_close(self):
        child, store = self.child()
        screen = self.draw()
        self.assertIn('Task leitura', screen.text())
        self.assertIn('provider/worker', screen.text())
        self.assertIn('Trabalhando', screen.text())
        self.assertIn('Aguardando resposta', screen.text())
        child['models_used'] = ['provider/actual']
        child['messages'].append({'role':'assistant','content':'Investigando fontes', 'tool_calls':[
            {'id':'read','function':{'name':'read_file','arguments':'{"path":"src/app.py"}'}}]})
        store.save(child)
        screen = self.draw()
        self.assertIn('provider/actual', screen.text())
        self.assertIn('src/app.py', screen.text())
        self.assertIn('Investigando fontes', screen.text())
        self.terminal.registry.set(child['id'],'waiting_input')
        self.assertIn('Aguardando input', self.draw().text())
        self.terminal.registry.set(child['id'],'stopped')
        self.assertNotIn('SUBAGENTES', self.draw().text())
        self.assertFalse(self.terminal.agent_panel_hits)
        self.assertEqual(len(self.store.agents()),1)  # Completion hides, never deletes history.

    def test_every_child_is_reachable_by_sidebar_scroll_across_parents(self):
        parent = self.store.new('main'); self.store.save(parent)
        for index in range(7): self.child(f'Tarefa {index}',parent=parent if index%2 else None)
        seen = set()
        for start in range(7):
            self.terminal.agent_panel_scroll = start
            self.draw((30,160))
            seen.update(hit[-1]['title'] for hit in self.terminal.agent_panel_hits)
        self.assertEqual(seen,{f'Tarefa {i}' for i in range(7)})
        area = self.terminal.agent_panel_area
        self.terminal.scroll = 9
        self.click(area[0],area[1],curses.BUTTON4_PRESSED)
        self.assertEqual(self.terminal.scroll,9)
        self.assertLess(self.terminal.agent_panel_scroll,6)

    def test_responsive_cards_do_not_overlap_chat_or_composer(self):
        for i in range(4): self.child(f'Task {i}')
        for height in (18,24,32,48):
            for width in (112,120,140,191,240):
                with self.subTest(height=height,width=width):
                    self.terminal.draft = '汉字é 🧭 texto '*8
                    screen = self.draw((height,width))
                    box = self.terminal.input_hitbox
                    for left,top,w,h,agent in self.terminal.agent_panel_hits:
                        self.assertGreaterEqual(left,box['left']+box['width'])
                        self.assertLess(top+h,box['top'])
                        borders=[entry for entry in screen.output if entry[1]==left and entry[2].startswith(('┌','└'))]
                        self.assertTrue(borders)
                    screen = self.draw((height,width))
                    self.assertEqual(self.terminal.draft,'汉字é 🧭 texto '*8)
        self.terminal.draft=''
        screen=self.draw((12,40))
        self.assertFalse(self.terminal.agent_panel_hits)
        self.assertIn('4 subagentes',screen.text())
        self.terminal.handle(curses.KEY_SLEFT); self.terminal.handle('\t')
        self.assertEqual(len([c for c in self.terminal.chats if c.get('parent_id')]),4)

    def test_new_chat_with_background_agents_has_no_welcome_overlap(self):
        self.child()
        self.terminal.chat['messages']=[]
        screen=self.draw((24,112))
        left=self.terminal.agent_panel_area[0]
        header=next(entry for entry in screen.output if entry[2].startswith('Digite sua intenção'))
        self.assertLessEqual(header[1]+len(header[2]),left)

    def test_wide_mode_question_approval_and_completion_respect_sidebar(self):
        self.child()
        terminal=self.terminal
        for mode in ('wide','question','approval','completion'):
            for width in (112,160,191):
                with self.subTest(mode=mode,width=width):
                    terminal.question=terminal.approval=None
                    terminal.wide_chat=mode=='wide'
                    terminal.draft='$' if mode=='completion' else ''
                    if mode=='question':terminal.question=QuestionPicker('Decisão '*100,['Opção A','Opção B'],queue.Queue())
                    if mode=='approval':terminal.approval=('Confirmação '*100,queue.Queue())
                    self.draw((32,width))
                    area=terminal.agent_panel_area
                    self.assertIsNotNone(area)
                    if terminal.input_hitbox:
                        box=terminal.input_hitbox
                        self.assertLessEqual(box['left']+box['width'],area[0])
                    self.assertEqual(len(terminal.agent_panel_hits),1)
                    if terminal.question:self.assertTrue(terminal.question.answer.empty())
                    if terminal.approval:self.assertTrue(terminal.approval[1].empty())

    def test_click_card_reads_child_without_submitting_or_stopping(self):
        child,_=self.child()
        self.draw()
        left,top,_,_,_=self.terminal.agent_panel_hits[0]
        self.click(left+2,top+1)
        self.assertTrue(self.terminal.browser)
        self.assertEqual(self.terminal.agent_preview['id'],child['id'])
        self.assertEqual(self.terminal.registry.state(child['id']),'running')

    def test_click_waiting_child_opens_owning_parent_without_answering(self):
        parent=self.terminal.chat
        self.terminal.live_chats[parent['id']]=parent
        answers=queue.Queue()
        self.terminal.question=QuestionPicker('Qual?', ['A','B'], answers)
        child,_=self.child(state='waiting_input')
        self.terminal.create_chat_from_menu()
        self.draw()
        left,top,_,_,_=self.terminal.agent_panel_hits[0]
        self.click(left+1,top+1)
        self.assertEqual(self.terminal.chat['id'],parent['id'])
        self.assertIsNotNone(self.terminal.question)
        self.assertTrue(answers.empty())

    def test_click_mapping_wrapping_wide_combining_and_line_ends(self):
        layout=layout_input('ab汉é\nxyz',10)
        self.assertEqual(layout.at(0,3),2)  # Middle of wide glyph: left boundary.
        self.assertEqual(layout.at(0,5),5)  # Never split the combining accent.
        self.assertEqual(layout.at(1,2),8)
        self.assertEqual(layout.at(8,999),9)
        for width in (4,5):
            layout=layout_input('abcdefghij',width)
            self.assertEqual(layout.at(0,999),width)
            self.assertEqual(layout.at(1,0),width)

    def test_click_composer_padding_blank_rows_and_insert(self):
        terminal=self.terminal
        terminal.draft='abc\n汉字é'
        self.draw((24,80)); box=terminal.input_hitbox
        self.click(box['text_left']+2,box['top'])
        terminal.handle('!')
        self.assertEqual(terminal.draft,'ab!c\n汉字é')
        self.draw((24,80)); box=terminal.input_hitbox
        self.click(box['left'],box['top']); self.assertEqual(terminal.cursor,0)
        self.click(box['text_left']+4,box['top']+1); self.assertEqual(terminal.cursor,7)
        self.click(box['left']+box['width']-1,box['top']+2)
        self.assertEqual(terminal.cursor,len(terminal.draft))
        self.assertFalse(terminal.busy)

    def test_click_visible_scrolled_input_uses_full_draft_indices(self):
        terminal=self.terminal
        terminal.draft='\n'.join(f'linha {i}' for i in range(14))
        self.draw((24,80)); box=terminal.input_hitbox
        self.assertGreater(box['start_row'],0)
        self.click(box['text_left']+3,box['top'])
        self.assertEqual(terminal.cursor,box['layout'].at(box['start_row'],3))
        self.assertGreater(terminal.cursor,3)

    def test_marker_click_is_atomic_and_late_click_cannot_edit_new_draft(self):
        terminal=self.terminal
        marker='[Arquivo #1]'
        terminal.draft='abc '+marker+' fim'
        terminal.pending_attachments.append({'marker':marker,'span':[4,4+len(marker)],'name':'a.txt','kind':'text','size':3})
        self.draw((24,80));box=terminal.input_hitbox
        self.click(box['text_left']+7,box['top']);self.assertEqual(terminal.cursor,4)
        self.click(box['text_left']+14,box['top']);self.assertEqual(terminal.cursor,16)
        terminal.draft='Outra mensagem';terminal.cursor=8
        self.click(box['text_left'],box['top']);self.assertEqual(terminal.cursor,8)
        self.draw((24,80));box=terminal.input_hitbox
        terminal.chat=self.store.new('main')
        self.click(box['text_left'],box['top']);self.assertEqual(terminal.cursor,8)

    def test_click_rename_and_free_answer_horizontal_window(self):
        terminal=self.terminal
        terminal.begin_rename(terminal.chat)
        terminal.rename_text='Título '+('X'*65);terminal.rename_cursor=len(terminal.rename_text)
        self.draw((12,40));box=terminal.input_hitbox
        self.assertGreater(box['start_index'],0)
        self.click(box['text_left']+2,box['top'])
        self.assertEqual(terminal.rename_cursor,box['start_index']+2)
        terminal.rename_target=None
        answers=queue.Queue();terminal.question=QuestionPicker('Qual?',[],answers)
        terminal.question.text='Resposta '+('Y'*80);terminal.question.cursor=len(terminal.question.text)
        self.draw((24,80));box=terminal.input_hitbox
        self.click(box['text_left']+1,box['top'])
        self.assertEqual(terminal.question.cursor,box['start_index']+1)
        self.assertTrue(answers.empty())

    def test_motion_release_and_approval_click_never_execute(self):
        terminal=self.terminal;terminal.draft='abc'
        self.draw();box=terminal.input_hitbox;cursor=terminal.cursor
        self.click(box['text_left'],box['top'],curses.BUTTON1_RELEASED)
        self.assertEqual(terminal.cursor,cursor)
        answers=queue.Queue();terminal.approval=('Executar?',answers)
        self.draw();self.click(5,30)
        self.assertTrue(answers.empty())

    def test_refresh_skips_archived_transcript_before_deserializing(self):
        live,store=self.child('Vivo')
        stopped,_=self.child('Parado','stopped')
        with patch('centaur_cli.history.json.loads',wraps=json.loads) as parse:
            self.terminal.refresh_agents()
        self.assertEqual([a['id'] for a in self.terminal.active_agents],[live['id']])
        self.assertEqual(len([call for call in parse.call_args_list if stopped['id'] in call.args[0] and 'messages' in call.args[0]]),0)

    def test_delegation_lifetime_heartbeat_retention_and_terminal_outcomes(self):
        terminal=self.terminal
        for outcome in ('success','failure','cancel'):
            with self.subTest(outcome=outcome):
                started=threading.Event();release=threading.Event();results=[];cancelled=[]
                cancel=threading.Event()
                class Client:
                    def complete(inner,*args,**kwargs):
                        started.set()
                        if not release.wait(3): raise RuntimeError('fixture blocked')
                        if outcome=='failure': raise RuntimeError('fixture failure')
                        if cancel.is_set(): raise TurnCancelled('Interrompido')
                        return {'role':'assistant','content':'Relatório validável'}
                parent=self.store.new('main')
                parent['created']=(datetime.now(timezone.utc)-timedelta(hours=65)).isoformat()
                self.store.save(parent)
                base=ProjectTools(self.root,lambda _:True,cancel_event=cancel)
                tools=SubagentTools(base,Client(),parent['id'],lambda _:None,registry=terminal.registry)
                def delegate():
                    try:
                        results.append(json.loads(tools.execute('delegate_task',{'title':'Longa','task':'Aguardar execução'})))
                    except TurnCancelled as error:
                        cancelled.append(error)
                worker=threading.Thread(target=delegate)
                worker.start()
                try:
                    self.assertTrue(started.wait(2))
                    self.draw()
                    child=next(a for a in terminal.active_agents if a['parent_id']==parent['id'])
                    before=terminal.registry.records[child['id']]['heartbeat']
                    with patch('centaur_cli.sessions.time.time',return_value=before+1900):
                        terminal.registry.heartbeat()
                        self.assertEqual(terminal.registry.state(child['id']),'running')
                        self.assertNotIn(parent['id'],self.store.prune())
                    self.assertTrue(worker.is_alive())  # No coordinator-wide inference deadline.
                    terminal.registry.last_heartbeat=0;terminal.registry.heartbeat()
                    if outcome=='cancel':cancel.set()
                finally:
                    release.set();worker.join(3)
                self.assertFalse(worker.is_alive())
                self.draw()
                self.assertNotIn(child['id'],{a['id'] for a in terminal.active_agents})
                self.assertEqual(terminal.registry.state(child['id']),'stopped')
                if outcome == 'cancel':
                    self.assertEqual(len(cancelled), 1)
                    self.assertEqual(results, [])
                    self.assertEqual(next(a for a in self.store.agents() if a['id'] == child['id'])['status'], 'cancelled')
                else:
                    self.assertEqual(results[0]['status'],'reported' if outcome=='success' else 'failed')
