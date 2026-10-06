"""Projeção local de specs e análise opcional, sem alterar seus estados."""

import importlib.util
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from .tools import ProjectTools, TOOLS, tool
from .skill_catalog import SKILL_ROOT

STATES = {'Pendente': 'a implementar', 'Em andamento': 'a implementar',
          'Bloqueada': 'bloqueada', 'Em revisão': 'em revisão',
          'Concluída': 'feito', 'Cancelada': 'cancelada'}
REFERENCE = re.compile(r'(?<![\w/])([\w.-]+/[\w.-]+)(?![\w/])')


def field(body, name):
    match = re.search(r'^\*\*' + re.escape(name) + r':\*\*\s*(.*)$', body, re.M)
    return match.group(1).strip() if match else ''


def inside(root, path):
    resolved = (root / path).resolve()
    resolved.relative_to(root)
    return resolved


def snapshot(root):
    root = Path(root).resolve()
    warnings, specs = [], {}
    try:
        workspace_path = inside(root, '.centaur/workspace.json')
        if workspace_path.exists():
            workspace = json.loads(workspace_path.read_text(encoding='utf-8'))
            scopes = workspace['scopes']
            if not isinstance(scopes, dict) or not scopes or 'master' not in scopes:
                raise ValueError('workspace exige escopos e master')
        else:
            legacy = '.centaur/specs' if (root / '.centaur/specs').exists() else 'specs'
            scopes = {'master': {'specs': legacy}}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'specs': {}, 'warnings': [f'Workspace inválido: {error}']}
    for scope, config in scopes.items():
        try:
            directory = inside(root, config['specs'])
            for path in sorted(directory.glob('*/README.md')):
                try:
                    inside(root, path)
                    body = path.read_text(encoding='utf-8')
                    identifier = f'{scope}/{path.parent.name}'
                    title = re.search(r'^#\s+(.+)', body, re.M)
                    checklist = re.search(r'^## Checklist de conclusão\s*$(.*?)(?=^## |\Z)', body, re.M | re.S)
                    tasks = [{'title': title, 'done': check.lower() == 'x'}
                             for check, title in re.findall(r'^\s*-\s*\[([ xX])\]\s*(.+)$', checklist.group(1) if checklist else '', re.M)]
                    specs[identifier] = {'id': identifier, 'scope': scope,
                        'title': title.group(1) if title else path.parent.name,
                        'status': field(body, 'Status') or 'Sem status',
                        'path': str(path.relative_to(root)), 'tasks': tasks,
                        'parent': field(body, 'Spec mestre'), 'children': field(body, 'Specs filhas'),
                        'dependencies': field(body, 'Dependências')}
                except (OSError, ValueError, UnicodeError) as error:
                    warnings.append(f'Spec {scope}/{path.parent.name}: {error}')
        except (OSError, ValueError, KeyError, TypeError) as error:
            warnings.append(f'Escopo {scope}: {error}')
    return {'specs': specs, 'warnings': warnings}


def relationships(data):
    specs, warnings = data['specs'], list(data['warnings'])
    parents = {}
    for identifier, spec in specs.items():
        references = REFERENCE.findall(spec['parent'])
        if len(references) == 1:
            parents[identifier] = references[0]
        elif spec['parent'] not in ('', '—', '-', 'Nenhuma'):
            warnings.append(f'{identifier}: spec mestre ambígua ou sem ID qualificado')
    for identifier, spec in specs.items():
        for child in REFERENCE.findall(spec['children']):
            if child not in specs:
                warnings.append(f'{identifier}: filha ausente {child}')
            elif child in parents and parents[child] != identifier:
                warnings.append(f'{child}: vínculo mestre/filha divergente ({identifier}, {parents[child]})')
            else:
                parents[child] = identifier
    for child, parent in list(parents.items()):
        if parent not in specs:
            warnings.append(f'{child}: mestre ausente {parent}')
            del parents[child]
            continue
        seen, node = {child}, parent
        while node in parents:
            if node in seen:
                warnings.append(f'{child}: ciclo entre specs mestre/filhas')
                del parents[child]
                break
            seen.add(node)
            node = parents[node]
    return parents, warnings


