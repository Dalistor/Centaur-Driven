from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from centaur_cli.interaction import TurnCancelled
from centaur_cli.permissions import TRUSTED_PATH
from centaur_cli.tools import ProjectTools, MAX_OUTPUT, glob_matcher, stop_background


class ToolTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.addCleanup(stop_background, self.root)
        self.approvals = []

    def tools(self, mode='never', allow=True, **options):
        return ProjectTools(self.root, lambda action: self.approvals.append(action) or allow,
                            approval_mode=mode, **options)

    def put(self, relative, content):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        return target

    def test_large_file_is_paged_with_an_explicit_continuation_instead_of_silent_truncation(self):
        self.put('big.txt', ''.join(f'linha {number} ' + 'x' * 60 + '\n' for number in range(1, 1201)))
        first = self.tools().execute('read_file', {'path': 'big.txt'})
        self.assertTrue(first.startswith('1\tlinha 1 '))
        self.assertLessEqual(len(first), MAX_OUTPUT)
        last = int(first.rsplit('offset=', 1)[1].split('.')[0]) - 1
        self.assertIn(f'[Linhas 1–{last} de 1200. Há mais conteúdo: continue com offset={last + 1}.]', first)
        self.put('short.txt', ''.join(f'{number}\n' for number in range(1, 901)))
        page = self.tools().execute('read_file', {'path': 'short.txt'})
        self.assertIn('[Linhas 1–400 de 900. Há mais conteúdo: continue com offset=401.]', page)
        self.assertNotIn('Há mais', self.tools().execute('read_file', {'path': 'short.txt', 'limit': 900}))
        rest = self.tools().execute('read_file', {'path': 'big.txt', 'offset': 1190, 'limit': 5})
        self.assertEqual(rest.split('\n')[0].split('\t')[0], '1190')
        self.assertIn('[Linhas 1190–1194 de 1200. Há mais conteúdo: continue com offset=1195.]', rest)
        self.assertIn('[Linhas 1199–1200 de 1200.]', self.tools().execute('read_file', {'path': 'big.txt', 'offset': 1199}))
        self.assertIn('além do fim', self.tools().execute('read_file', {'path': 'big.txt', 'offset': 5000}))
        self.assertIn('Erro', self.tools().execute('read_file', {'path': 'big.txt', 'offset': '2'}))

    def test_edit_replaces_only_a_unique_exact_excerpt_and_keeps_the_rest_of_a_large_file(self):
        body = ''.join(f'valor_{number} = {number}\n' for number in range(3000))
        self.put('settings.py', body)
        tools = self.tools()
        self.assertIn('Arquivo editado', tools.execute('edit_file', {'path': 'settings.py', 'old_string': 'valor_2999 = 2999', 'new_string': 'valor_2999 = 0'}))
        self.assertEqual((self.root / 'settings.py').read_text(), body.replace('valor_2999 = 2999', 'valor_2999 = 0'))
        self.assertIn('vezes', tools.execute('edit_file', {'path': 'settings.py', 'old_string': 'valor_1', 'new_string': 'v'}))
        self.assertIn('não encontrado', tools.execute('edit_file', {'path': 'settings.py', 'old_string': 'ausente', 'new_string': 'v'}))
        self.assertIn('não encontrado', tools.execute('edit_file', {'path': 'novo.py', 'old_string': 'a', 'new_string': 'b'}))
        self.put('dup.txt', 'a a a\n')
        self.assertIn('3 substituições', tools.execute('edit_file', {'path': 'dup.txt', 'old_string': 'a', 'new_string': 'b', 'replace_all': True}))
        self.assertEqual((self.root / 'dup.txt').read_text(), 'b b b\n')

    def test_view_image_attaches_a_project_image_once_and_never_reads_outside_the_project(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow ausente')
        import base64, io
        Image.new('RGB', (3200, 1200), 'white').save(self.root / 'shot.png')
        Image.new('RGB', (40, 20), 'red').save(self.root / 'small.jpg')
        self.put('notes.txt', 'texto')
        tools = self.tools()
        self.assertEqual(tools.observation_messages(), [])
        self.assertIn('reduzida para 1600×600', tools.execute('view_image', {'path': 'shot.png'}))
        self.assertIn('recorte [3000, 1000, 200, 100]', tools.execute('view_image', {'path': 'shot.png', 'region': [3000, 1000, 200, 100]}))
        self.assertIn('small.jpg · 40×20 px', tools.execute('view_image', {'path': 'small.jpg'}))
        self.assertIn('Até 3 imagens', tools.execute('view_image', {'path': 'small.jpg'}))
        message, = tools.observation_messages()
        sizes = []
        for block in message['content']:
            if block['type'] == 'image_url':
                prefix, data = block['image_url']['url'].split(',', 1)
                self.assertEqual(prefix, 'data:image/png;base64')
                sizes.append(Image.open(io.BytesIO(base64.b64decode(data))).size)
        self.assertEqual(sizes, [(1600, 600), (200, 100), (40, 20)])
        self.assertIn('não confiável', message['content'][0]['text'])
        self.assertEqual(tools.observation_messages(), [])  # Efêmera: entregue uma única vez.
        for arguments in ({'path': 'notes.txt'}, {'path': 'missing.png'}, {'path': '../outside.png'},
                          {'path': 'shot.png', 'region': [0, 0, 3201, 10]}, {'path': 'shot.png', 'region': [0, 0, 10]}):
            self.assertIn('Erro', tools.execute('view_image', arguments))
        self.assertEqual(tools.observation_messages(), [])

    def test_edit_preserves_windows_line_endings(self):
        target = self.root / 'crlf.txt'
        target.write_bytes(b'um\r\ndois\r\ntres\r\n')
        self.tools().execute('edit_file', {'path': 'crlf.txt', 'old_string': 'um\ndois', 'new_string': 'um\n2'})
        self.assertEqual(target.read_bytes(), b'um\r\n2\r\ntres\r\n')

    def test_changes_ask_with_a_diff_and_refusal_leaves_the_file_untouched(self):
        self.put('a.txt', 'um\ndois\n')
        tools = self.tools('ask', allow=False)
        self.assertIn('recusada', tools.execute('edit_file', {'path': 'a.txt', 'old_string': 'dois', 'new_string': 'três'}))
        self.assertIn('recusada', tools.execute('write_file', {'path': 'a.txt', 'content': 'um\n'}))
        self.assertEqual((self.root / 'a.txt').read_text(), 'um\ndois\n')
        self.assertIn('-dois\n+três', self.approvals[0])
        self.assertIn('-dois', self.approvals[1])
        self.assertIn('recusada', self.tools('auto', allow=False).execute('edit_file', {'path': '.env', 'old_string': 'x', 'new_string': 'y'})
                      if self.put('.env', 'x') else '')

    def search_fixture(self):
        self.put('src/app.py', 'import os\n\ndef principal():\n    return "Centaur"\n')
        self.put('src/web/view.ts', 'export const nome = "centaur"\n')
        self.put('docs/guia.md', 'Guia do Centaur\n')
        self.put('.oculto/segredo.py', 'Centaur oculto\n')
        self.put('node_modules/lib/index.py', 'Centaur dependência\n')
        self.put('.centaur/computer-permissions/chat.json', 'Centaur autorização\n')
        (self.root / 'fora').symlink_to(self.root.parent)

    def test_glob_and_grep_agree_with_and_without_ripgrep(self):
        self.search_fixture()
        engines = [None] + ([shutil.which('rg', path=TRUSTED_PATH)] if shutil.which('rg', path=TRUSTED_PATH) else [])
        for engine in engines:
            with self.subTest(ripgrep=bool(engine)), patch('centaur_cli.tools.shutil.which', return_value=engine):
                tools = self.tools('ask', allow=False)
                self.assertEqual(sorted(tools.execute('glob', {'pattern': '**/*.py', 'path': 'src'}).split('\n')), ['src/app.py'])
                self.assertEqual(sorted(tools.execute('glob', {'pattern': '*.{py,ts}', 'path': 'src'}).split('\n')), ['src/app.py', 'src/web/view.ts'])
                found = tools.execute('grep', {'pattern': 'centaur', 'ignore_case': True, 'path': 'src'})
                self.assertEqual(sorted(found.split('\n')), ['src/app.py:4:    return "Centaur"', 'src/web/view.ts:1:export const nome = "centaur"'])
                self.assertEqual(tools.execute('grep', {'pattern': 'Centaur', 'glob': '*.md', 'files_only': True}), 'docs/guia.md')
                everything = tools.execute('grep', {'pattern': 'Centaur'})
                self.assertNotIn('.oculto', everything)
                self.assertNotIn(self.root.parent.name + '/', everything.replace(str(self.root), ''))
                self.assertNotIn('autorização', tools.execute('grep', {'pattern': 'Centaur', 'path': '.centaur'}))
                self.assertIn('src/app.py-3-def principal():', tools.execute('grep', {'pattern': 'return', 'path': 'src/app.py', 'context': 1}))
                self.assertEqual(tools.execute('grep', {'pattern': 'inexistente'}), 'Nenhuma ocorrência.')
                self.assertIn('Erro', tools.execute('grep', {'pattern': 'x', 'path': '../'}))
                self.assertEqual(self.approvals, [])

    def test_glob_patterns(self):
        self.assertTrue(glob_matcher('*.py')('a/b/c.py'))
        self.assertTrue(glob_matcher('src/**/*.py')('src/c.py'))
        self.assertTrue(glob_matcher('src/**/*.py')('src/a/b/c.py'))
        self.assertFalse(glob_matcher('src/*.py')('src/a/c.py'))
        self.assertFalse(glob_matcher('*.py')('a.pyc'))

    def test_long_command_output_keeps_the_end_and_saves_the_full_text(self):
        result = self.tools().execute('run_command', {'command': 'seq 1 20000; echo FALHA-NO-FIM; exit 3'})
        self.assertTrue(result.startswith('Código de saída: 3\n1\n2\n'))
        self.assertLessEqual(len(result), MAX_OUTPUT)
        self.assertIn('FALHA-NO-FIM', result)
        self.assertIn('caracteres omitidos no meio', result)
        saved = self.root / result.rsplit('íntegra em ', 1)[1].split(' ')[0]
        self.assertTrue(saved.read_text().endswith('20000\nFALHA-NO-FIM\n'))
        self.assertIn('10000', self.tools().execute('grep', {'pattern': '^10000$', 'path': str(saved.relative_to(self.root))}))

    def test_command_timeout_is_chosen_per_call_and_reports_partial_output(self):
        started = time.monotonic()
        result = self.tools().execute('run_command', {'command': 'echo antes; sleep 30', 'timeout': 1})
        self.assertLess(time.monotonic() - started, 10)
        self.assertTrue(result.startswith('Comando encerrado: limite de 1 segundos'))
        self.assertIn('antes', result)
        self.assertIn('Erro', self.tools().execute('run_command', {'command': 'true', 'timeout': 601}))

    def test_background_command_reports_incremental_output_and_can_be_stopped(self):
        tools = self.tools('ask')
        started = tools.execute('run_command', {'command': 'echo $((40+2)); sleep 30; echo nunca', 'background': True})
        self.assertIn('Executar em segundo plano', self.approvals[0])
        identifier = started.split('id=')[1].split('.')[0]
        deadline = time.monotonic() + 5
        output = ''
        while '\n42' not in output and time.monotonic() < deadline:
            output += tools.execute('command_output', {'id': identifier, 'wait': 0})
            time.sleep(.05)
        self.assertIn('Em execução', output)
        self.assertIn('\n42', output)
        self.assertIn('Sem saída nova', tools.execute('command_output', {'id': identifier}))
        stopped = tools.execute('command_output', {'id': identifier, 'stop': True})
        self.assertIn('encerrado por sinal', stopped)
        self.assertNotIn('nunca', stopped)
        quick = tools.execute('run_command', {'command': 'echo fim; exit 4', 'background': True}).split('id=')[1].split('.')[0]
        self.assertTrue(tools.execute('command_output', {'id': quick, 'wait': 10}).startswith('Código de saída: 4\nfim'))
        self.assertIn('desconhecido', tools.execute('command_output', {'id': 'ffffffff'}))
        self.assertIn('recusada', self.tools('ask', allow=False).execute('run_command', {'command': 'sleep 30', 'background': True}))

    def test_waiting_for_a_background_command_stops_when_the_turn_is_cancelled(self):
        cancel = threading.Event()
        tools = self.tools(cancel_event=cancel)
        identifier = tools.execute('run_command', {'command': 'sleep 30', 'background': True}).split('id=')[1].split('.')[0]
        threading.Timer(.2, cancel.set).start()
        with self.assertRaises(TurnCancelled):
            tools.execute('command_output', {'id': identifier, 'wait': 30})


if __name__ == '__main__':
    unittest.main()
