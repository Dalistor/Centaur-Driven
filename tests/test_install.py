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
        self.base = Path(self.temp.name)
        self.root = self.base / 'source'
        self.target = self.base / 'skills'
        self.root.mkdir()
        self.target.mkdir()
        self.put(self.root / 'centaur-driven-check/SKILL.md', 'new skill')
        self.put(self.target / 'centaur-driven-check/SKILL.md', 'old skill')
        self.put(self.target / 'centaur-driven-commitAndPush/SKILL.md', 'obsolete')
        self.put(self.target / 'other/SKILL.md', 'unrelated')

    def put(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)

    def test_dry_run_then_replace_and_remove_obsolete_idempotently(self):
        self.put(self.root / 'centaur-driven-check/__pycache__/x.pyc', 'cache')
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

    def test_symlink_is_rejected_without_touching_unrelated_target(self):
        self.put(self.base / 'outside/SKILL.md', 'outside')
        (self.target / 'centaur-driven-linked').symlink_to(self.base / 'outside')
        self.put(self.root / 'centaur-driven-linked/SKILL.md', 'replacement')
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


if __name__ == '__main__':
    unittest.main()
