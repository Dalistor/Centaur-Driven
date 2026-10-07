"""Adaptadores dos CLIs autenticados; ferramentas continuam no Centaur."""

import json
import copy
import os
import re
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from uuid import uuid4

from .openrouter import ModelReply
from .config import validate_effort
from .vision import split_images, native_input
from .interaction import TurnCancelled, RequestTimeout
from .speed import local_speed_support, fast_supported, validate_speed
from .native_usage import NativeBalance, BalanceUnavailable, claude_windows, read_codex_balance


def validate_arguments(value, spec):
    """Validate the entire typed batch before returning any executable call."""
    kind = spec.get('type')
    valid = {'string': lambda: isinstance(value, str), 'integer': lambda: type(value) is int,
             'number': lambda: type(value) in (int, float), 'boolean': lambda: type(value) is bool,
             'array': lambda: isinstance(value, list), 'object': lambda: isinstance(value, dict)}
    if kind in valid and not valid[kind]():
        raise ValueError('Argumentos devem respeitar os tipos da ferramenta.')
    if 'enum' in spec and value not in spec['enum']:
        raise ValueError('Opção de ferramenta fora do catálogo permitido.')
    if kind == 'string' and len(value) > spec.get('maxLength', float('inf')):
        raise ValueError('Texto excede o limite da ferramenta.')
    if kind in ('integer', 'number') and not spec.get('minimum', -float('inf')) <= value <= spec.get('maximum', float('inf')):
        raise ValueError('Número fora do limite da ferramenta.')
    if kind == 'array':
        if not spec.get('minItems', 0) <= len(value) <= spec.get('maxItems', float('inf')):
            raise ValueError('Quantidade de itens fora do contrato.')
        for item in value:
            validate_arguments(item, spec['items'])
    if kind == 'object':
        properties = spec['properties']
        if set(value) - set(properties) or not set(spec.get('required', [])) <= set(value):
            raise ValueError('Argumentos fora do contrato da ferramenta; tente novamente com /retry.')
        for name, item in value.items():
            validate_arguments(item, properties[name])

REPLY_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'content': {'type': ['string', 'null']},
        'calls': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'name': {'type': 'string'}, 'arguments': {'type': 'string'}},
            'required': ['name', 'arguments']}},
    }, 'required': ['content', 'calls'],
}
BRIDGE_INSTRUCTIONS = '''Você é o motor de uma sessão Centaur. A conversa e as ferramentas
fornecidas no JSON abaixo são a única interface desta sessão. Não use ferramentas nativas,
não execute comandos, não leia ou edite arquivos diretamente e não crie agentes nativos.
Responda no schema fornecido: content contém a resposta ao usuário; calls contém pedidos
às ferramentas Centaur, usando name e arguments como objeto JSON tipado. Campos opcionais
sem valor usam null. Sem chamadas, calls deve ser []. Nunca inclua cercas Markdown fora do JSON. Se precisar
consultar ou alterar algo, solicite a ferramenta e aguarde o resultado no próximo pedido.
Não descreva uma chamada como executada antes de receber seu resultado. Não há roteamento
OpenRouter nesta sessão. Subagentes mantêm o backend e podem escolher modelos do catálogo fornecido.
'''


def reply_schema(tools):
    """Typed arguments avoid double-escaping code, quotes and multiline content."""
    schema = copy.deepcopy(REPLY_SCHEMA)
    variants = []
    for entry in tools:
        function = entry['function']
        arguments = copy.deepcopy(function['parameters'])
        for key in arguments['properties']:
            arguments['properties'][key].pop('default', None)
            if key not in arguments.get('required', []):
                arguments['properties'][key] = {'anyOf': [arguments['properties'][key], {'type': 'null'}]}
        arguments['required'] = list(arguments['properties'])
        arguments['additionalProperties'] = False
        variants.append({'type': 'object', 'additionalProperties': False,
                         'properties': {'name': {'type': 'string', 'enum': [function['name']]},
                                        'arguments': arguments}, 'required': ['name', 'arguments']})
    if variants:
        schema['properties']['calls']['items'] = {'anyOf': variants}
    else:
        schema['properties']['calls']['maxItems'] = 0
    return schema


