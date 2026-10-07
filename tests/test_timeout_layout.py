"""Slow models have 30 minutes; diagnostics stay inside the reading column."""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from centaur_cli.appearance import cell_width, fit_notice
from centaur_cli.context import compact_chat, save_compaction
from centaur_cli.history import ChatStore
from centaur_cli.interaction import TurnCancelled
from centaur_cli.native_client import NativeClient
from centaur_cli.openrouter import OpenRouter
from centaur_cli.terminal import Terminal, display_lines
from test_terminal_settings import Screen


class TimeoutLayoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ChatStore(self.root)
        self.terminal = Terminal(self.root, 'main', self.store, None)

    def test_native_default_gives_the_process_thirty_minutes(self):
        with patch.dict(os.environ, {}, clear=True), patch('centaur_cli.native_client.shutil.which', return_value='/fixture/codex'):
            client = NativeClient('codex', 'main')
        process = Mock(returncode=1)
        process.communicate.return_value = ('', 'fixture failure')
        with patch('centaur_cli.native_client.subprocess.Popen', return_value=process):
            with self.assertRaises(RuntimeError): client.complete('main', [], [])
        self.assertEqual(client.timeout, 1800)
        self.assertLessEqual(process.communicate.call_args.kwargs['timeout'], .1)

    def test_compaction_default_allows_a_slow_summary_and_keeps_history(self):
        chat = self.store.new('main')
        chat['messages'] = [{'role':'user' if i%2==0 else 'assistant', 'content':'Histórico importante '*70} for i in range(14)]
        original = copy.deepcopy(chat)
        elapsed = [0]
        budgets = []
        def reply(model, messages, tools, **options):
            self.assertEqual(tools, [])
            budgets.append(options['request_timeout'])
            elapsed[0] += 300  # Longer than both old 90s per-request and 180s total.
            return {'content':'Objetivo, decisões e validações pendentes preservados.'}
        client = Mock(context_windows={'main':10000},supports_request_timeout=True,supports_cancellation=False)
        client.model_efforts = {}; client.redact = str; client.complete.side_effect = reply
        with patch.dict(os.environ,{},clear=True), patch('centaur_cli.context.time.monotonic',side_effect=lambda:elapsed[0]):
            state, before, after = compact_chat(chat,client)
        self.assertEqual(budgets[0],1800)
        self.assertTrue(all(0 < budget <= 1800 for budget in budgets))
        self.assertGreater(elapsed[0],180)
        self.assertEqual(chat,original)
        self.assertLess(after,before)
        self.assertIn('Objetivo',state['summary'])

    def test_openrouter_default_override_and_summary_budget(self):
        payload = json.dumps({'choices':[{'message':{'role':'assistant','content':'Pronto'}}]}).encode()
        for configured, expected in ((None,1800),('2400',2400),('60',60)):
            values={} if configured is None else {'CENTAUR_OPENROUTER_TIMEOUT':configured}
            with patch.dict(os.environ,values,clear=True): client=OpenRouter('fake')
            with patch('centaur_cli.openrouter.urlopen',return_value=io.BytesIO(payload)) as request:
                client.complete('main',[],[])
            self.assertEqual(request.call_args.kwargs['timeout'],expected)
            with patch('centaur_cli.openrouter.urlopen',return_value=io.BytesIO(payload)) as request:
                client.complete('main',[],[],request_timeout=1500)
            self.assertEqual(request.call_args.kwargs['timeout'],min(expected,1500))
        for value in ('0','29','3601','bad','nan'):
            with patch.dict(os.environ,{'CENTAUR_OPENROUTER_TIMEOUT':value}):
                with self.assertRaises(ValueError): OpenRouter('fake')

    def test_long_errors_fit_the_composer_and_full_diagnostic_stays_readable(self):
        terminal = self.terminal
        error = 'codex: tempo limite de 1800 segundos; ' + 'Falha漢字é🧭/'*180 + ' FIM_DIAGNOSTICO'
        terminal.chat['messages'] = [{'role':'user','content':'Pedido'}]
        terminal.chat['last_error'] = error
        terminal.notice = 'Erro: '+error+' · /retry retoma este turno.'
        for size in ((12,40),(24,80),(30,140)):
            with self.subTest(size=size):
                screen=Screen(size); terminal.draw(screen)
                separator = max((entry for entry in screen.output if entry[2] and set(entry[2]) == {'─'}),key=lambda entry:entry[0])
                notices = [entry for entry in screen.output if entry[0]==separator[0]+1]
                self.assertEqual(len(notices),1)
                row,column,text,_ = notices[0]
                self.assertLessEqual(column+cell_width(text),separator[1]+cell_width(separator[2]))
                self.assertNotIn('Falha',text)
                self.assertIn('Erro',text)
                lines=terminal.lines(cell_width(separator[2])-2)
                self.assertTrue(all(cell_width(line)<=cell_width(separator[2])-2 for line in lines))
                self.assertIn('FIM_DIAGNOSTICO',''.join(lines))
        self.assertEqual(terminal.chat['last_error'],error)
        terminal.notice = 'Erro: formato de anexo inválido'
        screen=Screen((30,140));terminal.draw(screen)
        self.assertIn('Erro: formato de anexo inválido',screen.text())
        terminal.notice = 'Aviso extenso '*100
        screen=Screen((30,140));terminal.draw(screen)
        notice=next(entry[2] for entry in screen.output if entry[2].startswith('Aviso extenso'))
        self.assertTrue(notice.endswith('…'))

    def test_wide_diagnostic_wrap_preserves_characters_and_clamps_controls(self):
        text='漢字🧭é/arquivo_sem_espacos'*40
        for width in (2,15,34,73):
            lines=display_lines(text,width)
            self.assertTrue(all(cell_width(line)<=width for line in lines))
            self.assertEqual(''.join(lines),text)
        for width in (0,1,30):
            notice=fit_notice('Erro:\n'+text+'\x1b',width)
            self.assertLessEqual(cell_width(notice),width)
            self.assertNotIn('\n',notice)
            self.assertNotIn('\x1b',notice)

    def test_compaction_failure_is_saved_and_footer_does_not_repeat_full_error(self):
        terminal=self.terminal
        terminal.busy=True
        original=copy.deepcopy(terminal.chat['messages'])
        error='Erro detalhado de compactação '+('caminho/'*200)+' FIM_ERRO'
        with patch('centaur_cli.terminal.compact_chat',side_effect=RuntimeError(error)):
            terminal.compact(terminal.chat,None,terminal.cancel_event)
        terminal.drain_events()
        self.assertFalse(terminal.busy)
        self.assertEqual(self.store.list()[0]['compaction_error'],error)
        self.assertEqual(terminal.chat['messages'],original)
        self.assertIn('FIM_ERRO',''.join(terminal.lines(50)))
        self.assertEqual(terminal.notice,'Erro na compactação · detalhes na conversa · $compact retoma.')
        previous=copy.deepcopy(terminal.chat)
        with patch.object(self.store,'save',side_effect=OSError):
            with self.assertRaises(OSError): save_compaction(terminal.chat,self.store,{'summary':'novo','through':0})
        self.assertEqual(terminal.chat,previous)
        save_compaction(terminal.chat,self.store,{'summary':'novo','through':0})
        self.assertNotIn('compaction_error',terminal.chat)
        self.assertNotIn('compaction_error',self.store.list()[0])

    def test_cancelled_compaction_does_not_become_an_error(self):
        terminal=self.terminal
        terminal.busy=True
        with patch('centaur_cli.terminal.compact_chat',side_effect=TurnCancelled('Compactação interrompida.')):
            terminal.compact(terminal.chat,None,terminal.cancel_event)
        terminal.drain_events()
        self.assertFalse(terminal.busy)
        self.assertNotIn('compaction_error',terminal.chat)
        self.assertEqual(terminal.notice,'Compactação interrompida.')

    def test_routed_subagent_forwards_summary_deadline_and_capabilities(self):
        from centaur_cli.subagents import RoutedClient
        client=Mock(supports_request_timeout=True,context_windows={'model':200000})
        routed=RoutedClient(client,'child','medium')
        self.assertIs(routed.supports_request_timeout,True)
        self.assertEqual(routed.context_windows,{'model':200000})
        routed.complete('model',[],[],request_timeout=25,effort='low')
        client.complete.assert_called_once_with('model',[],[],cost_tier='medium',session_id='child',request_timeout=25,effort='low')

    def test_background_compaction_error_belongs_to_originating_chat(self):
        terminal=self.terminal
        first=terminal.chat
        terminal.busy=True
        worker=terminal.worker_context()
        terminal.create_chat_from_menu()
        worker.events.put(('compaction_failed',(first,'Diagnóstico da primeira conversa')))
        terminal.drain_events()
        self.assertFalse(terminal.session_states[first['id']]['busy'])
        self.assertEqual(self.store.path(first['id']).read_text().count('Diagnóstico da primeira conversa'),1)
        self.assertNotIn('compaction_error',terminal.chat)
        self.assertNotIn('Erro',terminal.notice)
