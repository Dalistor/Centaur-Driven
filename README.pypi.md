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
# Abre a seleção inicial: backend, modelo padrão e effort.
centaur .

codex login
centaur --backend codex .

claude auth login
centaur --backend claude .
```

Antes de abrir o chat, escolha **Backend → Modelo padrão → Effort → Permissões → Iniciar conversa**.
As preferências da pasta ficam pré-selecionadas. Flags como `--backend`, `--model` e
`--effort` também preenchem essas escolhas; `--no-setup` abre diretamente com elas.
↑/↓ navegam, Enter confirma e Esc volta ou cancela.

Modelo e effort definem o agente principal. Ao executar tasks com subagentes, o Centaur
escolhe modelos do mesmo backend conforme complexidade e risco. O modo padrão pede aprovação para gravações e comandos. O modo sem perguntar executa com
as permissões do usuário, sem sandbox. A conexão é validada antes
de salvar as preferências e abrir o chat; falhas preservam as escolhas.
Ao confirmar OpenRouter sem chave, o cadastro usa entrada oculta.

Uso dos modelos segue a autenticação, custos e limites do backend selecionado.
Mensagens e arquivos consultados pelo agente são enviados ao provedor.

## Recursos

- `$config`: seletor de backend, modelo e esforço de raciocínio.
- `Shift+←` ou `/chats`: histórico por pasta; `/rename` renomeia a conversa.
- Skills distribuídas no pacote: `$spec`, `$run`, `$check`, `$skill` e outras.
- Permissões por seletor: pedir aprovação, automático de baixo risco ou sem perguntar; subagentes herdam o modo.
- `/wide` amplia o chat; erros completos e `/retry` preservam o turno e os resultados anteriores.
- Validação do ciclo intenção → contrato → implementação → evidência → integração.
- Emblema Convergência em Braille, com curvas finas, flecha verde, luz e animação.
- `CENTAUR_REDUCED_MOTION=1` reduz movimento; `CENTAUR_GRAPHICS=0` usa blocos/ASCII.

[Documentação completa](https://github.com/Dalistor/Centaur-Driven/tree/main)
· [Código-fonte](https://github.com/Dalistor/Centaur-Driven)
· [Reportar problema](https://github.com/Dalistor/Centaur-Driven/issues)

Versão inicial experimental. A instalação não substitui os CLIs nativos opcionais,
não configura servidores externos e não inicia chamadas pagas automaticamente.
