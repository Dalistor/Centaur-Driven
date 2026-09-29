import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'centaur-driven-graphify/scripts/graphify-local.py'
spec = importlib.util.spec_from_file_location('graphify_local', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GraphifyLocalTests(unittest.TestCase):
    def test_absent_graph_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, str(SCRIPT), temp, 'query', 'question'], capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_output_and_corpus_cannot_be_overridden(self):
        for args in (['extract', '/other'], ['export', 'html', '--output=/tmp/leak'], ['extract', '--global'], ['hook', 'install']):
            with self.assertRaises(ValueError): module.command_for(Path('/project'), args)

    def test_cli_receives_isolated_output_and_literal_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary = root / 'bin/graphify'
            binary.parent.mkdir()
            binary.write_text('#!/bin/sh\nprintf "%s\\n" "$GRAPHIFY_OUT" "$PWD" "$@"\n')
            binary.chmod(0o755)
            result = subprocess.run([sys.executable, str(SCRIPT), temp, 'extract', '--code-only'], env={**os.environ, 'PATH': str(binary.parent) + os.pathsep + os.environ['PATH']}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [str(root / '.centaur/graphify'), temp, 'extract', temp, '--code-only'])
            self.assertFalse((root / 'graphify-out').exists())
