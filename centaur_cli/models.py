"""O que cada opção de modelo realmente é: nome, modelo servido, contexto e preço.

Os dados vêm do catálogo do provedor (OpenRouter, cache do Codex) ou do que o
próprio CLI informou ao responder (Claude). Nada aqui é estimado: campo ausente
fica ausente na tela.
"""

import json
import os
import select
import shutil
import stat
import subprocess
import tempfile
import time
from datetime import date
from decimal import Decimal, InvalidOperation

from .credentials import credentials_path

BACKEND_LABELS = {'openrouter': 'OpenRouter', 'codex': 'Codex', 'claude': 'Claude'}
# Aliases aceitos pelo Claude Code; o modelo exato atrás de cada um muda com o tempo e a conta.
CLAUDE_ALIASES = {'fable': 'Mais capaz · problemas difíceis e trabalho longo',
                  'opus': 'Raciocínio profundo · arquitetura e investigação',
                  'sonnet': 'Equilíbrio · implementação do dia a dia',
                  'haiku': 'Mais rápido e econômico · tarefas simples'}
DEFAULT_LABELS = {'openrouter': 'Padrão da conta OpenRouter', 'codex': 'Padrão do Codex CLI',
                  'claude': 'Padrão do Claude Code'}


def learned_path():
    return credentials_path().parent / 'models.json'


def read_store():
    try:
        descriptor = os.open(learned_path(), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, encoding='utf-8') as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                return {}
            data = json.load(source)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_store(data):
    path = learned_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix='.models-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output_file:
            json.dump(data, output_file, ensure_ascii=False, indent=1)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_learned(backend):
    """Modelos já observados em respostas reais: {alias: {'id', 'context', 'output', 'seen'}}."""
    data = read_store().get(backend)
    if not isinstance(data, dict):
        return {}
    return {alias: entry for alias, entry in data.items()
            if isinstance(alias, str) and isinstance(entry, dict) and isinstance(entry.get('id'), str)}


def probe_claude(command=None, timeout=15):
    """Lista de modelos do Claude Code, com a versão exata de cada alias.

    É a resposta de inicialização do próprio CLI: não envia mensagem ao modelo
    nem consome tokens. Levanta RuntimeError quando o CLI não responde.
    """
    command = command or shutil.which('claude')
    if not command:
        raise RuntimeError('claude não instalado')
    arguments = [command, '--print', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose',
                 '--tools', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--setting-sources', '',
                 '--disable-slash-commands', '--no-session-persistence']
    try:
        with tempfile.TemporaryDirectory(prefix='centaur-models-') as directory:
            process = subprocess.Popen(arguments, cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                process.stdin.write(b'{"type":"control_request","request_id":"models","request":{"subtype":"initialize"}}\n')
                process.stdin.flush()
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if not select.select([process.stdout], [], [], .2)[0]:
                        if process.poll() is not None:
                            break
                        continue
                    line = process.stdout.readline()
                    if not line:
                        break
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(event, dict) and event.get('type') == 'control_response':
                        entries = event['response']['response']['models']
                        return [entry for entry in entries if isinstance(entry, dict) and isinstance(entry.get('value'), str)]
            finally:
                process.kill()
                process.wait(timeout=5)
                process.stdin.close()
                process.stdout.close()
    except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError):
        pass
    raise RuntimeError('o Claude Code não informou a lista de modelos')


def refresh_claude(command=None):
    """Consulta o CLI e guarda a lista para que a próxima abertura já a mostre."""
    entries = probe_claude(command)
    try:
        data = read_store()
        data['claude_models'] = {'seen': date.today().isoformat(), 'models': entries}
        write_store(data)
    except OSError:
        pass
    return entries


def cached_claude():
    cached = read_store().get('claude_models')
    entries = cached.get('models') if isinstance(cached, dict) else None
    return [entry for entry in entries if isinstance(entry, dict) and isinstance(entry.get('value'), str)] \
        if isinstance(entries, list) else []


