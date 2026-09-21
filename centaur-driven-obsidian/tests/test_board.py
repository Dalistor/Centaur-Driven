import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/sync_board.py'
spec = importlib.util.spec_from_file_location('sync_board', SCRIPT)
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def record(self, path, status='Pendente'):
        target = self.root / path / 'README.md'
        target.parent.mkdir(parents=True)
        target.write_text(f'# Compra\n\n**Status:** {status}\n**Responsável:** Ana\n**Spec mestre:** master/0001\n- [x] Task 01 — entregue\n- [ ] Task 02 — falta\n')

    def test_modules_preserve_identity_and_status(self):
        self.record('.centaur/specs/0001', 'Concluída')
        self.record('.centaur/modules/frontend/specs/0001', 'Bloqueada')
        (self.root / '.centaur/workspace.json').write_text(json.dumps({'scopes': {
            'master': {'specs': '.centaur/specs'},
            'frontend': {'specs': '.centaur/modules/frontend/specs'},
        }}))
        self.assertEqual(board.sync(self.root), 2)
        specs = board.read_specs(self.root)
        self.assertEqual([s['id'] for s in specs], ['master/0001', 'frontend/0001'])
        self.assertEqual([s['status'] for s in specs], ['Concluída', 'Bloqueada'])
        self.assertEqual(specs[1]['progress'], '1/2')
        canvas = json.loads((self.root / '.centaur/obsidian/Sistema/Quadro de specs.canvas').read_text())
        cards = [n for n in canvas['nodes'] if n['type'] == 'text']
        self.assertEqual(len(cards), 2)
        self.assertNotEqual(cards[0]['id'], cards[1]['id'])
        self.assertTrue(all('[Ver spec](file://' in n['text'] for n in cards))

    def test_initializer_preserves_human_content_and_is_idempotent(self):
        self.record('.centaur/specs/0001')
        system = self.root / '.centaur/obsidian/Sistema'
        system.mkdir(parents=True)
        (system / 'Visão geral.md').write_text('Texto humano')
        original = {'nodes': [{'id': 'custom', 'type': 'text', 'text': 'Meu mapa', 'x': 0, 'y': 0, 'width': 300, 'height': 200}], 'edges': []}
        map_path = system / 'Mapa do sistema.canvas'
        map_path.write_text(json.dumps(original))
        command = ['python3', str(SCRIPT.with_name('init_vault.py')), str(self.root), '--skill-source', str(SCRIPT.parents[1])]
        subprocess.run(command, check=True, capture_output=True)
        first = map_path.read_text()
        subprocess.run(command, check=True, capture_output=True)
        self.assertEqual(first, map_path.read_text())
        self.assertEqual((system / 'Visão geral.md').read_text(), 'Texto humano')
        self.assertEqual(json.loads(first)['nodes'][0], original['nodes'][0])
        self.assertTrue((self.root / '.centaur/obsidian/.agents/skills/centaur-driven-obsidian/references/team-workspace.md').exists())

    def test_unknown_status_is_visible_and_empty_workspace_supported(self):
        self.assertEqual(board.sync(self.root), 0)
        self.record('.centaur/specs/0001-ana-a7f2', 'Cancelada')
        record = board.read_specs(self.root)[0]
        self.assertEqual(record['status'], 'A verificar')
        self.assertIn('Cancelada', board.card_text(record))

    def test_config_cannot_escape_project(self):
        (self.root / '.centaur').mkdir()
        (self.root / '.centaur/workspace.json').write_text(json.dumps({'scopes': {'master': {'specs': '../outside'}}}))
        with self.assertRaises(ValueError):
            board.sync(self.root)


if __name__ == '__main__':
    unittest.main()
