"""Adaptador HTTP do OpenRouter, sem dependências externas."""

import json
import os
import queue
import threading
import time
from decimal import Decimal, InvalidOperation
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .credits import CreditBalance, amount
from .speed import validate_speed
from .interaction import RequestTimeout, TurnCancelled
from .tool_protocol import validate_arguments, omit_optional_nulls
from .models import openrouter_details


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


urlopen = build_opener(NoRedirect()).open


class ModelReply(dict):
    """Mensagem com metadados locais que não são reenviados ao provedor."""

    def __init__(self, message, model=None, usage=None, service_tier=None):
        super().__init__(message)
        self.model = model
        self.usage = usage or {}
        self.service_tier = service_tier

RETRY_STATUS = frozenset((408, 429, 500, 502, 503, 504, 529))


class StreamInterrupted(OSError):
    """A conexão caiu antes do fim da resposta; nada dela foi executado."""


def read_stream(response, cancel_event=None, on_delta=None):
    """Monta, a partir dos eventos SSE, o mesmo envelope da resposta não transmitida."""
    message, choice, result = {'role': 'assistant', 'content': None}, {}, {}
    text, calls, details, size, done, notified, shown = [], {}, {}, 0, False, 0, None
    for raw in response:
        if cancel_event is not None and cancel_event.is_set():
            return None  # Fechar a conexão interrompe a geração nos provedores compatíveis.
        size += len(raw)
        if size > 8_000_000:
            raise ValueError('Resposta OpenRouter excedeu 8 MB.')
        line = raw.decode('utf-8').strip()
        if not line.startswith('data:'):
            continue  # Linhas vazias e comentários de keep-alive (": OPENROUTER PROCESSING").
        data = line[5:].strip()
        if data == '[DONE]':
            done = True
            break
        chunk = json.loads(data)
        if not isinstance(chunk, dict):
            raise ValueError('Evento de stream inválido.')
        if chunk.get('error'):
            result['error'] = chunk['error']
            break
        for key in ('model', 'usage', 'service_tier'):
            if chunk.get(key) is not None:
                result[key] = chunk[key]
        for part in chunk.get('choices') or []:
            if not isinstance(part, dict) or part.get('index', 0) != 0:
                continue
            if part.get('error'):
                choice['error'] = part['error']
            if part.get('finish_reason'):
                choice['finish_reason'] = part['finish_reason']
            delta = part.get('delta') or {}
            if isinstance(delta.get('content'), str) and delta['content']:
                text.append(delta['content'])
                if on_delta is not None and time.monotonic() - notified >= .08:
                    notified, shown = time.monotonic(), ''.join(text)
                    on_delta(shown)
            for call in delta.get('tool_calls') or []:
                entry = calls.setdefault(call.get('index', 0), {'id': None, 'type': 'function',
                                                                'function': {'name': '', 'arguments': ''}})
                function = call.get('function') or {}
                if call.get('id'):
                    entry['id'] = call['id']
                if isinstance(function.get('name'), str):
                    entry['function']['name'] += function['name']
                if isinstance(function.get('arguments'), str):
                    entry['function']['arguments'] += function['arguments']
            for detail in delta.get('reasoning_details') or []:
                # Fragmentos do mesmo bloco chegam separados; a assinatura vem no último.
                entry = details.setdefault((detail.get('type'), detail.get('index', 0)), {})
                for key, value in detail.items():
                    if key in ('text', 'summary', 'data') and isinstance(value, str) and isinstance(entry.get(key), str):
                        entry[key] += value
                    elif value is not None or key not in entry:
                        entry[key] = value
    if not done and not choice.get('finish_reason') and 'error' not in result and 'error' not in choice:
        raise StreamInterrupted('stream encerrado antes do fim da resposta')
    if text:
        message['content'] = ''.join(text)
        if on_delta is not None and message['content'] != shown:
            on_delta(message['content'])
    if calls:
        message['tool_calls'] = [calls[index] for index in sorted(calls)]
        for call in message['tool_calls']:
            call['function']['arguments'] = call['function']['arguments'] or '{}'
    if details:
        message['reasoning_details'] = list(details.values())
    choice['message'] = message
    result['choices'] = [choice]
    return result


def read_response(response, cancel_event=None, on_delta=None):
    headers = getattr(response, 'headers', None)
    if headers is not None and 'text/event-stream' in str(headers.get('Content-Type', '')):
        return read_stream(response, cancel_event, on_delta)
    raw = response.read(8_000_001)
    if len(raw) > 8_000_000:
        raise ValueError('Resposta OpenRouter excedeu 8 MB.')
    return json.loads(raw)


