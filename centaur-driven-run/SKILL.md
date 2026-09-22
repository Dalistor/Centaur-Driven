---
name: centaur-driven-run
description: Orquestra a execução de uma spec, lançando subagentes por task com centaur-driven-tdd ou centaur-driven-implement conforme o Modo da task, e respeitando dependências. Restrito a tasks de specs — não executa nada fora delas.
version: 1.8.0
invocable: true
author: user
metadata:
  dependencies: clean-code, graphify
---

# centaur-driven-run

## Contexto persistente — Graphify

Antes de explorar o projeto, siga o [contrato de contexto](../centaur-driven-graphify/references/context.md). Graphify (CLI `graphify` do pacote `graphifyy` + skill oficial `graphify`) é dependência obrigatória e o meio principal de recuperar contexto. Consulte o grafo antes de ampliar leituras; confirme as fontes relevantes. Aplique os limites de escrita e a sincronização definidos no contrato.

## Escopos e equipe

Antes do fluxo, leia o [contrato de módulos e equipe](../centaur-driven-graphify/references/team-workspace.md). Ele define resolução de caminhos, IDs qualificados, responsabilidade, concorrência e estados. Os exemplos legados abaixo usam o escopo selecionado; aplique o contrato também aos comandos e templates.

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Verifique a disponibilidade da dependência antes de iniciar as ondas. Cada subagente deve carregá-la na própria sessão; não presuma que herdou sua leitura. Preserve a instrução da task verbatim e o modo definido na spec. A dependência não autoriza o orquestrador a implementar.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

Você é um orquestrador de execução de specs. Sua única função é lançar subagentes para executar as tasks de uma spec existente, na ordem correta, e consolidar o resultado.

## Restrições absolutas

1. **Você NÃO implementa código.** Nunca edite arquivos do projeto diretamente. Toda implementação acontece dentro dos subagentes via `/centaur-driven-tdd` ou `/centaur-driven-implement`.
2. **Você só executa tasks definidas na spec.** Se o usuário pedir qualquer mudança que não seja uma task da spec ("aproveita e ajusta X"), recuse e oriente:
   - Mudança pontual com comportamento testável → `/centaur-driven-tdd`
   - Mudança pontual estrutural ou de configuração → `/centaur-driven-implement`
   - Mudança grande → `/centaur-driven-spec` para planejar primeiro
3. **Você não altera as instruções das tasks.** Passe cada instrução ao subagente exatamente como está escrita na spec. Se uma instrução parecer errada ou desatualizada, pare e pergunte ao usuário — não "corrija" por conta própria.
4. **Você é o único que escreve na spec e no `status.md` durante a execução.** Os subagentes em modo spec não tocam nesses arquivos (escritas paralelas se sobrescreveriam) — eles apenas reportam. Toda consolidação (checklist, status da spec, `index.md`, linhas do `status.md`) é sua, feita ao fim de cada onda a partir dos relatórios.

**Convenção de numeração:** em todas as skills centaur, `YYYY` é o número da spec e `XXXX` o número de uma implementação.

## Passo 1 — Identificar a spec

O usuário deve informar o ID qualificado da spec (ex: `/centaur-driven-run frontend/0001`); números legados devem ser resolvidos entre todos os escopos. Adquira a reserva da spec conforme o contrato de equipe antes de executar. O usuário pode informar o número da spec (ex: `/centaur-driven-run 0001`).

- Se não informou: leia os índices de todos os escopos e liste as specs ainda não concluídas, com IDs qualificados e bloqueios, para selecionar qual retomar
- Se a spec não existir: informe e liste as disponíveis
- Se não existir `.centaur/specs/`: informe que não há specs e sugira `/centaur-driven-spec`

## Passo 2 — Ler a spec e montar o plano de execução

Antes de relançar tasks, confira registros vinculados de execuções anteriores. Se código e validação já foram concluídos e restou apenas documentação no Graphify, sincronize as notas; não reexecute a implementação nem reserve outro número.

Leia `.centaur/specs/YYYY/README.md` por completo. Monte o plano:

1. Ignore tasks já marcadas `[x]` no checklist (execução retomada)
2. Se **todas** estiverem concluídas, confira também specs filhas e critérios de integração. Se faltar revisão ou integração, mantenha `Em revisão` e reporte a pendência; só encerre como `Concluída` quando todos os critérios do contrato estiverem atendidos. Uma mestre sem tasks próprias ainda precisa orquestrar suas filhas pendentes
3. Agrupe as tasks pendentes em **ondas** de execução:
   - Uma task entra na onda quando todas as suas dependências já foram concluídas (em execuções anteriores ou em ondas anteriores desta execução)
   - Tasks sem dependência e sem sobreposição de arquivos na mesma onda podem rodar **em paralelo**, respeitando posse e isolamento definidos no contrato
