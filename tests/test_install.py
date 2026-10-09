import importlib.util
from pathlib import Path
import tempfile
import shutil
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
        self.put(self.root / 'skills/centaur-driven-check/SKILL.md', 'new skill')
        self.put(self.target / 'centaur-driven-check/SKILL.md', 'old skill')
        self.put(self.target / 'centaur-driven-commitAndPush/SKILL.md', 'obsolete')
        self.put(self.target / 'other/SKILL.md', 'unrelated')

    def put(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)

    def test_dry_run_then_replace_and_remove_obsolete_idempotently(self):
        self.put(self.root / 'skills/centaur-driven-check/__pycache__/x.pyc', 'cache')
        result = install.install(self.root, [self.target])
        self.assertFalse(result['applied'])
        self.assertEqual((self.target / 'centaur-driven-check/SKILL.md').read_text(), 'old skill')
        result = install.install(self.root, [self.target], True)
        self.assertEqual((self.target / 'centaur-driven-check/SKILL.md').read_text(), 'new skill')
        self.assertFalse((self.target / 'centaur-driven-check/__pycache__').exists())
        self.assertFalse((self.target / 'centaur-driven-commitAndPush').exists())
        self.assertEqual((self.target / 'other/SKILL.md').read_text(), 'unrelated')
        self.assertEqual((Path(result['backup']) / '0/centaur-driven-check/SKILL.md').read_text(), 'old skill')
        self.assertEqual(install.install(self.root, [self.target], True)['changed'], [])

    def test_failure_restores_previous_installation(self):
        real_replace = install.os.replace
        def fail_publish(source, destination):
            if Path(source).name == 'centaur-driven-check' and Path(destination).parent == self.target:
                raise OSError('publish failed')
            real_replace(source, destination)
        with patch.object(install.os, 'replace', side_effect=fail_publish):
            with self.assertRaises(OSError):
                install.install(self.root, [self.target], True)
        self.assertEqual((self.target / 'centaur-driven-check/SKILL.md').read_text(), 'old skill')
        self.assertTrue((self.target / 'centaur-driven-commitAndPush/SKILL.md').exists())

    def test_short_names_and_old_internal_resources_are_preserved(self):
        self.put(self.target / 'check/SKILL.md', 'unrelated short name')
        self.put(self.target / 'memory/SKILL.md', 'unrelated memory')
        self.put(self.target / '_internal/memory/SKILL.md', 'existing resources')
        result = install.install(self.root, [self.target], True)
        self.assertNotIn(str(self.target / 'check'), result['remove'])
        self.assertEqual((self.target / 'check/SKILL.md').read_text(), 'unrelated short name')
        self.assertEqual((self.target / 'memory/SKILL.md').read_text(), 'unrelated memory')
        self.assertEqual((self.target / '_internal/memory/SKILL.md').read_text(), 'existing resources')

    def test_obsolete_removal_failure_restores_previous_installation(self):
        obsolete = self.target / 'centaur-driven-commitAndPush'
        real_replace = install.os.replace
        def fail_remove(source, destination):
            if Path(source) == obsolete:
                raise OSError('obsolete removal failed')
            real_replace(source, destination)
        with patch.object(install.os, 'replace', side_effect=fail_remove):
            with self.assertRaises(OSError):
                install.install(self.root, [self.target], True)
        self.assertEqual((obsolete / 'SKILL.md').read_text(), 'obsolete')
        self.assertEqual((self.target / 'centaur-driven-check/SKILL.md').read_text(), 'old skill')

    def test_memory_is_installed_as_a_complete_public_skill(self):
        self.put(self.root / 'skills/centaur-driven-memory/SKILL.md', 'memory skill')
        self.put(self.root / 'skills/centaur-driven-memory/references/contract.md', 'contract')
        self.put(self.target / 'centaur-driven-memory/SKILL.md', 'previous memory')
        preview = install.install(self.root, [self.target])
        self.assertEqual(preview['install'], ['centaur-driven-check', 'centaur-driven-memory'])
        self.assertEqual((self.target / 'centaur-driven-memory/SKILL.md').read_text(), 'previous memory')
        result = install.install(self.root, [self.target], True)
        self.assertEqual((self.target / 'centaur-driven-memory/references/contract.md').read_text(), 'contract')
        self.assertEqual((Path(result['backup']) / '0/centaur-driven-memory/SKILL.md').read_text(), 'previous memory')
        self.assertFalse((self.target / '_internal').exists())
        self.assertEqual(install.install(self.root, [self.target], True)['changed'], [])

    def test_memory_publish_failure_restores_all_skills(self):
        self.put(self.root / 'skills/centaur-driven-memory/SKILL.md', 'memory skill')
        self.put(self.target / 'centaur-driven-memory/SKILL.md', 'previous memory')
        real_replace = install.os.replace
        def fail_publish(source, destination):
            if Path(source).name == 'centaur-driven-memory' and Path(destination).parent == self.target:
                raise OSError('memory publish failed')
            real_replace(source, destination)
        with patch.object(install.os, 'replace', side_effect=fail_publish):
            with self.assertRaises(OSError):
                install.install(self.root, [self.target], True)
        self.assertEqual((self.target / 'centaur-driven-memory/SKILL.md').read_text(), 'previous memory')
        self.assertEqual((self.target / 'centaur-driven-check/SKILL.md').read_text(), 'old skill')

    def test_symlink_is_rejected_without_touching_unrelated_target(self):
        self.put(self.base / 'outside/SKILL.md', 'outside')
        (self.target / 'centaur-driven-linked').symlink_to(self.base / 'outside')
        self.put(self.root / 'skills/centaur-driven-linked/SKILL.md', 'replacement')
        with self.assertRaisesRegex(ValueError, 'simbólico'):
            install.install(self.root, [self.target], True)
        self.assertEqual((self.base / 'outside/SKILL.md').read_text(), 'outside')
        self.assertFalse((self.root / '.centaur/backups').exists())

    def test_multiple_targets_failure_rolls_back_first_target(self):
        second = self.base / 'second'
        second.mkdir()
        self.put(second / 'centaur-driven-check/SKILL.md', 'second old')
        real_replace = install.os.replace
        def fail_second(source, destination):
            if Path(source).name == 'centaur-driven-check' and Path(destination).parent == second:
                raise OSError('second failed')
            real_replace(source, destination)
        with patch.object(install.os, 'replace', side_effect=fail_second):
            with self.assertRaises(OSError):
                install.install(self.root, [self.target, second], True)
        self.assertEqual((self.target / 'centaur-driven-check/SKILL.md').read_text(), 'old skill')
        self.assertTrue((self.target / 'centaur-driven-commitAndPush').exists())
        self.assertEqual((second / 'centaur-driven-check/SKILL.md').read_text(), 'second old')

    def test_complete_bundle_installs_for_three_clients_without_runtime(self):
        bundle = Path(__file__).resolve().parents[1]
        # Copy only the distribution inputs so backups stay in the temporary source.
        shutil.rmtree(self.root / 'skills')
        shutil.copytree(bundle / 'skills', self.root / 'skills')
        targets = [self.base / client / 'skills' for client in ('.agents', '.claude', '.gemini')]
        for target in targets:
            target.mkdir(parents=True)
        preview = install.install(self.root, targets)
        self.assertEqual(len(preview['install']), 12)
        self.assertTrue(all(not any(target.iterdir()) for target in targets))
        install.install(self.root, targets, True)
        for target in targets:
            self.assertEqual(sorted(p.name for p in target.iterdir()), preview['install'])
            for name in preview['install']:
                self.assertEqual(install.fingerprint(target / name), install.clean_fingerprint(self.root / 'skills' / name))
        self.assertEqual(install.install(self.root, targets, True)['changed'], [])


if __name__ == '__main__':
    unittest.main()
