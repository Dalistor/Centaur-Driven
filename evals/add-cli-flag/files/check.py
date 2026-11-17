"""Verificação da tarefa: não faz parte do que o agente deve alterar."""
import subprocess
import sys
import tempfile
from pathlib import Path


def run(*arguments):
    return subprocess.run([sys.executable, 'wc.py', *arguments], capture_output=True, text=True, timeout=20).stdout.split('\n')


with tempfile.TemporaryDirectory() as directory:
    a, b = Path(directory, 'a.txt'), Path(directory, 'b.txt')
    a.write_text('um dois\ntrês\n')
    b.write_text('quatro  cinco seis\n\nsete\n')
    expected = {
        (): [f'2 {a}', f'3 {b}', ''],
        ('--words',): [f'3 {a}', f'4 {b}', ''],
        ('--words', '--total'): [f'3 {a}', f'4 {b}', '7 total', ''],
        ('--total',): [f'2 {a}', f'3 {b}', '5 total', ''],
    }
    failures = [(options, run(*options, str(a), str(b))) for options, lines in expected.items()
                if run(*options, str(a), str(b)) != lines]
    for options, output in failures:
        print('falhou', options, output)
    sys.exit(1 if failures else 0)
