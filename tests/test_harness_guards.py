"""Freios do turno, prompt fixo, gravação protegida, posse de arquivos, histórico e sandbox."""
import json
import os
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from centaur_cli import grants, sandbox
from centaur_cli.agent import run_turn
from centaur_cli.history import ChatStore
from centaur_cli.openrouter import ModelReply
from centaur_cli.subagents import SubagentTools
from centaur_cli.tools import ProjectTools, glob_matcher


def call(name, identifier, **arguments):
    return {'id': identifier, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(arguments)}}


class Base(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name, 'project').resolve()
        self.root.mkdir()
        environment = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(Path(temporary.name, 'config'))})
        environment.start()
        self.addCleanup(environment.stop)
        self.store = ChatStore(self.root)
        self.chat = self.store.new('main')
        self.chat['messages'] = [{'role': 'user', 'content': 'Trabalhe'}]

    def client(self, replies):
        client = Mock(backend='openrouter', secrets=(), supports_cancellation=False, supports_streaming=False,
                      supports_progress=False, context_windows={})
        client.complete.side_effect = replies if callable(replies) else list(replies)
        return client

    def tools(self, mode='never', approve=lambda _: True):
        return ProjectTools(self.root, approve, approval_mode=mode)


class TurnGuardTests(Base):
    def test_identical_calls_with_the_same_result_are_flagged_on_the_third_time(self):
        replies = [{'role': 'assistant', 'content': None, 'tool_calls': [call('list_files', f'c{index}', path='.')]}
                   for index in range(3)] + [{'role': 'assistant', 'content': 'fim'}]
        run_turn(self.chat, self.client(replies), self.tools(), self.store, lambda: None)
        results = [message['content'] for message in self.chat['messages'] if message['role'] == 'tool']
        self.assertNotIn('Aviso do harness', results[0] + results[1])
        self.assertIn('mesmo resultado 3 vezes', results[2])

    def test_step_limit_pauses_the_turn_with_history_saved_and_can_be_disabled(self):
        endless = lambda *args, **options: {'role': 'assistant', 'content': None,
                                            'tool_calls': [call('report_progress', os.urandom(4).hex(), message='ainda')]}
        with patch.dict(os.environ, {'CENTAUR_TURN_STEPS': '4'}):
            client = self.client(endless)
            with self.assertRaisesRegex(RuntimeError, 'pausado após 4 chamadas'):
                run_turn(self.chat, client, self.tools(), self.store, lambda: None)
        self.assertEqual(client.complete.call_count, 4)
        self.assertEqual(len(self.store.list()[0]['messages']), 9)
        with patch.dict(os.environ, {'CENTAUR_TURN_STEPS': '0'}):
            replies = [endless() for _ in range(6)] + [{'role': 'assistant', 'content': 'fim'}]
            run_turn(self.chat, self.client(replies), self.tools(), self.store, lambda: None)

    def test_cost_limit_uses_only_what_this_turn_spent(self):
        self.chat['spend'] = {'requests': 9, 'input': 1, 'cached': 0, 'output': 1, 'cost': 5.0}
        reply = lambda *args, **options: ModelReply(
            {'role': 'assistant', 'content': None, 'tool_calls': [call('report_progress', os.urandom(4).hex(), message='x')]},
            usage={'prompt_tokens': 10, 'completion_tokens': 1, 'cost': 0.4})
        with patch.dict(os.environ, {'CENTAUR_TURN_COST': '1'}):
            client = self.client(reply)
            with self.assertRaisesRegex(RuntimeError, 'CENTAUR_TURN_COST'):
                run_turn(self.chat, client, self.tools(), self.store, lambda: None)
        self.assertEqual(client.complete.call_count, 3)

    def test_system_prompt_stays_identical_when_a_command_is_granted_mid_turn(self):
        def reply(model, payload, definitions, **options):
            prompts.append(payload[0]['content'])
            if len(prompts) == 1:
                grants.grant(self.root, 'make deploy')
                return {'role': 'assistant', 'content': None, 'tool_calls': [call('list_files', 'a', path='.')]}
            return {'role': 'assistant', 'content': 'fim'}
        prompts = []
        run_turn(self.chat, self.client(reply), self.tools(), self.store, lambda: None)
        self.assertEqual(prompts[0], prompts[1])
        self.chat['messages'].append({'role': 'user', 'content': 'de novo'})
        run_turn(self.chat, self.client(reply), self.tools(), self.store, lambda: None)
        self.assertIn('make deploy', prompts[-1])