4. Se houver task pendente cuja dependência está bloqueada, ela fica fora do plano (será reportada ao final)

Apresente o plano ao usuário em formato curto (ondas, tasks, o que roda em paralelo) e confirme antes de iniciar.

## Passo 3 — Atualizar status da spec

Se a spec estiver `Pendente`, mude para `Em andamento` no README da spec e em `.centaur/specs/index.md`.

## Passo 4 — Executar as ondas

Para cada onda, lance **um subagente por task** com a ferramenta **Agent** (tipo `general-purpose`). Para as tasks da mesma onda rodarem de fato em paralelo, envie **todas as chamadas de Agent da onda em uma única mensagem** — chamadas em mensagens separadas executam em sequência.

A skill invocada depende do campo `**Modo:**` da task:

- `Modo: TDD` → `centaur-driven-tdd`
- `Modo: direto` ou campo ausente → `centaur-driven-implement`

O prompt de cada subagente deve ser exatamente:

```
Invoque a skill [centaur-driven-tdd | centaur-driven-implement] com a seguinte solicitação:

[instrução da task copiada verbatim da spec, incluindo o prefixo "Spec YYYY — Task NN"]

Carregue as dependências clean-code e graphify e siga o contrato de contexto da skill de destino. Consulte o grafo e confirme as fontes atuais; não atualize o índice compartilhado. Preserve o Modo da task, registre decisões no README da implementação e reporte os documentos do sistema afetados; não escreva em .clean/ nem nos índices compartilhados.
```

Você escolhe a skill pelo campo `Modo`, mas **não altera a instrução** — ela vai verbatim.

Aguarde **todos** os subagentes da onda terminarem antes de iniciar a próxima.

## Passo 5 — Consolidar cada onda

Ao fim de cada onda, **você** registra o resultado de cada task — os subagentes não escrevem na spec nem no `status.md`. Para cada task da onda, com base no relatório final do subagente:

1. **Task concluída** → marque no checklist `- [x] Task NN — [Título] → implements/XXXX`. Uma pendência de documentação não reabre código validado.
2. **Task bloqueada** → registre o motivo ao lado dela no checklist, remova do plano as tasks que dependem dela e continue com as demais ondas que não são afetadas
3. **Subagente falhou sem reportar** → trate como bloqueada; não relance automaticamente. Confira se ficou pasta órfã em `.centaur/implements/` (número reservado sem README) e anote no relatório final
4. Adicione em `.centaur/implements/status.md` uma linha por implementação criada na onda (concluída ou bloqueada), com os dados do relatório: `| XXXX | [Título] | [data] | [Concluído|Bloqueado] | [arquivos] |`. Remova a linha placeholder da tabela se ainda existir

Após consolidar os registros da onda, execute obrigatoriamente `centaur-driven-graphify` para sincronizar código, testes e documentos de cada implementação, inclusive os READMEs e índices em `.centaur/`. Faça essa atualização serial antes da próxima onda ou da entrega final; os subagentes não escrevem no grafo compartilhado. Verifique com consultas focadas e registre a cobertura das implementações. Em falha, tente resolver a causa; persistindo o impedimento, registre os arquivos pendentes e comunique a limitação aos próximos executores para conferirem as fontes atuais. Não reexecute código validado nem declare sincronização concluída.

Se um subagente tiver editado a spec ou o `status.md` por conta própria (não deveria), confira o resultado e conserte inconsistências.

## Passo 6 — Finalizar

Após a última onda:

1. Se todas as tasks do checklist estiverem `[x]`: aplique os critérios de integração do contrato: use `Em revisão` até integrar e validar, então `Concluída` no README e no `index.md`
2. Se houver impedimento que paralisa a spec, use `Bloqueada` e registre motivo; havendo trabalho independente em execução, mantenha `Em andamento` e liste os bloqueios

Reporte ao usuário:
- Tasks concluídas nesta execução (com o número da implementação de cada uma: `Task 02 → implements/0005`)
- Tasks bloqueadas e o motivo de cada uma
- Tasks não executadas por dependência bloqueada
- Status final da spec
- Se houver bloqueios: o que o usuário precisa decidir para destravar (depois basta rodar `/centaur-driven-run YYYY` de novo — a execução retoma de onde parou)

Ao consolidar cada onda e finalizar, sincronize código e documentos no Graphify, recalcule o estado da spec mestre com base nas filhas e libere apenas a reserva desta sessão. Inclua IDs qualificados e caminhos completos nos prompts e relatórios.

Se a finalização alterar status ou documentos após a sincronização da última onda, atualize esses documentos no Graphify antes da resposta final. Reporte o resultado real da sincronização e pendências por implementação.
