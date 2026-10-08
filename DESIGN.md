---
version: alpha
typography:
  display:
    fontFamily: "monospace"
  body:
    fontFamily: "monospace"
omitted:
  - section: colors
    reason: "Cores herdadas do emulador por slots ANSI e padrões curses; não existem RGB fixos do produto."
  - section: rounded
    reason: "Interface de caracteres; não existem raios em pixels."
  - section: spacing
    reason: "Geometria medida em células e linhas do terminal, não em CSS."
---

# Centaur CLI

Interface de operação para programação com agentes. A identidade escolhida pelo usuário
é “Convergência”: duas faixas curvas finas, prateada e verde, que se encontram em uma ponta
comum, com uma flecha verde fina cruzando o centro e avançando além da junção. Representa julgamento humano e execução por IA na mesma direção. Mantém a assinatura
“HUMAN INTENT. AMPLIFIED.”. A marca aparece na abertura; a conversa ocupa a superfície
assim que o usuário começa a trabalhar.

## Linguagem visual

- Fundo e texto padrão do emulador, conforme pedido do proprietário de 2026-10-08,
  com contenção visual inspirada nos CLIs Codex e Claude. Conversa, composer, seleção
  e execução lateral compartilham o mesmo fundo, inclusive em temas claros ou transparentes.
  Hierarquia por espaçamento, marcadores e peso; sem blocos de cor por mensagem.
- Palavra CENTAUR espaçada, emblema abstrato de Convergência em relevo Braille Unicode
  (2 × 4 pontos por célula). Faixa superior prateada e inferior verde; ambas são arcos finos
  com espaço negativo amplo, ponta compartilhada e flecha verde horizontal ao centro. Curvas Bézier cúbicas com largura total
  aproximada de 0,13 unidades e afilamento na junção; perspectiva, bisel e luz em CPU.
  O fallback em blocos/ASCII deriva da mesma geometria. Não usa imagens nem fontes externas.
- Cor de texto padrão para conteúdo; verde ANSI para comandos e autores; azul ANSI
  para modelo e ferramentas; texto atenuado para caminhos, atalhos e separadores;
  amarelo ANSI para confirmações e erros. Os RGB são definidos pelo emulador.
- Linhas horizontais discretas separam identidade, trabalho e campo de entrada.
- A fonte é a monoespaçada do terminal do usuário. O CLI não troca fontes ou configurações.

## Paleta do terminal

`appearance.Palette.TOKENS` é a fonte canônica dos papéis: texto `-1` (padrão),
verde ANSI 2, azul ANSI 4 e aviso ANSI 3. `Palette.initialize` habilita
`curses.use_default_colors`; todos os pares têm fundo `-1`, sem `init_color`, paleta
programável ou preenchimentos navy. Secundário e separadores usam o texto padrão
com `A_DIM`. O programa herda a aparência clara, escura ou transparente do emulador;
não tenta detectar o tema nem substituir preferências pessoais.

Terminais de oito ou 256 cores usam os mesmos slots nativos. Se cores padrão ou um
par não forem suportados, os papéis correspondentes usam atributos monocromáticos,
preservando o fundo. `NO_COLOR` não inicializa pares e mantém seleção por `>` e
negrito, autores/ações em negrito e marcadores textuais. Não usa inversão de cores.

## Composição e estados

Em janelas amplas, símbolo e wordmark aparecem à esquerda, com apresentação e exemplos de skills
à direita: `$spec`, `$run master/0001`, `$check` e `$skill`. Comandos próprios, como
`$status` e `/new`, aparecem separados em azul. Em 80 × 24 o símbolo fica compacto. Em janelas estreitas, prioriza os comandos;
abaixo de 40 × 12 mostra orientação de tamanho e preserva o campo de entrada.

O título em negrito fica no topo da coluna de leitura (até 100 células), acima da pasta e do modelo. A conversa e a entrada compartilham o mesmo alinhamento. Mensagens do usuário usam o fundo padrão, texto principal e negrito; respostas usam o texto normal, com autor em verde. Comentários públicos da IA e `report_progress` usam texto principal em peso normal. Ações pendentes/concluídas usam informação azul em negrito; falha, interrupção e recusa usam âmbar. Cabeçalho de trabalho e espera mantêm tom secundário. Ações mostram estado por texto e símbolo; Ctrl+O alterna as saídas completas. O cabeçalho identifica a pasta e o modelo. O rodapé mantém estado, mensagem digitada e
atalhos. A lista de chats destaca toda a linha selecionada, com data quando houver espaço. A seta esquerda edita o texto; Shift+← abre os chats.
Confirmações usam âmbar e instruções explícitas para permitir, recusar e revisar a ação.
O cursor fica visível durante a digitação e oculto na lista ou confirmação.

