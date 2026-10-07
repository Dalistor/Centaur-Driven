# Validação Centaur CLI 0.9.3

Data: 2026-10-07. Fluxo aprovado pelo proprietário: uma autorização durante a vida do
chat para ver/controlar desktop, sem confirmação por ação, captura durante a tarefa,
pausa em menus/outro chat, retomada fluida, exclusividade e revogação visível.

- ComputerPermissions mantém consentimento 0600 em diretório privado separado de
  transcript/imagens, por ID de chat. Novos turnos/controller/reinício reutilizam o
  consentimento; outro chat não herda. Refusa não inicializa backend e não repete a
  pergunta no mesmo turno. Permissões do SO continuam necessárias.
- Grant/revoke são serializados no controller. Teste com gravação bloqueada e revogação
  concorrente confirma que uma aprovação atrasada não restaura acesso. Saves comuns do
  ChatStore não afetam consentimento; exclusão e TTL removem o registro. Symlinks,
  IDs/JSON inválidos falham fechados. Ferramentas de arquivo do modelo não editam grants.
- ComputerControl compartilha foco entre facades de workers. Menus/config/input/outro
  chat suspende, descarta frames/coordenadas e libera desktop; worker aguarda com estado
  waiting_input, retomando com novos quadros quando o chat volta. Pausa manual exige
  resume. Espera verifica cancelamento a cada 100ms. Subagentes não recebem o controlador.
- DesktopLease usa flock exclusivo 0600 por UID em /tmp, comum entre projetos/processos,
  incluindo TMPDIR diferentes. Teste em subprocess real verifica exclusão e liberação;
  o lock não é apagado para não permitir dois inodes concorrentes. Falha ao iniciar
  backend libera o lock e preserva consentimento. Workers antigos não soltam dono novo.
- Sem expiração de captura de 120s por padrão; teste avança relógio em 3600s, mantendo
  buffer de três frames. Task concluída/falha/cancel/stop encerra captura; grant permanece.
  Revogação é conferida antes de input e exige consentimento novo; não reautoriza através
  de observe/action. Ctrl+G/revoke cancela o turno e impede persistência tardia do grant.
- Move/scroll captura imediatamente, sem settle. Clique/texto/teclas/drag buscam dois
  intervalos estáveis (150ms, orçamento de 1s); sucesso continua sendo verificado pela IA.
  Referência de 60s, resolução/origem física, alvo/destino e consumo antes de input
  permanecem validados. Falha parcial não autoriza replay; fail-safe/liberação de teclas
  permanecem ativos. Computador em uso/pausado e atividade aparecem no terminal.
- $computer status/pause/resume/revoke são locais, utilizáveis durante execução;
  Ctrl+G funciona também em menus/perguntas/aprovações. Worker real em thread percorre
  aprovação inicial, captura, menu, novo chat, espera, retorno, nova referência, ação e
  encerramento. Testes das três políticas verificam apenas uma pergunta por captura+
  ações. Desktop Xvfb real no CI verifica input, repaint atrasado, alvo alterado e fail-safe.
- Suíte de 461 casos: 455 aprovados localmente, seis opt-in de desktop/clipboard no CI.
  Dezoito casos de consentimento/controle, além de testes existentes de input/transporte,
  sessões concorrentes e PTY real em quatro modos (SGR e X10 negociados).
- Wheel/sdist, twine strict, check_dist com 68 recursos e instalação limpa; compileall,
  diff check, auditoria UI strict e lint DESIGN sem erros/avisos. CI Linux 3.10/3.13,
  macOS 3.13 e desktop Xvfb descartável antes de build/release.

Testes locais usam backend de desktop injetado; nenhum desktop pessoal foi controlado,
nenhuma chamada paga/autenticada ao modelo foi feita. Não foi testado input real macOS;
CI macOS valida CLI/PTY/clipboard. X11 é exercitado em desktop descartável no CI.
Sem Windows/Wayland/múltiplos monitores, sandbox, vídeo contínuo para o modelo ou controle
em segundo plano. PyPI requer Trusted Publisher e tem job separado da release GitHub.

## Navy e espera de subagentes

- Tokens RGB canônicos no Palette; adaptação programável reversível, fallback ANSI navy
  e NO_COLOR. Três novos casos cobrem restauração em erro/saída, rejeição parcial do
  terminal e fallback sem mutação. PTY existente exercita interação e teardown real.
- Fase real do executor separada de heartbeat; tempo de modelo/input/comando/compactação
  aparece em preview/cartões. Cancelamento agora propaga, com histórico cancelled;
  falha persiste last_error e retorna relatório ao coordenador.
- Nove testes novos de watchdog, incluindo processos Python reais silenciosos, saída
  crescente, deadline absoluto apesar de atividade, cancelamento, resumo e descendente
  em nova sessão segurando pipes. Teste real de subagente termina com relatório failed
  e runtime stopped; nenhum backend autenticado é usado.
- Preview SVG gerado por `python -m scripts.render_cli_preview docs/images/cli-0.9.3.svg`
  usa TerminalView/Palette de produção e dados demonstrativos, não uma execução real
  de task. Inspeção visual inclui conversa 140×32, abertura 110×32 e janela 40×12.

A imagem recebida mostra um comando concluído seguido de Trabalhando; sem logs do
processo do usuário não é possível afirmar a causa exata. A correção trata espera
silenciosa e limpeza sem prazo, e torna a fase observável. Processamento legítimo
pode ser silencioso; o novo limite é configurável. OpenRouter mantém seu timeout de
rede existente; esse watchdog é específico dos processos Codex/Claude.
