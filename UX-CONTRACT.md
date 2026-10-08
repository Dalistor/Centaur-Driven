# Comportamento do terminal Centaur

Produto: CLI curses em português para desenvolvimento assistido. A identidade visual
está em [DESIGN.md](DESIGN.md). O pedido desta mudança autoriza seletor, effort, Shift+←,
rename e melhorias visuais; as regras de desenvolvimento vêm de
[graphify/references/lifecycle.md](centaur_cli/skills/graphify/references/lifecycle.md).

| Capacidade | Dono canônico | Estados e contrato | Verificação |
| --- | --- | --- | --- |
| Select/Listbox | `settings.ConfigPicker`, `appearance.TerminalView.settings` | ↑/↓ selecionam; Enter abre/confirma; Esc volta/cancela; filtro local; salvar explícito | `tests/test_terminal_settings.py` |
| Inicialização | `startup.StartupPicker`, `StartupWizard`, `__main__.main` | Backend → modelo → effort → permissões → velocidade → revisão; escolhas antes de autenticar; cancelar não cria chat; falha permite tentar novamente | `tests/test_startup.py`, terminal real com PTY |
| Form | `Terminal.handle_settings`, `Terminal.handle_rename` | Validação textual, valores preservados em falha; bloqueio de salvamento duplicado | `tests/test_terminal_settings.py` |
| Feedback | `Terminal.notice`, `ConfigPicker.error`, `TerminalView.draw` | Mensagem no rodapé, erro permanece no seletor; não substituir erro por sucesso | `tests/test_terminal_settings.py` |
| Chats | `history.ChatStore`, `Terminal` | IDs imutáveis, gravação atômica, retomada por seleção; rename lê conteúdo atual do disco | `tests/test_cli.py`, `tests/test_terminal_settings.py` |
| Gráfico da abertura | `graphics.Renderer`, `WelcomeAnimation`, `Palette`, `TerminalView.logo` | Relógio visível; giro finito; digitação encerra; F5 repete; resize mantém fase; reduced motion e fallback estáticos | `tests/test_graphics.py` |
| Histórico e foco | `Terminal.cursor`, `Terminal.scroll`, `TerminalView` | Shift+← ou /chats abre lista; rascunho preservado ao voltar/cancelar; PgUp/PgDn rolam | `tests/test_terminal_settings.py` |
| Foco da janela | `keyboard.KeyboardReader`, `Terminal.run_screen`, `WelcomeAnimation` | Perda de foco pausa desenho; agentes/eventos/heartbeat continuam; retorno ou tecla redesenha o estado atual sem alterar rascunho ou autorizar ações | `tests/test_composer.py`, `tests/test_terminal_pty.py` |
| Entrada multilinha | `composer.layout_input`, `keyboard.KeyboardReader`, `Terminal.handle` | Quebra visual sem alterar texto; Enter envia, Shift+Enter/Ctrl+J insere linha; colagem não envia ou aprova | `tests/test_composer.py` |
| Comandos locais | `completion.LOCAL_COMMANDS`, `SkillCompletion.local_command`, `Terminal.handle` | Enter executa comando local isolado com autocomplete; Tab só completa; skills/menções em frases apenas inserem; compactação informa progresso por fragmento | `tests/test_completion.py`, `tests/test_terminal_pty.py` |
| Velocidade | `speed`, `ConfigPicker`, `NativeClient`, `OpenRouter` | Standard padrão; Fast só anunciado; custo explicado; não altera modelo/effort; tier solicitado não é tier confirmado | `tests/test_native_usage_speed.py` |
| Cotas nativas | `native_usage`, `Terminal.request_credits` | RPC Codex somente leitura; eventos Claude públicos em cache; sem saldo inventado, credenciais ou prompts na consulta | `tests/test_native_usage_speed.py` |
| Contexto e compactação | `context.active_messages`, `compact_chat`, `save_compaction`, `save_compaction_progress`, `agent.run_turn` | Barra estimada sem limite inventado; autocompact a 80%, alvo 60%; prefixo seguro pode concluir antes; orçamento total 1800s e chamadas com orçamento restante; timeout reduz fragmento; progresso em disco; pausa retomável sem erro de modelo; histórico/lotes intactos | `tests/test_context.py` |
| Prompts anteriores | `Terminal.recall_prompt`, `keyboard.read_key` | ↑/↓ percorrem prompts e restauram rascunho/cursor vazio ou preenchido; CSI/SS3 não viram texto; editar cópia não altera mensagem salva | `tests/test_composer.py`, `tests/test_terminal_pty.py` |
| Trabalho e permissões | `Terminal.approval`, `ProjectTools` | Troca/rename do chat ativo aguardam turno; aprovações continuam prioritárias | `tests/test_cli.py` |
| Ciclo de vida | `lifecycle.load_project`, `spec_completion_issues` | Gate somente leitura; prova corrente e integração separadas; conclusão não deriva do status | `tests/test_lifecycle.py` |