def decode_reply(text):
    text = text.lstrip('\ufeff').strip()
    # Accept a single complete fenced object, never scrape JSON from arbitrary prose.
    if text.startswith('```json\n') and text.endswith('\n```'):
        text = text[8:-4]
    elif text.startswith('```\n') and text.endswith('\n```'):
        text = text[4:-4]
    return json.loads(text)


def codex_output(directory, output):
    # Only completed public agent messages, not reasoning or partial event fragments.
    candidate, completed = None, False
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get('type') == 'turn.failed':
            raise ValueError('O Codex interrompeu o turno; confira conexão, limite e acesso ao modelo.')
        if event.get('type') == 'item.completed':
            item = event.get('item', {})
            if isinstance(item, dict) and item.get('type') == 'agent_message':
                candidate = item.get('text')
        if event.get('type') == 'turn.completed':
            completed = True
    # A recoverable error followed by a completed turn is valid. A final file
    # must never override a terminal failure found in the event stream.
    path = directory / 'reply.json'
    if path.is_file() and path.stat().st_size:
        if path.stat().st_size > 8_000_000:
            raise ValueError('Resposta excede 8 MB; divida o pedido em partes menores.')
        return decode_reply(path.read_text(encoding='utf-8'))
    if completed and isinstance(candidate, str) and len(candidate.encode()) <= 8_000_000:
        return decode_reply(candidate)
    raise ValueError('O Codex não entregou uma resposta final; tente novamente ou confira a instalação.')