O campo sem preenchimento começa com três linhas e cresce até oito conforme o espaço. `composer.layout_input`
é o dono da quebra por células e da posição do cursor; `keyboard.KeyboardReader` decodifica
Shift+Enter e colagem protegida. Enter envia, Shift+Enter/Ctrl+J insere linha; ↑/↓ editam
linhas no rascunho multilinha; em campo vazio/de uma linha, percorrem prompts até o rascunho
atual, inclusive vazio. `Terminal.recall_prompt` conserva as mensagens salvas e o cursor do
rascunho. PgUp/PgDn continuam rolando a conversa. O campo acompanha
o cursor com ↑/↓ indicando linhas ocultas. Modais conservam sua geometria e suas ações.

Contexto e créditos compartilham a linha acima dos atalhos, à esquerda e à direita, sem
sobreposição. `context` estima apenas o contexto ativo; `~` permanece explícito e limite
desconhecido mostra `[?]`, sem porcentagem. Âmbar indica 20% ou menos de espaço. `$compact`
usa IA sem ferramentas, mantém o histórico visível e torna a redução observável no rodapé.
Autocompact usa esse mesmo estado/feedback antes da próxima chamada a 80% da janela
conhecida; desconhecida não dispara automaticamente. Revisões de resumo são limitadas,
sem truncar memória. Falha preserva histórico e interrompe a próxima chamada com orientação.
Comandos locais isolados executam com um único Enter no autocomplete; Tab só completa.
Skills e menções no meio de frases conservam inserção antes do envio. O rodapé diferencia
essas ações. Compactação mostra fragmento atual/total e a revisão em andamento, com o
tempo de atividade já existente; progresso não representa uma porcentagem de inferência.
Compactação informa o orçamento total (1800s por padrão) e reduz fragmentos após timeout.
O progresso é persistido, sem substituir memória ativa; interrupção orienta retomar com
`$compact`, inclusive após reinício. Rascunhos só são reutilizados para o mesmo prefixo,
modelo e memória anterior. Nenhuma tentativa prolonga indefinidamente a operação.
Autocompact conclui assim que recupera espaço (alvo estimado de 60% da janela, incluindo
overhead). Ao esgotar o prazo, um resumo validado pode reduzir apenas um prefixo seguro;
mensagens e lotes não totalmente resumidos permanecem integrais. Falta de divisão segura
ou de espaço suficiente produz “Turno pausado”, em tom secundário, com `$compact` e
`/retry`; nunca implica falha do modelo. Falhas reais permanecem em âmbar. Erro legado
de prazo de compactação é apresentado como pausa anterior, sem apagar sua retomada.

Créditos ficam no canto inferior direito. A barra usa
10 células em janelas amplas e 5 nas estreitas, com valor em US$. Verde indica disponibilidade;
âmbar indica 20% ou menos, ou saldo desatualizado (prefixo `~`). Em janelas mínimas o valor
é priorizado sobre o desenho da barra; backends nativos usam `native_usage.native_label` para cotas/ créditos na unidade original, com ausência explícita e cache `~` do Claude. “Conta” e “Chave” distinguem
saldo global de limite da credencial. Durante resize, a barra acompanha o canto e o conteúdo
é recomposto a partir do estado atual, preservando rascunho, seleção e conversas.

## Seletores, edição e movimento

`TerminalView` e `Palette` são os donos do desenho; `ConfigPicker` é o dono compartilhado
da seleção de backend/modelo/effort/permissões/velocidade. Lista de chats, autocomplete e configuração destacam
o texto da linha em negrito e mostram a seleção por `>`, sem trocar o fundo. A edição de título fica na mesma
superfície e preserva o rascunho da conversa. Telas de edição em menos de 20 linhas usam
a área de conteúdo inteira; mensagens curtas não movem os controles de salvar/cancelar.
Textos largos são recortados por células, incluindo a janela de entrada e seu cursor.

`startup.StartupPicker` reutiliza `ConfigPicker` e o mesmo desenho para a sequência
Backend → Modelo padrão → Effort → Permissões → Velocidade → revisão. O rodapé explica o agente principal e a
seleção de modelos por task; erros de conexão têm prioridade nessa área. A tela inicial
requer 40 × 18 e preserva escolhas ao redimensionar. Autenticação acontece depois da revisão,
fora de curses para manter entrada de chave oculta; o chat e sua animação começam em seguida.