Escolher backend/modelo/effort/velocidade não grava. Salvar valida em segundo plano e,
somente após persistir a configuração, aplica as escolhas. No mesmo backend preserva
ID/título/mensagens/memória/erro; troca de backend cria chat novo. Falha mantém conversa e escolhas.
Catálogo atrasado só atualiza o seletor que iniciou a leitura e o mesmo backend. Catálogo
indisponível permite informar ID; resultado de rede não é confundido com prova de acesso ao
modelo. Credenciais não entram na configuração, no título ou na conversa.

Renomear não chama o modelo, não altera ID/modelo/effort/mensagens e não cria outro chat.
Título deve ter 1–80 caracteres imprimíveis. Enter salva; Esc cancela; uma falha conserva o
texto digitado. Um chat em execução não pode ser renomeado. A lista mantém selecionado o
ID editado, mesmo se a ordenação por data mudar.

Resize conserva conteúdo e posição do cursor; a entrada mostra as linhas que contêm o
cursor, medidas em células Unicode, com três linhas iniciais e até oito conforme o espaço.
Modais mantêm sua geometria de edição; teclas e colagens do chat não confirmam permissões.
Movimento reduzido e ausência de cor preservam todos
os comandos e a indicação textual da seleção. As superfícies são de terminal, sem HTML,
DOM, popups de navegador, fontes remotas ou scrollbars CSS.

`--complete` nunca altera READMEs ou estado. Ele exige vínculos explícitos e percorre
filhas/dependências; integração/publicação remota continua exigindo observação externa.
O harness não transforma uma resposta de IA ou relatório de subagente em aprovação.

## Conversa e títulos gerados

`conversation.py` é o dono dos resumos de ações, da apresentação de Markdown e do pedido
de título. `Terminal.lines` preserva a ordem da conversa: usuário, progresso público,
ferramentas resumidas, resposta final. `Ctrl+O` alterna detalhes sem mudar foco ou rascunho.
`TranscriptLine` leva o estilo definido pela origem até `TerminalView`: comentário branco,
ação azul, falha/recusa âmbar. Quebra de linha e rolagem preservam a distinção; marcadores
ou indentação dentro do conteúdo não mudam o papel visual. `NO_COLOR` distingue ações
em negrito de comentários normais, conservando símbolos e descrições de estado.

Autocompact pode concluir um prefixo menor assim que há espaço suficiente (alvo estimado
de 60%, incluindo overhead). Ao esgotar prazo, só mensagens completamente processadas
podem sair do contexto ativo; lotes de ferramentas continuam inteiros e toda mensagem
restante fica integral. O resumo usado precisa ser válido e reduzir contexto. Sem divisão
segura ou espaço suficiente, `CompactionPaused` interrompe a próxima chamada com estado
`turn_paused`, sem registrar erro de modelo; `/retry` retoma sem duplicar o pedido.
Cancelar ou falhar no provedor continua preservando memória ativa e checkpoints.
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
Cancelar ou falhar ao salvar conserva o modo e a conversa ativos. Aplicar permissões, modelo, effort ou velocidade
preserva o chat no mesmo backend; mudar backend cria outro. Histórico não concede permissões.
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
novas mensagens. PgUp/PgDn são equivalentes da roda do mouse; Ctrl+E volta ao
fim. ↑/↓ percorrem prompts no campo vazio/de uma linha e restauram rascunho/cursor atual,
inclusive vazio. Durante a navegação, prompts multilinha também podem ser percorridos.
Editar uma cópia encerra essa navegação sem alterar o histórico; rascunhos multilinha
fora da navegação usam as setas para mover o cursor. `Terminal.recall_prompt` é o dono.
Completar skills, lista de chats, perguntas e preferências têm prioridade sobre
rolagem do chat. Resize recalcula a quebra de linhas sem perder texto ou seleção.

