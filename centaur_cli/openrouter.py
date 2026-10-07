"""Adaptador HTTP do OpenRouter, sem dependências externas."""

import json
import os
import queue
import threading
import time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .credits import CreditBalance, amount
from .speed import validate_speed
from .interaction import RequestTimeout, TurnCancelled
from .tool_protocol import validate_arguments, omit_optional_nulls


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

class OpenRouter:
    backend = 'openrouter'
    allows_model_routing = True
    supports_request_timeout = True
    supports_cancellation = True

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
        self.speed_support = {}
        self.pending_requests = threading.BoundedSemaphore(8)

    def request_json(self, request, timeout, cancel_event=None):
        # urllib can block inside connect/read. Keep the agent cancellable without
        # retrying the POST or allowing an abandoned reply to execute tools.
        if cancel_event is None:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(8_000_001)
                if len(raw) > 8_000_000:
                    raise ValueError('Resposta OpenRouter excedeu 8 MB.')
                return json.loads(raw)
        if cancel_event.is_set():
            raise TurnCancelled('Turno interrompido pelo usuário.')
        if not self.pending_requests.acquire(blocking=False):
            raise RuntimeError('Há requisições OpenRouter ainda encerrando; aguarde antes de retomar.')
        result = queue.Queue(maxsize=1)
        def request_once():
            try:
                with urlopen(request, timeout=timeout) as response:
                    raw = response.read(8_000_001)
                    if len(raw) > 8_000_000:
                        raise ValueError('Resposta OpenRouter excedeu 8 MB.')
                    result.put((True, json.loads(raw)))
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
            arguments = omit_optional_nulls(json.loads(function['arguments']), parameters)
            validate_arguments(arguments, parameters)
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

    def complete(self, model, messages, tools, *, cost_tier=None, session_id=None, effort='default', speed='standard', request_timeout=None, cancel_event=None):
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
        request = Request('https://openrouter.ai/api/v1/chat/completions',
                          data=self.redact(json.dumps(payload)).encode('utf-8'),
                          headers={'Authorization': 'Bearer ' + self.api_key,
                                   'Content-Type': 'application/json',
                                   'X-OpenRouter-Title': 'Centaur CLI'})
        try:
            result = self.request_json(request, timeout, cancel_event)
            if not isinstance(result, dict):
                raise ValueError('Envelope de resposta inválido.')
            if 'error' in result:
                raise RuntimeError('OpenRouter recusou a requisição. Confira chave, saldo e modelo.')
            choice = result['choices'][0]
            if not isinstance(choice, dict):
                raise ValueError('Envelope de resposta inválido.')
            if choice.get('finish_reason') in ('length', 'content_filter', 'error'):
                raise RuntimeError('OpenRouter não concluiu a resposta; nenhuma ferramenta dessa resposta foi executada.')
            message = self.reply(choice['message'], tools)
            return ModelReply(json.loads(self.redact(json.dumps(message))),
                              self.redact(str(result['model'])) if result.get('model') else None,
                              result.get('usage') if isinstance(result.get('usage'), dict) else None,
                              result.get('service_tier'))
        except HTTPError as error:
            raise RuntimeError(f'OpenRouter HTTP {error.code}. Confira chave, saldo e modelo.') from error
        except TimeoutError as error:
            raise RequestTimeout('Tempo limite da requisição OpenRouter; tente novamente.') from error
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise RequestTimeout('Tempo limite da requisição OpenRouter; tente novamente.') from error
            raise RuntimeError('Falha de conexão com OpenRouter; tente novamente.') from error
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise RuntimeError('Resposta inválida do OpenRouter; nenhuma ferramenta dessa resposta foi executada.') from error
