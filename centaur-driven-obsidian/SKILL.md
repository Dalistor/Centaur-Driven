---
name: centaur-driven-obsidian
description: Cria e mantém o vault local `.centaur/obsidian` com drafts, fluxos, decisões e referências de specs; use com o Claudian para planejar e documentar sistemas.
metadata:
  version: 1.1.0
  invocable: true
---

# centaur-driven-obsidian

O Obsidian é a fonte humana do sistema. As notas descrevem intenções, decisões e fluxos; o código e os resultados de validação continuam sendo a evidência para afirmar o que existe. Nunca crie uma nota que apresente uma hipótese como implementação concluída.

## Vault local e Claudian

O vault do projeto é sempre `.centaur/obsidian/`. Se ele não existir, crie-o antes de registrar um draft, fluxo, decisão ou spec, com as pastas abaixo e o arquivo `.obsidian/app.json` mínimo. Não use um vault externo como fonte de verdade e não grave fora de `.centaur/obsidian/`.

O [Claudian](https://github.com/YishenTu/claudian) executa Codex diretamente no vault. Para usá-lo, abra `.centaur/obsidian/` como vault no Obsidian, selecione Codex no painel Claudian e use `@` para anexar a nota ou pasta relevante. Copie esta skill para `.centaur/obsidian/.agents/skills/centaur-driven-obsidian/` quando o vault for criado, para que o Claudian a descubra no escopo do vault.

## Estrutura de notas

- `Sistema/Visão geral.md`: propósito, limites, capacidades e links para fluxos.
- `Sistema/Fluxos/<slug>.md`: um fluxo em linguagem humana, com Mermaid e links entre conceitos.
- `Sistema/Drafts/<slug>.md`: única entrada criada manualmente pelo usuário. Registra objetivo, hipótese e resultado esperado; um Canvas irmão pode ser adicionado pelo Centaur.
- `Sistema/Perspectivas/<id>.canvas`: leitura visual do sistema existente ou planejado, em linguagem humana; cada Canvas tem uma nota irmã explicativa.
- `Sistema/Decisões/`: decisões confirmadas e seus motivos.
- `Sistema/Specs/`: notas de referência das specs, com link para `.centaur/specs/YYYY/README.md`; o README continua sendo o plano executável.

## Criar ou inicializar vault

Execute o inicializador idempotente antes de usar o vault:

```bash
python3 <pasta-da-skill>/scripts/init_vault.py <raiz-do-projeto> --skill-source <pasta-da-skill>
```

Ele cria, quando faltar, `.centaur/obsidian/.obsidian/app.json`, `Sistema/Visão geral.md`, `Sistema/Drafts/`, `Sistema/Fluxos/`, `Sistema/Perspectivas/`, `Sistema/Decisões/`, `Sistema/Specs/` e a cópia completa da skill em `.agents/skills/`. As notas iniciais declaram explicitamente que propósito e capacidades ainda estão a definir; não invente conteúdo do sistema. Preserve qualquer nota existente.

## Atualizar a partir do código

Use `sincronizar` após abrir ou alterar um projeto. Leia `AGENTS.md`, os READMEs de implementação, a spec relevante e apenas o código necessário para confirmar responsabilidades e fluxos. Atualize `Sistema/Visão geral.md`, Fluxos, Decisões e Perspectivas afetados com linguagem humana. Arquivos, símbolos e testes entram apenas como evidência na nota; nunca como cards do Canvas. Não apague uma afirmação sem confirmar que o código a contradiz ou que foi superada por uma implementação posterior.

## Criar perspectivas

Use `perspectiva <objetivo>` para criar ou atualizar um Canvas em `Sistema/Perspectivas/`, por exemplo jornada do usuário, dados, segurança, publicação ou limites de contexto. Leia [o formato Canvas](references/canvas.md) antes de escrever. Cada perspectiva deve responder uma pergunta, ter título e nota irmã, usar conceitos e setas em linguagem humana e marcar claramente conteúdo planejado. Reutilize conceitos entre perspectivas por wikilinks, não por cards técnicos duplicados.

## Draft criado pelo usuário e promoção

Aceite criação manual somente em `Sistema/Drafts/<slug>.md`; ignore `_modelo.md` e não use arquivos fora dessa pasta como Draft. Leia [o ciclo de promoção](references/draft-lifecycle.md) antes de refinar.

No modo `refinar <slug>`, preserve o arquivo original, liste hipóteses, compare com `AGENTS.md` e código no escopo necessário e faça todas as perguntas que alterem comportamento, limites, dados ou responsabilidade. Não gere spec nem código enquanto houver ambiguidade material.

Após o usuário aprovar, use `promover <slug>`: marque o Draft como promovido, escreva ou atualize Fluxo, Decisões, Visão Geral e uma Perspectiva quando ela ajudar a compreensão. Em seguida, crie a spec usando `/centaur-driven-spec`, com links para as notas de origem em `Sistema/Specs/YYYY.md`. Use `implementar YYYY` somente quando a spec estiver confirmada; ele delega para `/centaur-driven-run YYYY`, que preserva TDD ou modo direto de cada task.

## Sincronizar implementação

Depois de uma implementação validada, atualize somente as notas e fluxos afetados com o comportamento estabelecido, decisão relevante, caminhos de evidência e resultado real da validação. Ao criar uma spec, registre em `Sistema/Specs/YYYY.md` o objetivo, os drafts/fluxos/decisões de origem e um link relativo ao README executável. Em execução paralela, o executor apenas relata as notas afetadas; o orquestrador escreve no vault serialmente ao fim da onda. Falha de documentação não invalida código já validado, mas deve ser reportada como pendência.

## Entrega

Informe as notas e Canvases alterados, o que foi confirmado versus hipótese, a origem de cada spec e a validação real. O vault local sempre é a origem de documentação; não dependa de MCP.
