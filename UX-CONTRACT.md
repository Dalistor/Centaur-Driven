# Comportamento do terminal Centaur

Produto: CLI curses em português para desenvolvimento assistido. A identidade visual
está em [DESIGN.md](DESIGN.md). O pedido desta mudança autoriza seletor, effort, Shift+←,
rename e melhorias visuais; as regras de desenvolvimento vêm de
[graphify/references/lifecycle.md](centaur_cli/skills/graphify/references/lifecycle.md).

| Capacidade | Dono canônico | Estados e contrato | Verificação |
| --- | --- | --- | --- |
| Select/Listbox | `settings.ConfigPicker`, `appearance.TerminalView.settings` | ↑/↓ selecionam; Enter abre/confirma; Esc volta/cancela; filtro local; salvar explícito | `tests/test_terminal_settings.py` |
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