class FileGuardTests(Base):
    def test_unreviewed_overwrite_needs_a_fresh_read_but_confirmation_and_new_files_do_not(self):
        target = self.root / 'a.txt'
        target.write_text('do usuário\n')
        tools = self.tools()
        self.assertIn('não foi lido', tools.execute('write_file', {'path': 'a.txt', 'content': 'x\n'}))
        tools.execute('read_file', {'path': 'a.txt'})
        target.write_text('mudou por fora, maior\n')
        self.assertIn('mudou desde', tools.execute('write_file', {'path': 'a.txt', 'content': 'x\n'}))
        self.assertEqual(target.read_text(), 'mudou por fora, maior\n')
        tools.execute('read_file', {'path': 'a.txt'})
        self.assertIn('gravado', tools.execute('write_file', {'path': 'a.txt', 'content': 'x\n'}))
        # O próprio agente acabou de gravar: sabe o que há no arquivo.
        self.assertIn('gravado', tools.execute('write_file', {'path': 'a.txt', 'content': 'y\n'}))
        self.assertIn('gravado', tools.execute('write_file', {'path': 'novo.txt', 'content': 'n\n'}))
        (self.root / 'b.txt').write_text('b\n')
        seen = []
        asking = self.tools('ask', lambda preview: seen.append(str(preview)) or True)
        self.assertIn('gravado', asking.execute('write_file', {'path': 'b.txt', 'content': 'c\n'}))
        self.assertIn('-b', seen[0])

    def test_write_replaces_the_file_keeping_its_mode_and_hard_links(self):
        script = self.root / 'run.sh'
        script.write_text('echo a\n')
        script.chmod(0o750)
        tools = self.tools()
        tools.execute('edit_file', {'path': 'run.sh', 'old_string': 'a', 'new_string': 'b'})
        self.assertEqual((script.read_text(), script.stat().st_mode & 0o777), ('echo b\n', 0o750))
        os.link(script, self.root / 'alias.sh')
        tools.execute('edit_file', {'path': 'run.sh', 'old_string': 'b', 'new_string': 'c'})
        self.assertEqual((self.root / 'alias.sh').read_text(), 'echo c\n')
        self.assertEqual([item.name for item in self.root.iterdir() if item.name.endswith('.tmp')], [])

    def test_executor_cannot_write_outside_its_owned_files(self):
        tools = self.tools()
        tools.owned = [[glob_matcher('src/**')], [glob_matcher('src/api/*.py'), glob_matcher('README.md')]]
        self.assertIn('gravado', tools.execute('write_file', {'path': 'src/api/a.py', 'content': 'a\n'}))
        self.assertIn('fora dos arquivos de posse', tools.execute('write_file', {'path': 'src/web/b.py', 'content': 'b\n'}))
        self.assertIn('fora dos arquivos de posse', tools.execute('write_file', {'path': 'README.md', 'content': 'b\n'}))
        self.assertFalse((self.root / 'README.md').exists())
        self.assertIn('gravado', tools.execute('write_file', {'path': '.centaur/implements/x.md', 'content': 'r\n'}))


