#!/usr/bin/env python3
"""Install only the Centaur skills into explicitly selected skill directories."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

OBSOLETE = 'centaur-driven-commitAndPush'
LEGACY_PREFIX = 'centaur-driven-'
INTERNAL = '_internal'
RETIRED = ('memory', 'centaur-driven-memory')


def reject_symlink(path):
    for entry in (path, *path.parents):
        if entry.is_symlink():
            raise ValueError(f'Link simbólico exige revisão: {path}')


def fingerprint(directory):
    reject_symlink(directory)
    if not directory.exists():
        return None
    if not directory.is_dir():
        raise ValueError(f'Destino não é diretório: {directory}')
    result = {}
    for item in sorted(directory.rglob('*')):
        reject_symlink(item)
        if item.is_file():
            result[item.relative_to(directory).as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
        elif not item.is_dir():
            raise ValueError(f'Arquivo especial não suportado: {item}')
    return result


def source_skills(root):
    skills = {}
    for directory in sorted((root / 'centaur_cli/skills').glob('*')):
        reject_symlink(directory)
        if directory.name in (OBSOLETE, INTERNAL) or not directory.is_dir():
            continue
        if not (directory / 'SKILL.md').is_file():
            raise ValueError(f'Skill incompleta: {directory.name}')
        # Reject symlinks/special files before copying anything.
        files = fingerprint(directory)
        if any((Path(name).name.startswith('.env') or Path(name).name in ('id_rsa', 'id_ed25519')) or Path(name).suffix in ('.pem', '.key', '.p12', '.pfx') for name in files):
            raise ValueError(f'Possível credencial na skill: {directory.name}')
        skills[directory.name] = directory
    if not skills:
        raise ValueError('Nenhuma skill Centaur válida encontrada')
    return skills


def clean_fingerprint(directory):
    return {name: value for name, value in fingerprint(directory).items()
            if '__pycache__' not in Path(name).parts and not name.endswith(('.pyc', '.pyo'))}


def install(root, targets, apply=False):
    public_skills = source_skills(root)
    skills = dict(public_skills)
    internal = root / 'centaur_cli/skills' / INTERNAL
    reject_symlink(internal)
    if internal.exists():
        files = fingerprint(internal)
        if any(Path(name).name.startswith('.env') or Path(name).name in ('id_rsa', 'id_ed25519') or Path(name).suffix in ('.pem', '.key', '.p12', '.pfx') for name in files):
            raise ValueError('Possível credencial nas subskills internas')
        for directory in internal.iterdir():
            if directory.is_dir() and not (directory / 'SKILL.md').is_file():
                raise ValueError(f'Subskill incompleta: {directory.name}')
        skills[INTERNAL] = internal
    if not targets:
        raise ValueError('Informe pelo menos um --target explícito')
    targets = list(dict.fromkeys(Path(os.path.abspath(target)) for target in targets))
    for target in targets:
        reject_symlink(target)
        if target.exists() and target.stat().st_dev != root.stat().st_dev:
            raise ValueError('Destinos em outro filesystem exigem instalação manual; staging fica em .centaur/tmp')
        if not target.is_dir():
            raise ValueError(f'Diretório de skills inexistente: {target}')
        if target == root or root in target.parents or target in root.parents:
            raise ValueError('Instalação deve ficar fora da árvore fonte')
    for target in targets:
        if any(other != target and other in target.parents for other in targets):
            raise ValueError('Destinos aninhados não são suportados')
    obsolete_names = [LEGACY_PREFIX + name for name in public_skills] + [OBSOLETE, *RETIRED]
    names = [*skills, *obsolete_names]
    before = {(target, name): fingerprint(target / name) for target in targets for name in names}
    expected = {name: clean_fingerprint(path) for name, path in skills.items()}
    changed = [(target, name) for target in targets for name in names
               if before[target, name] != expected.get(name)]
    result = {'targets': [str(t) for t in targets], 'install': list(public_skills),
              'resources': [INTERNAL] if INTERNAL in skills else [],
              'remove': [str(t / name) for t in targets for name in obsolete_names
                         if before[t, name] is not None],
              'changed': [str(t / n) for t, n in changed], 'applied': apply, 'backup': None}
    if not apply or not changed:
        return result
    backup_root = root / '.centaur/backups'
    reject_symlink(backup_root)
    backup = backup_root / ('install-' + uuid.uuid4().hex)
    backup.mkdir(parents=True, mode=0o700)
    result['backup'] = str(backup)
    manifest = []
    for target, name in changed:
        entry = {'target': str(target / name), 'before': before[target, name], 'backup': None}
        if before[target, name] is not None:
            saved = backup / str(targets.index(target)) / name
            shutil.copytree(target / name, saved)
            if fingerprint(saved) != before[target, name]:
                raise ValueError(f'Conteúdo mudou durante backup: {target / name}')
            entry['backup'] = str(saved.relative_to(backup))
        manifest.append(entry)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    staged, temporary, touched = {}, [], []
    stages = {}
    staging_root = root / '.centaur/tmp'
    reject_symlink(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)
    try:
        # Preflight requires the same filesystem, allowing atomic renames from .centaur.
        for target in targets:
            stage = Path(tempfile.mkdtemp(prefix='install-', dir=staging_root))
            stages[target] = stage
            temporary.append(stage)
            for name, source in skills.items():
                if (target, name) not in changed:
                    continue
                new = stage / name
                shutil.copytree(source, new, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
                if fingerprint(new) != expected[name]:
                    raise ValueError(f'Staging inválido: {name}')
                staged[target, name] = new
        for target, name in changed:
            destination = target / name
            if fingerprint(destination) != before[target, name]:
                raise ValueError(f'Instalação mudou durante preparação: {destination}')
            old = stages[target] / ('old-' + name)
            if destination.exists():
                os.replace(destination, old)
            touched.append((destination, old))
            if name in skills:
                os.replace(staged[target, name], destination)
                if fingerprint(destination) != expected[name]:
                    raise ValueError(f'Instalação inválida: {name}')
    except BaseException:
        for destination, old in reversed(touched):
            if destination.exists():
                shutil.rmtree(destination)
            if old.exists():
                os.replace(old, destination)
        raise
    finally:
        for stage in temporary:
            shutil.rmtree(stage)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--target', type=Path, action='append', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.root.resolve(strict=True), args.target, args.apply), indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f'Instalação interrompida: {error}\n')


if __name__ == '__main__':
    main()
