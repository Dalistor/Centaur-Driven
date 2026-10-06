"""Canonical contract reader and conservative lifecycle projection (stdlib only)."""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
RULE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
FLOW_ID = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,39}$")
TEXT_EXT = {'.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.java', '.kt', '.vue', '.svelte', '.css', '.html', '.md', '.json', '.yaml', '.yml', '.sql', '.toml', '.sh', '.dart', '.cs', '.rb', '.php', '.txt'}
DENIED = {'.git', 'node_modules', '.venv', 'venv', 'memory-pending', 'ai-memory', 'backups', 'tmp', 'graphify'}


def project_path(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError(f'Caminho relativo inválido: {relative}')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Caminho fora do projeto: {relative}')
    return path


def readable_path(root, relative):
    path = project_path(root, relative)
    parts = path.relative_to(root.resolve()).parts
    if any(p in DENIED or p.startswith('.env') for p in parts) or path.suffix.lower() in {'.pem', '.key', '.p12', '.pfx'} or any(s in path.name.lower() for s in ('secret', 'credential', 'id_rsa', 'id_ed25519')):
        raise ValueError(f'Arquivo reservado não pode ser incorporado: {relative}')
    return path


def read_json(path):
    if path.stat().st_size > 2_000_000:
        raise ValueError(f'JSON excede 2 MB: {path.name}')
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def git(root, *args):
    try:
        p = subprocess.run(['git', '--no-optional-locks', '-C', str(root), *args], capture_output=True, text=True, timeout=10)
        return p.stdout.strip() if p.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_specification(contract):
    """Validate optional conceptual definitions against the contract's rule IDs."""
    for rule in contract['rules']:
        require(rule.get('kind', 'functional') in ('functional', 'non_functional'), 'kind deve ser functional ou non_functional')
    spec = contract.get('specification')
    if spec is None:
        return
    require(isinstance(spec, dict), 'specification deve ser objeto')

    def texts(value, name, nonempty=False):
        require(isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value), f'{name} deve ser lista de textos')
        require(not nonempty or bool(value), f'{name} não pode ser vazio')

    actors = spec.get('actors', [])
    texts(actors, 'actors')
    texts(spec.get('exclusions', []), 'exclusions')
    require(len(set(actors)) == len(actors), 'Ator duplicado')
    cases = spec.get('use_cases', [])
    require(isinstance(cases, list), 'use_cases deve ser lista')
    ids = set()
    rules = {r['id'] for r in contract['rules']}
    for case in cases:
        require(isinstance(case, dict), 'Caso de uso deve ser objeto')
        cid = case.get('id')
        require(isinstance(cid, str) and RULE_ID.fullmatch(cid) and cid not in ids, 'ID de caso de uso inválido ou duplicado')
        ids.add(cid)
        require(isinstance(case.get('title'), str) and case['title'].strip(), 'Título de caso de uso obrigatório')
        require(isinstance(case.get('actor'), str) and case['actor'] in actors, 'Ator do caso de uso não declarado')
        for field in ('preconditions', 'main_flow', 'alternatives', 'postconditions', 'rules'):
            texts(case.get(field, []), field, nonempty=field in ('main_flow', 'rules'))
        require(set(case['rules']).issubset(rules), 'Caso de uso referencia regra desconhecida')
    model = spec.get('data_model', {})
    require(isinstance(model, dict), 'data_model deve ser objeto')
    entities = model.get('entities', [])
    require(isinstance(entities, list), 'entities deve ser lista')
    names = set()
    for entity in entities:
        require(isinstance(entity, dict), 'Entidade deve ser objeto')
        name = entity.get('name')
        require(isinstance(name, str) and name.strip() and name not in names, 'Nome de entidade inválido ou duplicado')
        names.add(name)
        texts(entity.get('attributes', []), 'attributes')
        texts(entity.get('invariants', []), 'invariants')
    relations = model.get('relationships', [])
    require(isinstance(relations, list), 'relationships deve ser lista')
    for relation in relations:
        require(isinstance(relation, dict), 'Relação deve ser objeto')
        require(isinstance(relation.get('from'), str) and relation['from'] in names and isinstance(relation.get('to'), str) and relation['to'] in names, 'Relação referencia entidade desconhecida')
        require(relation.get('cardinality') in ('1:1', '1:N', 'N:1', 'N:N'), 'Cardinalidade inválida')
        texts(relation.get('invariants', []), 'invariants')


