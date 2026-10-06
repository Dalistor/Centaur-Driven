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
`/status` e `/new`, aparecem separados em azul. Em 80 × 24 o símbolo fica compacto. Em janelas estreitas, prioriza os comandos;
abaixo de 40 × 12 mostra orientação de tamanho e preserva o campo de entrada.

O cabeçalho identifica a pasta e o modelo. O rodapé mantém estado, mensagem digitada e
atalhos. A lista de chats destaca toda a linha selecionada, com data quando houver espaço. A seta esquerda edita o texto; Shift+← abre os chats.
Confirmações usam âmbar e instruções explícitas para permitir, recusar e revisar a ação.
O cursor fica visível durante a digitação e oculto na lista ou confirmação.

Créditos ocupam uma linha própria no canto inferior direito, acima dos atalhos. A barra usa
10 células em janelas amplas e 5 nas estreitas, com valor em US$. Verde indica disponibilidade;
âmbar indica 20% ou menos, ou saldo desatualizado (prefixo `~`). “Conta” e “Chave” distinguem
saldo global de limite da credencial. Durante resize, a barra acompanha o canto e o conteúdo
é recomposto a partir do estado atual, preservando rascunho, seleção e conversas.

## Seletores, edição e movimento

`TerminalView` e `Palette` são os donos do desenho; `ConfigPicker` é o dono compartilhado
da seleção de backend/modelo/effort. Lista de chats, autocomplete e configuração destacam
a linha inteira e mostram a seleção por `>` além da cor. A edição de título fica na mesma
superfície e preserva o rascunho da conversa. Telas de edição em menos de 20 linhas usam
a área de conteúdo inteira; mensagens curtas não movem os controles de salvar/cancelar.
Textos largos são recortados por células, incluindo a janela de entrada e seu cursor.

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
mapeiam text/primary/secondary/border/info/warning. `TerminalView.put` é o único caminho de desenho
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
| Créditos em linha própria | Preservado no redesenho | `TerminalView.draw` |

Comportamentos duráveis e recuperação estão em [UX-CONTRACT.md](UX-CONTRACT.md).
