"""Cadastro interativo executado localmente antes de iniciar o chat."""

import getpass
import warnings
import webbrowser

from .credentials import valid_key_input
from .openrouter import OpenRouter
from .appearance import setup_heading

KEYS_URL = 'https://openrouter.ai/settings/keys'


def configure_key(store, purpose='chat'):
    setup_heading()
    keys_url = KEYS_URL
    if purpose == 'credits':
        keys_url = 'https://openrouter.ai/settings/management-keys'
        print('\nCréditos da conta OpenRouter\n'
              f'1. Acesse {keys_url}.\n'
              '2. Crie uma Management API Key chamada Centaur créditos e escolha a validade.\n'
              '3. Cole somente no campo oculto abaixo.\n'
              'Essa chave tem poderes administrativos na conta. O CLI usa apenas GET /credits;\n'
              'ela fica separada da chave de chat e não é enviada ao modelo.\n')
    else:
        print('\nConfiguração do OpenRouter\n'
          '1. Entre ou crie sua conta no OpenRouter.\n'
          f'2. Acesse {KEYS_URL} e crie uma API key chamada Centaur.\n'
          '3. Defina um limite de crédito e copie a chave criada.\n'
          '4. Cole somente no campo oculto abaixo, nunca no chat.\n'
          'A chave será validada diretamente no OpenRouter e salva localmente.\n'
          'Ela não será exibida nem incluída no histórico das conversas.\n')
    try:
        if input('Enter abre a página no navegador; n continua sem abrir: ').strip().lower() != 'n':
            try:
                if not webbrowser.open(keys_url):
                    print('Não foi possível abrir o navegador. Acesse o endereço acima manualmente.')
            except webbrowser.Error:
                print('Não foi possível abrir o navegador. Acesse o endereço acima manualmente.')
        while True:
            with warnings.catch_warnings():
                # Falha fechada: getpass nunca pode recorrer a uma entrada com eco.
                warnings.simplefilter('error', getpass.GetPassWarning)
                key = getpass.getpass('Chave OpenRouter (entrada oculta; vazio cancela): ').strip()
            if not key:
                raise RuntimeError('Configuração cancelada.')
            if not valid_key_input(key):
                print('Formato inválido. Cole apenas a chave, sem espaços ou quebras de linha.')
                continue
            print('Validando a chave…')
            try:
                if purpose == 'credits':
                    OpenRouter('', credits_key=key).credits()
                else:
                    OpenRouter(key).validate_key()
            except RuntimeError as error:
                print(str(error))
                continue
            try:
                if purpose == 'credits':
                    store.save_credits_key(key)
                else:
                    store.save(key)
            except (OSError, ValueError):
                raise RuntimeError('Não foi possível salvar a chave com segurança.') from None
            print('Chave cadastrada. Nas próximas aberturas ela será usada automaticamente.\n')
            return key
    except getpass.GetPassWarning:
        raise RuntimeError('O terminal não permite entrada oculta. Cadastro interrompido para proteger a chave.') from None
    except (EOFError, KeyboardInterrupt):
        raise RuntimeError('Configuração cancelada.') from None