def claude_catalog(entries):
    """Entradas do CLI → (catálogo, efforts por modelo, detalhes). 'default' descreve o Padrão do provedor."""
    contexts = {entry['id']: entry for entry in load_learned('claude').values()}
    catalog, efforts, details = {}, {}, {}
    for entry in entries:
        value = '' if entry['value'] == 'default' else entry['value']
        served = entry.get('resolvedModel') if isinstance(entry.get('resolvedModel'), str) else None
        name = entry.get('displayName') if isinstance(entry.get('displayName'), str) else ''
        description = entry.get('description') if isinstance(entry.get('description'), str) else ''
        if not value:
            name, description = description, ''  # "Default (recommended)" · "Fable 5.2": o nome útil é o segundo.
        levels = [level for level in entry.get('supportedEffortLevels') or [] if isinstance(level, str)]
        known = contexts.get(served, {})
        details[value] = {key: item for key, item in (
            ('name', name), ('description', description), ('served', served), ('modalities', ['text', 'image']),
            ('efforts', levels), ('fast', entry.get('supportsFastMode') is True),
            ('context', known.get('context')), ('output', known.get('output'))) if item}
        if value:
            catalog[value] = name
            efforts[value] = ['default', *levels]
    return catalog, efforts, details


def remember(backend, alias, identifier, context=None, output=None):
    """Registra o modelo que serviu um alias; falha de gravação nunca interrompe a conversa."""
    if not isinstance(identifier, str) or not identifier or len(identifier) > 128:
        return
    entry = {'id': identifier, 'seen': date.today().isoformat()}
    if type(context) is int and context > 0:
        entry['context'] = context
    if type(output) is int and output > 0:
        entry['output'] = output
    try:
        data = read_store()
        known = data.get(backend) if isinstance(data.get(backend), dict) else {}
        current = known.get(alias) if isinstance(known.get(alias), dict) else {}
        if {**current, **entry} == current:
            return  # Nada novo hoje: evita regravar a cada resposta.
        data[backend] = {**known, alias: {**current, **entry}}
        write_store(data)
    except OSError:
        pass


def tokens_label(count):
    if type(count) is not int or count <= 0:
        return ''
    if count >= 1_000_000:
        value = count / 1_000_000
        return (f'{value:.1f}'.rstrip('0').rstrip('.') if value < 10 else str(round(value))) + 'M'
    return f'{round(count / 1000)}k' if count >= 1000 else str(count)


def price_label(per_token):
    """Preço por token do catálogo → US$ por milhão de tokens."""
    try:
        value = Decimal(str(per_token)) * 1_000_000
    except (InvalidOperation, ValueError, TypeError):
        return ''
    if not value.is_finite() or value < 0:
        return ''
    if value == 0:
        return 'grátis'
    text = f'{value:.2f}' if value < 10 else f'{value:.0f}'
    return '$' + (text.rstrip('0').rstrip('.') if '.' in text else text)


def openrouter_details(entry):
    """Campos públicos de uma entrada de /api/v1/models."""
    pricing = entry.get('pricing') if isinstance(entry.get('pricing'), dict) else {}
    architecture = entry.get('architecture') if isinstance(entry.get('architecture'), dict) else {}
    reasoning = entry.get('reasoning') if isinstance(entry.get('reasoning'), dict) else {}
    details = {'name': entry.get('name') if isinstance(entry.get('name'), str) else '',
               'context': entry.get('context_length') if type(entry.get('context_length')) is int else None,
               'input_price': price_label(pricing.get('prompt')), 'output_price': price_label(pricing.get('completion')),
               'modalities': [item for item in architecture.get('input_modalities') or [] if isinstance(item, str)],
               'reasoning': bool(reasoning) or 'reasoning' in (entry.get('supported_parameters') or [])}
    top = entry.get('top_provider') if isinstance(entry.get('top_provider'), dict) else {}
    if type(top.get('max_completion_tokens')) is int:
        details['output'] = top['max_completion_tokens']
    return details


def codex_details(entry):
    window = entry.get('context_window') or entry.get('max_context_window')
    return {'name': entry.get('display_name') if isinstance(entry.get('display_name'), str) else '',
            'description': entry.get('description') if isinstance(entry.get('description'), str) else '',
            'context': window if type(window) is int and window > 0 else None,
            'modalities': [item for item in entry.get('input_modalities') or [] if isinstance(item, str)]}


