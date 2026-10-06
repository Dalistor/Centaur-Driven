"""Leitura do catálogo de skills distribuído com o CLI."""

from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent / 'skills'


def names():
    return sorted(path.parent.name for path in SKILL_ROOT.glob('*/SKILL.md'))


def additional_root(project_root):
    project = Path(project_root).resolve()
    catalog = (project / '.centaur/skills').resolve()
    catalog.relative_to(project)
    return catalog


def additional_names(project_root):
    try:
        catalog = additional_root(project_root)
        result = []
        for path in catalog.glob('*/SKILL.md'):
            if path.parent.name.startswith(('.', '_')):
                continue
            try:
                path.resolve().relative_to(path.parent.resolve())
                path.parent.resolve().relative_to(catalog)
                if path.is_file():
                    result.append(path.parent.name)
            except ValueError:
                continue
        return sorted(result)
    except (OSError, ValueError):
        return []


def dependency_root(project_root):
    candidates = [Path(project_root) / '.centaur/skills/clean-code',
                  Path.home() / '.agents/skills/clean-code',
                  Path.home() / '.codex/skills/clean-code',
                  Path.home() / '.claude/skills/clean-code']
    return next((path for path in candidates if (path / 'SKILL.md').is_file()), None)


def read(path, start_line, project_root=None):
    catalog = SKILL_ROOT
    relative = Path(path)
    if relative.parts and relative.parts[0].startswith('@'):
        name = relative.parts[0][1:]
        if name not in additional_names(project_root or Path.cwd()):
            raise ValueError('Skill adicional não instalada em .centaur/skills.')
        catalog = (additional_root(project_root or Path.cwd()) / name).resolve()
        relative = Path(*relative.parts[1:])
    elif relative.parts and relative.parts[0] == 'clean-code':
        catalog = dependency_root(project_root or Path.cwd())
        if catalog is None:
            raise ValueError('Dependência clean-code não instalada; instale a skill completa.')
        relative = Path(*relative.parts[1:])
    source = (catalog / relative).resolve()
    source.relative_to(catalog.resolve())
    start = int(start_line)
    if start < 1:
        raise ValueError('A linha inicial deve ser maior que zero.')
    lines = source.read_text(encoding='utf-8').splitlines()
    excerpt = lines[start - 1:start + 199]
    end = start + len(excerpt) - 1
    return f'Skill: {path} | linhas {start}–{end} de {len(lines)}\n' + '\n'.join(excerpt)
