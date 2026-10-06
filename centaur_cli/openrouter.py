"""Adaptador HTTP do OpenRouter, sem dependências externas."""

import json
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .credits import CreditBalance, amount


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


urlopen = build_opener(NoRedirect()).open


class ModelReply(dict):
    """Mensagem com metadados locais que não são reenviados ao provedor."""

    def __init__(self, message, model=None):
        super().__init__(message)
        self.model = model

class OpenRouter:
    backend = 'openrouter'
    allows_model_routing = True

    def __init__(self, api_key, credits_key=None):
        self.api_key = api_key
        self.credits_key = credits_key
        self.model_efforts = {}

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
            self.model_efforts = {}
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

    def complete(self, model, messages, tools, *, cost_tier=None, session_id=None, effort='default'):
        from .config import validate_effort
        validate_effort(self.backend, effort)
        if model in self.model_efforts and effort not in self.model_efforts[model]:
            raise ValueError('Este modelo não aceita o effort selecionado; use $config e escolha um nível disponível.')
        payload = {'messages': messages, 'tools': tools,
                   'provider': {'require_parameters': True}}
        if effort != 'default':
            payload['reasoning'] = {'effort': effort}
        if model:
            payload['model'] = model
        if model in ('openrouter/auto', 'openrouter/auto-beta') and cost_tier:
            if cost_tier not in ('low', 'medium', 'high', 'xhigh', 'max'):
                raise ValueError('Faixa de custo inválida para o Auto Router.')
            payload['plugins'] = [{'id': 'auto-beta-router' if model.endswith('-beta') else 'auto-router',
                                   'cost_tier': cost_tier}]
        if session_id:
            payload['session_id'] = session_id
        request = Request('https://openrouter.ai/api/v1/chat/completions',
                          data=self.redact(json.dumps(payload)).encode('utf-8'),
                          headers={'Authorization': 'Bearer ' + self.api_key,
                                   'Content-Type': 'application/json',
                                   'X-OpenRouter-Title': 'Centaur CLI'})
        try:
            with urlopen(request, timeout=60) as response:
                result = json.load(response)
            if 'error' in result:
                raise RuntimeError('OpenRouter recusou a requisição. Confira chave, saldo e modelo.')
            message = result['choices'][0]['message']
            if not message.get('content') and not message.get('tool_calls'):
                raise RuntimeError('OpenRouter retornou uma resposta vazia.')
            return ModelReply(json.loads(self.redact(json.dumps(message))),
                              self.redact(str(result['model'])) if result.get('model') else None)
        except HTTPError as error:
            raise RuntimeError(f'OpenRouter HTTP {error.code}. Confira chave, saldo e modelo.') from error
        except (URLError, TimeoutError) as error:
            raise RuntimeError('Falha de conexão com OpenRouter; tente novamente.') from error
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise RuntimeError('Resposta inválida do OpenRouter.') from error