def transient_error(result):
    """Erro temporário devolvido com HTTP 200, no envelope ou na escolha."""
    choices = result.get('choices') if isinstance(result, dict) else None
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    for error in (result.get('error') if isinstance(result, dict) else None, choice.get('error')):
        if isinstance(error, dict) and error.get('code') in RETRY_STATUS:
            return error
    return None


class OpenRouter:
    backend = 'openrouter'
    allows_model_routing = True
    supports_request_timeout = True
    supports_cancellation = True
    supports_streaming = True

    def __init__(self, api_key, credits_key=None):
        try:
            self.timeout = int(os.environ.get('CENTAUR_OPENROUTER_TIMEOUT', '1800'))
            if not 30 <= self.timeout <= 3600:
                raise ValueError
        except ValueError:
            raise ValueError('CENTAUR_OPENROUTER_TIMEOUT deve ser um inteiro de 30 a 3600 segundos.') from None
        self.api_key = api_key
        self.credits_key = credits_key
        self.model_efforts = {}
        self.context_windows = {}
        self.model_details = {}
        self.speed_support = {}
        self.pending_requests = threading.BoundedSemaphore(8)
        # Esperas, em segundos, antes de repetir falhas transitórias (429, 5xx, conexão).
        self.retry_delays = (1, 2, 4)
        self.stream = os.environ.get('CENTAUR_OPENROUTER_STREAM', '1').lower() not in ('0', 'false', 'off')
        self.cache = os.environ.get('CENTAUR_PROMPT_CACHE', '1').lower() not in ('0', 'false', 'off')

    def request_json(self, request, timeout, cancel_event=None, on_delta=None):
        # urllib can block inside connect/read. Keep the agent cancellable without
        # allowing an abandoned reply to execute tools.
        if cancel_event is None:
            with urlopen(request, timeout=timeout) as response:
                return read_response(response, None, on_delta)
        if cancel_event.is_set():
            raise TurnCancelled('Turno interrompido pelo usuário.')
        if not self.pending_requests.acquire(blocking=False):
            raise RuntimeError('Há requisições OpenRouter ainda encerrando; aguarde antes de retomar.')
        result = queue.Queue(maxsize=1)
        def request_once():
            try:
                with urlopen(request, timeout=timeout) as response:
                    result.put((True, read_response(response, cancel_event, on_delta)))
            except Exception as error:
                result.put((False, error))
            finally:
                self.pending_requests.release()
        try:
            thread = threading.Thread(target=request_once, daemon=True)
            thread.start()
        except BaseException:
            self.pending_requests.release()
            raise
        deadline = time.monotonic() + timeout
        while True:
            if cancel_event.is_set():
                raise TurnCancelled('Turno interrompido; a requisição remota pode continuar, mas sua resposta não executará ferramentas.')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RequestTimeout('Tempo limite da requisição OpenRouter; tente novamente.')
            try:
                success, value = result.get(timeout=min(.1, remaining))
            except queue.Empty:
                continue
            if cancel_event.is_set():
                raise TurnCancelled('Turno interrompido pelo usuário.')
            if success:
                return value
            raise value

    def send(self, payload, deadline, cancel_event=None, on_delta=None, first_timeout=None):
        """Uma requisição lógica: falhas transitórias são repetidas com espera crescente."""
        for attempt in range(len(self.retry_delays) + 1):
            if cancel_event is not None and cancel_event.is_set():
                raise TurnCancelled('Turno interrompido pelo usuário.')
            remaining = first_timeout if first_timeout is not None and attempt == 0 else deadline - time.monotonic()
            if remaining <= 0:
                raise RequestTimeout('Tempo limite da requisição OpenRouter; tente novamente.')
            request = Request('https://openrouter.ai/api/v1/chat/completions',
                              data=self.redact(json.dumps(payload)).encode('utf-8'),
                              headers={'Authorization': 'Bearer ' + self.api_key,
                                       'Content-Type': 'application/json',
                                       'X-OpenRouter-Title': 'Centaur CLI'})
            last, delay = attempt == len(self.retry_delays), 0
            try:
                result = self.request_json(request, remaining, cancel_event, on_delta)
                if last or transient_error(result) is None:
                    return result
            except HTTPError as error:
                if last or error.code not in RETRY_STATUS:
                    raise
                try:
                    delay = min(30, float(error.headers.get('Retry-After', 0))) if error.headers else 0
                except (TypeError, ValueError):
                    delay = 0
                error.close()
            except (URLError, ConnectionError, HTTPException, StreamInterrupted) as error:
                if last or isinstance(error, TimeoutError) or isinstance(getattr(error, 'reason', None), TimeoutError):
                    raise
            delay = max(delay, self.retry_delays[attempt])
            if time.monotonic() + delay >= deadline:
                raise RequestTimeout('Tempo limite da requisição OpenRouter; tente novamente.')
            if on_delta is not None:
                on_delta('')  # Texto parcial da tentativa descartada.
            if cancel_event is not None:
                cancel_event.wait(delay)
            else:
                time.sleep(delay)

    def reply(self, message, tools):
        if not isinstance(message, dict) or message.get('role') != 'assistant':
            raise ValueError('Envelope de resposta inválido.')
        content = message.get('content')
        if content is not None and not isinstance(content, str):
            raise ValueError('Conteúdo de resposta inválido.')
        calls = message.get('tool_calls', [])
        if calls is None:
            calls = []
        if not isinstance(calls, list):
            raise ValueError('Lote de ferramentas inválido.')
        allowed = {entry['function']['name']: entry['function']['parameters'] for entry in tools}
        identifiers, normalized = set(), []
        for call in calls:
            if not isinstance(call, dict) or call.get('type') != 'function':
                raise ValueError('Chamada de ferramenta inválida.')
            identifier, function = call.get('id'), call.get('function')
            if not isinstance(identifier, str) or not identifier or identifier in identifiers:
                raise ValueError('Identificador de ferramenta ausente ou duplicado.')
            if not isinstance(function, dict) or not isinstance(function.get('name'), str) or function['name'] not in allowed:
                raise ValueError('Ferramenta indisponível.')
            if not isinstance(function.get('arguments'), str):
                raise ValueError('Argumentos devem ser JSON textual.')
            parameters = allowed[function['name']]
            try:
                arguments = omit_optional_nulls(json.loads(function['arguments']), parameters)
                validate_arguments(arguments, parameters)
            except ValueError as error:
                raise ValueError(function['name'] + ': ' + str(error)) from error
            identifiers.add(identifier)
            normalized.append({'id': identifier, 'type': 'function', 'function': {
                'name': function['name'], 'arguments': json.dumps(arguments, ensure_ascii=False)}})
        if not normalized and not (isinstance(content, str) and content.strip()):
            raise ValueError('Resposta vazia.')
        reply = {'role': 'assistant', 'content': content}
        if normalized:
            reply['tool_calls'] = normalized
        if message.get('reasoning_details'):
            reply['reasoning_details'] = message['reasoning_details']
        return reply

    def supports_fast(self, model):
        if not model or model.startswith('openrouter/') or ':' in model:
            return False
        if model not in self.speed_support:
            request = Request('https://openrouter.ai/api/v1/models/' + model + '/endpoints',
                              headers={'Authorization': 'Bearer ' + self.api_key} if self.api_key else {})
            try:
                with urlopen(request, timeout=10) as response:
                    endpoints = json.load(response)['data']['endpoints']
                self.speed_support[model] = any(
                    isinstance(entry, dict) and (
                        entry.get('service_tier') in ('fast', 'priority')
                        or str(entry.get('tag', '')).rsplit('/', 1)[-1] in ('fast', 'priority'))
                    for entry in endpoints)
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
                raise RuntimeError('Suporte ao modo rápido indisponível; mantenha Padrão ou tente novamente.') from None
        return self.speed_support[model]

    def check_speed(self, model, speed):
        validate_speed(speed)
        if speed == 'fast' and not self.supports_fast(model):
            raise ValueError('Este modelo não anuncia capacidade Fast/priority; selecione Padrão.')

    @property
    def secrets(self):
        return tuple(key for key in (self.api_key, self.credits_key) if key)

    def redact(self, text):
        for key in self.secrets:
            text = text.replace(key, '[CHAVE OCULTA]')
        return text

    def _error_detail(self, error):
        text = self.redact(str(error))
        return ' '.join(''.join(character if character.isprintable() else ' '
                                for character in text).split())[:500]

    def _api_error(self, error, status=None):
        if isinstance(error, dict):
            status = status if status is not None else error.get('code')
            detail = error.get('message', '')
        else:
            detail = error or ''
        prefix = f'OpenRouter HTTP {self._error_detail(status)}' if status else 'OpenRouter recusou a requisição'
        detail = self._error_detail(detail)
        return RuntimeError(f'{prefix}: {detail or "Confira chave, saldo e modelo."}')

    def credits(self):
        endpoint = 'credits' if self.credits_key else 'key'
        request = Request('https://openrouter.ai/api/v1/' + endpoint,
                          headers={'Authorization': 'Bearer ' + (self.credits_key or self.api_key)})
        try:
            with urlopen(request, timeout=10) as response:
                data = json.load(response)['data']
            if self.credits_key:
                total, used = amount(data['total_credits']), amount(data['total_usage'])
                return CreditBalance('account', total, max(amount(0), total - used))
            if data['limit'] is None:
                return CreditBalance('key', None, None)
            total = amount(data['limit'])
            remaining = Decimal(str(data['limit_remaining']))
            if not remaining.is_finite():
                raise ValueError('Saldo inválido.')
            remaining = max(amount(0), remaining)
            return CreditBalance('key', total, remaining)
        except HTTPError as error:
            if error.code == 403:
                raise RuntimeError('Consulta de saldo exige uma chave de gerenciamento válida.') from None
            raise RuntimeError('Não foi possível consultar os créditos no OpenRouter.') from None
        except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError, InvalidOperation):
            raise RuntimeError('Não foi possível consultar os créditos no OpenRouter.') from None

    def validate_key(self):
        request = Request('https://openrouter.ai/api/v1/key',
                          headers={'Authorization': 'Bearer ' + self.api_key})
        try:
            with urlopen(request, timeout=30) as response:
                result = json.load(response)
            if not isinstance(result.get('data'), dict) or 'error' in result:
                raise RuntimeError('Não foi possível validar a chave no OpenRouter.')
        except HTTPError as error:
            if error.code in (401, 403):
                raise RuntimeError('Chave recusada. Crie ou copie uma chave válida no OpenRouter.') from None
            raise RuntimeError(f'OpenRouter indisponível para validação (HTTP {error.code}). Tente novamente.') from None
        except (URLError, TimeoutError, OSError):
            raise RuntimeError('Falha de conexão ao validar a chave. Tente novamente.') from None
        except (ValueError, AttributeError, TypeError):
            raise RuntimeError('Resposta inválida ao validar a chave.') from None

    def model_catalog(self):
        request = Request('https://openrouter.ai/api/v1/models',
                          headers={'Authorization': 'Bearer ' + self.api_key} if self.api_key else {})
        try:
            with urlopen(request, timeout=10) as response:
                data = json.load(response)['data']
            from .config import EFFORTS
            self.input_modalities = {entry['id']: (entry.get('architecture') or {}).get('input_modalities', []) for entry in data}
            self.model_efforts = {}
            self.model_details = {entry['id']: openrouter_details(entry) for entry in data}
            self.context_windows = {entry['id']: entry['context_length'] for entry in data
                                    if type(entry.get('context_length')) is int and entry['context_length'] > 0}
            for entry in data:
                reasoning = entry.get('reasoning') or {}
                levels = reasoning.get('supported_efforts', [])
                if levels is None:
                    levels = [level for level in EFFORTS if level != 'default']
                if reasoning.get('mandatory'):
                    levels = [level for level in levels if level != 'none']
                self.model_efforts[entry['id']] = ['default', *levels]
            return {entry['id']: entry.get('name', entry['id']) for entry in data
                    if 'tools' in entry.get('supported_parameters', [])}
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
            raise RuntimeError('Catálogo indisponível; use Modelo personalizado ou tente novamente.') from None

    def complete(self, model, messages, tools, *, cost_tier=None, session_id=None, effort='default', speed='standard', request_timeout=None, cancel_event=None, on_delta=None):
        if cancel_event is not None and cancel_event.is_set():
            raise TurnCancelled('Turno interrompido pelo usuário.')
        if request_timeout is not None and (isinstance(request_timeout, bool)
                or not isinstance(request_timeout, (int, float)) or not 0 < request_timeout <= 3600):
            raise ValueError('Tempo limite de requisição inválido.')
        timeout = self.timeout if request_timeout is None else min(self.timeout, request_timeout)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 3600:
            raise ValueError('Tempo limite de requisição inválido.')
        from .config import validate_effort
        validate_effort(self.backend, effort)
        self.check_speed(model, speed)
        if model in self.model_efforts and effort not in self.model_efforts[model]:
            raise ValueError('Este modelo não aceita o effort selecionado; use $config e escolha um nível disponível.')
        payload = {'messages': messages,
                   'provider': {'require_parameters': True}}
        # Anthropic só cacheia com marcador; o breakpoint automático acompanha a conversa.
        # Os demais provedores compatíveis fazem cache do prefixo sem marcação.
        cached = self.cache and isinstance(model, str) and model.lstrip('~').startswith('anthropic/')
        if cached:
            payload['cache_control'] = {'type': 'ephemeral'}
        if self.stream:
            payload['stream'] = True
        if tools:
            payload['tools'] = tools
        if effort != 'default':
            payload['reasoning'] = {'effort': effort}
        if speed == 'fast':
            payload['service_tier'] = 'fast'
        if model:
            payload['model'] = model
        if model in ('openrouter/auto', 'openrouter/auto-beta') and cost_tier:
            if cost_tier not in ('low', 'medium', 'high', 'xhigh', 'max'):
                raise ValueError('Faixa de custo inválida para o Auto Router.')
            payload['plugins'] = [{'id': 'auto-beta-router' if model.endswith('-beta') else 'auto-router',
                                   'cost_tier': cost_tier}]
        if any(block.get('type') == 'file' for message in messages
               if isinstance(message.get('content'), list) for block in message['content']):
            payload.setdefault('plugins', []).append({'id': 'file-parser', 'pdf': {'engine': 'native'}})
        if session_id:
            payload['session_id'] = session_id
        deadline = time.monotonic() + timeout
        try:
            for attempt in range(2):
                result = self.send(payload, deadline, cancel_event, on_delta, timeout if attempt == 0 else None)
                if not isinstance(result, dict):
                    raise ValueError('Envelope de resposta inválido.')
                if 'error' in result:
                    raise self._api_error(result['error'])
                choice = result['choices'][0]
                if not isinstance(choice, dict):
                    raise ValueError('Envelope de resposta inválido.')
                if choice.get('error'):
                    raise self._api_error(choice['error'])
                if choice.get('finish_reason') in ('length', 'content_filter', 'error'):
                    raise RuntimeError('OpenRouter não concluiu a resposta; nenhuma ferramenta dessa resposta foi executada.')
                try:
                    message = self.reply(choice['message'], tools)
                except ValueError as error:
                    if attempt:
                        raise
                    # The entire rejected batch is still unexecuted. Ask for one
                    # corrected reply without replaying it or changing the model.
                    if on_delta is not None:
                        on_delta('')
                    payload['messages'] = [*messages, {'role': 'user', 'content':
                        'Aviso local do Centaur: a última resposta foi rejeitada: '
                        + self._error_detail(error) + ' Nenhuma ferramenta dessa resposta foi executada. '
                        'Retome a tarefa com uma resposta completa; use somente as ferramentas disponíveis '
                        'e argumentos JSON nos tipos e campos dos schemas fornecidos. '
                        'Não repita operações já concluídas no histórico.'}]
                    continue
                return ModelReply(json.loads(self.redact(json.dumps(message))),
                                  self.redact(str(result['model'])) if result.get('model') else None,
                                  result.get('usage') if isinstance(result.get('usage'), dict) else None,
                                  result.get('service_tier'))
        except HTTPError as error:
            try:
                with error:
                    body = json.loads(error.read(16384))
                detail = body.get('error') if isinstance(body, dict) else None
            except (OSError, ValueError):
                detail = None
            if (not model and error.code == 400 and isinstance(detail, dict)
                    and detail.get('message') == 'No models provided'):
                return self.complete('openrouter/auto', messages, tools, cost_tier=cost_tier,
                                     session_id=session_id, effort=effort, speed=speed,
                                     request_timeout=request_timeout, cancel_event=cancel_event, on_delta=on_delta)
            if cached and error.code in (400, 404, 422):
                # Rota sem suporte ao marcador: repete uma vez sem cache e só mantém
                # o cache desligado se era ele a causa da recusa.
                self.cache = False
                try:
                    return self.complete(model, messages, tools, cost_tier=cost_tier,
                                         session_id=session_id, effort=effort, speed=speed,
                                         request_timeout=request_timeout, cancel_event=cancel_event, on_delta=on_delta)
                except Exception:
                    self.cache = True
                    raise self._api_error(detail, error.code) from error
            raise self._api_error(detail, error.code) from error
        except TimeoutError as error:
            raise RequestTimeout('Tempo limite da requisição OpenRouter; tente novamente.') from error
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise RequestTimeout('Tempo limite da requisição OpenRouter; tente novamente.') from error
            raise RuntimeError('Falha de conexão com OpenRouter: ' + self._error_detail(error.reason) + '. Use /retry para retomar.') from error
        except (ConnectionError, HTTPException, StreamInterrupted) as error:
            raise RuntimeError('Falha de conexão com OpenRouter: ' + (self._error_detail(error) or type(error).__name__)
                               + '. Nenhuma ferramenta dessa resposta foi executada. Use /retry para retomar.') from error
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise RuntimeError('Resposta inválida do OpenRouter: ' + self._error_detail(error)
                               + ' Nenhuma ferramenta dessa resposta foi executada.') from error
