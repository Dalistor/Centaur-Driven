# Centaur CLI

Interface de operação para programação com agentes, inspirada na referência “Concept C”
fornecida pelo usuário: centauro arqueiro em caracteres de terminal, seta verde e assinatura
“HUMAN INTENT. AMPLIFIED.”. A marca aparece na abertura; a conversa ocupa a superfície
assim que o usuário começa a trabalhar.

## Linguagem visual

- Fundo escuro contínuo, sem painéis sobrepostos ou bordas decorativas em cada mensagem.
- Palavra CENTAUR espaçada, ilustração com blocos Unicode (`█`, `▀`, `▄`), com silhueta em pixels e seta verde. O símbolo mantém
  cabeça, braços, arco, corpo equino e quatro pernas legíveis; há fallback ASCII quando
  a codificação do terminal não suporta os blocos Unicode. Não usa imagens nem fontes externas.
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
atalhos. A lista de chats destaca toda a linha selecionada, com data quando houver espaço.
Confirmações usam âmbar e instruções explícitas para permitir, recusar e revisar a ação.
O cursor fica visível durante a digitação e oculto na lista ou confirmação.

Créditos ocupam uma linha própria no canto inferior direito, acima dos atalhos. A barra usa
10 células em janelas amplas e 5 nas estreitas, com valor em US$. Verde indica disponibilidade;
âmbar indica 20% ou menos, ou saldo desatualizado (prefixo `~`). “Conta” e “Chave” distinguem
saldo global de limite da credencial. Durante resize, a barra acompanha o canto e o conteúdo
é recomposto a partir do estado atual, preservando rascunho, seleção e conversas.