def read_contract(path):
    c = read_json(path)
    require(isinstance(c, dict), 'Contrato deve ser um objeto')
    require(c.get('schema') == 1, 'schema do contrato deve ser 1')
    require(isinstance(c.get('id'), str) and SLUG.fullmatch(c['id']), 'id de contrato inválido')
    require(type(c.get('version')) is int and c['version'] > 0, 'version deve ser inteiro positivo')
    for k in ('title', 'scope', 'intent'):
        require(isinstance(c.get(k), str) and bool(c[k].strip()), f'{k} obrigatório')
    require(c.get('status') in ('draft', 'approved', 'retired'), 'status de contrato inválido')
    require(isinstance(c.get('rules'), list) and c['rules'], 'rules deve conter ao menos uma regra')
    require(isinstance(c.get('extends', []), list), 'extends deve ser lista')
    for ref in c.get('extends', []):
        require(isinstance(ref, str) and re.fullmatch(r'[a-z0-9][a-z0-9_-]*@[1-9][0-9]*', ref), 'Referência extends inválida')
    if c['status'] == 'approved':
        approval = c.get('approval', {})
        require(isinstance(approval, dict) and all(isinstance(approval.get(k), str) and approval[k].strip() for k in ('by', 'at', 'reference')), 'Contrato aprovado exige autoria, data e referência da autorização')
    ids = set()
    for rule in c['rules']:
        require(isinstance(rule, dict), 'Regra deve ser objeto')
        require(isinstance(rule.get('id'), str) and RULE_ID.fullmatch(rule['id']), 'id de regra inválido')
        require(rule['id'] not in ids, 'Regra duplicada')
        ids.add(rule['id'])
        require(isinstance(rule.get('description'), str) and rule['description'].strip(), 'Descrição da regra obrigatória')
        require(isinstance(rule.get('acceptance'), list) and rule['acceptance'] and all(isinstance(x, str) and x.strip() for x in rule['acceptance']), 'acceptance deve conter comportamentos observáveis')
        require(isinstance(rule.get('depends_on', []), list) and all(isinstance(x, str) and x.strip() for x in rule.get('depends_on', [])), 'depends_on deve ser lista de IDs qualificados')
    for k in ('boundaries', 'autonomy', 'decisions'):
        require(isinstance(c.get(k, []), list) and all(isinstance(x, str) for x in c.get(k, [])), f'{k} deve ser lista de textos')
    validate_specification(c)
    return c


def source_record(root, entry):
    require(isinstance(entry, dict) and isinstance(entry.get('path'), str), 'Fonte exige path')
    path = readable_path(root, entry['path'])
    start, end = entry.get('start', 1), entry.get('end', entry.get('start', 1) + 39)
    require(type(start) is int and type(end) is int and 0 < start <= end, 'Intervalo de linhas inválido')
    base = {'path': entry['path'], 'start': start, 'end': end, 'role': str(entry.get('role', 'Implementação')), 'exists': path.is_file()}
    if not path.is_file():
        return {**base, 'code': '', 'warning': 'Arquivo ausente'}
    if path.suffix.lower() not in TEXT_EXT or path.stat().st_size > 1_000_000:
        return {**base, 'code': '', 'warning': 'Prévia indisponível para este tipo ou tamanho'}
    lines = path.read_text(encoding='utf-8').splitlines()
    require(start <= max(len(lines), 1), f'Linha inicial fora do arquivo: {entry["path"]}')
    stop = min(end, start + 119, len(lines))
    return {**base, 'end': stop, 'sha256': digest(path), 'code': '\n'.join(lines[start-1:stop]), 'warning': 'Trecho limitado a 120 linhas' if end > stop else ''}


