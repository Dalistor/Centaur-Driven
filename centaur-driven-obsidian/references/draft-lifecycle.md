# Ciclo de um Draft

1. O usuário cria `Sistema/Drafts/<slug>.md` a partir de `_modelo.md`.
2. `refinar <slug>` preserva o texto, registra hipóteses e perguntas abertas e confirma o que já existe no código.
3. Após respostas e aprovação, `promover <slug>` cria a documentação oficial: Fluxo, Decisão quando aplicável, Visão Geral e perspectiva visual quando útil.
4. A spec é criada a partir dessas notas e recebe uma referência em `Sistema/Specs/YYYY.md`.
5. `implementar YYYY` executa somente a spec aprovada; ao final, `sincronizar` atualiza o que o código realmente estabeleceu.

Drafts não são apagados: recebem frontmatter `estado: promovido` e links para os documentos oficiais. Um Draft sem aprovação permanece como hipótese.
