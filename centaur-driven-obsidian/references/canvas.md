# Canvas de perspectiva

Um arquivo `.canvas` é JSON do Obsidian Canvas. Crie apenas em `Sistema/Perspectivas/` ou como irmão de um Draft que está sendo refinado.

`Sistema/Quadro de specs.canvas` é uma projeção gerada com colunas por status, sem limite de cards. `Sistema/Mapa do sistema.canvas` é outra exceção: ele é um índice visual e pode usar cards de arquivo para abrir as áreas principais do vault. Não coloque arquivos técnicos nesse mapa.

## Gramática visual

- Dê a cada Canvas uma pergunta explícita, como “Como uma compra chega até a entrega?”.
- Use de 5 a 9 conceitos por perspectiva. Se precisar de mais, divida a leitura em duas perspectivas conectadas.
- Nomeie cards com conceitos ou ações humanas, por exemplo `Confirmar pedido`, nunca com caminhos, classes, endpoints ou arquivos.
- Organize o fluxo principal da esquerda para a direita; use grupos somente para fronteiras que o usuário reconhece, como `Cliente`, `Operação` ou `Parceiro`.
- Escreva cada seta como uma frase curta de transição, por exemplo `confirma itens` ou `notifica cliente`. Evite setas sem rótulo quando a relação não for óbvia.
- Evite cruzamentos, sobreposição e grandes distâncias vazias. O percurso principal deve ser reconhecível sem abrir a nota irmã.

## Estado e detalhe

- Use verde (`"4"`) para confirmado, amarelo (`"3"`) para planejado e vermelho (`"1"`) para decisão pendente. Explique a legenda na nota irmã.
- Não misture confirmado e planejado sem cor e texto explícitos.
- A nota irmã `<id>.md` responde à pergunta da perspectiva, resume a leitura em prosa e aponta por Wikilinks para fluxos, decisões e termos do Glossário.
- Quando for necessário comprovar algo, deixe caminhos, símbolos e testes em uma seção final `Evidências` da nota irmã. Esses detalhes nunca viram cards.
- Uma perspectiva mostra uma leitura do sistema. Não represente o repositório, a arquitetura de pastas, tasks ou specs.
