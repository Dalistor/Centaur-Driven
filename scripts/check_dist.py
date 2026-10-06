#!/usr/bin/env python3
"""Check packaged resources and install the wheel outside the source tree."""
import argparse
import email.parser
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def check(directory):
    wheels = list(directory.glob('*.whl'))
    sources = list(directory.glob('*.tar.gz'))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError('Expected exactly one wheel and one sdist in the distribution directory.')
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
        metadata_file = next(name for name in names if name.endswith('.dist-info/METADATA'))
        metadata = email.parser.Parser().parsestr(archive.read(metadata_file).decode())
        if metadata['Name'] != 'centaur-cli' or not metadata['Version'] or not metadata['Requires-Python']:
            raise ValueError('Missing package metadata.')
        version = metadata['Version']
        if not (metadata['Description-Content-Type'] or '').startswith('text/markdown'):
            raise ValueError('Missing Markdown project description.')
        expected = [p for p in (ROOT / 'centaur_cli').rglob('*') if p.is_file()
                    and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.pyo')]
        for source in expected:
            relative = source.relative_to(ROOT).as_posix()
            if relative not in names or archive.read(relative) != source.read_bytes():
                raise ValueError('Missing or stale resource: ' + relative)
        if any('/__pycache__/' in name or name.endswith(('.pyc', '.pyo', '/credentials.json'))
               for name in names):
            raise ValueError('Unexpected generated or credential file in the wheel.')
    with tarfile.open(sources[0], 'r:gz') as archive:
        members = archive.getmembers()
        if any(member.issym() or member.islnk() or not (member.isfile() or member.isdir())
               or '..' in Path(member.name).parts or Path(member.name).is_absolute() for member in members):
            raise ValueError('Invalid source archive member.')
        files = {member.name: member for member in members if member.isfile()}
        prefix = next(iter(files)).split('/')[0] + '/'
        for source in expected:
            name = prefix + source.relative_to(ROOT).as_posix()
            if name not in files or archive.extractfile(files[name]).read() != source.read_bytes():
                raise ValueError('Missing or stale sdist resource: ' + name)
        for name in ('pyproject.toml', 'README.pypi.md', 'scripts/check_dist.py'):
            if prefix + name not in files:
                raise ValueError('Missing sdist build input: ' + name)
    with tempfile.TemporaryDirectory(prefix='centaur-package-check-') as temporary:
        target = Path(temporary)
        venv.EnvBuilder(with_pip=True).create(target / 'venv')
        python = target / 'venv/bin/python'
        command = target / 'venv/bin/centaur'
        working = target / 'project'
        working.mkdir()
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        subprocess.run([str(python), '-I', '-m', 'pip', 'install', '--no-index', '--no-deps',
                        str(wheels[0].resolve())], cwd=working, env=environment, check=True, capture_output=True)
        result = subprocess.check_output([str(command), '--version'], cwd=working, env=environment, text=True).strip()
        if result != 'centaur ' + version:
            raise ValueError('Installed command version does not match the wheel: ' + result)
        subprocess.run([str(command), '--help'], cwd=working, env=environment, check=True, capture_output=True)
        subprocess.run([str(command), 'status', str(working)], cwd=working, env=environment, check=True, capture_output=True)
        probe = "from pathlib import Path; from centaur_cli import skill_catalog; import centaur_cli; " \
                "assert Path(centaur_cli.__file__).is_relative_to(Path(%r)); " \
                "assert {'run','spec','check','skill'} <= set(skill_catalog.names()); " \
                "assert (skill_catalog.SKILL_ROOT/'_internal/memory/references/contract.md').is_file()" % str(target)
        subprocess.run([str(python), '-I', '-c', probe], cwd=working, check=True)
    print(f'Validated centaur-cli {version}: wheel, sdist, all {len(expected)} resources and clean install.')
    return version


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, nargs='?', default=ROOT / 'dist')
    args = parser.parse_args()
    try:
        check(args.directory.resolve())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')
