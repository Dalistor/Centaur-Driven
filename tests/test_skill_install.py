import importlib.util
import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

from centaur_cli.completion import SkillCompletion
from centaur_cli.skill_catalog import names, read

PATH = Path(__file__).resolve().parents[1] / 'centaur_cli/skills/skill/scripts/install.py'
SPEC = importlib.util.spec_from_file_location('additional_skill_installer', PATH)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class SkillInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def archive(self, entries=None):
        output = io.BytesIO()
        with ZipFile(output, 'w') as archive:
            for name, body in (entries or {
                'repo-main/skills/example/SKILL.md': '---\nname: example\ndescription: Exemplo\n---\n# Exemplo\n',
                'repo-main/skills/example/references/guide.md': 'Guia completo',
                'repo-main/skills/example/assets/template.txt': 'Modelo',
                'repo-main/skills/example/scripts/run.sh': 'exit 99',
                'repo-main/other/private.txt': 'Não pertence à skill',
            }).items():
                archive.writestr(name, body)
        return output.getvalue()

    def install(self, payload=None, **options):
        return installer.install(self.root, 'owner/repo', 'skills/example',
                                 fetch=lambda *_: payload if payload is not None else self.archive(), **options)

    def test_complete_install_is_immediately_discoverable_and_not_executed(self):
        result = self.install()
        destination = self.root / '.centaur/skills/example'
        self.assertEqual((destination / 'assets/template.txt').read_text(), 'Modelo')
        self.assertEqual((destination / 'scripts/run.sh').read_text(), 'exit 99')
        self.assertFalse((self.root / '.centaur/skills/other').exists())
        self.assertEqual(result['invoke'], '@example')
        self.assertEqual(len(result['archive_sha256']), 64)
        completion = SkillCompletion(self.root)
        completion.update('@ex')
        self.assertEqual(completion.options, ['example'])
        self.assertIn('Guia completo', read('@example/references/guide.md', 1, self.root))
        self.assertIn('skill', names())

    def test_existing_installation_is_preserved_without_downloading(self):
        self.install()
        fetch = lambda *_: self.fail('Não deve baixar ao substituir uma instalação')
        with self.assertRaisesRegex(ValueError, 'já instalada'):
            installer.install(self.root, 'owner/repo', 'skills/example', fetch=fetch)
        self.assertIn('name: example', (self.root / '.centaur/skills/example/SKILL.md').read_text())

    def test_invalid_skill_and_traversal_never_publish(self):
        for entries in ({'repo-main/skills/example/README.md': 'não é skill'},
                        {'repo-main/skills/example/SKILL.md': '---\nname:\ndescription: Sem nome\n---\n'},
                        {'repo-main/skills/example/../../outside': 'escape'}):
            with self.assertRaises((OSError, ValueError)):
                self.install(self.archive(entries))
            self.assertFalse((self.root / '.centaur/skills/example').exists())
            self.assertFalse((self.root / 'outside').exists())

    def test_symlink_in_archive_and_symlink_destination_are_rejected(self):
        output = io.BytesIO()
        entry = ZipInfo('repo-main/skills/example/SKILL.md')
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        with ZipFile(output, 'w') as archive:
            archive.writestr(entry, '/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'Links'):
            self.install(output.getvalue())
        (self.root / '.centaur/skills').parent.mkdir(exist_ok=True)
        (self.root / '.centaur/skills').symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'link simbólico'):
            self.install()

    def test_failure_rolls_back_partial_install_and_publishes_skill_last(self):
        actual = installer.os.replace
        published = []
        def fail(source, target):
            published.append(Path(source).name)
            if Path(source).name == 'SKILL.md':
                raise OSError('falha na publicação')
            return actual(source, target)
        with patch.object(installer.os, 'replace', side_effect=fail):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(published[-1], 'SKILL.md')
        self.assertFalse((self.root / '.centaur/skills/example').exists())
        self.assertEqual(list((self.root / '.centaur/tmp').iterdir()), [])

    def test_download_failure_and_archive_limit_do_not_install(self):
        def unavailable(*_):
            raise OSError('download indisponível')
        with self.assertRaises(OSError):
            installer.install(self.root, 'owner/repo', 'skills/example', fetch=unavailable)
        with patch.object(installer, 'MAX_CONTENT', 1):
            with self.assertRaisesRegex(ValueError, 'limites'):
                self.install()
        self.assertFalse((self.root / '.centaur/skills/example').exists())

    def test_github_url_and_slash_ref_are_resolved_explicitly(self):
        self.assertEqual(installer.source(url='https://github.com/owner/repo/tree/main/skills/example'),
                         ('owner/repo', 'skills/example', 'main'))
        self.assertEqual(installer.source(ref='feature/skills', url='https://github.com/owner/repo/tree/feature/skills/skills/example'),
                         ('owner/repo', 'skills/example', 'feature/skills'))
        for options in ({'repo': 'owner/repo', 'path': '../outside'},
                        {'url': 'https://example.com/owner/repo/tree/main/skills/example'},
                        {'repo': '../repo', 'path': 'skills/example'}):
            with self.assertRaises(ValueError):
                installer.source(**options)


if __name__ == '__main__':
    unittest.main()
