#!/usr/bin/env python3
"""Transactional, conservative migration of Centaur-owned local artifacts."""
import argparse
import hashlib
import json
import os
import re
from urllib.parse import quote, unquote, urlsplit
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid


MAPPINGS = {
    'graphify-out': '.centaur/graphify',
    '.ai-memory.toml': '.centaur/ai-memory/config.toml',
    '.centaur/memory-pending': '.centaur/ai-memory/pending',
}
HTML_MARKERS = ('centaur-volante-redirect', 'centaur-volante', 'CENTAUR_DATA', 'CENTAUR DRIVEN')


def safe_path(root, relative):
    path = root / relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError(f'Caminho fora do projeto: {relative}')
    for parent in (path, *path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError(f'Link simbólico exige revisão manual: {relative}')
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command_works(command, root, env=None):
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, timeout=30, env=env)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def check_dependencies(root, clean_code, memory_check):
    if not clean_code.is_file():
        raise ValueError('Dependência obrigatória ausente: clean-code/SKILL.md')
    health = {'clean-code': 'disponível'}
    graphify = shutil.which('graphify')
    graph_env = dict(os.environ, GRAPHIFY_OUT=str(root / '.centaur/graphify'))
    health['graphify'] = ('CLI funcional; índice preservado, sem reindexação' if graphify and
                          command_works([graphify, '--version'], root, graph_env) else 'opcional indisponível')
    for graph in (root / '.centaur/graphify/graph.json', root / 'graphify-out/graph.json'):
        if graphify and graph.is_file():
            graph_env['GRAPHIFY_OUT'] = str(graph.parent)
            health['graphify-index'] = ('consulta funcional' if command_works([graphify, 'query', 'Centaur', '--budget', '100'], root, graph_env) else 'consulta falhou; índice preservado')
            break
    workspace = root / '.centaur/workspace.json'
    backend = json.loads(workspace.read_text()).get('memory', {}).get('backend', 'files') if workspace.exists() else 'files'
    if backend not in ('files', 'ai-memory'):
        raise ValueError('Backend de memória desconhecido')
    configured = backend == 'ai-memory' or any((root / p).exists() for p in
                 ('.ai-memory.toml', '.centaur/ai-memory/config.toml'))
    if configured:
        if not memory_check or not command_works(memory_check, root):
            raise ValueError('ai-memory configurado: forneça --memory-check com comando real de leitura que valide conexão e identidade; migração não aplicada')
        health['ai-memory'] = 'verificação de acesso concluída'
    return health


class PlannedWrites(dict):
    """Bind prepared bytes to the exact input snapshot reviewed by the caller."""
    expected = None


def rewrite_links(text, old_path, new_path, moves):
    """Rebase local Markdown destinations; leave code blocks and external URLs intact."""
    def destination(value):
        angle = value.startswith('<') and value.endswith('>')
        raw = value[1:-1] if angle else value
        if '(' in raw and not angle:
            return value  # Complex Markdown destinations need an explicit review.
        parsed = urlsplit(raw)
        if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith('/'):
            return value
        original = Path(os.path.normpath(str(Path(old_path).parent / unquote(parsed.path)))).as_posix()
        target = moves.get(original, original)
        relative = Path(os.path.relpath(target, Path(new_path).parent)).as_posix()
        result = quote(relative, safe='/._~-') + ('?' + parsed.query if parsed.query else '') + ('#' + parsed.fragment if parsed.fragment else '')
        return '<' + result + '>' if angle else result

    def replace_inline(match):
        return match[1] + destination(match[2])

    chunks = re.split(r'(^[ \t]*(?:```|~~~).*?^[ \t]*(?:```|~~~)[^\n]*$)', text, flags=re.M | re.S)
    for index in range(0, len(chunks), 2):
        chunks[index] = re.sub(r'(\]\()(<[^>]+>|[^\s)]+)', replace_inline, chunks[index])
        chunks[index] = re.sub(r'(^[ \t]*\[(?!\^)[^]\n]+\]:[ \t]*)(<[^>]+>|[^\s]+)', replace_inline, chunks[index], flags=re.M)
    return ''.join(chunks)