Verificação: `tests/test_interaction.py`, suite completa e PTY com pergunta, resposta
livre, pular, rolagem durante execução, mouse, interrupção, resize e janela 40 × 12.

## Computer use

`ComputerSession` é o dono da captura/referência visual; `ComputerControl` gerencia foco,
pausa e lock exclusivo; `ComputerPermissions` persiste o consentimento privado por chat.
O extra `computer` é opcional: imports de desktop não afetam a instalação base.
`computer_start` exige consentimento inicial para captura/controle do monitor principal,
inclusive em never. Vale para o chat até revogação/exclusão e persiste fora das mensagens.
Ações seguintes não pedem aprovação; captura dura a tarefa e subagentes não têm acesso.
O sistema não oferece execução arbitrária de código de computer use.

Captura local em aproximadamente 2 quadros/s, buffer de três quadros; imagens reais são
anexadas a cada chamada de decisão via OpenRouter, `--image` no Codex ou entrada
`stream-json` do Claude. O transporte é de quadros por chamada, não vídeo em tempo real.
`vision.py` valida PNGs e limita anexos. Quadros efêmeros de computer use não entram no ChatStore; arquivos PNG
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
Depois de clique/texto/teclas/arrasto, espera limitada de aproximadamente 1s procura estabilidade visual;
movimento e rolagem atualizam o quadro sem essa espera;
estabilidade ou timeout jamais são evidência de sucesso da tarefa. Falha pós-input
informa que a ação já foi entregue e nunca permite replay automático.

Frames conservam PNG codificado e até três imagens recentes; a decisão recebe somente
as últimas cópias de imagens idênticas, em ordem temporal. A última sempre é a referência.
Instalar uma sessão nova é atômico; workers/operações de sessões antigas não podem
limpar seu backend ou registrar falhas nela. Encerramento descarta também o recorte.

Captura termina com Ctrl+C, conclusão/falha do turno, `computer_stop` ou fail-safe do
PyAutoGUI (ponteiro em um canto). Menus/outro chat pausam; retornar captura novos quadros.
Erros não alegam sucesso. Consentimento persiste até revogar/excluir, sem expiração de 120s. Linux X11/macOS com display e permissões; Wayland, desktop bloqueado,
Windows nativo, múltiplos monitores e uso em segundo plano não têm suporte anunciado.

Verificação: `tests/test_interaction.py`, dependências opcionais em virtualenv e
transporte nativo simulado; testes de desktop isolado são registrados separadamente
das verificações com contas reais de provedores.

## Anexos preparados pelo usuário

A identificação em `clipboard.pasted_paths` confirma a lista inteira antes de tratar
uma colagem como arquivos. Falhas de consulta, sintaxe de URI ou expansão de home
retornam ao texto literal; não descartam a mensagem nem encerram o terminal. Texto
longo/Unicode mantém rascunho e cursor nas colagens protegida e via Ctrl+V. Preparar
arquivos confirmados continua seguindo validação de formato, capacidade e permissões.

`attachments.py` é o owner de leitura limitada, tipos, capacidades, normalização de
imagem, captura única, cópias privadas e hidratação para o provedor. `Terminal` possui
as filas por chat, preparação em worker cancelável e revisão/envio; `TerminalView`
possui apenas sua apresentação. Imports de mss/Pillow são opcionais e tardios.