`graphics.Renderer` é o dono da geometria, projeção, profundidade e luminosidade;
`WelcomeAnimation` é o dono do relógio de tempo visível. A abertura faz uma volta em 6 s,
com easing quintic, fade de entrada e pose frontal estável ao terminar. Cadência alvo: 20 FPS
(50 ms, descontando o tempo de desenho). A malha é calculada uma vez; o último quadro é
reutilizado quando estático. Palco limitado a 36 × 16 células, ou 26 × 10 no modo compacto.

A animação pausa quando outra superfície a oculta; digitar encerra o giro na pose frontal.
F5 repete somente na abertura sem rascunho, trabalho ou modal; novos chats não reiniciam
o giro automaticamente. Movimento não altera foco, seleção, rascunho ou layout.
`CENTAUR_REDUCED_MOTION=1` apresenta a pose final imediatamente e troca o spinner por
um marcador fixo. `CENTAUR_GRAPHICS=0` seleciona o emblema estático em blocos/ASCII, também útil
para fontes sem Braille. Codificação sem Braille usa fallback estático automaticamente.

O indicador de atividade continua com 4 frames a 8 passos por segundo e tempo decorrido;
não representa porcentagem de execução.

## Mapeamento dos tokens

`appearance.Palette.TOKENS` define slots ANSI, não RGB. Os estilos text/green/blue/warning
mapeiam texto padrão/verde/azul/amarelo do terminal; muted/line usam o texto padrão
atenuado. `comment` deriva de text, `action` de blue com negrito. Em `NO_COLOR`, ações
ficam em negrito e comentários em peso normal. `conversation.TranscriptLine` transporta
o estilo de origem por todas as linhas quebradas, sem inferir papéis por indentação
ou texto fornecido pela IA. Title e user usam texto padrão com negrito; input usa
texto normal. Input e cartões reutilizam os mesmos estilos, sem pares de superfície.
Selecionado usa verde/negrito e marcador `>`, conservando o fundo padrão.

`TerminalView.put` é o único caminho de desenho para cabeçalho, conversa, seletor,
rename, autocomplete, gráfico e rodapé. O gráfico mantém 16 níveis de luminosidade
geométrica, quantizados em atributos dim/normal/bold no texto padrão ou verde ANSI,
sem misturar RGB com um fundo presumido. A forma, movimento e marca permanecem;
a fonte e os valores de cor ficam sob controle do terminal do usuário.

| Regra anterior | Evolução autorizada | Execução |
| --- | --- | --- |
| A marca aparece só na abertura | Convergência em relevo, arcos finos, giro e pose final | `graphics.Renderer`, `TerminalView.logo` |
| Cabeçalho mostra pasta/modelo | Acrescenta nome do chat, effort e estado | `TerminalView.draw` |
| Esquerda abre histórico | Shift+← abre; esquerda edita | `Terminal.handle` |
| Créditos no rodapé | Compartilha linha com contexto, sem sobreposição | `TerminalView.draw` |

Comportamentos duráveis e recuperação estão em [UX-CONTRACT.md](UX-CONTRACT.md).

## Permissões e amplitude da conversa

O seletor canônico também controla permissões, com explicação da opção focada. “Sem perguntar”
usa âmbar e descreve o acesso do usuário. O cabeçalho prioriza o nome do modo, inclusive em
janelas estreitas. A ação final ocupa a linha disponível, sem duplicar o texto em duas colunas.
Em seletores curtos, a lista acompanha o foco para manter salvar acessível. Alterar modelo, effort, velocidade ou
permissões preserva a conversa no mesmo backend; mudar conexão inicia outra.
Velocidade explica o custo maior, oferece Fast só quando anunciado e conserva effort.
O cabeçalho diferencia Fast solicitado de tier efetivamente informado pelo provedor.

`/wide` usa a largura disponível para histórico e entrada; o modo normal mantém a coluna de
100 células. Falhas completas são quebradas em linhas dentro da conversa e podem ser roladas.
A indicação “Erro no turno” usa âmbar; `/retry` é explícito e preserva checkpoints existentes.

## Perguntas, leitura e observação da tela

Fonte: pedidos do usuário em 2026-10-06. O seletor de perguntas usa a mesma paleta,
coluna e rodapé da conversa: título verde, opção focada com `selected`, instrução
secundária e erro em âmbar. `TerminalView.question` é o único desenho desse seletor;
`QuestionPicker` mantém seleção, texto, cursor e validação. Em 40 × 12 ele ocupa a
região compacta dos editores; PgUp/PgDn tornam toda pergunta/opção longa acessível.
Resposta livre fica no compositor canônico, sem substituir o rascunho da conversa.

