import functools
import hashlib
import http.server
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest


SKILL = Path(__file__).resolve().parents[1] / 'skills/ops'
SCRIPTS = SKILL / 'scripts'


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipUnless(sys.platform.startswith('linux'), 'Static deployment requires Linux/GNU tools and flock')
class DeployTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.old = self.root / 'releases/old/site'
        self.old.mkdir(parents=True)
        (self.old / 'index.html').write_text('old content')
        (self.old / 'centaur-release.txt').write_text('old\n')
        (self.root / 'current').symlink_to(self.old)
        self.release = self.root / 'releases/new'
        site = self.release / 'site'
        site.mkdir(parents=True)
        (site / 'index.html').write_text('new content')
        (site / 'centaur-release.txt').write_text('new\n')
        (self.release / 'SHA256SUMS').write_text(''.join(
            f'{hashlib.sha256(path.read_bytes()).hexdigest()}  site/{path.name}\n'
            for path in sorted(site.iterdir())
        ))
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        sleep = self.bin / 'sleep'
        # Keep candidate startup waits, accelerate only post-switch failures and retries.
        sleep.write_text('#!/bin/sh\n[ "$1" != 0.1 ] || /bin/sleep 0.1\nexit 0\n')
        sleep.chmod(0o755)
        self.env = {**os.environ, 'PATH': f'{self.bin}:{os.environ["PATH"]}'}

    def server(self, directory):
        handler = functools.partial(QuietHandler, directory=str(directory))
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f'http://127.0.0.1:{server.server_port}/centaur-release.txt'

    def activate(self, health):
        return subprocess.run(
            ['bash', str(SCRIPTS / 'activate-static.sh'), str(self.root), 'new', health],
            env=self.env, capture_output=True, text=True, timeout=15,
        )

    def test_activates_healthy_release_and_preserves_old_and_shared_data(self):
        shared = self.root / 'shared'
        shared.mkdir()
        (shared / 'upload').write_text('user data')
        result = self.activate(self.server(self.root / 'current'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'current').resolve(), self.release / 'site')
        self.assertEqual((self.old / 'index.html').read_text(), 'old content')
        self.assertEqual((shared / 'upload').read_text(), 'user data')

    def test_corruption_blocks_activation(self):
        (self.release / 'site/index.html').write_text('corrupted transfer')
        result = self.activate(self.server(self.root / 'current'))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / 'current').resolve(), self.old)

    def test_wrong_served_release_rolls_back(self):
        # Simulate a proxy that still routes to the old release after a local switch.
        result = self.activate(self.server(self.old))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('previous release restored', result.stderr)
        self.assertEqual((self.root / 'current').resolve(), self.old)
        self.assertTrue((self.release / 'site/index.html').exists())

    def test_unhealthy_previous_release_blocks_activation(self):
        result = self.activate(self.server(self.release / 'site'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Previous release health failed', result.stderr)
        self.assertEqual((self.root / 'current').resolve(), self.old)

    def test_missing_previous_release_fails_closed(self):
        (self.root / 'current').unlink()
        result = self.activate(self.server(self.old))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'current').exists())

    def test_site_symlink_cannot_publish_external_files(self):
        import shutil
        shutil.rmtree(self.release / 'site')
        (self.release / 'site').symlink_to(self.old)
        result = self.activate(self.server(self.old))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / 'current').resolve(), self.old)

    def test_traversal_release_identifier_is_rejected(self):
        result = subprocess.run(
            ['bash', str(SCRIPTS / 'activate-static.sh'), str(self.root), '../old', self.server(self.old)],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual((self.root / 'current').resolve(), self.old)

    def seal(self):
        artifact = self.root / 'artifact'
        result = subprocess.run(
            ['bash', str(SCRIPTS / 'seal-static.sh'), str(self.release / 'site'), str(artifact)],
            env={**self.env, 'RELEASE_ID': 'new'}, capture_output=True, text=True, timeout=5,
        )
        return result, artifact

    def test_seal_excludes_build_working_files_and_hashes_scripts(self):
        (self.release / '.env').write_text('PRIVATE_TOKEN=secret')
        result, artifact = self.seal()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((artifact / '.env').exists())
        self.assertIn('activate-static.sh', (artifact / 'SHA256SUMS').read_text())
        check = subprocess.run(['sha256sum', '--check', 'SHA256SUMS'], cwd=artifact, capture_output=True)
        self.assertEqual(check.returncode, 0)

    def test_seal_rejects_credentials_in_public_site(self):
        (self.release / 'site/private.key').write_text('private key')
        result, artifact = self.seal()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(artifact.exists())

    def test_seal_rejects_symlinks_into_private_files(self):
        (self.release / 'secret').write_text('private')
        (self.release / 'site/public.txt').symlink_to(self.release / 'secret')
        result, artifact = self.seal()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(artifact.exists())

    def transfer(self, failures):
        counter = self.root / 'attempts'
        command = self.root / 'transfer.sh'
        command.write_text(
            '#!/bin/bash\n'
            f'count=$(cat "{counter}" 2>/dev/null || echo 0)\n'
            'count=$((count + 1))\n'
            f'echo "$count" > "{counter}"\n'
            f'[[ "$count" -gt {failures} ]]\n'
        )
        result = subprocess.run(
            ['bash', str(SCRIPTS / 'retry-transfer.sh'), 'bash', str(command)],
            env=self.env, capture_output=True, text=True, timeout=5,
        )
        return result, int(counter.read_text())

    def test_transfer_recovers_after_transient_failures(self):
        result, attempts = self.transfer(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(attempts, 3)

    def test_transfer_exhaustion_remains_failure(self):
        result, attempts = self.transfer(3)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(attempts, 3)


class WorkflowTemplateTests(unittest.TestCase):
    def workflows(self):
        return {name: (SKILL / 'templates' / name).read_text() for name in ('ci.yml', 'deploy-vps.yml')}

    def test_actions_are_pinned_to_full_commits_and_checkout_drops_the_token(self):
        for name, text in self.workflows().items():
            uses = re.findall(r'uses:\s*(\S+)', text)
            self.assertTrue(uses, name)
            for reference in uses:
                self.assertRegex(reference, r'^[\w.-]+/[\w./-]+@[0-9a-f]{40}$', f'{name}: {reference}')
            for checkout in re.finditer(r'uses: actions/checkout@.*\n((?:\s+.*\n){1,3})', text):
                self.assertIn('persist-credentials: false', checkout.group(1), name)

    def test_token_has_no_default_permissions_and_jobs_are_bounded(self):
        for name, text in self.workflows().items():
            self.assertIn('\npermissions: {}\n', text, name)
            self.assertNotIn('write', re.sub(r'#.*', '', text), name)
            jobs = re.findall(r'^  \w[\w-]*:\n    (?:needs: \w+\n    )?runs-on:', text, re.M)
            self.assertEqual(len(jobs), text.count('timeout-minutes:'), name)
            self.assertIsNone(re.search(r'run:[^\n]*\$\{\{', text), name)  # Entradas só por env.

    def test_templates_stay_blocked_until_real_commands_replace_the_placeholder(self):
        for name, text in self.workflows().items():
            self.assertIn('exit 1', text, name)
        self.assertNotIn('cancel-in-progress: true', self.workflows()['deploy-vps.yml'])
        self.assertIn('package-ecosystem: github-actions', (SKILL / 'templates/dependabot.yml').read_text())

    def test_skill_links_resolve_inside_the_package(self):
        for document in [SKILL / 'SKILL.md', *sorted((SKILL / 'references').glob('*.md'))]:
            for target in re.findall(r'\]\((?!https?:)([^)#]+)', document.read_text()):
                self.assertTrue((document.parent / target).exists(), f'{document.name}: {target}')


if __name__ == '__main__':
    unittest.main()