Colagem/arrasto e Ctrl+S preparam anexos sem comandos `$attach`/`$screenshot`. A captura única é
solicitada explicitamente pelo usuário; não cria uma sessão ComputerSession. `$detach`
remove itens e Enter envia com a mensagem (inclusive vazia). Falha de capacidade ou
persistência mantém o rascunho/fila e não acrescenta mensagem. A cópia usa 0600/pasta
0700, SHA-256 e referência confinada; mudanças e ausência bloqueiam reenvio. Falha de
preparação restaura o comando se o campo continuar vazio, sem sobrescrever texto novo.

Capacidades OpenRouter vêm de architecture.input_modalities. Codex usa seu cache e
seu padrão oficial legado; modelo desconhecido exige seleção explícita. Claude permite
aliases e famílias versionadas conhecidas. Textos UTF-8 são enviados como dados não
confiáveis. Imagens são PNG nativo via --image/stream-json; PDF somente OpenRouter file
com parser native, sem fallback OCR implícito. Tipos desconhecidos não são descartados
silenciosamente no transporte nativo. Arquivos enviados persistem separadamente dos
metadados de chat; filas não enviadas duram apenas a sessão e não cruzam chats.

Compactação inclui texto e manifesto, preserva os arquivos e não envia binários/base64
ao resumidor. Originais visuais compactados deixam o contexto ativo; o resumo registra
observações existentes, não reconstrói imagens. Reanálise exige anexar novamente.
A estimativa do contexto inclui texto pendente; imagens/PDFs dependem do uso real do
provedor. Limites: oito itens/mensagem, texto 512 KiB, arquivo 8 MiB, imagem 25 MP,
anexos ativos 64 MiB; transporte nativo admite até 32 imagens no contexto, incluindo
os até três quadros recentes da sessão computer use.

Verificação: test_attachments.py e test_terminal_pty.py; CI com desktop descartável,
sem credenciais reais ou inferências pagas. Instalação base continua sem dependências.

## Composer e sessões — 0.9.0

O campo aceita Ctrl+V e caminhos locais com marcadores azuis `[Imagem #N]`/`[Arquivo #N]`.
Os marcadores são elementos atômicos, visíveis antes do envio e removíveis com Backspace/
Delete. Navegação ↑/↓ restaura anexos e preserva o rascunho atual; controles do clipboard
não entram como comandos. Falhas ou resultados tardios não sobrescrevem texto novo.

Shift+← abre o menu mesmo durante input. N + Novo chat fica abaixo do resumo dos estados;
Tab alterna chats/todos os agentes. Cada linha informa Trabalhando (verde), Aguardando
input (âmbar) ou Parado (cinza), também por texto sem cor. Perguntas/aprovações continuam
pendentes no chat de origem. Enter em subagente abre leitura; Enter no preview abre seu
coordenador local. Editores de título têm prioridade visual sobre lista e input pendente.

Vários chats deste processo executam simultaneamente, com eventos/cancelamento/config
capturados por sessão. Rascunhos e anexos retornam ao trocar. Ctrl+C afeta apenas o chat
aberto; sair exige que todos terminem. Captura de computer use para ao trocar de sessão.
Chats e agentes compartilham o diretório de trabalho; não há isolamento de arquivos.

Retenção: mais de 64h da criação imutável, verificação ao abrir menu e a cada minuto.
Expirados livres removem histórico/anexos/subagentes. Sessões vivas e rascunhos/anexos
pendentes adiam a remoção. Runtime usa registros privados separados dos chats, PID e
heartbeat de 20s com validade de 120s. Histórico legado preserva updated como criação.

Verificação: test_attachment_composer.py, test_sessions.py e PTY real em cores, NO_COLOR,
movimento reduzido e resize 40×12; clipboard/captura reais em desktop Xvfb no CI.

## Prazos e diagnósticos — 0.9.1

Inferência e operação de compactação têm padrão de 1800s, configurável de 30–3600s.
Resumo usa o orçamento restante e o limite do backend, sem teto fixo de 90s; roteamento
de subagente repassa capacidades/effort/prazo. Cancelamento/checkpoints continuam ativos.