Histórico mostra posição e retorno ao fim quando rolado; conteúdo novo preserva a
linha superior visível. Setas seguem a prioridade dos seletores já abertos. A roda do
mouse é complementar ao teclado. Nenhuma animação ou resultado força retorno ao fim.
O estado `TELA ATIVA` no cabeçalho informa a captura contínua e desaparece quando ela
para. O CLI não desenha uma falsa prévia de vídeo nem representa chamadas por quadros
como inferência em tempo real. Confirmações do desktop reutilizam a superfície canônica
de permissões, com escopo, duração, destino dos quadros e ação explícitos.

## Anexos na mensagem

Arquivos preparados usam a cor informativa azul, com quantidade e nomes numa linha
junto ao campo quando há altura suficiente; a lista completa aparece ao final da
conversa. Em 40 × 12, os nomes ocupam linhas compactas, preservando o campo e o cursor.
Não há animação decorativa adicional: aviso de preparação/espera e cancelamento usam
os estados existentes. Mensagens enviadas exibem identidade dos anexos em tom secundário,
sem imprimir seus bytes, texto inteiro ou base64 no transcript. Cores e geometria
continuam acessíveis no modo monocromático e em movimento reduzido.

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

## Atividade verificável — 0.9.3

Fonte: referência visual e relato do proprietário em 2026-10-07, com revisão do fundo
em 2026-10-08. Composer e cartões compartilham o fundo padrão do emulador, com
comentários na cor de texto padrão e ações azuis. Não há efeitos novos durante
trabalho; Convergência e movimento reduzido mantêm seus controles.

Subagentes mostram a fase real — Aguardando modelo, Executando comando, Lendo arquivo
ou Compactando — e tempo nessa fase. Heartbeat confirma processo vivo, não progresso.
Input é explícito; parada encerra o cartão. Falha persiste diagnóstico no preview.
Cores ANSI e padrões são herdados uma vez na sessão, sem redefinição; fonte, mouse, wrapping,
scroll e checkpoints mantêm os donos canônicos. Verificação e preview do renderer
real estão em [docs/validation-cli-0.9.3.md](docs/validation-cli-0.9.3.md).


## Hierarquia e observação da execução — 0.9.6

Fonte: pedido e capturas do proprietário em 2026-10-07. `agent_tree.AgentTree` é o dono
compartilhado de ancestralidade, ordem e conectores `├─↳`/`└─↳`. As setas representam
relações, sem animação adicional. Raízes ficam acima dos filhos; menu preserva o estado
textual e a seleção por ID. Profundidade muito grande comprime a indentação, sem perder
acesso às linhas. Pais ausentes mostram identidade disponível sem inventar um principal.

Cartões identificam o principal por ID/nome, seguidos por task, modelo/effort/velocidade,
fase e último evento do CLI. Mantêm o fundo padrão, papéis de cor e geometria do
renderer canônico. O preview informa principal e pai imediato; Enter retorna à raiz
local. A barra de contexto passa a mostrar o agente em leitura com rótulo `Agente`,
sem contabilizar o rascunho do principal. A leitura não autoriza ações.

`SessionRegistry` mantém metadados públicos e tempo sem nova saída separados do heartbeat.
Ausência de bytes é explicitamente observação, não conclusão de travamento. Novos eventos
não alteram scroll/foco nem reiniciam o relógio da fase/deadline. Nenhum texto privado do
provedor entra no estado visual. Narrow, NO_COLOR e movimento reduzido preservam árvore,
acesso por teclado, modelo e estado. Referências demonstrativas usam o TerminalView real.

## Coordenação durante execução — desenvolvimento local

Fonte: pedido do proprietário em 2026-10-07. O compositor canônico permanece editável
durante execução; Enter aceita mensagem em fila e mantém o foco. `Terminal.lines`
exibe o texto recebido com rótulo Aguardando entrega após a etapa atual, sem afirmar
resposta concluída. Falhas preservam texto/anexos. Captura única passa para Ctrl+S;
colagem/arrasto continuam no mesmo compositor, sem novos comandos auxiliares.

`AgentGroup` coordena seis vagas por principal e mailboxes entre etapas; a árvore
existente representa também delegações recursivas reais. Relatórios recebidos em
segundo plano retomam a sessão de origem e preservam o chat/rascunho visíveis.
Perguntas e permissões concorrentes usam o seletor canônico, uma de cada vez.
Fundo padrão do emulador, geometria, cores por papel, scroll e movimento reduzido permanecem.