def evidence_record(root, evidence_id, contract, fingerprint, rule, sources):
    require(isinstance(evidence_id, str) and SLUG.fullmatch(evidence_id), 'ID de evidência inválido')
    path = readable_path(root, f'.centaur/evidence/{evidence_id}.json')
    e = read_json(path)
    require(isinstance(e, dict) and e.get('schema') == 1 and e.get('id') == evidence_id, 'Identidade de evidência inválida')
    require(e.get('contract') == f'{contract["id"]}@{contract["version"]}' and e.get('rule') == rule['id'], 'Evidência pertence a outro contrato/regra')
    require(e.get('result') in ('passed', 'failed'), 'Resultado inválido')
    require(e.get('method') in ('test', 'manual', 'inspection', 'integration'), 'Método inválido')
    require(all(isinstance(e.get(k), str) and e[k].strip() for k in ('at', 'summary', 'reference')), 'Evidência exige data, resumo e referência')
    files = e.get('files', {})
    require(isinstance(files, dict) and bool(files), 'Evidência exige hashes das fontes verificadas')
    stale = e.get('contract_hash') != fingerprint
    for relative, sha in files.items():
        require(isinstance(sha, str) and re.fullmatch(r'[0-9a-f]{64}', sha), 'SHA-256 inválido')
        f = readable_path(root, relative)
        stale = stale or not f.is_file() or digest(f) != sha
    stale = stale or not sources or any(s['path'] not in files or not s['exists'] for s in sources)
    return {**e, 'path': str(path.relative_to(root)), 'verification': 'desatualizada' if stale else ('aprovada' if e['result'] == 'passed' else 'falhou')}


def delivery_record(value):
    if not value:
        return {'stage': 'local', 'reference': '', 'revision': '', 'at': ''}
    require(isinstance(value, dict) and value.get('stage') in ('local', 'integrated', 'published'), 'Entrega inválida')
    if value['stage'] != 'local':
        require(all(isinstance(value.get(k), str) and value[k].strip() for k in ('reference', 'revision', 'at')), 'Integração/publicação exige referência, revisão e data')
    return value


def legacy_specs(root, scopes, warnings):
    records = []
    for scope, config in scopes.items():
        try:
            directory = project_path(root, config['specs'])
            for path in sorted(directory.glob('*/README.md')):
                readable_path(root, str(path.relative_to(root)))
                text = path.read_text(encoding='utf-8')
                def field(name):
                    m = re.search(r'^\*\*' + re.escape(name) + r':\*\*\s*(.*)$', text, re.M)
                    return m.group(1).strip() if m else ''
                title = re.search(r'^#\s+(.+)', text, re.M)
                checklist = re.search(r'^## Checklist de conclusão\s*$(.*?)(?=^## |\Z)', text, re.M | re.S)
                tasks = [{'title': t, 'done': x.lower() == 'x'} for x, t in re.findall(r'^\s*-\s*\[([ xX])\]\s*(.+)$', checklist.group(1) if checklist else text, re.M)]
                records.append({'id': f'{scope}/{path.parent.name}', 'scope': scope, 'title': title.group(1) if title else path.parent.name, 'status': field('Status') or 'Sem status', 'contract': field('Contrato'), 'rules': field('Regras'), 'parent': field('Spec mestre'), 'children': field('Specs filhas'), 'dependencies': field('Dependências'), 'tasks': tasks, 'path': str(path.relative_to(root)), 'body': text})
        except (ValueError, KeyError, OSError, UnicodeError) as error:
            warnings.append(f'Specs de {scope}: {error}')
    return records