def plan_migration(root, owned_docs=(), references=()):
    mappings = dict(MAPPINGS)
    for relative in owned_docs:
        if not relative.startswith('docs/system/'):
            raise ValueError('--owned-doc deve apontar para documento gerado em docs/system/')
        mappings[relative] = '.centaur/system/' + relative.removeprefix('docs/system/')
    writes, removals, replacements = PlannedWrites(), set(), {}
    moves = {}
    source_hashes = {}
    for old, new in mappings.items():
        source = safe_path(root, old)
        if not source.exists():
            continue
        if old in owned_docs and not source.is_file():
            raise ValueError('--owned-doc requer arquivo, não diretório')
        paths = sorted(source.rglob('*')) if source.is_dir() else [source]
        for item in paths:
            relative = item.relative_to(root).as_posix()
            safe_path(root, relative)
            if item.is_dir():
                continue
            if not item.is_file():
                raise ValueError(f'Artefato não regular exige revisão: {relative}')
            target = new + ('/' + item.relative_to(source).as_posix() if source.is_dir() else '')
            destination = safe_path(root, target)
            body = item.read_bytes()
            source_hashes[relative] = hashlib.sha256(body).hexdigest()
            if destination.exists() and (not destination.is_file() or destination.read_bytes() != body):
                raise ValueError(f'Conflito: {relative} → {target}; nada foi substituído')
            if target in writes and writes[target] != body:
                raise ValueError(f'Dois arquivos divergem no destino: {target}')
            if not destination.exists():
                writes[target] = body
            removals.add(relative)
            moves[relative] = target
        replacements[old] = new
    for directory in ('', '.centaur/'):
        for name in ('andamento.html', 'acompanhamento.html', 'volante.html'):
            relative = directory + name
            path = safe_path(root, relative)
            if path.is_file() and any(marker in path.read_text(errors='replace') for marker in HTML_MARKERS):
                removals.add(relative)
    for old, new in moves.items():
        if old in owned_docs:
            body = rewrite_links((root / old).read_bytes().decode('utf-8'), old, new, moves).encode()
            if (root / new).exists() and (root / new).read_bytes() != body:
                raise ValueError(f'Conflito após corrigir links: {new}')
            if not (root / new).exists():
                writes[new] = body
    # Only explicitly selected live references are rewritten; approved history stays byte-identical.
    for relative in references:
        path = safe_path(root, relative)
        if relative in removals or not path.is_file():
            raise ValueError(f'Referência inválida ou migrada: {relative}')
        original = path.read_bytes().decode('utf-8')
        updated = rewrite_links(original, relative, relative, moves) if path.suffix == '.md' else original
        for old, new in sorted(replacements.items(), key=lambda pair: -len(pair[0])):
            updated = updated.replace(old, new)
        if updated != original:
            source_hashes[relative] = hashlib.sha256(original.encode()).hexdigest()
            writes[relative] = updated.encode()
    moved_docs = {old: new for old, new in moves.items() if old in owned_docs}
    if moved_docs and ('.centaur/graphify/graph.json' in writes or (root / '.centaur/graphify/graph.json').exists()):
        marker = '.centaur/graphify/migration.json'
        marker_path = safe_path(root, marker)
        status = json.loads(writes[marker]) if marker in writes else (json.loads(marker_path.read_text()) if marker_path.exists() else {})
        status.setdefault('moved_document_paths', {}).update(moved_docs)
        status.update(needs_sync=True, reason='Documentos movidos; IDs e conteúdo do índice preservados. Sincronização sob demanda.')
        writes[marker] = (json.dumps(status, ensure_ascii=False, indent=2) + '\n').encode()
    writes.expected = {name: digest(safe_path(root, name)) if safe_path(root, name).is_file() else None for name in set(writes) | removals}
    if any(writes.expected[name] != checksum for name, checksum in source_hashes.items()):
        raise ValueError('Origem mudou durante o inventário; refaça o plano')
    return writes, removals