def claude_details():
    """Aliases com sua função e o modelo exato que os atende, pela lista do CLI ou por respostas anteriores."""
    learned = load_learned('claude')
    listed = claude_catalog(cached_claude())[2]
    if listed:
        for alias, entry in learned.items():
            if alias in listed:
                listed[alias].update({key: entry[key] for key in ('context', 'output') if entry.get(key)})
                listed[alias].setdefault('seen', entry.get('seen'))
        return listed
    details = {}
    for alias, description in CLAUDE_ALIASES.items():
        details[alias] = {'description': description, 'modalities': ['text', 'image'], **describe_learned(learned.get(alias))}
    for alias, entry in learned.items():
        if alias not in details:
            details[alias] = {'modalities': ['text', 'image'], **describe_learned(entry)}
    return details


def describe_learned(entry):
    if not entry:
        return {}
    return {key: value for key, value in (('served', entry.get('id')), ('context', entry.get('context')),
                                          ('output', entry.get('output')), ('seen', entry.get('seen'))) if value}


def summary(model, details):
    """Uma linha curta para a lista: o que distingue este modelo dos vizinhos."""
    details = details or {}
    parts = []
    served, name = details.get('served'), details.get('name')
    if name and name != model:
        parts.append(name)
    if served and served != model:
        parts.append(served)
    if details.get('context'):
        parts.append(tokens_label(details['context']) + ' ctx')
    if details.get('input_price') and details.get('output_price'):
        parts.append('grátis' if details['input_price'] == details['output_price'] == 'grátis'
                     else f'{details["input_price"]}/{details["output_price"]}')
    if not parts and details.get('description'):
        parts.append(details['description'])
    return ' · '.join(parts)


def detail_lines(backend, model, details):
    """Painel do item em foco: até quatro linhas (rótulo, texto)."""
    details = details or {}
    if model == '':
        default = load_learned(backend).get('') if backend == 'claude' else None
        lines = [('Modelo', DEFAULT_LABELS[backend] + ' · definido fora do Centaur')]
        if details.get('served'):
            lines.append(('Servido', ' · '.join(part for part in (details.get('name'), details['served'], 'hoje, segundo o Claude Code') if part)))
        elif default:
            lines.append(('Servido', f'{default["id"]} · visto em {default.get("seen", "?")}'
                          + (f' · {tokens_label(default.get("context"))} de contexto' if default.get('context') else '')))
        else:
            lines.append(('Servido', 'O provedor escolhe; o chat mostra o modelo exato após a primeira resposta.'))
        return lines
    if model is None:
        return [('Modelo', 'Digite o ID exato ou um alias aceito por ' + BACKEND_LABELS[backend] + '.')]
    lines = []
    if details.get('name') or details.get('description'):
        lines.append(('Modelo', ' · '.join(part for part in (details.get('name'), details.get('description')) if part)))
    if backend == 'claude':
        lines.append(('Servido', details['served'] + (f' · visto em {details["seen"]}' if details.get('seen') else '')
                      if details.get('served') else 'Alias do Claude Code; o modelo exato aparece após a primeira resposta.'))
    limits = [f'{tokens_label(details["context"])} de contexto' if details.get('context') else '',
              f'até {tokens_label(details["output"])} de saída' if details.get('output') else '']
    if any(limits):
        lines.append(('Limites', ' · '.join(part for part in limits if part)))
    if details.get('input_price') and details.get('output_price'):
        lines.append(('Preço', f'entrada {details["input_price"]} · saída {details["output_price"]} por 1M de tokens (US$)'))
    extras = []
    if 'image' in (details.get('modalities') or []):
        extras.append('imagens')
    if 'file' in (details.get('modalities') or []):
        extras.append('PDF')
    if details.get('reasoning'):
        extras.append('raciocínio ajustável')
    if details.get('efforts'):
        extras.append('effort ' + '/'.join(details['efforts']))
    if details.get('fast'):
        extras.append('modo rápido')
    if extras:
        lines.append(('Aceita', ' · '.join(extras)))
    return lines[:4] or [('Modelo', 'Sem dados no catálogo; o ID será usado como digitado.')]
