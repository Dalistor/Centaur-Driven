# Comportamento do terminal Centaur

Produto: CLI curses em português para desenvolvimento assistido. A identidade visual
está em [DESIGN.md](DESIGN.md). O pedido desta mudança autoriza seletor, effort, Shift+←,
rename e melhorias visuais; as regras de desenvolvimento vêm de
[graphify/references/lifecycle.md](centaur_cli/skills/graphify/references/lifecycle.md).

| Capacidade | Dono canônico | Estados e contrato | Verificação |
| --- | --- | --- | --- |
| Select/Listbox | `settings.ConfigPicker`, `appearance.TerminalView.settings` | ↑/↓ selecionam; Enter abre/confirma; Esc volta/cancela; filtro local; salvar explícito | `tests/test_terminal_settings.py` |
| Inicialização | `startup.StartupPicker`, `StartupWizard`, `__main__.main` | Backend → modelo → effort → permissões → revisão; escolhas antes de autenticar; cancelar não cria chat; falha permite tentar novamente | `tests/test_startup.py`, terminal real com PTY |
| Form | `Terminal.handle_settings`, `Terminal.handle_rename` | Validação textual, valores preservados em falha; bloqueio de salvamento duplicado | `tests/test_terminal_settings.py` |
| Feedback | `Terminal.notice`, `ConfigPicker.error`, `TerminalView.draw` | Mensagem no rodapé, erro permanece no seletor; não substituir erro por sucesso | `tests/test_terminal_settings.py` |
| Chats | `history.ChatStore`, `Terminal` | IDs imutáveis, gravação atômica, retomada por seleção; rename lê conteúdo atual do disco | `tests/test_cli.py`, `tests/test_terminal_settings.py` |
| Gráfico da abertura | `graphics.Renderer`, `WelcomeAnimation`, `Palette`, `TerminalView.logo` | Relógio visível; giro finito; digitação encerra; F5 repete; resize mantém fase; reduced motion e fallback estáticos | `tests/test_graphics.py` |
| Histórico e foco | `Terminal.cursor`, `Terminal.scroll`, `TerminalView` | Shift+← ou /chats abre lista; rascunho preservado ao voltar/cancelar; PgUp/PgDn rolam | `tests/test_terminal_settings.py` |
| Trabalho e permissões | `Terminal.approval`, `ProjectTools` | Troca/rename do chat ativo aguardam turno; aprovações continuam prioritárias | `tests/test_cli.py` |
| Ciclo de vida | `lifecycle.load_project`, `spec_completion_issues` | Gate somente leitura; prova corrente e integração separadas; conclusão não deriva do status | `tests/test_lifecycle.py` |

Escolher backend/modelo/effort não grava. Salvar valida em segundo plano e, somente após
persistir a configuração, troca o cliente e abre chat novo. Falha mantém conversa e escolhas.
Catálogo atrasado só atualiza o seletor que iniciou a leitura e o mesmo backend. Catálogo
indisponível permite informar ID; resultado de rede não é confundido com prova de acesso ao
modelo. Credenciais não entram na configuração, no título ou na conversa.

Renomear não chama o modelo, não altera ID/modelo/effort/mensagens e não cria outro chat.
Título deve ter 1–80 caracteres imprimíveis. Enter salva; Esc cancela; uma falha conserva o
texto digitado. Um chat em execução não pode ser renomeado. A lista mantém selecionado o
ID editado, mesmo se a ordenação por data mudar.

Resize conserva conteúdo e posição do cursor; a entrada mostra a janela que contém o
cursor, medida em células Unicode. Movimento reduzido e ausência de cor preservam todos
os comandos e a indicação textual da seleção. As superfícies são de terminal, sem HTML,
DOM, popups de navegador, fontes remotas ou scrollbars CSS.

`--complete` nunca altera READMEs ou estado. Ele exige vínculos explícitos e percorre
filhas/dependências; integração/publicação remota continua exigindo observação externa.
O harness não transforma uma resposta de IA ou relatório de subagente em aprovação.

## Conversa e títulos gerados

`conversation.py` é o dono dos resumos de ações, da apresentação de Markdown e do pedido
de título. `Terminal.lines` preserva a ordem da conversa: usuário, progresso público,
ferramentas resumidas, resposta final. `Ctrl+O` alterna detalhes sem mudar foco ou rascunho.
Resultados continuam íntegros no histórico; campos de reasoning do provedor não são renderizados.
Marcadores de execução só mostram sucesso quando a ferramenta já retornou sem falha/recusa.
Confirmações continuam prioritárias e os resumos não concedem aprovação.