def apply_migration(root, writes, removals):
    if not writes and not removals:
        return None
    affected = set(writes) | removals
    before = {name: digest(safe_path(root, name)) if safe_path(root, name).is_file() else None for name in affected}
    if getattr(writes, 'expected', None) is not None and before != writes.expected:
        raise ValueError('Arquivos mudaram após o inventário; refaça o plano antes de aplicar')
    base = root / '.centaur'
    safe_path(root, '.centaur/tmp')
    safe_path(root, '.centaur/backups')
    (base / 'tmp').mkdir(parents=True, exist_ok=True)
    backup = base / 'backups' / ('update-' + uuid.uuid4().hex)
    backup.mkdir(parents=True, mode=0o700)
    for name, checksum in before.items():
        if checksum is not None:
            target = backup / 'files' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, target)
            if digest(target) != checksum:
                raise ValueError(f'Arquivo mudou durante backup: {name}')
    (backup / 'manifest.json').write_text(json.dumps({'before': before, 'writes': sorted(writes), 'removals': sorted(removals)}, indent=2))
    with tempfile.TemporaryDirectory(prefix='update-', dir=base / 'tmp') as temporary:
        stage = Path(temporary)
        for name, body in writes.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            target.chmod((root / name).stat().st_mode & 0o777 if (root / name).exists() else (0o600 if 'ai-memory' in name else 0o644))
            if target.read_bytes() != body:
                raise ValueError('Falha ao validar staging')
        for name, checksum in before.items():
            path = root / name
            current = digest(path) if path.is_file() else None
            if current != checksum:
                raise ValueError(f'Arquivo mudou durante preparação: {name}')
        touched = []
        try:
            for name in sorted(writes):
                destination = safe_path(root, name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(stage / name, destination)
                touched.append(name)
                if destination.read_bytes() != writes[name]:
                    raise ValueError(f'Transferência inválida: {name}')
            for name in sorted(removals):
                if digest(safe_path(root, name)) != before[name]:
                    raise ValueError(f'Origem mudou durante aplicação: {name}')
                safe_path(root, name).unlink()
                touched.append(name)
        except BaseException:
            for name in reversed(touched):
                target = root / name
                if before[name] is None:
                    target.unlink(missing_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup / 'files' / name, target)
            raise
    # Prune only emptied source parents; never delete unrelated contents.
    for name in removals:
        parent = (root / name).parent
        while parent not in (root, base):
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    return str(backup.relative_to(root))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--apply', action='store_true', help='Aplicar; padrão apenas inventaria')
    parser.add_argument('--owned-doc', action='append', default=[], help='Documento comprovadamente gerado, caminho relativo')
    parser.add_argument('--reference', action='append', default=[], help='Arquivo vivo autorizado para atualizar referências')
    parser.add_argument('--clean-code', type=Path, default=Path.home() / '.agents/skills/clean-code/SKILL.md')
    parser.add_argument('--memory-check', help='Array JSON de argv de verificação real de leitura/acesso (sem shell)')
    args = parser.parse_args()
    try:
        root = args.root.resolve(strict=True)
        check = json.loads(args.memory_check) if args.memory_check else None
        if check is not None and (not isinstance(check, list) or not check or not all(isinstance(x, str) for x in check)):
            raise ValueError('--memory-check requer array de strings')
        health = check_dependencies(root, args.clean_code, check)
        writes, removals = plan_migration(root, args.owned_doc, args.reference)
        backup = apply_migration(root, writes, removals) if args.apply else None
        print(json.dumps({'health': health, 'writes': sorted(writes), 'removals': sorted(removals), 'applied': args.apply, 'backup': backup}, ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Update interrompido: {exc}\n')


if __name__ == '__main__':
    main()
