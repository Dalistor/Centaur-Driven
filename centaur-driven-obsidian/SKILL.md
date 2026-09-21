---
name: centaur-driven-obsidian
description: Cria e mantém a visão humana do sistema no vault local `.centaur/obsidian`, com mapa, drafts, fluxos, perspectivas e decisões; use com o Claudian para compreender e planejar o produto.
metadata:
  version: 2.0.0
  invocable: true
---

# centaur-driven-obsidian

O Obsidian é a visão humana do sistema. As notas explicam o produto, intenções, decisões e fluxos para quem precisa compreendê-lo; o código e os resultados de validação continuam sendo a evidência para afirmar o que existe. Nunca apresente uma hipótese como implementação concluída.

Mantenha a separação de públicos:

- `AGENTS.md`, `.centaur/specs/` e `.centaur/implements/` são memória operacional da IA: contexto técnico, tasks, status e trilha de execução.
- `.centaur/obsidian/` é leitura do usuário: capacidades, jornadas, conceitos, decisões e possibilidades em linguagem humana.

Exponha specs no quadro por status, incluindo concluídas e pendentes. Mantenha apenas resumos e links de origem no vault; as instruções e checklists técnicos permanecem nos READMEs canônicos.

## Escopos e equipe

Leia o [contrato de módulos e equipe](references/team-workspace.md) antes de localizar registros ou sincronizar o quadro. Ele define caminhos, IDs qualificados, responsáveis e estados, incluindo compatibilidade com projetos legados.

## Vault local e Claudian

O vault do projeto é sempre `.centaur/obsidian/`. Se ele não existir, crie-o antes de registrar um draft, fluxo, perspectiva ou decisão, com as pastas abaixo e o arquivo `.obsidian/app.json` mínimo. Não use um vault externo como fonte de verdade e não grave fora de `.centaur/obsidian/`.