Após a primeira resposta, `Terminal.make_title` faz uma única chamada sem ferramentas
no mesmo backend/modelo. `ChatStore.generated_title` atualiza somente metadados de título
a partir do arquivo atual. Resultados atrasados não sobrescrevem rename manual nem recriam
chats excluídos. O evento aguarda o fim de um novo turno em execução para preservar a
gravação do histórico. Falha na geração não altera a resposta nem bloqueia navegação.
O título é validado e limitado a 60 caracteres; nomes manuais continuam aceitando até 80.
A chamada adicional segue os custos do provedor, como documentado no README.

Verificação: `tests/test_conversation.py` e teste de terminal real com PTY, incluindo
resumo/detalhes, erro, recusa, resize, rename e título atrasado.

## Seleção inicial

A abertura padrão passa pelo seletor, com flags, ambiente e preferências pré-selecionados.
`--no-setup` mantém a abertura direta. Modelo e effort são do agente principal; o rodapé
explica que o Centaur escolhe modelos do mesmo backend por complexidade e risco nas tasks.
Autenticação roda após sair de curses. Somente conexão válida permite salvar preferências
e abrir o chat; falha retorna à revisão sem perder escolhas. Esc, Ctrl+C e Ctrl+Q cancelam
sem gravar preferências ou criar conversa. Abaixo de 40 × 18, só resize e cancelamento
ficam disponíveis. Catálogos atrasados não alteram escolhas de outro backend.

Verificação com PTY: três backends, NO_COLOR, movimento reduzido, resize, cancelamento e
falha de Codex seguida de troca para Claude, com autenticação e catálogo simulados.

## Política de permissões

Fonte: pedido do usuário e escolha “Edições e consultas” para o modo automático em 2026-10-06.
Contrato de execução: [docs/permissions.md](docs/permissions.md). `permissions.py` é o dono da
classificação; `ProjectTools` aplica a regra; `SubagentTools` herda o modo sem poder ampliá-lo.
`ConfigPicker` e `StartupPicker` compartilham opções, seleção e confirmação. Padrão legado: ask.
Cancelar ou falhar ao salvar conserva o modo e a conversa ativos. Aplicar somente permissões
preserva o chat; mudanças de backend/modelo/effort criam outro. Histórico não concede permissões.
O modo auto inclui documentos de `.centaur` e o validador de ciclo de vida instalado;
Python e Git usam execução isolada de hooks/ambiente e executáveis do sistema.

`$status` e `$status --ai` aparecem no autocomplete e na orientação inicial. `/status`
continua como alias, incluindo históricos antigos. A análise com IA usa somente `StatusTools`.

Verificação: `tests/test_permissions.py`, `tests/test_startup.py` e PTY nos três modos, incluindo
recusa de comandos gerais, escrita automática, consultas, sem confirmação e resize a 40 × 12.

## Falha e retomada nativa

`native_client.reply_schema` usa argumentos tipados; `reply` valida o lote inteiro antes da
execução. `codex_output` só aceita o arquivo final ou mensagem pública em turno concluído.
Erro completo é persistido em `last_error`, fora das mensagens enviadas ao modelo. `/retry`
retoma o histórico sem duplicar o pedido; resultados anteriores não são repetidos. Não há retry
automático de comandos, mudança de backend ou tentativa de executar fragmentos de resposta.
`/wide` altera apenas a largura visual. Verificação: `tests/test_native_resilience.py` e PTY.

## Turnos, perguntas e leitura do histórico

Fonte: pedido do usuário, 2026-10-06. `agent.run_turn` não limita a quantidade de etapas;
a conclusão vem de uma resposta sem ferramentas, uma falha ou cancelamento explícito.
`TurnCancelled` e um evento compartilhado bloqueiam novas ações após Ctrl+C, inclusive
nas tasks delegadas. Comandos locais encerram o grupo de processos; os CLIs nativos
são interrompidos; OpenRouter pode aguardar o timeout de rede. Checkpoints já salvos
permanecem. A retomada marca chamadas sem resultado como interrompidas, sem repeti-las.

