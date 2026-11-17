import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from centaur_cli.appearance import Palette
from centaur_cli.conversation import generate_title, readable_markdown, tool_activity
from centaur_cli.history import ChatStore
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools
from test_terminal_settings import Screen


def call(name='read_file', **arguments):
    return {'id': 'read-1', 'type': 'function', 'function': {
        'name': name, 'arguments': json.dumps(arguments)}}


class ConversationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ChatStore(self.root)
        self.terminal = Terminal(self.root, 'model', self.store, None)

    def test_progress_precedes_final_and_raw_results_are_optional(self):
        terminal = self.terminal
        terminal.chat['messages'] = [
            {'role': 'user', 'content': 'Revisar projeto'},
            {'role': 'assistant', 'content': 'Vou conferir o contrato.',
             'tool_calls': [call(path='README.md')], 'reasoning': 'PRIVATE REASONING'},
            {'role': 'tool', 'tool_call_id': 'read-1', 'content': 'RAW TOOL OUTPUT'},
            {'role': 'assistant', 'content': '**Contrato** validado.'}]
        compact = '\n'.join(terminal.lines(74))
        self.assertLess(compact.index('Vou conferir'), compact.index('Contrato validado'))
        self.assertIn('✓ Leu README.md', compact)
        self.assertNotIn('RAW TOOL OUTPUT', compact)
        self.assertNotIn('PRIVATE REASONING', compact)
        terminal.handle('\x0f')
        self.assertIn('RAW TOOL OUTPUT', '\n'.join(terminal.lines(74)))
        self.assertNotIn('PRIVATE REASONING', '\n'.join(terminal.lines(74)))

    def test_activity_never_claims_pending_failed_or_refused_actions_succeeded(self):
        action = call('run_command', command='python -m unittest')
        self.assertTrue(tool_activity(action).startswith('○ Executando'))
        self.assertTrue(tool_activity(action, 'Código de saída: 2\nfailed').startswith('! Falha'))
        self.assertTrue(tool_activity(action, 'Execução recusada pelo usuário.').startswith('– Recusado'))
        self.assertTrue(tool_activity(action, 'Código de saída: 0\nOK').startswith('✓ Executou'))

    def test_delegation_status_distinguishes_failure_from_received_report(self):
        action = call('delegate_task', title='Validar ZIP')
        for status, label in (('failed', '! Subagente falhou'),
                              ('cancelled', '! Subagente interrompido'),
                              ('reported', '✓ Relatório recebido')):
            with self.subTest(status=status):
                result = json.dumps({'status': status, 'report': 'PRIVATE DETAILS'})
                self.assertEqual(tool_activity(action, result), label + ' · Validar ZIP')
        self.assertTrue(tool_activity(action).startswith('○ Delegando'))

    def test_wrapped_actions_comments_and_literal_markers_keep_their_own_styles(self):
        terminal = self.terminal
        read = call(path='frontend/src/services/' + 'long-path/' * 8 + 'index.js')
        progress = dict(call('report_progress', message='✓ Comentário público da IA'), id='progress')
        failed = dict(call('run_command', command='python -m unittest'), id='failed')
        refused = dict(call('write_file', path='README.md'), id='refused')
        terminal.chat['messages'] = [
            {'role': 'user', 'content': '◆ Centaur\nPedido do usuário'},
            {'role': 'assistant', 'content': '✓ Comentário que parece ação\n  Texto indentado',
             'tool_calls': [read, progress, failed, refused]},
            {'role': 'tool', 'tool_call_id': read['id'], 'content': 'arquivo lido'},
            {'role': 'tool', 'tool_call_id': progress['id'], 'content': '✓ Comentário público da IA'},
            {'role': 'tool', 'tool_call_id': failed['id'], 'content': 'Código de saída: 1\nerro'},
            {'role': 'tool', 'tool_call_id': refused['id'], 'content': 'Execução recusada pelo usuário.'},
            {'role': 'assistant', 'content': '```python\n  print("✓ Leu arquivo")\n```'}]
        lines = terminal.lines(28)
        self.assertEqual(next(line for line in lines if 'Comentário que' in line).style, 'comment')
        self.assertEqual(next(line for line in lines if 'público da IA' in line).style, 'comment')
        self.assertTrue(all(line.style == 'user' for line in lines if line.startswith('› ')))
        # Ações ocupam uma linha: marcador colorido, rótulo legível e detalhe discreto, cortado com reticências.
        action_lines = [line for line in lines if line.style == 'muted' and line.spans]
        self.assertEqual(len(action_lines), 3)
        self.assertTrue(action_lines[0].startswith('  ✓ Leu') and action_lines[0].endswith('…'))
        self.assertEqual(action_lines[0].spans, ((2, 3, 'ok'), (3, 8, 'text')))
        for line in action_lines[1:]:
            self.assertTrue('Falha' in line or 'Recusado' in line)
            self.assertEqual({mark for _, _, mark in line.spans}, {'warning'})
        terminal.show_details = True
        detailed = terminal.lines(28)  # Ctrl+O quebra a ação em linhas em vez de cortar.
        self.assertFalse(any(line.endswith('…') for line in detailed if getattr(line, 'spans', ())))
        self.assertGreater(len([line for line in detailed if 'long-path' in line]), 2)
        terminal.show_details = False
        self.assertTrue(all(line.style == 'code' for line in lines if 'print(' in line))  # Código nunca vira ação.
        # The actual drawing path consumes the same styles after wrapping/scroll.
        terminal.view.palette.styles.update(comment=101, action=102, warning=103, text=104, code=105, ok=106, muted=107)
        screen = Screen((40, 80))
        with patch('centaur_cli.appearance.curses.curs_set'):
            terminal.draw(screen)
        output = screen.output
        self.assertEqual(next(style for _, _, text, style in output if 'Comentário que' in text), 101)
        self.assertEqual(next(style for _, _, text, style in output if '✓ Leu frontend' in text), 107)  # Linha discreta…
        self.assertEqual(next(style for _, _, text, style in output if text == '✓'), 106)  # …com o marcador em verde
        self.assertEqual(next(style for _, _, text, style in output if text.strip() == 'Leu'), 104)  # e o rótulo legível.
        self.assertEqual(next(style for _, _, text, style in output if text == '!'), 103)
        self.assertEqual(next(style for _, _, text, style in output if text.startswith(' Falha')), 103)
        self.assertEqual(next(style for _, _, text, style in output if 'print(' in text), 105)
        with patch.dict('os.environ', {'NO_COLOR': '1'}):
            palette = Palette()
            palette.initialize()
        self.assertNotEqual(palette.styles['action'], palette.styles['comment'])

    def test_progress_tool_has_no_side_effects_and_redacts_secrets(self):
        tools = ProjectTools(self.root, lambda _: self.fail('Progress requested approval'), protected_keys=('secret',))
        self.assertEqual(tools.execute('report_progress', {'message': 'Conferindo secret'}), 'Conferindo [CHAVE OCULTA]')
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertIn('Erro na ferramenta', tools.execute('report_progress', {'message': 'x' * 281}))

    def test_markdown_preserves_literal_code(self):
        self.assertEqual(readable_markdown('## Resultado\n**Pronto** e `teste`\n```python\nvalue = "**literal**"\n```'),
                         'Resultado\nPronto e teste\n  Código · python\n  value = "**literal**"')

    def test_title_request_is_tool_free_and_does_not_include_private_reasoning(self):
        class Client:
            secrets = ()
            def complete(client, model, messages, tools):
                self.assertEqual(model, 'model')
                self.assertEqual(tools, [])
                self.assertNotIn('PRIVATE', json.dumps(messages))
                return {'content': 'Revisão do fluxo de desenvolvimento'}
        messages = [{'role': 'user', 'content': 'Revisar'}, {'role': 'assistant', 'content': 'Validado', 'reasoning': 'PRIVATE'}]
        self.assertEqual(generate_title(Client(), 'model', messages), 'Revisão do fluxo de desenvolvimento')

    def test_invalid_titles_and_secret_replies_are_discarded(self):
        class Client:
            secrets = ('private-key',)
            title = ''
            def complete(client, *args): return {'content': client.title}
        client = Client()
        messages = [{'role': 'user', 'content': 'Revisar'}, {'role': 'assistant', 'content': 'Pronto'}]
        for title in ('', 'x' * 61, 'line\nbreak', 'private-key', '/home/user/project', 'user@example.org'):
            client.title = title
            self.assertIsNone(generate_title(client, 'model', messages))

    def test_late_title_preserves_new_messages_and_manual_rename(self):
        chat = self.terminal.chat
        self.store.save(chat)
        newer = dict(chat, messages=[{'role': 'user', 'content': 'New content'}])
        self.store.save(newer)
        generated = self.store.generated_title(chat['id'], 'Título da IA')
        self.assertEqual(generated['messages'], newer['messages'])
        self.assertTrue(generated['title_generated'])
        self.assertIsNone(self.store.generated_title(chat['id'], 'Outro título'))
        manual = self.store.rename(chat['id'], 'Título manual')
        self.assertIsNone(self.store.generated_title(chat['id'], 'Título atrasado'))
        self.assertEqual(self.store.list()[0]['title'], manual['title'])

    def test_title_event_is_deferred_during_work_and_does_not_recreate_deleted_chat(self):
        terminal = self.terminal
        self.store.save(terminal.chat)
        terminal.busy = True
        terminal.events.put(('title', (terminal.chat['id'], 'Título gerado')))
        terminal.drain_events()
        self.assertEqual(terminal.chat['title'], 'Novo chat')
        terminal.events.put(('done', 'Pronto.'))
        terminal.drain_events()
        self.assertEqual(terminal.chat['title'], 'Título gerado')
        removed = self.store.new('model')
        self.store.save(removed)
        self.store.delete(removed['id'])
        terminal.events.put(('title', (removed['id'], 'Resultado atrasado')))
        terminal.drain_events()
        self.assertFalse(self.store.path(removed['id']).exists())

    def test_title_failure_leaves_response_and_navigation_available(self):
        class Client:
            def complete(client, *args): raise RuntimeError('offline')
        terminal = self.terminal
        terminal.chat['messages'] = [{'role': 'user', 'content': 'Olá'}, {'role': 'assistant', 'content': 'Resposta preservada'}]
        self.store.save(terminal.chat)
        terminal.make_title(terminal.chat['id'], Client(), 'model', terminal.chat['messages'])
        terminal.drain_events()
        self.assertIn('Resposta preservada', '\n'.join(terminal.lines(70)))
        self.assertFalse(terminal.busy)
        self.assertEqual(terminal.chat['title'], 'Novo chat')
