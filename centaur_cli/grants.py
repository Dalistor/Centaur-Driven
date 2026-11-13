"""Comandos que o usuário liberou explicitamente para rodar sem confirmação nesta pasta.

Uma regra é um comando escrito pelo usuário: `git push origin main` libera exatamente
esse comando; `git push *` libera `git push` com quaisquer argumentos. Regras nascem só
de um gesto do usuário ($allow ou "a" na confirmação) e ficam fora do projeto, onde as
ferramentas de arquivo do agente não alcançam.
"""

import json
import os
import re
import shlex
import stat
import tempfile
from pathlib import Path

from .credentials import credentials_path

SEPARATORS = (';', '&&', '||', '|')
PUNCTUATION = ';&|><()'
MAX_RULES = 200
# Redirecionamentos inofensivos, comuns em comandos de build e deploy.
HARMLESS = re.compile(r'\s+(?:2>&1|[12]?>\s*/dev/null)(?=\s|$)')


class Request(str):
    """Texto de uma confirmação; `remember` lista as regras que "sempre permitir" gravaria."""
    remember = ()


def request(text, remember=()):
    value = Request(text)
    value.remember = tuple(remember)
    return value


def grants_path():
    return credentials_path().parent / 'permissions.json'


def segments(command):
    """Divide em comandos simples; None quando o shell poderia executar algo além deles."""
    if (not isinstance(command, str) or any(mark in command for mark in ('\n', '\r', '`', '$(', '<(', '>('))
            or len(command) > 4000):
        return None
    if '"' not in command and "'" not in command:
        command = HARMLESS.sub('', ' ' + command).strip()
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=PUNCTUATION)
        lexer.whitespace_split = True
        lexer.commenters = ''
        tokens = list(lexer)
    except ValueError:
        return None
    parts, current = [], []
    for token in tokens:
        if token and all(character in PUNCTUATION for character in token):
            if token not in SEPARATORS or not current:
                return None
            parts.append(current)
            current = []
        else:
            current.append(token)
    if not current:
        return None
    return parts + [current]


def parse_rule(text):
    """Tokens de uma regra válida; ValueError explica o que o usuário deve corrigir."""
    parts = segments(text.strip()) if isinstance(text, str) else None
    if not parts or len(parts) != 1:
        raise ValueError('Regra deve ser um único comando simples, sem ;, &&, |, redirecionamento ou substituição.')
    tokens = parts[0]
    if tokens[0] == '*' or '=' in tokens[0] or '*' in tokens[:-1]:
        raise ValueError('Comece pelo nome do comando; * só vale no fim, para "quaisquer argumentos".')
    return tokens


def matches(rule, tokens):
    return tokens[:len(rule) - 1] == rule[:-1] if rule[-1] == '*' else tokens == rule


def allowed(command, rules):
    """Todo comando simples da linha precisa estar coberto por uma regra."""
    parts = segments(command)
    if not parts or not rules:
        return False
    parsed = []
    for rule in rules:
        try:
            parsed.append(parse_rule(rule))
        except ValueError:
            continue
    return all(any(matches(rule, tokens) for rule in parsed) for tokens in parts)


def suggested(command):
    """Regras exatas que tornariam este comando automático; vazio se não puder ser lembrado."""
    parts = segments(command)
    if not parts or any(tokens[-1] == '*' or '=' in tokens[0] for tokens in parts):
        return []
    rules = []
    for tokens in parts:
        rule = shlex.join(tokens)
        try:
            if parse_rule(rule) == tokens and rule not in rules:
                rules.append(rule)
        except ValueError:
            return []
    return rules


def read_store():
    """Retorna (dados, erro). Arquivo alheio ou gravável por outros não concede nada."""
    path = grants_path()
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return {}, None
    except OSError as error:
        return {}, f'não foi possível ler {path}: {error.strerror or error}'
    try:
        with os.fdopen(descriptor, encoding='utf-8') as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o022:
                return {}, f'{path} deve ser um arquivo comum do próprio usuário, sem escrita para grupo ou outros'
            data = json.load(source)
        projects = data['projects']
        if not isinstance(projects, dict) or any(not isinstance(rules, list) or any(not isinstance(rule, str) for rule in rules)
                                                 for rules in projects.values()):
            raise ValueError('"projects" deve mapear pastas para listas de comandos')
        return projects, None
    except (ValueError, KeyError, TypeError) as error:
        return {}, f'{path} inválido: {error}'


def load_rules(root):
    """Regras desta pasta, seguidas das gerais ("*", editadas à mão)."""
    projects, error = read_store()
    return [*projects.get(str(Path(root).resolve()), []), *projects.get('*', [])], error


def project_rules(root):
    return list(read_store()[0].get(str(Path(root).resolve()), []))


def write_rules(root, rules):
    projects, error = read_store()
    if error:
        raise ValueError(error)
    key = str(Path(root).resolve())
    if rules:
        projects[key] = rules
    else:
        projects.pop(key, None)
    path = grants_path()
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid():
        raise ValueError('Pasta de configuração insegura.')
    descriptor, temporary = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump({'projects': projects}, output, ensure_ascii=False, indent=1)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def grant(root, rule):
    """Acrescenta a regra; devolve o texto normalizado."""
    tokens = parse_rule(rule)
    rule = ' '.join('*' if index == len(tokens) - 1 and token == '*' else shlex.quote(token)
                    for index, token in enumerate(tokens))
    rules = project_rules(root)
    if rule not in rules:
        if len(rules) >= MAX_RULES:
            raise ValueError(f'Limite de {MAX_RULES} regras nesta pasta; remova alguma com $revoke.')
        write_rules(root, rules + [rule])
    return rule


def revoke(root, reference):
    """Remove pelo número mostrado em $allow ou pelo texto exato; devolve a regra removida."""
    rules = project_rules(root)
    reference = reference.strip()
    if reference.isdigit() and 1 <= int(reference) <= len(rules):
        removed = rules.pop(int(reference) - 1)
    elif reference in rules:
        rules.remove(reference)
        removed = reference
    else:
        raise ValueError('Regra não encontrada; $allow lista as regras numeradas.')
    write_rules(root, rules)
    return removed