class OwnershipTests(Base):
    def test_delegated_task_with_files_is_held_to_them(self):
        class Client:
            backend, allows_model_routing, calls = 'openrouter', True, 0
            def complete(inner, model, messages, tools, **options):
                inner.calls += 1
                if inner.calls == 1:
                    return ModelReply({'role': 'assistant', 'content': None, 'tool_calls': [
                        call('write_file', 'a', path='src/a.py', content='a\n'),
                        call('write_file', 'b', path='other/b.py', content='b\n')]}, 'provider/model')
                return ModelReply({'role': 'assistant', 'content': 'Relatório.'}, 'provider/model')
        tools = SubagentTools(self.tools(), Client(), 'a' * 32, lambda _: None)
        self.assertIn('files deve listar', tools.execute('delegate_task', {'title': 't', 'task': 'x', 'files': []}))
        result = json.loads(tools.execute('delegate_task', {'title': 't', 'task': 'Edite src.', 'files': ['src/**']}))
        self.assertEqual(result['status'], 'reported')
        self.assertTrue((self.root / 'src/a.py').exists())
        self.assertFalse((self.root / 'other/b.py').exists())
        history = json.loads(Path(result['history']).read_text())
        self.assertIn('fora dos arquivos de posse', history['messages'][-2]['content'])


class HistoryTests(Base):
    def test_repeated_saves_do_not_reread_the_transcript_and_creation_stays_immutable(self):
        self.store.save(self.chat)
        created = self.chat['created']
        with patch.object(Path, 'read_text', side_effect=AssertionError('transcript re-read')):
            self.chat['created'] = 'alterado'
            self.store.save(self.chat)
        self.assertEqual(self.store.list()[0]['created'], created)


@unittest.skipUnless(shutil.which('bwrap'), 'requires bubblewrap')
class SandboxTests(Base):
    def setUp(self):
        super().setUp()
        environment = patch.dict(os.environ, {'CENTAUR_SANDBOX': '1', 'DEPLOY_TOKEN': 'segredo-do-ambiente'})
        environment.start()
        self.addCleanup(environment.stop)
        sandbox.PROBED.clear()
        if sandbox.wrap(self.root, 'true') is None:
            self.skipTest('bubblewrap cannot create namespaces here')
        self.asked = []
        self.auto = self.tools('auto', lambda request: self.asked.append(str(request)) or False)

    def run_command(self, command, **options):
        return self.auto.execute('run_command', {'command': command, **options})

    def test_auto_runs_unrecognized_commands_isolated_without_asking(self):
        (self.root / '.git').mkdir()
        (self.root / '.env').write_text('SENHA=1\n')
        result = self.run_command('echo feito > out.txt; cat .env; echo "[$DEPLOY_TOKEN]"; touch .git/hook; touch "$HOME/fora" /etc/fora')
        self.assertEqual(self.asked, [])
        self.assertIn('Executado em sandbox', result)
        self.assertIn('[]', result)
        self.assertNotIn('SENHA', result)
        self.assertEqual((self.root / 'out.txt').read_text(), 'feito\n')
        self.assertFalse((self.root / '.git' / 'hook').exists())
        self.assertFalse((Path.home() / 'fora').exists())
        offline = self.run_command('python3 -c "import socket; socket.create_connection((\'1.1.1.1\', 80), 2)"')
        self.assertNotIn('Código de saída: 0', offline)

    def test_outside_sandbox_asks_and_other_modes_or_a_disabled_sandbox_are_unchanged(self):
        self.assertIn('recusada', self.run_command('touch a.txt', outside_sandbox=True))
        self.assertEqual(len(self.asked), 1)
        ask = self.tools('ask', lambda request: self.asked.append(str(request)) or False)
        self.assertIn('recusada', ask.execute('run_command', {'command': 'touch a.txt'}))
        with patch.dict(os.environ, {'CENTAUR_SANDBOX': '0'}):
            self.assertIn('recusada', self.run_command('touch a.txt'))
        self.assertFalse((self.root / 'a.txt').exists())
        self.assertEqual(len(self.asked), 3)


if __name__ == '__main__':
    unittest.main()