def spec_completion_issues(data, identifier, visiting=()):
    """Check observed completion independently of a README status/checkbox claim."""
    if identifier in visiting:
        return [f'{identifier}: ciclo entre specs ou dependências']
    specs = {spec['id']: spec for spec in data['specs']}
    spec = specs.get(identifier)
    if spec is None:
        return [f'{identifier}: spec ausente']
    issues = []
    if not spec['tasks'] or not all(task['done'] for task in spec['tasks']):
        issues.append(f'{identifier}: checklist ausente ou tasks pendentes')
    contracts = {f'{contract["id"]}@{contract["version"]}': contract for contract in data['contracts']}
    contract = contracts.get(spec['contract'].strip('` '))
    if contract is None or contract['status'] != 'approved':
        issues.append(f'{identifier}: contrato vigente aprovado não vinculado')
    else:
        references = re.findall(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)?', spec.get('rules', ''))
        rules = {rule['id']: rule for rule in contract['rules']}
        if not references:
            issues.append(f'{identifier}: Regras da entrega não declaradas')
        for ref in references:
            rule = rules.get(ref.removeprefix(contract['id'] + '/'))
            if not rule:
                issues.append(f'{identifier}: regra desconhecida {ref}')
            elif (not rule['eligible'] or rule['issues'] or rule['waiting']
                  or rule['implementation'] != 'implementada' or rule['verification'] != 'aprovada'
                  or rule['delivery']['stage'] not in ('integrated', 'published')):
                issues.append(f'{identifier}: {rule["key"]} exige implementação, evidência corrente e integração')
    reference_pattern = r'(?<![\w/])([\w.-]+/[\w.-]+)(?![\w/])'
    empty_links = ('', '—', '-', 'Nenhuma')
    for field in ('parent', 'children', 'dependencies'):
        value = spec.get(field, '')
        if value not in empty_links and not re.findall(reference_pattern, value):
            issues.append(f'{identifier}: {field} exige ID qualificado')
    parents = re.findall(reference_pattern, spec.get('parent', ''))
    if len(parents) > 1:
        issues.append(f'{identifier}: spec mestre ambígua')
    for parent in parents:
        if parent not in specs:
            issues.append(f'{identifier}: mestre ausente {parent}')
        elif parent == identifier:
            issues.append(f'{identifier}: ciclo entre specs mestre/filhas')
        else:
            listed = re.findall(reference_pattern, specs[parent].get('children', ''))
            if listed and identifier not in listed:
                issues.append(f'{identifier}: vínculo mestre/filha divergente em {parent}')
    children = set(re.findall(reference_pattern, spec.get('children', '')))
    children.update(child['id'] for child in data['specs']
                    if identifier in re.findall(reference_pattern, child.get('parent', '')))
    dependencies = set(re.findall(reference_pattern, spec.get('dependencies', '')))
    for related in sorted(children | dependencies):
        if related in children and related in specs:
            parents = re.findall(reference_pattern, specs[related].get('parent', ''))
            if parents and parents != [identifier]:
                issues.append(f'{identifier}: vínculo mestre/filha divergente em {related}')
        issues.extend(spec_completion_issues(data, related, (*visiting, identifier)))
    return list(dict.fromkeys(issues))


def validate_use_case(value, contract):
    """Constrain editable diagrams; a use case is a draft, never contract approval."""
    require(isinstance(value, dict) and value.get('schema') == 1, 'Caso de uso exige schema 1')
    require(value.get('contract') == contract['id'] and value.get('version') == contract['version'], 'Caso de uso deve apontar ao contrato vigente')
    for field in ('title', 'summary'):
        require(isinstance(value.get(field), str) and 0 < len(value[field].strip()) <= 500, f'{field} inválido')
    nodes, edges = value.get('nodes'), value.get('edges')
    require(isinstance(nodes, list) and 1 <= len(nodes) <= 32, 'Fluxo exige entre 1 e 32 passos')
    require(isinstance(edges, list) and len(edges) <= 64, 'Fluxo excede 64 conexões')
    ids = set()
    for node in nodes:
        require(isinstance(node, dict) and isinstance(node.get('id'), str) and FLOW_ID.fullmatch(node['id']), 'ID de passo inválido')
        require(node['id'] not in ids, 'Passo duplicado')
        ids.add(node['id'])
        require(node.get('kind') in ('start', 'action', 'decision', 'end'), 'Tipo de passo inválido')
        require(isinstance(node.get('label'), str) and 0 < len(node['label'].strip()) <= 120, 'Título de passo inválido')
        require(isinstance(node.get('detail', ''), str) and len(node.get('detail', '')) <= 500, 'Descrição de passo inválida')
    require(any(n['kind'] == 'start' for n in nodes), 'Fluxo exige um início')
    seen = set()
    for edge in edges:
        require(isinstance(edge, dict) and edge.get('from') in ids and edge.get('to') in ids, 'Conexão aponta a passo inexistente')
        require(edge['from'] != edge['to'], 'Conexão para o próprio passo')
        require(isinstance(edge.get('label', ''), str) and len(edge.get('label', '')) <= 80, 'Rótulo de conexão inválido')
        key = (edge['from'], edge['to'], edge.get('label', ''))
        require(key not in seen, 'Conexão duplicada')
        seen.add(key)
    return value


