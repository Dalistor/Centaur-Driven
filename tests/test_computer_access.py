"""Persistent human consent, foreground resumption, revocation and OS desktop lock."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock

from centaur_cli.computer import ComputerSession
from centaur_cli.computer_access import ComputerControl, ComputerPermissions, DesktopLease
from centaur_cli.history import ChatStore
from centaur_cli.interaction import TurnCancelled
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools
from test_computer_session import Backend
from test_terminal_settings import Screen


class ComputerAccessTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.store=ChatStore(self.root)
        self.chat=self.store.new('main');self.store.save(self.chat)
        self.control=ComputerControl(self.root,self.chat['id'],lease=DesktopLease(self.root/'desktop.lock'))
        self.prompts=[]
        targets=patch.object(ComputerSession,'validate_targets')
        targets.start();self.addCleanup(targets.stop)

    def session(self, chat=None, approve=None, control=None, cancel=None):
        backend=Backend()
        session=ComputerSession(approve or (lambda prompt:self.prompts.append(prompt) or True),cancel,
                               lambda:backend,control=control or self.control,
                               chat_id=(chat or self.chat)['id'], interval=60,settle_timeout=0)
        self.addCleanup(session.close)
        return session,backend

    def start(self,session):
        session.start('Consultar e editar a interface solicitada')
        session.observation_messages()

    def action(self,session):
        return session.execute('computer_action',{'action':'click','frame_id':session.reference.identifier if session.reference else 0,'x':10,'y':20})

    def test_once_across_actions_turns_process_controller_and_restart(self):
        session,backend=self.session();self.start(session)
        self.assertIn('sem confirmações',self.prompts[0]);self.assertIn('revogar',self.prompts[0])
        for _ in range(3):
            session.observation_messages();self.action(session)
        session.execute('computer_stop',{});self.start(session)
        session.close()
        second=ComputerControl(self.root,self.chat['id'],lease=DesktopLease(self.root/'desktop.lock'))
        resumed,_=self.session(control=second,approve=lambda _:self.fail('Consent repeated'))
        self.start(resumed);self.action(resumed)
        self.assertEqual(len(self.prompts),1)
        self.assertEqual(len(backend.actions),3)
        permission=self.control.permissions.path(self.chat['id'])
        self.assertEqual(os.stat(permission).st_mode & 0o777,0o600)
        self.assertNotIn('granted',self.store.path(self.chat['id']).read_text())
        self.assertNotIn('base64',permission.read_text())

    def test_new_chat_has_separate_consent_refusal_and_no_capture(self):
        first,_=self.session();self.start(first)
        chat=self.store.new('main');self.control.focus(chat['id'])
        refused,backend=self.session(chat=chat,approve=lambda _:False)
        with patch.object(backend,'capture',wraps=backend.capture) as capture:
            self.assertIn('recusada',refused.start('Outra task'))
            self.assertIn('recusado',refused.start('Repetir chamada'))
            capture.assert_not_called()
        self.assertFalse(self.control.permissions.granted(chat['id']))
        self.assertTrue(self.control.permissions.granted(self.chat['id']))

    def test_default_capture_has_no_120_second_expiry_but_frames_are_bounded(self):
        session,_=self.session();self.start(session)
        before=time.monotonic()
        with patch('centaur_cli.computer.time.monotonic',return_value=before+3600):
            for _ in range(6):session.capture()
            self.assertTrue(session.active)
        self.assertEqual(len(session.frames),3)
        session.close();self.assertFalse(session.active);self.assertFalse(session.frames)
        self.assertTrue(self.control.permissions.granted(self.chat['id']))

    def test_focus_pause_blocks_capture_resumes_fresh_without_permission(self):
        session,backend=self.session();self.start(session)
        old_reference=session.reference.identifier
        old_worker=session.thread
        self.control.focus(None)
        old_worker.join(1)
        self.assertTrue(session.resume_requested)
        self.assertFalse(session.active);self.assertIsNone(session.reference);self.assertFalse(session.frames)
        result=[];done=threading.Event()
        worker=threading.Thread(target=lambda:(result.extend(session.observation_messages()),done.set()))
        worker.start()
        try:
            self.assertFalse(done.wait(.05))
            self.assertEqual(backend.actions,[])
            self.control.focus(self.chat['id'])
            self.assertTrue(done.wait(2))
            self.assertGreater(session.reference.identifier,old_reference)
            self.assertEqual(len(self.prompts),1)
            self.assertTrue(result)
        finally:
            self.control.focus(self.chat['id']);worker.join(2)

    def test_switch_during_inference_discards_coordinates_before_resuming_action(self):
        session,backend=self.session();self.start(session)
        old=session.reference.identifier
        self.control.focus(None);self.control.focus(self.chat['id'])
        with self.assertRaisesRegex(ValueError,'Quadro antigo'):
            session.execute('computer_action',{'action':'click','frame_id':old,'x':1,'y':1})
        self.assertFalse(backend.actions)
        session.observation_messages();self.action(session)
        self.assertEqual(len(backend.actions),1)
        self.assertEqual(len(self.prompts),1)

    def test_explicit_pause_resume_and_cancellation_of_wait(self):
        cancel=threading.Event();session,_=self.session(cancel=cancel);self.start(session)
        self.control.pause(self.chat['id'])
        self.assertFalse(session.active)
        self.control.resume(self.chat['id']);session.observation_messages();self.assertTrue(session.active)
        self.control.focus(None);cancel.set()
        with self.assertRaises(TurnCancelled):session.observation_messages()
        self.assertFalse(session.frames)

    def test_revocation_during_actions_requires_new_consent_even_after_save(self):
        session,backend=self.session();self.start(session)
        self.control.revoke(self.chat['id'])
        self.store.save(self.chat)  # A late conversation write cannot re-grant control.
        self.assertFalse(self.control.permissions.granted(self.chat['id']))
        self.assertFalse(session.active);self.assertFalse(session.resume_requested)
        with self.assertRaises(ValueError):self.action(session)
        self.assertEqual(backend.actions,[])
        self.start(session);self.assertEqual(len(self.prompts),2)

    def test_remote_revocation_is_checked_before_input(self):
        session,backend=self.session();self.start(session)
        ComputerPermissions(self.root).revoke(self.chat['id'])
        with self.assertRaises(ValueError):self.action(session)
        self.assertEqual(backend.actions,[]);self.assertFalse(session.frames)

    def test_lease_excludes_other_process_and_releases_without_unlink(self):
        lease=self.control.lease;lease.acquire()
        self.addCleanup(lease.release)
        code='from centaur_cli.computer_access import DesktopLease; import sys; l=DesktopLease(sys.argv[1]); l.acquire(); l.release()'
        options={'capture_output':True,'text':True,'timeout':5,'env':{**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])}}
        denied=subprocess.run([sys.executable,'-c',code,str(lease.path)],**options)
        self.assertNotEqual(denied.returncode,0);self.assertIn('Outro chat/processo',denied.stderr)
        lease.release()
        allowed=subprocess.run([sys.executable,'-c',code,str(lease.path)],**options)
        self.assertEqual(allowed.returncode,0,allowed.stderr)
        self.assertTrue(lease.path.exists())

    def test_replacement_session_and_old_watch_cannot_release_new_owner(self):
        first,_=self.session();self.start(first);old=first.thread
        backend=first.backend
        def restart_backend():
            old.join(1)
            self.assertFalse(old.is_alive())
            return backend
        with patch.object(first,'backend_factory',side_effect=restart_backend):
            self.start(first)
        self.assertIs(self.control.owner,first)
        self.assertTrue(first.active)
        self.assertEqual(len(self.prompts),1)
        old=first.thread
        first.close()
        second,_=self.session();self.start(second);old.join(1)
        self.assertIs(self.control.owner,second)
        self.assertTrue(second.active)
        first.close()
        self.assertIs(self.control.owner,second)
        first.close();second.close()
        self.assertIsNone(self.control.lease.descriptor)

    def test_malformed_grants_symlinks_and_model_file_access_fail_closed(self):
        permissions=self.control.permissions
        for content in ('[]','{','null',json.dumps({'schema':1,'id':'b'*32,'granted':True})):
            permissions.directory.mkdir(parents=True,exist_ok=True)
            permissions.path(self.chat['id']).write_text(content)
            self.assertFalse(permissions.granted(self.chat['id']))
        permission=permissions.path(self.chat['id']);permission.unlink()
        target=self.root/'target';target.write_text('unchanged');permission.symlink_to(target)
        self.assertFalse(permissions.granted(self.chat['id']))
        with self.assertRaises(ValueError):permissions.grant(self.chat['id'])
        self.assertEqual(target.read_text(),'unchanged');permission.unlink()
        tools=ProjectTools(self.root,lambda _:True,approval_mode='never')
        path=f'.centaur/computer-permissions/{self.chat["id"]}.json'
        self.assertIn('gerenciadas pelo usuário',tools.execute('write_file',{'path':path,'content':'{}'}))
        self.assertFalse(permission.exists())

    def test_deleting_or_expiring_chat_removes_its_consent(self):
        self.control.permissions.grant(self.chat['id'])
        self.store.delete(self.chat['id']);self.assertFalse(self.control.permissions.granted(self.chat['id']))
        old=self.store.new('main');old['created']=(datetime.now(timezone.utc)-timedelta(hours=65)).isoformat()
        self.store.save(old);self.control.permissions.grant(old['id'])
        self.assertIn(old['id'],self.store.prune());self.assertFalse(self.control.permissions.granted(old['id']))

    def test_backend_failure_keeps_consent_releases_lease_and_does_not_move(self):
        session,_=self.session()
        session.backend_factory=Mock(side_effect=RuntimeError('missing display'))
        with self.assertRaises(RuntimeError):session.start('Teste')
        self.assertTrue(self.control.permissions.granted(self.chat['id']))
        self.assertIsNone(self.control.owner);self.assertIsNone(self.control.lease.descriptor)
        session.backend_factory=Backend;self.start(session)
        self.assertEqual(len(self.prompts),1)

    def test_terminal_busy_revoke_shortcut_and_commands_never_call_model(self):
        terminal=Terminal(self.root,'main',self.store,None)
        terminal.computer_control.permissions.grant(terminal.chat['id'])
        terminal.busy=True
        terminal.draft='$computer revoke';terminal.submit()
        self.assertTrue(terminal.cancel_event.is_set())
        self.assertFalse(terminal.computer_control.permissions.granted(terminal.chat['id']))
        terminal.computer_control.permissions.grant(terminal.chat['id'])
        terminal.browser=True;terminal.handle('\x07')
        self.assertFalse(terminal.computer_control.permissions.granted(terminal.chat['id']))
        self.assertIn('revogado',terminal.notice)
        terminal.browser=False;terminal.busy=False
        for command in ('$computer status','$computer pause','$computer resume'):
            terminal.draft=command;terminal.submit();self.assertEqual(terminal.draft,'')
        self.assertEqual(terminal.chat['messages'],[])
        terminal.draw(Screen((12,40)))

    def test_move_scroll_skip_settle_but_click_checks_stability(self):
        session,_=self.session();self.start(session)
        with patch.object(session,'settle',return_value='estável') as settle:
            for action,args in (('move',{}),('scroll',{'amount':1}),('click',{})):
                session.observation_messages()
                session.execute('computer_action',dict(action=action,frame_id=session.reference.identifier,x=3,y=4,**args))
            self.assertEqual(settle.call_count,1)

    def test_real_worker_pauses_in_menu_resumes_on_return_and_closes_after_task(self):
        terminal=Terminal(self.root,'main',self.store,None)
        terminal.computer_control.lease=DesktopLease(self.root/'worker.lock')
        parent=terminal.chat
        parent.update(title_attempted=True,messages=[{'role':'user','content':'Usar o computador'}])
        started=threading.Event();continue_task=threading.Event();actions=[]
        def run(chat,client,tools,store,emit,instructions,progress):
            computer=tools.base.computer
            computer.start('Testar formulário');computer.observation_messages()
            original=computer.reference.identifier
            started.set()
            if not continue_task.wait(3):raise RuntimeError('fixture timed out')
            try:
                computer.execute('computer_action',{'action':'click','frame_id':original,'x':4,'y':5})
            except ValueError:
                computer.observation_messages()
                computer.execute('computer_action',{'action':'click','frame_id':computer.reference.identifier,'x':4,'y':5})
            actions.extend(computer.backend.actions)
            chat['messages'].append({'role':'assistant','content':'Teste concluído'})
            store.save(chat)
        def factory(approve,cancel,**kwargs):
            return ComputerSession(approve,cancel,Backend,interval=60,settle_timeout=0,**kwargs)
        def wait(predicate):
            until=time.monotonic()+3
            while time.monotonic()<until:
                terminal.drain_events();terminal.housekeeping()
                if predicate():return
                time.sleep(.005)
            self.fail('worker did not reach state')
        with patch('centaur_cli.terminal.ComputerSession',side_effect=factory),patch('centaur_cli.terminal.run_turn',side_effect=run):
            terminal.start_work()
            wait(lambda:terminal.approval is not None)
            self.assertIn('Autorizar este chat',terminal.approval[0])
            terminal.handle('y')
            wait(started.is_set)
            session=terminal.computer
            terminal.draw(Screen((24,140)))
            terminal.open_chats();self.assertFalse(session.active);self.assertTrue(session.resume_requested)
            terminal.create_chat_from_menu()
            continue_task.set()
            wait(lambda:terminal.registry.state(parent['id'])=='waiting_input')
            self.assertFalse(actions)
            terminal.switch_chat(parent)
            wait(lambda:not terminal.busy)
            self.assertEqual(len(actions),1)
            self.assertIsNone(terminal.computer)
            self.assertFalse(session.frames)
            self.assertTrue(terminal.computer_control.permissions.granted(parent['id']))
            self.assertNotIn('computer-permissions',self.store.path(parent['id']).read_text())

    def test_cancel_before_consent_does_not_create_grant_or_backend(self):
        cancel=threading.Event();cancel.set()
        session,backend=self.session(cancel=cancel)
        with self.assertRaises(TurnCancelled):session.start('Teste')
        self.assertEqual(self.prompts,[])
        self.assertFalse(self.control.permissions.granted(self.chat['id']))
        self.assertIsNone(self.control.lease.descriptor)

    def test_late_consent_write_cannot_restore_revoked_permission(self):
        cancellation=threading.Event();entered=threading.Event();release=threading.Event()
        original=self.control.permissions.grant
        def write(chat_id):
            entered.set()
            if not release.wait(2):raise RuntimeError('fixture blocked')
            original(chat_id)
        writer=threading.Thread(target=lambda:self.control.grant(self.chat['id'],cancellation))
        revoked=threading.Event()
        revoker=threading.Thread(target=lambda:(self.control.revoke(self.chat['id']),revoked.set()))
        with patch.object(self.control.permissions,'grant',side_effect=write):
            writer.start()
            try:
                self.assertTrue(entered.wait(1))
                cancellation.set();revoker.start()
                self.assertFalse(revoked.wait(.03))
            finally:
                release.set();writer.join(2);revoker.join(2)
        self.assertTrue(revoked.is_set())
        self.assertFalse(self.control.permissions.granted(self.chat['id']))
        with self.assertRaises(TurnCancelled):self.control.grant(self.chat['id'],cancellation)
        self.assertFalse(self.control.permissions.granted(self.chat['id']))
