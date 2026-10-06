#!/usr/bin/env python3
"""Baixar uma skill pública GitHub completa para .centaur/skills/."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from urllib.parse import quote, unquote, urlsplit
from urllib.request import urlopen
from zipfile import ZipFile, BadZipFile

MAX_DOWNLOAD = 32 * 1024 * 1024
MAX_CONTENT = 64 * 1024 * 1024
MAX_FILES = 4000
NAME = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')
REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')


def source(repo=None, path=None, ref=None, url=None):
    if url:
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != 'github.com' or parsed.query or parsed.fragment:
            raise ValueError('Use uma URL HTTPS github.com sem query ou fragmento.')
        parts = unquote(parsed.path).strip('/').split('/')
        if len(parts) < 5 or parts[2] != 'tree':
            raise ValueError('A URL deve apontar para /dono/repo/tree/ref/pasta.')
        repo = '/'.join(parts[:2])
        tail = '/'.join(parts[3:])
        if ref:
            if not tail.startswith(ref + '/'):
                raise ValueError('A referência explícita não corresponde à URL.')
            path = tail[len(ref) + 1:]
        else:
            ref, path = parts[3], '/'.join(parts[4:])
    if not repo or not REPO.fullmatch(repo) or any(part in ('.', '..') for part in repo.split('/')):
        raise ValueError('Informe --repo dono/repositorio ou uma URL de pasta GitHub.')
    if not path or '\\' in path or path.startswith('/') or any(part in ('', '.', '..') for part in path.split('/')):
        raise ValueError('Informe uma pasta relativa válida que contenha SKILL.md.')
    ref = ref or 'main'
    if not ref.strip() or any(ord(char) < 32 for char in ref):
        raise ValueError('Referência Git inválida.')
    return repo, path, ref


def download(repo, ref):
    url = f'https://codeload.github.com/{repo}/zip/{quote(ref, safe="")}'
    with urlopen(url, timeout=30) as response:
        payload = response.read(MAX_DOWNLOAD + 1)
    if len(payload) > MAX_DOWNLOAD:
        raise ValueError('Download excede 32 MB.')
    return payload


def extract(payload, path, staging):
    """Extraia somente arquivos da pasta selecionada, sem executar conteúdo."""
    with ZipFile(io.BytesIO(payload)) as archive:
        members = archive.infolist()
        roots = {PurePosixPath(entry.filename).parts[0] for entry in members if entry.filename}
        if len(roots) != 1:
            raise ValueError('Arquivo GitHub sem uma raiz única.')
        prefix = next(iter(roots)) + '/' + path + '/'
        selected = [entry for entry in members if entry.filename.startswith(prefix)]
        if not selected:
            raise ValueError('Pasta solicitada não encontrada no download.')
        if len(selected) > MAX_FILES or sum(entry.file_size for entry in selected) > MAX_CONTENT:
            raise ValueError('Skill excede os limites de arquivos ou tamanho.')
        seen = set()
        for entry in selected:
            relative = entry.filename[len(prefix):]
            if not relative or entry.is_dir():
                continue
            parts = relative.split('/')
            if '\\' in relative or any(part in ('', '.', '..') for part in parts):
                raise ValueError('Caminho inválido no download.')
            mode = entry.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if kind not in (0, stat.S_IFREG):
                raise ValueError('Links e arquivos especiais não são suportados.')
            if relative in seen:
                raise ValueError('Arquivo duplicado no download.')
            seen.add(relative)
            target = staging.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as origin, target.open('xb') as output:
                shutil.copyfileobj(origin, output)
            target.chmod(0o755 if mode & 0o111 else 0o644)
    skill = staging / 'SKILL.md'
    text = skill.read_text(encoding='utf-8')
    header = re.match(r'\A---\s*\n(.*?)\n---(?:\s*\n|\Z)', text, re.S)
    if not header or any(not re.search(r'^' + field + r':[ \t]*\S+', header[1], re.M)
                         for field in ('name', 'description')):
        raise ValueError('SKILL.md exige frontmatter com name e description.')


def local_directory(root, relative):
    directory = root / relative
    for component in (directory, *directory.parents):
        if component == root:
            break
        if component.is_symlink():
            raise ValueError('Diretório operacional não pode ser um link simbólico.')
    directory.resolve().relative_to(root)
    return directory


def install(project, repo, path, ref='main', name=None, fetch=download):
    repo, path, ref = source(repo, path, ref)
    root = Path(project).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError('A raiz do projeto deve ser um diretório.')
    name = name or PurePosixPath(path).name
    if not NAME.fullmatch(name):
        raise ValueError('Nome deve ter até 64 caracteres: letras minúsculas, números e hífens.')
    catalog = local_directory(root, '.centaur/skills')
    destination = catalog / name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Skill já instalada; instalação não substitui conteúdo existente.')
    payload = fetch(repo, ref)
    temporary = local_directory(root, '.centaur/tmp')
    temporary.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='skill-install-', dir=temporary) as directory:
        staging = Path(directory) / name
        staging.mkdir()
        extract(payload, path, staging)
        # Reserve sem sobrescrever uma instalação feita enquanto o download ocorria.
        catalog.mkdir(parents=True, exist_ok=True)
        destination.mkdir()
        try:
            for item in sorted(staging.iterdir(), key=lambda item: item.name == 'SKILL.md'):
                os.replace(item, destination / item.name)
        except BaseException:
            shutil.rmtree(destination)
            raise
    return {'name': name, 'source': f'https://github.com/{repo}', 'ref': ref,
            'path': path, 'archive_sha256': hashlib.sha256(payload).hexdigest(),
            'destination': str(destination), 'invoke': '@' + name}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    origin = parser.add_mutually_exclusive_group(required=True)
    origin.add_argument('--repo')
    origin.add_argument('--url')
    parser.add_argument('--path')
    parser.add_argument('--ref')
    parser.add_argument('--name')
    options = parser.parse_args()
    try:
        repo, path, ref = source(options.repo, options.path, options.ref, options.url)
        result = install(options.project, repo, path, ref, options.name)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, BadZipFile) as error:
        parser.exit(1, f'Instalação interrompida: {error}\n')


if __name__ == '__main__':
    main()
