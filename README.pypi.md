# Centaur CLI

Harness de desenvolvimento assistido por IA com **OpenRouter, Codex e Claude**.
O humano define intenção, comportamentos e limites; o agente trabalha com specs,
contratos, ferramentas e evidências de entrega.

Requer **Python 3.10+** e terminal interativo em **Linux ou macOS**. Não possui
dependências Python obrigatórias de execução. Computer use usa o extra opcional `computer`. Codex e Claude são integrações opcionais que
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
# Abre a seleção inicial: backend, modelo padrão, effort, permissões e velocidade.
centaur .

codex login
centaur --backend codex .

claude auth login
centaur --backend claude .
```

Antes de abrir o chat, escolha **Backend → Modelo padrão → Effort → Permissões → Velocidade → Iniciar conversa**.
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

- `$config`: backend, modelo, effort, permissões e velocidade; alterações no mesmo backend preservam o chat.
- Fast quando anunciado pelo modelo, independente de effort; pode consumir mais créditos. `--speed fast` e `CENTAUR_SPEED` também configuram.
- `$credits`: cotas e créditos Codex via App Server; Claude usa eventos públicos da resposta com indicação de cache. Dados ausentes não recebem saldos inventados.
- `$status`: árvore local das specs; `$status --ai` analisa evidências somente em leitura. `/status` permanece como alias.
- `Shift+←` ou `/chats`: histórico por pasta; `/rename` renomeia a conversa.
- Skills distribuídas no pacote: `$spec`, `$run`, `$check`, `$skill` e outras.
- Permissões por seletor: pedir aprovação, automático de baixo risco ou sem perguntar; subagentes herdam o modo.
- Automático reconhece o validador de ciclo de vida incluído, documentos de `.centaur` e consultas com glob ou leitura por intervalos.
- `/wide` amplia o chat; erros completos e `/retry` preservam o turno e os resultados anteriores.
- Entrada com quebra automática, Shift+Enter/Ctrl+J para nova linha e campo de três a oito linhas; colagem protegida não envia automaticamente.
- Barra de contexto livre estimado; `$compact` resume mensagens antigas com IA sem apagar o histórico ou repetir ferramentas. `/compact` é alias.
- Timeout Codex/Claude de 600s por chamada; `CENTAUR_NATIVE_TIMEOUT=900` ajusta (30–3600s). `CENTAUR_CONTEXT_WINDOW` informa a janela real quando não consta no catálogo.
- Turnos sem limite fixo de etapas; Ctrl+C interrompe comandos e bloqueia novas ações.
- ↑/↓ recuperam prompts anteriores e avançam até o rascunho atual, inclusive vazio; prompts salvos não são alterados. PgUp/PgDn e roda do mouse rolam a conversa; Ctrl+E volta ao fim.
- Autocompact a 80% da janela conhecida, sem apagar histórico; `CENTAUR_AUTOCOMPACT=0` desativa. Resumos longos recebem até duas revisões sem truncar a memória.
- `$compact` inicia com um único Enter e mostra progresso por fragmento; o resumo usa effort baixo anunciado ou padrão do provedor sem mudar o effort do chat.
- Perguntas interativas da IA, com opções ou resposta livre e preservação do rascunho.
- Computer use opcional: captura contínua local e até três quadros recentes por decisão da IA, mouse/teclado com confirmação em todos os modos.
- Validação do ciclo intenção → contrato → implementação → evidência → integração.
- Emblema Convergência em Braille, com curvas finas, flecha verde, luz e animação.
- `CENTAUR_REDUCED_MOTION=1` reduz movimento; `CENTAUR_GRAPHICS=0` usa blocos/ASCII.

[Documentação completa](https://github.com/Dalistor/Centaur-Driven/tree/main)
· [Código-fonte](https://github.com/Dalistor/Centaur-Driven)
· [Reportar problema](https://github.com/Dalistor/Centaur-Driven/issues)

Para instalar diretamente do Git com computer use:

```bash
pipx install --force 'centaur-cli[computer] @ git+https://github.com/Dalistor/Centaur-Driven.git@main'
```

Requer modelo com visão e desktop Linux X11 ou macOS com permissões de tela/acessibilidade.
Captura autorizada por até 120s, cerca de 2 quadros/s; cada ação pede confirmação.
Zoom de áreas pequenas, arrasto, cliques adicionais, rolagem horizontal e teclas F1–F12.
Quadros repetidos são deduplicados. Esperas canceláveis e estabilização visual após input
ajudam a observar carregamentos; o modelo ainda precisa verificar o resultado da tarefa.
Ctrl+C para a captura. Não é inferência contínua por vídeo; as decisões seguem a latência
do modelo. Quadros não ficam no histórico; Codex usa anexos temporários apagados após
a requisição. No Linux, texto Unicode precisa de xclip/xsel.

Versão inicial experimental. A instalação não substitui os CLIs nativos opcionais,
não configura servidores externos e não inicia chamadas pagas automaticamente.
