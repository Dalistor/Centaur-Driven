import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('centaur_install', Path(__file__).resolve().parents[1] / 'scripts/install.py')
install = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'source'
        self.target = self.base / 'skills'
        self.root.mkdir()
        self.target.mkdir()
        self.put(self.root / 'centaur_cli/skills/check/SKILL.md', 'new skill')
        self.put(self.target / 'check/SKILL.md', 'old skill')
        self.put(self.target / 'centaur-driven-commitAndPush/SKILL.md', 'obsolete')
        self.put(self.target / 'other/SKILL.md', 'unrelated')

    def put(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)

    def test_dry_run_then_replace_and_remove_obsolete_idempotently(self):
        self.put(self.root / 'centaur_cli/skills/check/__pycache__/x.pyc', 'cache')
        result = install.install(self.root, [self.target])
        self.assertFalse(result['applied'])
        self.assertEqual((self.target / 'check/SKILL.md').read_text(), 'old skill')
        result = install.install(self.root, [self.target], True)
        self.assertEqual((self.target / 'check/SKILL.md').read_text(), 'new skill')
        self.assertFalse((self.target / 'check/__pycache__').exists())
        self.assertFalse((self.target / 'centaur-driven-commitAndPush').exists())
        self.assertEqual((self.target / 'other/SKILL.md').read_text(), 'unrelated')
        self.assertEqual((Path(result['backup']) / '0/check/SKILL.md').read_text(), 'old skill')
        self.assertEqual(install.install(self.root, [self.target], True)['changed'], [])

    def test_failure_restores_previous_installation(self):
        real_replace = install.os.replace
        def fail_publish(source, destination):
            if Path(source).name == 'check' and Path(destination).parent == self.target:
                raise OSError('publish failed')
            real_replace(source, destination)
        with patch.object(install.os, 'replace', side_effect=fail_publish):
            with self.assertRaises(OSError):
                install.install(self.root, [self.target], True)
        self.assertEqual((self.target / 'check/SKILL.md').read_text(), 'old skill')
        self.assertTrue((self.target / 'centaur-driven-commitAndPush/SKILL.md').exists())

    def test_renamed_skill_migrates_legacy_installation_with_backup(self):
        legacy = self.target / 'centaur-driven-check/SKILL.md'
        self.put(legacy, 'legacy skill')
        preview = install.install(self.root, [self.target])
        self.assertIn(str(legacy.parent), preview['remove'])
        self.assertTrue(legacy.exists())
        result = install.install(self.root, [self.target], True)
        self.assertFalse(legacy.exists())
        self.assertEqual((self.target / 'check/SKILL.md').read_text(), 'new skill')
        self.assertEqual((Path(result['backup']) / '0/centaur-driven-check/SKILL.md').read_text(), 'legacy skill')
        self.assertEqual(install.install(self.root, [self.target], True)['changed'], [])

    def test_legacy_installation_survives_failed_migration(self):
        legacy = self.target / 'centaur-driven-check/SKILL.md'
        self.put(legacy, 'legacy skill')
        real_replace = install.os.replace
        def fail_remove(source, destination):
            if Path(source) == legacy.parent:
                raise OSError('legacy removal failed')
            real_replace(source, destination)
        with patch.object(install.os, 'replace', side_effect=fail_remove):
            with self.assertRaises(OSError):
                install.install(self.root, [self.target], True)
        self.assertEqual(legacy.read_text(), 'legacy skill')
        self.assertEqual((self.target / 'check/SKILL.md').read_text(), 'old skill')

    def test_memory_moves_to_internal_resources_with_backup(self):
        self.put(self.root / 'centaur_cli/skills/_internal/memory/SKILL.md', 'internal memory')
        self.put(self.root / 'centaur_cli/skills/_internal/memory/references/contract.md', 'contract')
        for name in ('memory', 'centaur-driven-memory'):
            self.put(self.target / name / 'SKILL.md', name)
        preview = install.install(self.root, [self.target])
        self.assertEqual(preview['install'], ['check'])
        self.assertEqual(preview['resources'], ['_internal'])
        self.assertTrue((self.target / 'memory/SKILL.md').exists())
        result = install.install(self.root, [self.target], True)
        self.assertEqual((self.target / '_internal/memory/references/contract.md').read_text(), 'contract')
        for name in ('memory', 'centaur-driven-memory'):
            self.assertFalse((self.target / name).exists())
            self.assertEqual((Path(result['backup']) / '0' / name / 'SKILL.md').read_text(), name)
        self.assertEqual(install.install(self.root, [self.target], True)['changed'], [])

    def test_internal_publish_failure_preserves_public_memory(self):
        self.put(self.root / 'centaur_cli/skills/_internal/memory/SKILL.md', 'internal memory')
        self.put(self.target / 'memory/SKILL.md', 'previous memory')
        self.put(self.target / '_internal/memory/SKILL.md', 'previous internal')
        real_replace = install.os.replace
        def fail_publish(source, destination):
            if Path(source).name == '_internal' and Path(destination).parent == self.target:
                raise OSError('internal publish failed')
            real_replace(source, destination)
        with patch.object(install.os, 'replace', side_effect=fail_publish):
            with self.assertRaises(OSError):
                install.install(self.root, [self.target], True)
        self.assertEqual((self.target / 'memory/SKILL.md').read_text(), 'previous memory')
        self.assertEqual((self.target / '_internal/memory/SKILL.md').read_text(), 'previous internal')
        self.assertEqual((self.target / 'check/SKILL.md').read_text(), 'old skill')

    def test_symlink_is_rejected_without_touching_unrelated_target(self):
        self.put(self.base / 'outside/SKILL.md', 'outside')
        (self.target / 'linked').symlink_to(self.base / 'outside')
        self.put(self.root / 'centaur_cli/skills/linked/SKILL.md', 'replacement')
        with self.assertRaisesRegex(ValueError, 'simbólico'):
            install.install(self.root, [self.target], True)
        self.assertEqual((self.base / 'outside/SKILL.md').read_text(), 'outside')
        self.assertFalse((self.root / '.centaur/backups').exists())

    def test_multiple_targets_failure_rolls_back_first_target(self):
        second = self.base / 'second'
        second.mkdir()
        self.put(second / 'check/SKILL.md', 'second old')
        real_replace = install.os.replace
        def fail_second(source, destination):
            if Path(source).name == 'check' and Path(destination).parent == second:
                raise OSError('second failed')
            real_replace(source, destination)
        with patch.object(install.os, 'replace', side_effect=fail_second):
            with self.assertRaises(OSError):
                install.install(self.root, [self.target, second], True)
        self.assertEqual((self.target / 'check/SKILL.md').read_text(), 'old skill')
        self.assertTrue((self.target / 'centaur-driven-commitAndPush').exists())
        self.assertEqual((second / 'check/SKILL.md').read_text(), 'second old')


if __name__ == '__main__':
    unittest.main()