O aviso do composer fica em uma linha, na largura exata do campo. Erro do turno tem
aviso curto com orientação para ler a conversa e retomar. Outros avisos longos recebem
reticências. Diagnósticos públicos completos ficam no transcript com quebra por células,
inclusive Unicode e palavras/caminhos longos. Falha de compactação é persistida; sucesso
remove o erro antigo somente após salvar a nova memória. Cancelamento não vira erro.

Verificação: test_timeout_layout.py, test_context.py e PTY real; tela 40×12, 80×24 e
140×30. Testes simulam relógio para 30 minutos sem esperar uma chamada real desse tempo.

## Execução lateral e cursor por clique — 0.9.2

Quadros finos azuis à direita mostram todos os subagentes ativos da pasta, inclusive de
outros chats/processos, com tarefa, modelo efetivo quando fornecido, estado, duração e
últimos comentários públicos/ações nas cores do transcript. Âmbar identifica input.
Só estados runtime vivos entram na lateral: sucesso, falha e cancelamento fecham o quadro
sem apagar o histórico. Atualização a cada 500ms; históricos parados são filtrados antes
de carregar mensagens. A roda percorre a lateral sem alterar o scroll da conversa.
Clique abre preview de leitura ou o coordenador deste processo com input pendente;
sessões de outro processo permanecem em leitura. Nenhum clique autoriza ações.

A lateral exige 112 colunas, 18 linhas e espaço para um quadro de seis linhas mais título
/rodapé. Conversa/composer/autocomplete/perguntas ocupam somente a coluna principal.
Com menos espaço, o rodapé indica subagentes e Shift+←/Tab abre o menu. Layout respeita
wide, resize e múltiplos quadros sem perder acesso aos demais.

Clique primário no campo de mensagem, título em edição ou resposta livre move o cursor
pelo índice de inserção mais próximo nas células visíveis. Considera Unicode largo,
acentos combinados, quebra visual/real, janela vertical/horizontal e margens do campo.
Marcadores de anexos continuam indivisíveis. Click atrasado de outro chat/texto é ignorado;
release/movimento não editam, e clique não envia respostas nem confirma permissões.
O teclado permanece completo; rastreamento de mouse é ativado somente na sessão curses.

Prazos de inferência continuam por chamada, sem deadline global para a espera de tasks.
Heartbeat de todos os executores mantém o runtime; subagentes vivos/aguardando input
protegem o coordenador da limpeza, inclusive com criação anterior a 64h. Ctrl+C propaga
cancelamento e fecha o painel ao encerrar o executor. O rodapé indica a retomada do
coordenador após receber o relatório.

## Computer use fluido — 0.9.3

Consentimento inicial único por ID do chat para captura do monitor principal, envio de
quadros ao provedor/modelo da conversa e controle de mouse/teclado sem novas confirmações.
Persiste privado fora do transcript; retomar/reiniciar mantém, revogar/excluir remove.
Recusa impede captura e repetição da pergunta no mesmo turno. Novo chat pede consentimento.
Permissões do sistema continuam separadas. Subagentes não herdam acesso ao desktop.

Captura dura a tarefa, buffer máximo de três quadros a 2fps, sem expiração fixa de 120s.
Menus/input/configuração/outro chat pausam e liberam lock; retorno retoma com novos quadros,
sem reutilizar coordenadas antigas. Lock POSIX por usuário impede dois processos/projetos
controlando simultaneamente. Turno encerrado/falha/cancelamento/stop descarta captura;
consentimento permanece. No terminal, Ctrl+C interrompe; Ctrl+G ou $computer revoke revoga
mesmo com input/menu aberto e cancela o turno. Comandos status/pause/resume/revoke funcionam
sem chamada ao modelo, inclusive ocupado. Pausa explícita espera $computer resume.