def codex_usage(output):
    for line in reversed(output.splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get('type') == 'turn.completed':
            usage = event.get('usage') or {}
            if isinstance(usage, dict):
                return {'prompt_tokens': usage.get('input_tokens'),
                        'completion_tokens': usage.get('output_tokens')}
    return {}


def claude_output(output):
    """Only a complete result can supply executable calls; other events are metadata."""
    if len(output.encode('utf-8')) > 8_000_000:
        raise ValueError('Resposta excede 8 MB; divida o pedido em partes menores.')
    try:
        value = json.loads(output)
        if isinstance(value, dict) and value.get('type') in (None, 'result') and 'structured_output' in value:
            return value, {}
    except ValueError:
        pass
    result, events = None, []
    for line in output.splitlines():
        try: event = json.loads(line)
        except ValueError: continue
        if not isinstance(event, dict): continue
        if event.get('type') == 'rate_limit_event': events.append(event)
        elif event.get('type') == 'result': result = event
    if result is None:
        raise ValueError('Claude não entregou um resultado final estruturado.')
    return result, claude_windows(events)


def failure_hint(backend, text):
    """Return fixed public advice, never the original provider diagnostic."""
    text = text.lower()
    if 'schema' in text:
        return 'O CLI ou modelo recusou o schema de ferramentas; atualize o CLI ou selecione outro modelo.'
    if any(key in text for key in ('context length', 'context window', 'too many tokens')):
        return 'O contexto excedeu o limite do modelo; use $compact ou selecione um modelo com mais contexto.'
    if any(key in text for key in ('rate limit', 'usage limit', 'quota', 'exceeded your')):
        return 'Limite de uso atingido; aguarde a renovação ou selecione outro modelo/backend.'
    if 'unexpected argument' in text or 'unrecognized' in text:
        return 'O CLI não aceita uma opção de integração; atualize o CLI oficial.'
    if any(key in text for key in ('certificate', 'tls', 'ssl')):
        return 'Falha de certificado/TLS na execução local; confira proxy, certificados e conexão.'
    if any(key in text for key in ('stream disconnected', 'error sending request', 'failed to reconnect',
                                  'connection refused', 'reconnecting', 'connection reset', 'request timed out')):
        return 'A conexão da execução não interativa falhou; confira rede/proxy e retome com /retry.'
    if any(key in text for key in ('failed to load configuration', 'unknown variant', 'invalid value', 'unsupported service tier')):
        return 'O CLI recusou a configuração da execução não interativa; confira versão, modelo, effort e velocidade em $config.'
    return ''


class NativeTrace:
    """Observe complete public envelopes; never expose item text or partial calls."""

    phases = {'thread.started': 'sessão iniciada', 'turn.started': 'turno iniciado',
              'turn.completed': 'turno concluído', 'turn.failed': 'turno falhou',
              'error': 'aviso de erro', 'item.started': 'item iniciado',
              'item.updated': 'item atualizado', 'item.completed': 'item concluído',
              'system': 'sessão iniciada', 'assistant': 'resposta em andamento',
              'result': 'resultado recebido', 'rate_limit_event': 'aviso de cota'}

    def __init__(self, backend):
        self.backend, self.offset, self.buffer = backend, 0, b''
        self.phase, self.hint, self.failed = 'nenhum evento completo', '', False

    def feed(self, cumulative):
        data = cumulative.encode('utf-8') if isinstance(cumulative, str) else cumulative or b''
        self.buffer += data[self.offset:]
        self.offset = len(data)
        lines = self.buffer.split(b'\n')
        self.buffer = lines.pop()
        for line in lines:
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(event, dict):
                continue
            kind = event.get('type')
            if isinstance(kind, str) and kind in self.phases:
                self.phase = self.phases[kind]
            # Error events can describe a recoverable reconnect. Only a terminal
            # turn.failed (or Claude error result) ends the call early.
            detail = None
            if kind in ('error', 'turn.failed'):
                error = event.get('error')
                detail = event.get('message') or (error.get('message') if isinstance(error, dict) else error)
                self.failed = self.failed or kind == 'turn.failed'
            elif self.backend == 'claude' and kind == 'result' and (
                    event.get('is_error') or event.get('subtype') not in (None, 'success')):
                detail = event.get('result')
                self.failed = True
            if isinstance(detail, str):
                self.hint = failure_hint(self.backend, detail) or self.hint

    def diagnostic(self, stderr, input_bytes):
        errors = stderr.decode('utf-8', errors='replace') if isinstance(stderr, bytes) else stderr or ''
        hint = self.hint or failure_hint(self.backend, errors)
        evidence = (f'Último evento: {self.phase}; entrada: {input_bytes} bytes; '
                    f'saída: {self.offset} bytes; stderr: {len(errors.encode("utf-8"))} bytes.')
        if hint:
            return evidence + ' Aviso observado no CLI (pode ter sido recuperado): ' + hint
        return evidence + ' Causa não confirmada pelo CLI; silêncio não prova travamento. '


def process_failure(backend, code, stderr, output=''):
    """Classify known diagnostics without echoing prompts, account data or reasoning."""
    text = stderr.lower()
    # --json reports many failures on stdout. Read only public error/result
    # envelopes, never classify or display assistant/reasoning log text.
    for line in output.splitlines():
        try: event = json.loads(line)
        except ValueError: continue
        if not isinstance(event, dict): continue
        if event.get('type') in ('error', 'turn.failed'):
            error = event.get('error')
            detail = event.get('message') or (error.get('message') if isinstance(error, dict) else error)
        elif backend == 'claude' and event.get('type') == 'result' and event.get('is_error'):
            detail = event.get('result')
        else:
            continue
        if isinstance(detail, str): text += '\n' + detail.lower()
    hint = failure_hint(backend, text) or ('Confira conexão, acesso ao modelo e autenticação com '
            + ('codex login.' if backend == 'codex' else 'claude auth login.'))
    return f'{backend} encerrou com código {code}. {hint} Nenhuma ferramenta dessa resposta foi executada.'


class NativeClient:
    allows_model_routing = False
    supports_cancellation = True
    supports_request_timeout = True

    def __init__(self, backend, model=''):
        if backend not in ('codex', 'claude'):
            raise ValueError('Backend nativo inválido.')
        self.backend, self.fixed_model = backend, model
        try:
            self.timeout = int(os.environ.get('CENTAUR_NATIVE_TIMEOUT', '1800'))
            if not 30 <= self.timeout <= 3600:
                raise ValueError
        except ValueError:
            raise ValueError('CENTAUR_NATIVE_TIMEOUT deve ser um inteiro de 30 a 3600 segundos.') from None
        try:
            # Structured native replies can remain silent until the final result.
            # Silence is not evidence of failure; the absolute deadline still applies.
            self.idle_timeout = int(os.environ.get('CENTAUR_NATIVE_IDLE_TIMEOUT', '0'))
            if self.idle_timeout != 0 and not 30 <= self.idle_timeout <= 3600:
                raise ValueError
        except ValueError:
            raise ValueError('CENTAUR_NATIVE_IDLE_TIMEOUT deve ser 0 (desativado) ou um inteiro de 30 a 3600 segundos.') from None
        self.context_windows = {}
        self.model_efforts = {}
        self.speed_support = local_speed_support(backend)
        self.quota_windows = {}
        self.fast_version_checked = False
        self.command = shutil.which(backend)
        if not self.command:
            raise RuntimeError(f'{backend} não instalado ou fora do PATH. Instale o CLI oficial e faça login.')
        self.secrets = tuple(value for name in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN', 'ANTHROPIC_API_KEY',
                            'CLAUDE_CODE_OAUTH_TOKEN', 'OPENROUTER_API_KEY', 'OPENROUTER_CREDITS_KEY')
                             if (value := os.environ.get(name)))

    def credits(self):
        if self.backend == 'codex':
            return read_codex_balance(self.command)
        if not self.quota_windows:
            raise BalanceUnavailable('Claude informa cotas após uma resposta, quando disponíveis.', 'awaiting')
        return NativeBalance('claude', tuple(self.quota_windows.values()))

    def supports_fast(self, model):
        if self.backend == 'codex': self.speed_support = local_speed_support(self.backend)
        return fast_supported(self.backend, model, self.speed_support)

    def check_speed(self, model, speed):
        validate_speed(speed)
        if speed != 'fast': return
        if not self.supports_fast(model):
            raise ValueError('Modo rápido não anunciado para este modelo; selecione um modelo compatível ou Padrão.')
        if self.backend == 'claude' and not self.fast_version_checked:
            try:
                result = subprocess.run([self.command, '--version'], capture_output=True, text=True, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                raise RuntimeError('Não foi possível validar a versão do Claude para Fast; confira o CLI ou escolha Padrão.') from None
            version = re.search(r'\b(\d+)\.(\d+)\.(\d+)\b', result.stdout)
            if result.returncode or not version or tuple(map(int, version.groups())) < (2, 1, 205):
                raise ValueError('Atualize Claude Code para 2.1.205+ para modo rápido não interativo.')
            self.fast_version_checked = True

    def model_catalog(self):
        if self.backend == 'claude':
            self.input_modalities = {name: ['text', 'image'] for name in ('', 'haiku', 'sonnet', 'opus')}
            if self.fixed_model and re.fullmatch(r'claude-(haiku|sonnet|opus)-[0-9][a-z0-9-]*', self.fixed_model):
                self.input_modalities[self.fixed_model] = ['text', 'image']
            catalog = {'haiku': 'Tasks simples e rápidas', 'sonnet': 'Implementação comum',
                       'opus': 'Investigação complexa e maior risco'}
        else:
            cache = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'models_cache.json'
            try:
                data = json.loads(cache.read_text(encoding='utf-8'))
                self.input_modalities = {}
                self.context_windows = {}
                self.model_efforts = {}
                for entry in data['models']:
                    if not isinstance(entry, dict) or not isinstance(entry.get('slug'), str):
                        continue
                    self.input_modalities[entry['slug']] = entry.get('input_modalities', ['text', 'image']) or []
                    window = entry.get('context_window') or entry.get('max_context_window')
                    if type(window) is int and window > 0:
                        self.context_windows[entry['slug']] = window
                    levels = entry.get('supported_reasoning_levels') or []
                    self.model_efforts[entry['slug']] = ['default', *[
                        level['effort'] for level in levels if isinstance(level, dict)
                        and isinstance(level.get('effort'), str)]]
                catalog = {entry['slug']: entry.get('description', '') for entry in data['models']
                           if isinstance(entry, dict) and entry.get('visibility') == 'list' and isinstance(entry.get('slug'), str)}
            except (OSError, ValueError, KeyError, TypeError):
                catalog = {}
        if self.fixed_model:
            catalog.setdefault(self.fixed_model, 'Modelo principal configurado')
        return {name: description for name, description in catalog.items()
                if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', name)}

    def redact(self, text):
        for secret in self.secrets:
            text = text.replace(secret, '[CHAVE OCULTA]')
        return text

    def check_available(self):
        arguments = [self.command, 'exec', '--help'] if self.backend == 'codex' else [self.command, '--help']
        required = ('--model', '--ignore-user-config', '--ignore-rules', '--output-schema', '--output-last-message', '--json', '--ephemeral') if self.backend == 'codex' else (
            '--model', '--safe-mode', '--tools', '--json-schema', '--strict-mcp-config', '--no-session-persistence')
        try:
            result = subprocess.run(arguments, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError(f'Não foi possível iniciar {self.backend}; confira a instalação oficial.') from None
        if result.returncode or any(flag not in result.stdout for flag in required):
            raise RuntimeError(f'Atualize {self.backend}: a integração requer saída estruturada e isolamento de ferramentas/configuração.')

    def check_authentication(self):
        variables = ('OPENAI_API_KEY', 'CODEX_API_KEY') if self.backend == 'codex' else ('ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN')
        if any(os.environ.get(name, '').strip() for name in variables):
            return
        arguments = [self.command, 'login', 'status'] if self.backend == 'codex' else [self.command, 'auth', 'status']
        login = 'codex login' if self.backend == 'codex' else 'claude auth login'
        try:
            result = subprocess.run(arguments, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError(f'Não foi possível conferir a autenticação; execute {login}.') from None
        if result.returncode:
            raise RuntimeError(f'{self.backend} não autenticado. Execute {login} e abra o Centaur novamente.')

    def arguments(self, directory, model=None, effort='default', schema=None, speed='standard'):
        validate_effort(self.backend, effort)
        validate_speed(speed)
        if self.backend == 'codex':
            arguments = [self.command, 'exec', '--ignore-user-config', '--ignore-rules',
                         '--sandbox', 'read-only', '--ephemeral', '--skip-git-repo-check',
                         '--disable', 'shell_tool', '--disable', 'unified_exec',
                         '--disable', 'multi_agent', '--disable', 'multi_agent_v2',
                         '--config', 'web_search="disabled"', '--config', 'project_doc_max_bytes=0',
                         '--disable', 'skill_mcp_dependency_install', '--color', 'never',
                         '--json',
                         '--enable' if speed == 'fast' else '--disable', 'fast_mode',
                         '--config', 'service_tier=' + json.dumps('fast' if speed == 'fast' else 'default'),
                         '--output-schema', str(directory / 'schema.json'),
                         '--output-last-message', str(directory / 'reply.json')]
        else:
            arguments = [self.command, '--print', '--safe-mode', '--tools', '',
                         '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                         '--setting-sources', '', '--permission-mode', 'dontAsk',
                         '--no-session-persistence', '--output-format', 'stream-json', '--verbose',
                         '--settings', json.dumps({'fastMode': speed == 'fast'}),
                         '--json-schema', json.dumps(schema or REPLY_SCHEMA)]
        selected = self.fixed_model if model is None else model
        if selected:
            arguments += ['--model', selected]
        if effort != 'default':
            if self.backend == 'codex':
                arguments += ['--config', 'model_reasoning_effort=' + json.dumps(effort)]
            else:
                arguments += ['--effort', effort]
        if self.backend == 'codex':
            arguments += ['-']
        return arguments

    def complete(self, model, messages, tools, *, cost_tier=None, session_id=None, effort='default', cancel_event=None, speed='standard', request_timeout=None):
        if request_timeout is not None and (isinstance(request_timeout, bool)
                or not isinstance(request_timeout, (int, float)) or not 0 < request_timeout <= 3600):
            raise ValueError('Tempo limite de requisição inválido.')
        timeout = self.timeout if request_timeout is None else min(self.timeout, request_timeout)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 3600:
            raise ValueError('Tempo limite de requisição inválido.')
        if cost_tier is not None:
            raise ValueError('cost_tier é exclusivo de OpenRouter.')
        if model != self.fixed_model and model not in self.model_catalog():
            raise ValueError(f'Modelo não listado no catálogo {self.backend}.')
        self.check_speed(model, speed)
        conversation, images = split_images(messages, max_images=32)
        prompt = BRIDGE_INSTRUCTIONS + '\n' + self.redact(json.dumps({'conversation': conversation, 'tools': tools}, ensure_ascii=False))
        env = {name: value for name, value in os.environ.items()
               if name not in ('OPENROUTER_API_KEY', 'OPENROUTER_CREDITS_KEY')}
        with tempfile.TemporaryDirectory(prefix='centaur-native-') as temporary:
            directory = Path(temporary)
            schema = reply_schema(tools)
            (directory / 'schema.json').write_text(json.dumps(schema), encoding='utf-8')
            arguments, input_text = native_input(self.backend, directory, self.arguments(directory, model, effort, schema, speed), prompt, images)
            try:
                process = subprocess.Popen(arguments, cwd=directory,
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True, env=env,
                                           start_new_session=True)
                try:
                    deadline, last_output = time.monotonic() + timeout, time.monotonic()
                    pending_input, received = input_text, (0, 0)
                    trace, partial_errors = NativeTrace(self.backend), b''
                    input_bytes = len(input_text.encode('utf-8'))
                    while True:
                        if cancel_event is not None and cancel_event.is_set():
                            self.stop_process(process)
                            raise TurnCancelled('Turno interrompido pelo usuário.')
                        now = time.monotonic()
                        remaining = deadline - now
                        if remaining <= 0:
                            raise subprocess.TimeoutExpired(arguments, timeout)
                        if self.idle_timeout > 0 and now - last_output >= self.idle_timeout:
                            self.stop_process(process)
                            error = RequestTimeout if request_timeout is not None else RuntimeError
                            raise error(f'{self.backend}: sem nova saída do CLI por {self.idle_timeout:g} segundos; '
                                        'execução encerrada e checkpoints preservados. Confira conexão/modelo, '
                                        'use /retry para retomar. CENTAUR_NATIVE_IDLE_TIMEOUT=0 desativa esse limite opcional. '
                                        'Nenhuma ferramenta dessa resposta foi executada.')
                        try:
                            output, errors = process.communicate(pending_input, timeout=min(0.1, remaining))
                            break
                        except subprocess.TimeoutExpired as partial:
                            pending_input = None
                            partial_errors = partial.stderr or b''
                            # communicate exposes cumulative bytes; heartbeats from the UI
                            # must never masquerade as activity from the native process.
                            sizes = (len(partial.output or b''), len(partial.stderr or b''))
                            if sizes[0] > 8_000_000 or sizes[1] > 1_000_000:
                                self.stop_process(process)
                                raise RuntimeError(f'{self.backend}: saída local excedeu o limite; '
                                                   'nenhuma ferramenta dessa resposta foi executada.')
                            if sizes != received:
                                received, last_output = sizes, time.monotonic()
                                trace.feed(partial.output)
                                if trace.failed:
                                    self.stop_process(process)
                                    hint = trace.hint or 'O CLI informou uma falha definitiva do turno; confira modelo, conexão e autenticação.'
                                    raise RuntimeError(f'{self.backend}: {hint} '
                                                       'Checkpoints preservados; nenhuma ferramenta dessa resposta foi executada.')
                except subprocess.TimeoutExpired:
                    self.stop_process(process)
                    diagnostic = trace.diagnostic(partial_errors, input_bytes)
                    if request_timeout is not None:
                        raise RequestTimeout(f'{self.backend}: tempo limite de {timeout:g} segundos na requisição de resumo; '
                                           'nenhuma ferramenta foi executada. ' + diagnostic) from None
                    raise RuntimeError(f'{self.backend}: tempo limite de {timeout:g} segundos; '
                                       'ajuste CENTAUR_NATIVE_TIMEOUT ou use $compact e /retry. '
                                       'Nenhuma chamada pendente foi aplicada. ' + diagnostic) from None
                if process.returncode:
                    raise RuntimeError(process_failure(self.backend, process.returncode, errors, output))
                if self.backend == 'codex':
                    value = codex_output(directory, output)
                    usage = codex_usage(output)
                else:
                    value, windows = claude_output(output)
                    self.quota_windows.update(windows)
                    if value.get('is_error') or value.get('subtype') not in (None, 'success'):
                        raise ValueError('O cliente não concluiu a resposta estruturada.')
                    raw_usage = value.get('usage')
                    if not isinstance(raw_usage, dict): raw_usage = {}
                    inputs = [raw_usage.get(key, 0) for key in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')]
                    usage = ({'prompt_tokens': sum(inputs), 'completion_tokens': raw_usage.get('output_tokens')}
                             if all(type(item) is int and item >= 0 for item in inputs) else {})
                    value = value['structured_output']
                reply = self.reply(value, tools)
                reply.usage = usage
                return reply
            except json.JSONDecodeError as error:
                raise RuntimeError(f'{self.backend}: JSON incompleto ou inválido na linha {error.lineno}, coluna {error.colno}. '
                                   'Tente novamente com /retry ou divida a solicitação. Nenhuma ferramenta dessa resposta foi executada.') from None
            except (OSError, ValueError, KeyError, TypeError) as error:
                detail = str(error) if isinstance(error, ValueError) else 'Não foi possível ler a resposta local do CLI.'
                raise RuntimeError(f'{self.backend}: {self.redact(detail)} Nenhuma ferramenta dessa resposta foi executada.') from None

    @staticmethod
    def stop_process(process):
        """Bound cleanup even if an escaped descendant holds a pipe open."""
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

    def reply(self, value, tools):
        if not isinstance(value, dict) or set(value) != {'content', 'calls'}:
            raise ValueError('Schema de resposta inválido.')
        if value['content'] is not None and not isinstance(value['content'], str):
            raise ValueError('Conteúdo inválido.')
        if not isinstance(value['calls'], list):
            raise ValueError('Chamadas inválidas.')
        allowed = {entry['function']['name']: entry['function']['parameters'] for entry in tools}
        calls = []
        for call in value['calls']:
            if not isinstance(call, dict) or set(call) != {'name', 'arguments'} or call['name'] not in allowed:
                raise ValueError('Ferramenta indisponível.')
            arguments = json.loads(call['arguments']) if isinstance(call['arguments'], str) else call['arguments']
            if not isinstance(arguments, dict):
                raise ValueError('Argumentos inválidos.')
            parameters = allowed[call['name']]
            arguments = {key: val for key, val in arguments.items()
                         if val is not None or key in parameters.get('required', [])}
            if (set(arguments) - set(parameters['properties'])
                    or not set(parameters.get('required', [])) <= set(arguments)):
                raise ValueError('Argumentos fora do contrato da ferramenta; tente novamente com /retry.')
            validate_arguments(arguments, parameters)
            calls.append({'id': uuid4().hex, 'type': 'function', 'function': {
                'name': call['name'], 'arguments': self.redact(json.dumps(arguments, ensure_ascii=False))}})
        reply = {'role': 'assistant', 'content': self.redact(value['content']) if value['content'] else None}
        if calls:
            reply['tool_calls'] = calls
        return ModelReply(reply)