O [Claudian](https://github.com/YishenTu/claudian) executa Codex diretamente no vault. Para usá-lo, abra `.centaur/obsidian/` como vault no Obsidian, selecione Codex no painel Claudian e use `@` para anexar a nota ou pasta relevante. Copie esta skill para `.centaur/obsidian/.agents/skills/centaur-driven-obsidian/` quando o vault for criado, para que o Claudian a descubra no escopo do vault.

## Estrutura de notas

- `Sistema/Mapa do sistema.canvas`: porta de entrada visual para as áreas do vault; organiza a navegação, sem tentar representar todo o código.
- `Sistema/Visão geral.md`: porta de entrada textual com propósito, estado, atores, capacidades, limites e links para as demais leituras.
- `Sistema/Quadro de specs.canvas`: quadro com colunas de status e cards de todas as specs mestre e dos módulos.
- `Sistema/Quadro de specs.md`: resumo navegável do mesmo quadro.
- `Sistema/Glossário.md`: vocabulário do domínio explicado para o usuário.
- `Sistema/Fluxos/<slug>.md`: um fluxo em linguagem humana, com Mermaid e links entre conceitos.
- `Sistema/Drafts/<slug>.md`: única entrada criada manualmente pelo usuário. Registra objetivo, hipótese e resultado esperado; um Canvas irmão pode ser adicionado pelo Centaur.
- `Sistema/Perspectivas/<id>.canvas`: leitura visual do sistema existente ou planejado, em linguagem humana; cada Canvas tem uma nota irmã explicativa.
- `Sistema/Decisões/`: decisões confirmadas e seus motivos.

## Criar ou inicializar vault

Execute o inicializador idempotente antes de usar o vault:

```bash
python3 <pasta-da-skill>/scripts/init_vault.py <raiz-do-projeto> --skill-source <pasta-da-skill>
```

Ele cria, quando faltar, `.centaur/obsidian/.obsidian/app.json`, `Sistema/Mapa do sistema.canvas`, `Sistema/Visão geral.md`, `Sistema/Glossário.md`, as pastas Drafts, Fluxos, Perspectivas e Decisões e a cópia completa da skill em `.agents/skills/`. As notas iniciais declaram explicitamente o que ainda está a definir; não invente conteúdo do sistema. Preserve notas humanas existentes; o quadro gerado é atualizado e vinculado ao mapa a cada execução. O inicializador não cria `.centaur/specs/` nem `Sistema/Specs/`.

## Atualizar a partir do código

Use `sincronizar` após abrir ou alterar um projeto. Leia `AGENTS.md`, os registros técnicos relevantes e apenas o código necessário para confirmar responsabilidades e fluxos. Atualize Visão Geral, Glossário, Fluxos, Decisões e Perspectivas afetados com linguagem humana. Detalhes de arquivos, símbolos e testes, quando necessários para sustentar uma afirmação, ficam em uma seção final `Evidências`, nunca na narrativa principal nem em cards do Canvas. Não apague uma afirmação sem confirmar que o código a contradiz ou que foi superada.

## Criar perspectivas

Use `perspectiva <objetivo>` para criar ou atualizar um Canvas em `Sistema/Perspectivas/`, por exemplo jornada do usuário, ciclo de um dado, segurança, publicação ou limites de contexto. Leia [o formato Canvas](references/canvas.md) antes de escrever. Cada perspectiva deve responder uma pergunta, ter título e nota irmã, usar conceitos e setas em linguagem humana e marcar claramente conteúdo planejado. Reutilize conceitos entre perspectivas por wikilinks, não por cards técnicos duplicados. Atualize o Mapa do sistema apenas quando uma nova perspectiva se tornar uma entrada importante de navegação.

## Draft criado pelo usuário e promoção

Aceite criação manual somente em `Sistema/Drafts/<slug>.md`; ignore `_modelo.md` e não use arquivos fora dessa pasta como Draft. Leia [o ciclo de promoção](references/draft-lifecycle.md) antes de refinar.

No modo `refinar <slug>`, preserve o arquivo original, liste hipóteses, compare com `AGENTS.md` e código no escopo necessário e faça todas as perguntas que alterem comportamento, limites, dados ou responsabilidade. Não gere spec nem código enquanto houver ambiguidade material.

Após o usuário aprovar, use `promover <slug>`: marque o Draft como promovido, escreva ou atualize Fluxo, Decisões, Visão Geral e uma Perspectiva quando ela ajudar a compreensão. Em seguida, crie a spec usando `/centaur-driven-spec`; a própria spec registra as notas humanas que lhe deram origem. Não crie uma nota espelho no vault. Use `implementar <escopo>/<id>` somente quando a spec estiver confirmada; ele delega para `/centaur-driven-run <escopo>/<id>`, que preserva TDD ou modo direto de cada task.

## Sincronizar implementação

Depois de uma implementação validada, atualize somente a leitura humana afetada: comportamento estabelecido, decisão relevante, estado confirmado e evidência discreta. Após consolidar os registros técnicos, regenere o quadro para mostrar o status e o progresso das specs; não replique instruções de tasks. Em execução paralela, o executor apenas relata as notas afetadas; o orquestrador escreve no vault serialmente ao fim da onda. Falha de documentação não invalida código já validado, mas deve ser reportada como pendência.

## Entrega

Informe as notas e Canvases alterados, o que foi confirmado versus hipótese e a validação real. O vault local é a origem da documentação humana; não dependa de MCP.

## Sincronizar quadro de specs

Execute após inicializar o vault e após cada mudança de estado canônico:

```bash
python3 <pasta-da-skill>/scripts/sync_board.py <raiz-do-projeto>
```

O script lê `.centaur/workspace.json` (ou usa master legado), os READMEs de specs e gera `Sistema/Quadro de specs.canvas` e `.md`, conectando o quadro ao mapa existente. Não requer plugin Kanban. Esses dois arquivos são projeções geradas: alterações de status devem ser feitas nos registros canônicos e então sincronizadas. Arrastar cards só altera a apresentação até a próxima sincronização. Cards incluem escopo, responsável, relação mestre/filhas, dependências e progresso; status desconhecido fica visível em `A verificar`. Links externos ao vault usam URI de arquivo e exigem acesso local ao projeto.
