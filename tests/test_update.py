import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('centaur_update', Path(__file__).resolve().parents[1] / 'centaur-driven-update/scripts/migrate.py')
update = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(update)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, name, body):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return path

    def test_moves_preserves_backup_and_repeats_without_changes(self):
        self.put('graphify-out/graph.json', '{"nodes":[]}')
        self.put('.centaur/memory-pending/item.md', 'pending')
        contract = self.put('.centaur/contracts/approved.json', '{"immutable":true}')
        self.put('docs/system/manual.md', 'human authored')
        self.put('docs/system/generated.md', 'generated')
        self.put('AGENTS.md', 'read docs/system/generated.md and graphify-out/graph.json')
        writes, removals = update.plan_migration(self.root, ['docs/system/generated.md'], ['AGENTS.md'])
        backup = update.apply_migration(self.root, writes, removals)
        self.assertEqual((self.root / '.centaur/graphify/graph.json').read_text(), '{"nodes":[]}')
        self.assertFalse((self.root / 'graphify-out').exists())
        self.assertEqual((self.root / backup / 'files/graphify-out/graph.json').read_text(), '{"nodes":[]}')
        self.assertEqual(contract.read_text(), '{"immutable":true}')
        self.assertTrue((self.root / 'docs/system/manual.md').exists())
        self.assertIn('.centaur/system/generated.md', (self.root / 'AGENTS.md').read_text())
        self.assertEqual(update.plan_migration(self.root, ['docs/system/generated.md'], ['AGENTS.md']), ({}, set()))

    def test_conflict_preserves_both_and_creates_nothing(self):
        self.put('graphify-out/graph.json', 'old')
        self.put('.centaur/graphify/graph.json', 'new')
        with self.assertRaisesRegex(ValueError, 'Conflito'):
            update.plan_migration(self.root)
        self.assertFalse((self.root / '.centaur/backups').exists())
        self.assertEqual((self.root / 'graphify-out/graph.json').read_text(), 'old')

    def test_failure_rolls_back_written_files(self):
        self.put('graphify-out/a', 'a')
        self.put('graphify-out/b', 'b')
        writes, removals = update.plan_migration(self.root)
        real_replace = update.os.replace
        def fail_second(source, target):
            if str(target).endswith('/b'):
                raise OSError('simulated failure')
            real_replace(source, target)
        with patch.object(update.os, 'replace', side_effect=fail_second):
            with self.assertRaises(OSError):
                update.apply_migration(self.root, writes, removals)
        self.assertTrue((self.root / 'graphify-out/a').exists())
        self.assertFalse((self.root / '.centaur/graphify/a').exists())

    def test_html_ownership_and_symlink_guard(self):
        self.put('andamento.html', 'my site')
        self.put('.centaur/andamento.html', '<!-- centaur-volante-redirect -->')
        _, removals = update.plan_migration(self.root)
        self.assertEqual(removals, {'.centaur/andamento.html'})
        (self.root / 'graphify-out').symlink_to(self.root / 'elsewhere')
        with self.assertRaisesRegex(ValueError, 'simbólico'):
            update.plan_migration(self.root)

    def test_required_dependency_failure_never_mutates(self):
        self.put('graphify-out/graph.json', '{}')
        with self.assertRaisesRegex(ValueError, 'clean-code'):
            update.check_dependencies(self.root, self.root / 'missing', None)
        skill = self.put('clean-code/SKILL.md', 'test')
        self.put('.centaur/workspace.json', '{"memory":{"backend":"ai-memory"}}')
        with self.assertRaisesRegex(ValueError, 'ai-memory configurado'):
            update.check_dependencies(self.root, skill, None)
        self.assertTrue((self.root / 'graphify-out/graph.json').exists())
        self.assertFalse((self.root / '.centaur/backups').exists())

    def test_rebases_links_between_moved_and_unmoved_documents(self):
        self.put('docs/system/a.md', '[B](b.md#part) [Manual](manual.md) [Code](../../src/app.py) [Web](https://example.com/x)\n[ref]: b.md\n```md\n[Example](b.md)\n```\n')
        self.put('docs/system/b.md', '# B')
        self.put('docs/system/manual.md', '# Manual')
        self.put('docs/guide.md', '[A](system/a.md)')
        self.put('src/app.py', 'code')
        docs = ['docs/system/a.md', 'docs/system/b.md']
        writes, removals = update.plan_migration(self.root, docs, ['docs/guide.md'])
        update.apply_migration(self.root, writes, removals)
        result = (self.root / '.centaur/system/a.md').read_text()
        self.assertIn('[B](b.md#part)', result)
        self.assertIn('[Manual](../../docs/system/manual.md)', result)
        self.assertIn('[Code](../../src/app.py)', result)
        self.assertIn('[Web](https://example.com/x)', result)
        self.assertIn('[ref]: b.md', result)
        self.assertIn('[Example](b.md)', result)
        self.assertEqual((self.root / 'docs/guide.md').read_text(), '[A](../.centaur/system/a.md)')

    def test_changed_source_after_inventory_aborts_without_deleting_it(self):
        source = self.put('graphify-out/graph.json', 'old')
        writes, removals = update.plan_migration(self.root)
        source.write_text('new content')
        with self.assertRaisesRegex(ValueError, 'após o inventário'):
            update.apply_migration(self.root, writes, removals)
        self.assertEqual(source.read_text(), 'new content')
        self.assertFalse((self.root / '.centaur/backups').exists())

    def test_moved_docs_mark_graph_stale_preserving_node_identity(self):
        graph = '{"nodes":[{"id":"docs/system/a.md","source_file":"docs/system/a.md"}]}'
        self.put('graphify-out/graph.json', graph)
        self.put('docs/system/a.md', '# A')
        writes, removals = update.plan_migration(self.root, ['docs/system/a.md'])
        update.apply_migration(self.root, writes, removals)
        self.assertEqual((self.root / '.centaur/graphify/graph.json').read_text(), graph)
        status = update.json.loads((self.root / '.centaur/graphify/migration.json').read_text())
        self.assertTrue(status['needs_sync'])
        self.assertEqual(status['moved_document_paths'], {'docs/system/a.md': '.centaur/system/a.md'})


if __name__ == '__main__':
    unittest.main()
