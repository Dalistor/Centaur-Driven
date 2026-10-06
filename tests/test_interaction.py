import curses
import json
from pathlib import Path
import queue
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import sys

from centaur_cli.agent import run_turn
from centaur_cli.computer import ComputerSession, COMPUTER_TOOLS
from centaur_cli.history import ChatStore
from centaur_cli.interaction import ASK_USER, QuestionPicker, TurnCancelled
from centaur_cli.native_client import NativeClient, reply_schema
from centaur_cli.terminal import Terminal
from centaur_cli.tools import ProjectTools
from centaur_cli.vision import split_images, native_input
from test_terminal_settings import Screen


class Image:
    """Backend fixture independent of optional Pillow installation."""
    def __init__(self, width=3200, height=2000):
        self.width, self.height = width, height
    @property
    def size(self): return self.width, self.height
    def convert(self, mode): return self
    def thumbnail(self, size): self.width, self.height = size
    def save(self, output, format): output.write(b'\x89PNG\r\n\x1a\nfixture')


class Desktop:
    def __init__(self): self.actions, self.captures = [], 0
    def capture(self):
        self.captures += 1
        return Image()
    def perform(self, action, x, y, arguments): self.actions.append((action, x, y, arguments))


class InteractionFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ChatStore(self.root)
        self.terminal = Terminal(self.root, 'model', self.store, None)