def render_status(root):
    data = snapshot(root)
    specs = data['specs']
    parents, warnings = relationships(data)
    counts = Counter(STATES.get(spec['status'], 'desconhecido') for spec in specs.values())
    lines = ['STATUS · specs do projeto',
             f'A implementar: {counts["a implementar"]} · Em revisão: {counts["em revisão"]} · Feito: {counts["feito"]} · Bloqueadas: {counts["bloqueada"]} · Canceladas: {counts["cancelada"]} · Sem estado reconhecido: {counts["desconhecido"]}',
             'Estados registrados nos READMEs; conclusão e liberação exigem verificação.', '']
    visited = set()

    def node(identifier, prefix, last):
        visited.add(identifier)
        spec = specs[identifier]
        branch = '└── ' if last else '├── '
        lines.append(f'{prefix}{branch}{identifier} · {spec["title"]} [{spec["status"]}]')
        continuation = prefix + ('    ' if last else '│   ')
        details = [f'Fonte: {spec["path"]}']
        if spec['dependencies'] not in ('', '—', '-'):
            details.append(f'Dependências: {spec["dependencies"]} (verificar integração antes de rodar)')
        pending = [task for task in spec['tasks'] if not task['done']]
        done = len(spec['tasks']) - len(pending)
        if spec['tasks']:
            details.append(f'Tasks registradas: {done}/{len(spec["tasks"])} marcadas; checkboxes não são evidência')
            details.extend(f'Falta: {task["title"]}' for task in pending)
        for detail in details:
            lines.append(continuation + detail)
        children = sorted(child for child, parent in parents.items() if parent == identifier and child not in visited)
        for index, child in enumerate(children):
            node(child, continuation, index == len(children) - 1)

    roots = [identifier for identifier in specs if identifier not in parents]
    scopes = sorted({specs[identifier]['scope'] for identifier in roots}, key=lambda scope: (scope != 'master', scope))
    for scope in scopes:
        lines.append(f'{scope}/')
        group = sorted(identifier for identifier in roots if specs[identifier]['scope'] == scope)
        for index, identifier in enumerate(group):
            node(identifier, '', index == len(group) - 1)
    if not specs:
        lines.append('Nenhuma spec encontrada nos escopos configurados.')
    for warning in warnings:
        lines.append('Aviso: ' + warning)
    lines.extend(['', 'Analisar evidências e próximos passos: /status --ai ou centaur status --ai'])
    # Arquivos locais podem conter controles de terminal; preserve somente texto.
    return ''.join(char if char.isprintable() or char == '\n' else ' ' for char in '\n'.join(lines))


@lru_cache(maxsize=1)
def lifecycle_reader():
    path = SKILL_ROOT / 'graphify/scripts/lifecycle.py'
    spec = importlib.util.spec_from_file_location('centaur_status_lifecycle', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lifecycle_status(root, start_line):
    data = lifecycle_reader().load_project(Path(root).resolve())
    projection = {key: data[key] for key in ('revision', 'dirty', 'warnings')}
    projection['contracts'] = [{key: contract[key] for key in
                               ('id', 'version', 'status', 'scope', 'hash', 'rules')}
                              for contract in data['contracts']]
    lines = json.dumps(projection, ensure_ascii=False, indent=2).splitlines()
    start = int(start_line)
    if start < 1:
        raise ValueError('A linha inicial deve ser maior que zero.')
    return f'Ciclo: linhas {start}–{min(start + 199, len(lines))} de {len(lines)}\n' + '\n'.join(lines[start - 1:start + 199])


ANALYSIS_INSTRUCTIONS = '''
Execute uma análise /status --ai somente leitura com o backend conectado. Leia check/SKILL.md, o ciclo normativo
em graphify/references/lifecycle.md e o contrato de módulos. Consulte project_status
para a árvore atual; leia READMEs, contratos, estado, evidências e fontes relevantes.
Use lifecycle_status, paginando até o fim, para conferir hashes de evidências, contratos,
estado e dependências pelas fontes atuais. Seu resultado é estrutural, não prova execução
nova de testes nem substitui aceite e integração das specs.
Classifique em árvore por mestre e filhas: a implementar, em revisão, feito registrado,
pode concluir (recomendação comprovada) e pode rodar (recomendação com pré-condições).
Para cada recomendação, cite caminhos e evidências, dependências qualificadas, posse/locks,
aprovação do contrato, integração e aceite. Detecte dependências ausentes ou circulares.
Uma mestre só pode concluir com filhas e aceite de integração comprovados. Checkboxes e
status não comprovam comportamento. Evidências precisam corresponder às fontes atuais.
Não execute tarefas, comandos ou alterações; não atualize status nem marque checkboxes.
Você só tem ferramentas de leitura; não pode executar testes. Hashes são conferidos
pela projeção lifecycle_status, sem permitir comandos arbitrários.
Se não conseguir comprovar um gate pelas leituras, indique verificação pendente e o check
necessário, sem liberar execução nem recomendar conclusão como confirmada. Não confunda
feito registrado com conclusão verificada. Não use delegate_task para contornar restrições.
Entregue a árvore e uma lista curta de recomendações e bloqueios com referências.
'''


class StatusTools(ProjectTools):
    definitions = [entry for entry in TOOLS if entry['function']['name'] in
                   ('read_skill', 'read_file', 'list_files')] + [
        tool('project_status', 'Árvore das specs registradas, somente leitura.', {}),
        tool('lifecycle_status', 'Conferir contratos, dependências e evidências com hashes atuais; não executa testes.',
             {'start_line': 'Primeira linha da projeção (1 para começar); continue até ler todas as linhas'})]

    def _execute(self, name, arguments):
        if name == 'lifecycle_status':
            return lifecycle_status(self.root, arguments['start_line'])
        if name == 'project_status':
            return render_status(self.root)
        if name not in ('read_skill', 'read_file', 'list_files'):
            raise ValueError('Análise de status permite somente leitura.')
        return super()._execute(name, arguments)
