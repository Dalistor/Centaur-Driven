# Centaur CLI

Harness de desenvolvimento assistido por IA com **OpenRouter, Codex e Claude**.
O humano define intenção, comportamentos e limites; o agente trabalha com specs,
contratos, ferramentas e evidências de entrega.

Requer **Python 3.10+** e terminal interativo em **Linux ou macOS**. Não possui
dependências Python de execução. Codex e Claude são integrações opcionais que
precisam de seus próprios executáveis e login.

## Instalação

Para disponibilizar `centaur` globalmente, em um ambiente isolado:

```bash
pipx install centaur-cli
centaur --version
centaur /caminho/do/projeto
```

Também pode instalar com pip em um ambiente Python que permita instalações:

```bash
python3 -m pip install centaur-cli
centaur .
```

Em distribuições com Python gerenciado pelo sistema, use pipx ou um virtualenv.
Não é necessário usar sudo nem alterar o Python do sistema.

Para atualizar: `pipx upgrade centaur-cli`, ou `python3 -m pip install --upgrade centaur-cli`.

## Backends

```bash
# OpenRouter: inicia o cadastro local da chave, com entrada oculta, se necessário.
centaur .

codex login
centaur --backend codex .

claude auth login
centaur --backend claude .
```

Uso dos modelos segue a autenticação, custos e limites do backend selecionado.
Mensagens e arquivos consultados pelo agente são enviados ao provedor.

## Recursos

- `$config`: seletor de backend, modelo e esforço de raciocínio.
- `Shift+←` ou `/chats`: histórico por pasta; `/rename` renomeia a conversa.
- Skills distribuídas no pacote: `$spec`, `$run`, `$check`, `$skill` e outras.
- Aprovação explícita de gravações e comandos, com executor identificado.
- Validação do ciclo intenção → contrato → implementação → evidência → integração.
- Emblema Convergência em Braille, com curvas finas, flecha verde, luz e animação.
- `CENTAUR_REDUCED_MOTION=1` reduz movimento; `CENTAUR_GRAPHICS=0` usa blocos/ASCII.

[Documentação completa](https://github.com/Dalistor/Centaur-Driven/tree/experimental/openrouter-cli)
· [Código-fonte](https://github.com/Dalistor/Centaur-Driven)
· [Reportar problema](https://github.com/Dalistor/Centaur-Driven/issues)

Versão inicial experimental. A instalação não substitui os CLIs nativos opcionais,
não configura servidores externos e não inicia chamadas pagas automaticamente.