def load_project(root):
    root = root.resolve()
    workspace = read_json(readable_path(root, '.centaur/workspace.json'))
    require(isinstance(workspace, dict), 'workspace.json deve ser objeto')
    scopes = workspace.get('scopes', {})
    require(isinstance(scopes, dict) and scopes, 'workspace.json não contém escopos')
    warnings, contracts, versions, invalid = [], [], {}, set()
    for scope, config in scopes.items():
        require(isinstance(config, dict) and isinstance(config.get('specs'), str), f'Escopo inválido: {scope}')
        project_path(root, config['specs'])
        project_path(root, config.get('code', '.'))
    contract_dir = project_path(root, '.centaur/contracts')
    for path in sorted(contract_dir.glob('*/v*.json')):
        try:
            readable_path(root, str(path.relative_to(root)))
            c = read_contract(path)
            require(c['scope'] in scopes, 'Escopo do contrato não existe')
            require(path.parent.name == c['id'] and path.name == f'v{c["version"]:03d}.json', 'Caminho e versão do contrato divergem')
            versions[f'{c["id"]}@{c["version"]}'] = c
        except (ValueError, OSError, UnicodeError, TypeError) as error:
            invalid.add(path.parent.name)
            warnings.append(f'{path.relative_to(root)}: {error}')

    def closure(ref, visiting=()):
        require(ref not in visiting, f'Herança circular: {ref}')
        require(ref in versions, f'Contrato herdado ausente: {ref}')
        c = versions[ref]
        require(c['status'] == 'approved', f'Contrato herdado não aprovado: {ref}')
        require(not c.get('decisions'), f'Contrato herdado tem decisão material aberta: {ref}')
        result = {ref: c}
        for parent in c.get('extends', []):
            result.update(closure(parent, (*visiting, ref)))
        return result

    for cid in sorted({c['id'] for c in versions.values()}):
        candidates = [c for c in versions.values() if c['id'] == cid]
        approved = [c for c in candidates if c['status'] == 'approved']
        current = max(approved or candidates, key=lambda c: c['version'])
        c = {**current, 'path': f'.centaur/contracts/{cid}/v{current["version"]:03d}.json', 'draft_versions': [c['version'] for c in candidates if c['status'] == 'draft'], 'rules': [], 'versions': sorted(candidates, key=lambda c: c['version'], reverse=True)}
        contract_ok = cid not in invalid and c['status'] == 'approved'
        inherited = {}
        try:
            for parent in c.get('extends', []):
                inherited.update(closure(parent))
        except ValueError as error:
            contract_ok = False
            warnings.append(f'{cid}: {error}')
        c['hash'] = object_digest({f'{cid}@{c["version"]}': current, **inherited})
        c['inherited'] = [{'id': ref, 'title': x['title'], 'rules': x['rules'], 'boundaries': x.get('boundaries', [])} for ref, x in inherited.items()]
        state_path = readable_path(root, f'.centaur/state/{cid}.json')
        state = {}
        if state_path.exists():
            try:
                state = read_json(state_path)
                require(isinstance(state, dict) and state.get('schema') == 1 and state.get('contract') == f'{cid}@{c["version"]}' and isinstance(state.get('rules'), dict), 'Estado não corresponde à versão vigente')
                require(set(state['rules']).issubset({r['id'] for r in current['rules']}), 'Estado contém regra removida ou desconhecida')
            except (ValueError, OSError, TypeError) as error:
                state = {}
                warnings.append(f'{cid}: {error}')
        for rule in current['rules']:
            key = f'{cid}/{rule["id"]}'
            r = {**rule, 'key': key, 'contract': cid, 'version': c['version'], 'scope': c['scope'], 'sources': [], 'evidence': [], 'implementation': 'ausente', 'verification': 'não verificada', 'delivery': {'stage': 'local'}, 'eligible': contract_ok and not c.get('decisions'), 'issues': []}
            try:
                s = state.get('rules', {}).get(rule['id'], {})
                require(isinstance(s, dict), 'Estado de regra inválido')
                impl = s.get('implementation', 'ausente')
                require(impl in ('ausente', 'parcial', 'implementada'), 'Estado de implementação inválido')
                require(isinstance(s.get('sources', []), list) and isinstance(s.get('evidence', []), list), 'sources/evidence devem ser listas')
                r['sources'] = [source_record(root, x) for x in s.get('sources', [])]
                r['implementation'] = impl
                if impl == 'implementada' and (not r['sources'] or any(not x['exists'] for x in r['sources'])):
                    r['implementation'] = 'parcial'
                    r['issues'].append('Implementação declarada sem fontes existentes')
                for eid in s.get('evidence', []):
                    r['evidence'].append(evidence_record(root, eid, c, c['hash'], rule, r['sources']))
                states = {e['verification'] for e in r['evidence']}
                r['verification'] = next((x for x in ('desatualizada', 'falhou', 'aprovada') if x in states), 'não verificada')
                if not contract_ok and r['verification'] == 'aprovada':
                    r['verification'] = 'desatualizada'
                r['delivery'] = delivery_record(s.get('delivery'))
                r['specs'] = s.get('specs', [])
                r['notes'] = str(s.get('notes', ''))
            except (ValueError, OSError, UnicodeError, TypeError, KeyError) as error:
                r['verification'] = 'não verificada'
                r['eligible'] = False
                r['issues'].append(str(error))
                warnings.append(f'{key}: {error}')
            c['rules'].append(r)
        contracts.append(c)
    all_rules = {r['key']: r for c in contracts for r in c['rules']}
    def check_deps(key, seen=()):
        require(key not in seen, f'Dependência circular: {key}')
        require(key in all_rules, f'Dependência ausente: {key}')
        for dep in all_rules[key].get('depends_on', []):
            check_deps(dep, (*seen, key))
    def dependency_ready(key, seen=()):
        if key in seen or key not in all_rules:
            return False
        r = all_rules[key]
        return (r['eligible'] and not r['issues'] and r['implementation'] == 'implementada'
                and r['verification'] == 'aprovada' and r['delivery']['stage'] in ('integrated', 'published')
                and all(dependency_ready(dep, (*seen, key)) for dep in r.get('depends_on', [])))

    for r in all_rules.values():
        try:
            check_deps(r['key'])
        except ValueError as error:
            r['issues'].append(str(error))
            r['eligible'] = False
            warnings.append(f'{r["key"]}: {error}')
        waiting = [dep for dep in r.get('depends_on', []) if not dependency_ready(dep)]
        r['waiting'] = waiting
        if r['issues']:
            r['next'] = 'Corrigir registros e evidências'
        elif not r['eligible']:
            r['next'] = 'Resolver contrato ou decisão humana'
        elif waiting:
            r['next'] = 'Aguardar dependências integradas'
        elif r['implementation'] != 'implementada':
            r['next'] = 'Implementar comportamento'
        elif r['verification'] == 'falhou':
            r['next'] = 'Corrigir comportamento e verificar'
        elif r['verification'] != 'aprovada':
            r['next'] = 'Verificar comportamento'
        elif r['delivery']['stage'] == 'local':
            r['next'] = 'Integrar entrega validada'
        elif r['delivery']['stage'] == 'integrated':
            r['next'] = 'Avaliar publicação conforme autorização'
        else:
            r['next'] = 'Observar funcionamento'
    documents = []
    doc_dir = project_path(root, '.centaur/system')
    for path in sorted(doc_dir.rglob('*.md'))[:80]:
        try:
            readable_path(root, str(path.relative_to(root)))
            if path.stat().st_size <= 100_000:
                documents.append({'path': str(path.relative_to(root)), 'title': path.stem, 'body': path.read_text(encoding='utf-8')})
        except (ValueError, OSError, UnicodeError) as error:
            warnings.append(str(error))
    use_cases = []
    for path in sorted(project_path(root, '.centaur/use-cases').glob('*.json')):
        try:
            readable_path(root, str(path.relative_to(root)))
            case = read_json(path)
            contract = next((c for c in contracts if c['id'] == path.stem), None)
            require(contract is not None, 'Contrato do caso de uso ausente')
            validate_use_case(case, contract)
            use_cases.append({**case, 'file_hash': digest(path)})
        except (ValueError, OSError, TypeError) as error:
            warnings.append(f'{path.relative_to(root)}: {error}')
    return {'schema': 1, 'project': str(workspace.get('name') or root.name), 'generated_at': datetime.now(timezone.utc).isoformat(), 'revision': git(root, 'rev-parse', 'HEAD'), 'dirty': bool(git(root, 'status', '--porcelain', '--untracked-files=normal', '--', '.')), 'scopes': [{'id': k, 'owner': v.get('owner', 'Não definido'), 'code': v.get('code', '.')} for k, v in scopes.items()], 'contracts': contracts, 'use_cases': use_cases, 'specs': legacy_specs(root, scopes, warnings), 'documents': documents, 'warnings': warnings}