class InteractionTests(InteractionFixture):
    def test_turn_can_execute_more_than_twenty_steps(self):
        class Client:
            count = 0
            def complete(client, *args):
                client.count += 1
                if client.count > 25:
                    return {'role': 'assistant', 'content': 'Concluído'}
                return {'role': 'assistant', 'content': 'Trabalhando', 'tool_calls': [{
                    'id': str(client.count), 'function': {'name': 'report_progress',
                    'arguments': json.dumps({'message': str(client.count)})}}]}
        client = Client()
        run_turn(self.terminal.chat, client, ProjectTools(self.root, lambda _: False), self.store, lambda: None)
        self.assertEqual(client.count, 26)
        self.assertEqual(sum(m['role'] == 'tool' for m in self.terminal.chat['messages']), 25)

    def test_cancelled_model_reply_executes_no_tools(self):
        cancel = threading.Event()
        class Client:
            def complete(client, *args):
                cancel.set()
                return {'role': 'assistant', 'tool_calls': [{'id': 'write', 'function': {
                    'name': 'write_file', 'arguments': '{"path":"bad","content":"bad"}'}}]}
        tools = ProjectTools(self.root, lambda _: True, cancel_event=cancel)
        with self.assertRaises(TurnCancelled):
            run_turn(self.terminal.chat, Client(), tools, self.store, lambda: None)
        self.assertFalse((self.root / 'bad').exists())
        self.assertEqual(self.terminal.chat['messages'], [])

    def test_question_options_custom_validation_skip_and_draft_preservation(self):
        terminal = self.terminal
        terminal.draft = 'rascunho para depois'
        terminal.cursor = 3
        picker = QuestionPicker('Qual conexão?', ['Codex', 'Claude'], queue.Queue())
        terminal.events.put(('question', picker))
        terminal.drain_events()
        terminal.handle(curses.KEY_DOWN)
        terminal.handle(curses.KEY_DOWN)
        terminal.handle('\n')
        self.assertIn('Digite', picker.error)
        for character in 'OpenRouter': terminal.handle(character)
        terminal.handle('\n')
        self.assertEqual(picker.answer.get_nowait(), {'status': 'answered', 'answer': 'OpenRouter'})
        self.assertEqual(terminal.draft, 'rascunho para depois')
        self.assertEqual(terminal.cursor, 3)
        picker = QuestionPicker('Continuar?', ['Sim'], queue.Queue())
        terminal.question = picker
        terminal.handle('\x1b')
        self.assertEqual(picker.answer.get_nowait()['status'], 'skipped')

    def test_question_secret_is_not_sent(self):
        picker = QuestionPicker('Qual valor?', [], queue.Queue())
        picker.text = 'private-key'
        self.assertIsNone(picker.handle('\n', ('private-key',)))
        self.assertIn('Chave detectada', picker.error)

    def test_question_tool_validates_and_persists_answer_as_tool_result(self):
        tools = ProjectTools(self.root, lambda _: self.fail('Question is not approval'),
                             ask_user=lambda q, o: {'status': 'answered', 'answer': o[1]})
        self.assertEqual(json.loads(tools.execute('ask_user', {'question': 'Escolha', 'options': ['A', 'B']}))['answer'], 'B')
        for options in (['A', 'A'], [1], ['A'] * 4, 'A'):
            self.assertIn('Erro na ferramenta', tools.execute('ask_user', {'question': 'Escolha', 'options': options}))

    def test_question_waits_and_returns_to_same_turn_with_saved_answer(self):
        terminal = self.terminal
        class Client:
            allows_model_routing = False
            fixed_model = 'model'
            count = 0
            def model_catalog(client): return {'model': 'model'}
            def complete(client, model, messages, tools, **options):
                client.count += 1
                if client.count == 1:
                    return {'role': 'assistant', 'tool_calls': [{'id': 'question', 'function': {
                        'name': 'ask_user', 'arguments': '{"question":"Qual opção?","options":["A","B"]}'}}]}
                answer = json.loads(messages[-1]['content'])
                return {'role': 'assistant', 'content': 'Escolha: ' + answer['answer']}
        terminal.client = Client()
        terminal.chat.update(messages=[{'role': 'user', 'content': 'Decidir'}], title_attempted=True)
        terminal.busy = True
        worker = threading.Thread(target=terminal.work, args=(terminal.chat,))
        worker.start()
        deadline = time.monotonic() + 2
        while terminal.question is None and time.monotonic() < deadline:
            terminal.drain_events()
            time.sleep(0.01)
        self.assertIsNotNone(terminal.question)
        terminal.handle(curses.KEY_DOWN)
        terminal.handle('\n')
        worker.join(2)
        terminal.drain_events()
        self.assertFalse(terminal.busy)
        self.assertEqual(terminal.chat['messages'][-1]['content'], 'Escolha: B')
        self.assertIn('Respondeu · B', '\n'.join(terminal.lines(60)))
        self.assertEqual(self.store.list()[0]['messages'][-1]['content'], 'Escolha: B')

    def test_question_real_layout_minimum_size_and_long_copy(self):
        terminal = self.terminal
        terminal.question = QuestionPicker('O que fazer? ' * 15, ['Investigar ' * 10, 'Implementar', 'Validar'], queue.Queue())
        for size in ((12, 40), (24, 80), (40, 120)):
            screen = Screen(size)
            for selected in range(4):
                terminal.question.selected = selected
                terminal.draw(screen)
                self.assertIn(('Investigar', 'Implementar', 'Validar', 'Escrever')[selected], screen.text())

    def test_minimum_chat_size_keeps_final_response_visible(self):
        terminal = self.terminal
        terminal.chat['messages'] = [{'role': 'assistant', 'content': 'Resposta preservada.'}]
        screen = Screen((12, 40))
        terminal.draw(screen)
        self.assertIn('Resposta preservada.', screen.text())
        self.assertIn('Pedir aprovação', screen.text())

    def test_scroll_anchor_bounds_mouse_and_completion_priority(self):
        terminal = self.terminal
        self.assertEqual(terminal.transcript_start(100, 10, 60), 90)
        terminal.handle(curses.KEY_PPAGE)
        self.assertEqual(terminal.transcript_start(100, 10, 60), 85)
        self.assertEqual(terminal.transcript_start(110, 10, 60), 85)
        terminal.scroll_chat(9999)
        self.assertEqual(terminal.transcript_start(110, 10, 60), 0)
        terminal.handle('\x05')
        self.assertEqual(terminal.scroll, 0)
        with patch('centaur_cli.terminal.curses.getmouse', return_value=(0, 4, 6, 0, curses.BUTTON4_PRESSED)):
            terminal.handle(curses.KEY_MOUSE)
        self.assertEqual(terminal.scroll, 3)
        terminal.draft = '$'
        terminal.handle(curses.KEY_DOWN)
        self.assertEqual(terminal.scroll, 3)
        self.assertEqual(terminal.completion.selected, 1)

    def test_cancellation_wakes_approval_and_question_waiters(self):
        terminal = self.terminal
        terminal.busy = True
        errors = []
        def wait():
            try: terminal.ask_user('Pergunta', [])
            except TurnCancelled: errors.append('cancelled')
        thread = threading.Thread(target=wait)
        thread.start()
        terminal.handle('\x03')
        thread.join(1)
        terminal.drain_events()
        self.assertEqual(errors, ['cancelled'])
        self.assertIsNone(terminal.question)
        self.assertIsNone(terminal.approval)

    def test_command_cancellation_terminates_process_group(self):
        cancel = threading.Event()
        tools = ProjectTools(self.root, lambda _: True, cancel_event=cancel)
        timer = threading.Timer(0.15, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)
        started = time.monotonic()
        with self.assertRaises(TurnCancelled):
            tools.execute('run_command', {'command': 'sleep 30'})
        self.assertLess(time.monotonic() - started, 2)


