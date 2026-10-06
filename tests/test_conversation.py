import json
from pathlib import Path
import tempfile
import unittest

from centaur_cli.conversation import generate_title, readable_markdown, tool_activity
from centaur_cli.history import ChatStore
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools


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