Cabeçalho identifica COMPUTADOR EM USO; ações públicas usam azul e o rodapé dá os atalhos
de pausa/revogação. Cliques/texto/teclas/arrasto buscam dois intervalos de estabilidade
(150ms, orçamento de 1s); move/scroll apenas atualizam a captura. Espera explícita até 10s
continua cancelável. Estabilidade não afirma sucesso. Idade/resolução/alvo/consentimento
continuam verificados; referências são consumidas antes de input e falha parcial não repete.

## Espera verificável e tema navy — 0.9.3

Fonte: referência visual e relato de subagente sem progresso do proprietário, 2026-10-07.
Palette adapta tokens compartilhados para conversa, input, seleção e cartões; slots
de cor programáveis são restaurados ao sair normalmente ou por erro. Fallback ANSI
e NO_COLOR mantêm teclado, inversão, marcadores e semântica. Não há troca de fonte.

SessionRegistry registra fase/tempo separado do heartbeat. agent.run_turn informa
modelo, ferramenta e compactação; input continua prioritário. Preview e lateral
mostram a fase e duração, sem imprimir análise privada. Heartbeat não afirma progresso.

NativeClient monitora saída cumulativa do CLI a cada 100ms. Desde 0.9.4, ausência de
bytes não encerra a chamada por padrão: saída estruturada pode aparecer somente no
fim. CENTAUR_NATIVE_IDLE_TIMEOUT=0 (padrão) desativa o corte por silêncio; um inteiro
30–3600s o ativa explicitamente. O deadline absoluto por inferência continua em 1800s,
inclusive sem saída, e Ctrl+C continua cancelando. Atividade não renova esse deadline.
O mesmo vale para subagentes e resumos, respeitando também o orçamento de compactação.
Perguntas/aprovações e tasks não consomem o timer da chamada nativa. O padrão de 300s
da 0.9.3 causava falsos erros e foi substituído por esta regra.

Kill de grupo e drenagem são limitados; um descendente que escape do grupo e mantenha
pipes abertos não prende o worker indefinidamente. Nenhuma resposta parcial executa
ferramentas e não há replay automático. Falha persiste last_error no chat do subagente,
fecha runtime/cartão e devolve relatório ao coordenador. Cancelamento persiste status
cancelled, fecha runtime e propaga TurnCancelled, sem continuar o coordenador.
/retry do coordenador preserva checkpoints e marca chamadas incompletas interrompidas.

Verificação: test_native_watchdog.py (processos reais descartáveis), test_graphics.py,
test_agent_panels_mouse.py e PTY real; preview usa TerminalView com dados demonstrativos.


Desde 0.9.5, NativeTrace lê apenas envelopes JSONL completos durante communicate:
tipos conhecidos e categorias fixas de erro. Timeout persiste fase e quantidades de
bytes, sem logs brutos ou raciocínio. Aviso anterior não confirma causa atual; ausência
de evidência é explicitamente desconhecida. turn.failed/resultado Claude de erro
encerram cedo; error recuperável não invalida conclusão válida. O arquivo final não
sobrepõe turn.failed. Sem retry automático, mudança de effort ou aumento do deadline.


## Hierarquia e diagnóstico durante execução — 0.9.6

Fonte: pedido explícito do proprietário e capturas de 2026-10-07. Owner da árvore:
`agent_tree.AgentTree`; navegação/caches em `Terminal`; desenho em `TerminalView`.
Menu ordena raízes/descendentes e mantém ID selecionado. Lateral identifica a raiz;
preview identifica raiz/pai e Enter ou clique com input retorna ao principal local.
Pais ausentes/ciclos não causam recursão infinita. Somente ancestrais necessários são
lidos para cartões ativos, sem desserializar arquivos parados não relacionados.
Executor continua sem delegate_task; renderizar uma árvore não concede delegação nova.

A barra no preview usa o contexto/modelo do executor e exclui rascunhos do principal.
Effort e velocidade são herdados quando compatíveis com o catálogo do modelo. Fallback
é default/standard e fica visível; não altera modelo, backend ou permissões.