`ask_user` aceita uma pergunta e até três opções; resposta livre sempre está disponível.
Não é aprovação de ferramentas e funciona em todos os modos. `QuestionPicker` é o dono
canônico da interação. ↑/↓/Tab navegam; Enter confirma; Esc pula com `status=skipped`,
sem inferir escolha; Ctrl+C cancela o turno. Resposta vazia ou chave conhecida mantém
o seletor aberto com erro. Perguntas longas têm PgUp/PgDn. Rascunho, cursor e posição
da conversa são preservados e restaurados ao fechar. A resposta válida volta como
resultado da ferramenta, salvo no histórico e visível no resumo público.

`Terminal.transcript_start` limita a rolagem e conserva a linha superior ao receber
novas mensagens. Setas e PgUp/PgDn são equivalentes da roda do mouse; Ctrl+E volta ao
fim. Completar skills, lista de chats, perguntas e preferências têm prioridade sobre
rolagem do chat. Resize recalcula a quebra de linhas sem perder texto ou seleção.

Verificação: `tests/test_interaction.py`, suite completa e PTY com pergunta, resposta
livre, pular, rolagem durante execução, mouse, interrupção, resize e janela 40 × 12.

## Computer use

`ComputerSession` é o dono da captura, referência visual e autorização efêmera.
O extra `computer` é opcional: imports de desktop não afetam a instalação base.
`computer_start` sempre exige autorização para observar o monitor principal inteiro,
inclusive no modo never. A autorização expira em 120s; não é gravada em configuração
ou histórico. Cada `computer_action` exige confirmação própria; subagentes não têm
acesso ao desktop. O sistema não oferece execução arbitrária de código de computer use.

Captura local em aproximadamente 2 quadros/s, buffer de três quadros; imagens reais são
anexadas a cada chamada de decisão via OpenRouter, `--image` no Codex ou entrada
`stream-json` do Claude. O transporte é de quadros por chamada, não vídeo em tempo real.
`vision.py` valida PNGs e limita anexos. Imagens não entram no ChatStore; arquivos PNG
temporários do Codex têm modo 0600 e vivem só durante a requisição. O provedor pode
processar/reter imagens conforme sua política. Texto de ações fica no histórico.

Coordenadas referem-se ao último quadro enviado; são limitadas à área capturada e
convertidas à resolução de entrada do monitor principal. A referência expira em 60s
e é consumida antes da operação; falha parcial não permite replay. Mudança de resolução
ou diferença visual no alvo após confirmação exige nova observação; essa heurística
não substitui uma identificação confiável de aplicativo. Texto/teclas aprovados incluem
um clique explícito para restaurar foco no alvo. Unicode usa clipboard com restauração.

`computer_observe` permite `region=[x,y,largura,altura]` referente ao último `frame_id`.
O recorte mantém um mapa de origem/extensão física e fornece nova referência visual;
coordenadas posteriores são pixels da nova imagem. Sem `region`, retorna ao monitor
inteiro. Trocar o recorte limpa o buffer/referência anteriores. `wait_seconds` (0–10)
é cancelável, não gera input, não renova acesso e não exige nova permissão dentro da
sessão já autorizada. Não reduz o escopo de captura originalmente autorizado.

Cada arrasto confirma origem/destino no mesmo quadro, verifica visualmente ambos e
libera o botão em `finally`. Atalhos liberam todas as teclas tentadas após falha.
Fail-safe só é suspenso para liberação de input já pressionado e restaurado em seguida.
Texto ASCII é aplicado em blocos de até 50 caracteres, com verificação de cancelamento.
Depois de input, espera limitada de aproximadamente 1,5s procura estabilidade visual;
estabilidade ou timeout jamais são evidência de sucesso da tarefa. Falha pós-input
informa que a ação já foi entregue e nunca permite replay automático.

Frames conservam PNG codificado e até três imagens recentes; a decisão recebe somente
as últimas cópias de imagens idênticas, em ordem temporal. A última sempre é a referência.
Instalar uma sessão nova é atômico; workers/operações de sessões antigas não podem
limpar seu backend ou registrar falhas nela. Encerramento descarta também o recorte.

Captura termina com Ctrl+C, expiração, conclusão/falha do turno, `computer_stop` ou
fail-safe do PyAutoGUI (ponteiro em um canto). Erros não alegam sucesso. Reiniciar exige
nova autorização. Linux X11/macOS com display e permissões; Wayland, desktop bloqueado,
Windows nativo, múltiplos monitores e uso em segundo plano não têm suporte anunciado.

Verificação: `tests/test_interaction.py`, dependências opcionais em virtualenv e
transporte nativo simulado; testes de desktop isolado são registrados separadamente
das verificações com contas reais de provedores.
