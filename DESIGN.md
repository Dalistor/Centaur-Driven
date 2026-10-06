---
version: alpha
colors:
  background: "#121212"
  text: "#d0d0d0"
  primary: "#87ff87"
  secondary: "#87afaf"
  border: "#4e4e4e"
  info: "#87afff"
  warning: "#ffaf5f"
typography:
  display:
    fontFamily: "monospace"
  body:
    fontFamily: "monospace"
omitted:
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

- Fundo escuro contínuo, sem painéis sobrepostos ou bordas decorativas em cada mensagem.
- Palavra CENTAUR espaçada, emblema abstrato de Convergência em relevo Braille Unicode
  (2 × 4 pontos por célula). Faixa superior prateada e inferior verde; ambas são arcos finos
  com espaço negativo amplo, ponta compartilhada e flecha verde horizontal ao centro. Curvas Bézier cúbicas com largura total
  aproximada de 0,13 unidades e afilamento na junção; perspectiva, bisel e luz em CPU.
  O fallback em blocos/ASCII deriva da mesma geometria. Não usa imagens nem fontes externas.
- Branco para conteúdo; verde para comandos e autores; azul para modelo, ferramentas e
  atalhos; tom secundário para caminhos e estados; âmbar para confirmações e erros.
- Linhas horizontais discretas separam identidade, trabalho e campo de entrada.
- A fonte é a monoespaçada do terminal do usuário. O CLI não troca fontes ou configurações.

## Paleta do terminal

Os pares curses usam a paleta ANSI de 256 cores quando disponível:
fundo 233 (`#121212`), texto 252 (`#d0d0d0`), verde 120 (`#87ff87`),
secundário 109 (`#87afaf`), linhas 239 (`#4e4e4e`), azul 111 (`#87afff`),
âmbar 215 (`#ffaf5f`). Em terminais de 8 cores, usa as cores ANSI correspondentes.
`NO_COLOR` desativa cores e mantém a seleção por inversão de vídeo.
O CLI não altera a paleta global do terminal.

## Composição e estados

Em janelas amplas, símbolo e wordmark aparecem à esquerda, com apresentação e exemplos de skills
à direita: `$spec`, `$run master/0001`, `$check` e `$skill`. Comandos próprios, como
`$status` e `/new`, aparecem separados em azul. Em 80 × 24 o símbolo fica compacto. Em janelas estreitas, prioriza os comandos;
abaixo de 40 × 12 mostra orientação de tamanho e preserva o campo de entrada.

O título em negrito fica no topo da coluna de leitura (até 100 células), acima da pasta e do modelo. A conversa e a entrada compartilham o mesmo alinhamento. Mensagens do usuário usam fundo ANSI 236 (`#303030`), texto 252 e negrito; respostas usam o texto normal, com autor em verde. Comentários públicos da IA e `report_progress` usam texto 252 em peso normal. Ações pendentes/concluídas usam azul 111 em negrito; falha, interrupção e recusa usam âmbar. Cabeçalho de trabalho e espera mantêm tom secundário. Ações mostram estado por texto e símbolo; Ctrl+O alterna as saídas completas. O cabeçalho identifica a pasta e o modelo. O rodapé mantém estado, mensagem digitada e
atalhos. A lista de chats destaca toda a linha selecionada, com data quando houver espaço. A seta esquerda edita o texto; Shift+← abre os chats.
Confirmações usam âmbar e instruções explícitas para permitir, recusar e revisar a ação.
O cursor fica visível durante a digitação e oculto na lista ou confirmação.

O campo cinza começa com três linhas e cresce até oito conforme o espaço. `composer.layout_input`
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
Compactação informa o orçamento total (180s por padrão) e reduz fragmentos após timeout.
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
a linha inteira e mostram a seleção por `>` além da cor. A edição de título fica na mesma
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

A paleta existente em `appearance.Palette.initialize` é a fonte de execução; este documento
espelha seus valores ANSI. Fundo 233 mapeia `background`; estilos text/green/muted/line/blue/warning
mapeiam text/primary/secondary/border/info/warning. `comment` deriva de text, `action` de blue com negrito; em `NO_COLOR`, ações ficam em negrito e comentários em peso normal. `conversation.TranscriptLine` transporta o estilo de origem por todas as linhas quebradas, sem inferir papéis por indentação ou texto fornecido pela IA. O estilo title deriva de text com negrito; user usa o par 40, texto 252 e superfície ANSI 236. Em modo monocromático usa negrito, preservando os marcadores do autor. `TerminalView.put` é o único caminho de desenho
para cabeçalho, conversa, seletor, rename, autocomplete, gráfico e rodapé. `Palette` gera
16 níveis por material entre fundo 233 e texto 252 / verde 120, quantizando para ANSI 256.
Os 32 pares gráficos são reservados uma vez (8–39); não se redefine a paleta do terminal.
Com menos cores/pares, usam-se os estilos existentes com dim/normal/bold. Terminais de 8 cores usam os
fallbacks ANSI já existentes; `NO_COLOR` usa atributos de texto. A tipografia permanece sob
controle do terminal do usuário, com autores/ações em negrito e conteúdo em peso normal.

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