class ComputerTests(InteractionFixture):
    def session(self, approval=lambda _: True, **options):
        desktop = Desktop()
        session = ComputerSession(approval, backend_factory=lambda: desktop, **options)
        self.addCleanup(session.close)
        return session, desktop

    def test_refused_capture_does_not_load_backend_or_capture(self):
        session, desktop = self.session(lambda _: False)
        self.assertIn('recusada', session.start('Testar aplicativo'))
        self.assertEqual(desktop.captures, 0)
        self.assertFalse(session.active)

    def test_continuous_capture_has_bounded_memory_and_expires(self):
        session, desktop = self.session(lifetime=0.08, interval=0.01)
        session.start('Verificar aplicativo')
        session.thread.join(1)
        self.assertGreater(desktop.captures, 2)
        self.assertFalse(session.active)
        self.assertEqual(list(session.frames), [])
        self.assertEqual(session.observation_messages(), [])

    def test_each_action_requires_approval_in_every_mode_and_uses_frame_coordinates(self):
        for mode in ('ask', 'auto', 'never'):
            prompts = []
            session, desktop = self.session(lambda prompt: prompts.append(prompt) or True)
            tools = ProjectTools(self.root, lambda _: self.fail('wrong approval path'), approval_mode=mode, computer=session)
            tools.execute('computer_start', {'purpose': 'Testar botão'})
            session.observation_messages()
            reference = session.reference[0]
            result = tools.execute('computer_action', {'action': 'click', 'frame_id': reference, 'x': 100, 'y': 50})
            self.assertIn('aplicada', result)
            self.assertEqual(len(prompts), 2)
            self.assertEqual(desktop.actions[0][:3], ('click', 200, 100))
            self.assertIn('Erro', tools.execute('computer_action', {'action': 'click', 'frame_id': reference, 'x': 100, 'y': 50}))
            self.assertEqual(len(desktop.actions), 1)
            session.close()

    def test_rejected_action_invalid_coordinates_and_cancel_do_not_move_pointer(self):
        allowed = [True, False]
        session, desktop = self.session(lambda _: allowed.pop(0))
        session.start('Testar')
        session.observation_messages()
        arguments = {'action': 'click', 'frame_id': session.reference[0], 'x': 5, 'y': 5}
        self.assertIn('recusada', session.execute('computer_action', arguments))
        with self.assertRaises(ValueError): session.execute('computer_action', dict(arguments, x=-1))
        self.assertEqual(desktop.actions, [])
        session.close()
        with self.assertRaises(ValueError): session.execute('computer_action', arguments)

    def test_partial_input_failure_stops_and_cannot_replay(self):
        session, desktop = self.session()
        session.start('Testar')
        session.observation_messages()
        with patch.object(desktop, 'perform', side_effect=RuntimeError('OS failed')):
            with self.assertRaisesRegex(RuntimeError, 'parcialmente'):
                session.execute('computer_action', {'action': 'click', 'frame_id': session.reference[0], 'x': 5, 'y': 5})
        self.assertFalse(session.active)
        self.assertIsNone(session.reference)

    def test_images_are_ephemeral_in_agent_loop_and_native_transports(self):
        session, desktop = self.session()
        session.start('Testar')
        tools = ProjectTools(self.root, lambda _: True, computer=session)
        requests = []
        class Client:
            def complete(client, model, messages, definitions):
                requests.append(messages)
                return {'role': 'assistant', 'content': 'Verificado'}
        run_turn(self.terminal.chat, Client(), tools, self.store, lambda: None)
        self.assertTrue(any(isinstance(m['content'], list) for m in requests[0]))
        self.assertNotIn('base64', self.store.path(self.terminal.chat['id']).read_text())
        conversation, images = split_images(requests[0])
        self.assertNotIn('base64', json.dumps(conversation))
        arguments, prompt = native_input('codex', self.root, ['codex', 'exec', '-'], 'prompt', images)
        self.assertEqual(arguments[-1], '-')
        self.assertIn('--image', arguments)
        for path in self.root.glob('frame-*.png'):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        arguments, prompt = native_input('claude', self.root, ['claude', '--print'], 'prompt', images)
        self.assertEqual(arguments[-2:], ['--input-format', 'stream-json'])
        message = json.loads(prompt)['message']
        self.assertEqual(message['content'][1]['source']['media_type'], 'image/png')

    def test_native_typed_schema_validates_arrays_and_integer_coordinates(self):
        with patch('centaur_cli.native_client.shutil.which', return_value='/fake/codex'):
            client = NativeClient('codex', 'model')
        self.assertTrue(reply_schema([ASK_USER, *COMPUTER_TOOLS]))
        for arguments in ({'question': 'Pergunta?', 'options': [3]},
                          {'question': 'Pergunta?', 'options': ['A', 'B', 'C', 'D']}):
            with self.assertRaises(ValueError):
                client.reply({'content': None, 'calls': [{'name': 'ask_user', 'arguments': arguments}]}, [ASK_USER])
        for x in ('1', True, 1.5):
            with self.assertRaises(ValueError):
                client.reply({'content': None, 'calls': [{'name': 'computer_action', 'arguments': {
                    'action': 'click', 'x': x, 'y': 1, 'frame_id': 1}}]}, COMPUTER_TOOLS)

    def test_native_clients_receive_image_bytes_and_delete_temporary_files(self):
        executable = self.root / 'native-fixture'
        executable.write_text('#!' + sys.executable + '\n' + '''import sys, json, base64
from pathlib import Path
args=sys.argv[1:]
text=sys.stdin.read()
Path(__file__).with_suffix('.directory').write_text(str(Path.cwd()))
if '--input-format' in args:
    message=json.loads(text)['message']['content']
    data=base64.b64decode(message[1]['source']['data'])
    assert data.startswith(b'\\x89PNG')
    assert 'base64' not in message[0]['text']
    print(json.dumps({'structured_output':{'content':'imagem recebida','calls':[]}}))
else:
    path=Path(args[args.index('--image')+1])
    assert path.read_bytes().startswith(b'\\x89PNG')
    assert 'base64' not in text
    Path(args[args.index('--output-last-message')+1]).write_text(json.dumps({'content':'imagem recebida','calls':[]}))
''')
        executable.chmod(0o700)
        session, desktop = self.session()
        session.start('Testar transporte')
        messages = session.observation_messages()
        for backend in ('codex', 'claude'):
            with patch('centaur_cli.native_client.shutil.which', return_value=str(executable)):
                client = NativeClient(backend, 'model')
            self.assertEqual(client.complete('model', messages, COMPUTER_TOOLS)['content'], 'imagem recebida')
            self.assertFalse(Path(executable.with_suffix('.directory').read_text()).exists())

    def test_native_cancellation_kills_real_pending_process(self):
        executable = self.root / 'native-fixture'
        executable.write_text('#!' + sys.executable + '\nimport time\ntime.sleep(30)\n')
        executable.chmod(0o700)
        with patch('centaur_cli.native_client.shutil.which', return_value=str(executable)):
            client = NativeClient('codex', 'model')
        cancel = threading.Event()
        timer = threading.Timer(0.15, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)
        started = time.monotonic()
        with self.assertRaises(TurnCancelled):
            client.complete('model', [], [], cancel_event=cancel)
        self.assertLess(time.monotonic() - started, 2)