NativeClient.on_progress entrega apenas event enum, warning enum e contagens de bytes.
SessionRegistry filtra campos e preserva phase_started e native_last_output no heartbeat.
Mudança de fase limpa a telemetria anterior. UI informa silêncio sem concluir travamento.
Observador indisponível não aborta inferência. Prazo absoluto/Ctrl+C não são renovados por
telemetria. Falha/resultado final mantém validação integral; chamadas parciais não executam.

ProjectTools.stop_command limita wait a 2s e trata ProcessLookupError na corrida de saída.
Timeout sem confirmação relata estado incerto; cancelamento propaga TurnCancelled.
Não há replay automático. Verificação: test_agent_hierarchy.py, test_agent_stalls.py,
PTY real com árvore/preview/retorno/resize, NO_COLOR e movimento reduzido.

## Coordenação concorrente — desenvolvimento local

Fonte: pedido do proprietário em 2026-10-07, com push/deploy suspensos até autorização.
`inbox.Inbox` é a fila privada persistida por chat; `agent.run_turn` entrega mensagens
somente após a etapa atual, salva antes de confirmar entrega e deduplica IDs recuperados.
Compositor aceita Enter durante execução; ferramentas não iniciadas de um lote anterior
recebem resultado explícito de não execução, sem replay. Subagentes existentes continuam.

`agent_runtime.AgentGroup` mantém seis vagas simultâneas por raiz, compartilhadas por
filhos/netos, e canais de progresso/mensagem. `SubagentTools` expõe consulta, orientação
e espera; o chat usa delegação em segundo plano. O modo síncrono da API Python permanece
compatível. Relatórios são conferidos pelo coordenador e não ampliam permissões.
Cancelamento da raiz afeta toda a árvore; concluir resposta do principal não cancela filhos.
Descendentes ativos protegem todos os ancestrais da limpeza; exclusão verifica toda a árvore.

`Terminal.ui_events` é o destino dos workers, mesmo quando outro chat está aberto;
retomada por relatório não altera o chat focado. Perguntas/aprovações são serializadas
por sessão, preservadas se a resposta principal terminar enquanto um executor espera.
`Ctrl+S` prepara captura única em 3s; Ctrl+C cancela. Anexos colados/arrastados durante
execução podem acompanhar orientação. Atalhos/Enter mantêm semântica em 40×12, NO_COLOR
e movimento reduzido.

`ComputerSession` envia um quadro atual por chamada e aceita `computer_batch` de até
quatro passos de edição no mesmo alvo. Todo lote é validado antes de input. Foco acontece
uma vez, Enter/Tab somente no último passo; navegar a outro alvo requer nova referência.
Idade, resolução e alvo continuam verificados; referência é consumida antes de input e
falha parcial não permite replay. Consentimento, pausa, revogação e desktop exclusivo
continuam nos mesmos owners; subagentes não recebem acesso ao desktop.

Verificação: `tests/test_agent_coordination.py`, `tests/test_computer_session.py`,
`tests/test_terminal_pty.py` e [evidências locais](docs/validation-cli-coordination.md).

## Execução sem foco — 0.10.2

Fonte: relato do proprietário em 2026-10-08 sobre congelamento ao desfocar o terminal.
Eventos de foco da janela usam o protocolo compartilhado de teclado, com restauração
ao sair. A perda de foco suspende apenas desenho, cursor visual e animação. O ciclo
mantém eventos, filas de mensagens, respostas e heartbeat de todas as sessões.
Resize em segundo plano não emite saída; retornar redesenha o estado atual. Digitar
também restaura o desenho caso a notificação de retorno seja perdida.

O foco da janela não muda chat, rascunho, cursor, scroll ou permissões. A seleção de
conversa continua sendo o critério de `ComputerControl`; desfocar para trabalhar no
desktop não pausa a tarefa autorizada. Perguntas e aprovações aguardam input explícito.
Terminais sem eventos de foco mantêm o comportamento normal.

Verificação: [reprodução e evidência](docs/validation-terminal-focus.md), com PTY real,
saída não consumida, resposta concluída, resize, rascunho e retorno por foco/tecla.
