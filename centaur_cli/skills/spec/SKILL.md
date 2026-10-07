---
name: spec
description: Define ou evolui contratos de comportamento, limites e autonomia; planeja entregas verticais pequenas com critérios de aceite, rastreabilidade e próximos passos.
metadata:
  version: 5.2.0
  dependencies: clean-code
  optional-dependencies: graphify, _internal/memory
---

# spec

## Base conceitual

Leia a [especificação do sistema](../graphify/references/specification.md). Registre requisitos funcionais e não funcionais em `rules`, e atores, casos de uso e modelo de dados em `specification` no contrato. Evite duplicar a definição; conecte regras a código, testes e evidências.

Para operações de memória, chame a [subskill interna memory](../_internal/memory/SKILL.md): leia suas instruções, informe operação e escopo e use seu contrato. Ela encapsula a dependência ai-memory; consulta permanece somente leitura e registros respeitam a posse de executor/coordenador. Não configure nem migre o backend como efeito colateral.

## Ciclo por contratos — obrigatório

Leia o [ciclo por contratos e evidências](../graphify/references/lifecycle.md) antes de planejar, executar ou declarar progresso. Ele é a fonte única de estados, aprovação, autonomia, rastreabilidade, gates e próximos passos. Contratos versionados definem o molde; specs planejam entregas; estado e evidências comprovam a realização. Preserve o histórico legado e nunca converta checklist em prova de comportamento.

## Memória de implementações

Leia o [contrato de memória](../_internal/memory/references/contract.md) junto do contexto. O backend em `.centaur/workspace.json` determina o destino dos registros: `files` mantém os READMEs legados; `ai-memory` usa páginas verificadas e dispensa novas pastas `implements/`. As etapas de reserva numérica e escrita em `implements/status.md` abaixo são exclusivas de `files`; no modo ai-memory, aplique o registro, a fila e a consolidação definidos no contrato. Preserve specs e histórico existente.

## Contexto persistente — Graphify

Antes de explorar o projeto, siga o [contrato de contexto](../graphify/references/context.md). Priorize busca textual e símbolos do editor. Graphify é opcional e sob demanda para relações amplas; consulte o índice existente apenas quando útil, confirmando as fontes atuais. Não inicialize nem sincronize o grafo como consequência de implementar ou consultar. Para histórico e decisões, consulte ai-memory quando configurado.

## Escopos e equipe

Antes do fluxo, leia o [contrato de módulos e equipe](../graphify/references/team-workspace.md). Ele define resolução de caminhos, IDs qualificados, responsabilidade, concorrência e estados. Os exemplos legados abaixo usam o escopo selecionado; aplique o contrato também aos comandos e templates.

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Leia `references/architecture.md` da dependência para decompor responsabilidades e explicitar a direção das dependências. Registre no contexto técnico da spec que cada executor deve carregar `clean-code`, confirmar as fontes atuais e usar Graphify somente quando necessário. Preserve os modos TDD/direto e planeje apenas as camadas necessárias à demanda.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

Você ajuda o humano a definir o molde e planeja a próxima entrega verificável. Não implemente código nesta skill.

## Passo 1 — Entender o sistema e a intenção

Leia AGENTS.md, workspace e os contratos pertinentes. Use busca e símbolos; consulte Graphify sob demanda e confirme fontes atuais. Separe: comportamento existente, desejo explícito, hipótese e lacuna. Leia somente o histórico necessário. Identifique o objetivo, atores, permissões, falhas relevantes, compatibilidade e limites arquiteturais. Preserve o backend e os caminhos dos escopos.

## Passo 2 — Definir ou evoluir o contrato

Use o formato e versionamento do ciclo normativo. Para uma capacidade nova, escreva `.centaur/contracts/<id>/v001.json`; para mudança em contrato aprovado, crie a próxima versão. Reutilize contratos gerais com herança fixada. Cada regra tem ID estável, descrição, aceite observável e dependências qualificadas quando necessárias.

Preencha `boundaries`, `autonomy` e `decisions` com o que importa ao produto. Apresente apenas dúvidas que alteram o comportamento, limites ou escopo e não estejam respondidas. Decisões de organização interna delegadas não exigem nova aprovação. Pedido inequívoco já autoriza as regras nele expressas; registre a referência real. Escolhas novas ainda não autorizadas ficam em rascunho. Não aprovar inferências nem completar lacunas com preferências próprias.

Quando houver duas alternativas de produto, mostrar consequência, recomendação e a decisão necessária. Uma decisão material aberta bloqueia somente o contrato afetado; separar capacidades independentes quando adequado. Não executar contrato não aprovado.

## Passo 3 — Comparar contrato e realização

Leia estado e evidências da versão vigente e confira código relevante. Identifique regras ausentes, parciais, sem prova ou desatualizadas; não reimplemente o que já está validado. Registre impacto previsto em módulos, dados, interfaces e compatibilidade. Arquivos são rastreabilidade técnica; progresso humano é comportamento demonstrável.

## Passo 4 — Planejar uma entrega vertical pequena

Escolha a menor capacidade demonstrável de ponta a ponta. Uma entrega pode atravessar domínio, persistência, API e interface, respeitando seus limites. Não decomponha obrigatoriamente por camada nem use número de arquivos como limiar de tamanho. Divida por risco, dependências e possibilidade de validação/integracão independente.

Dentro da entrega, tasks têm responsável, posse de arquivos, dependências e modo. Aplique a [política de testes nos pontos vitais](../graphify/references/testing.md): `TDD` só para falha concreta em ponto vital ainda sem proteção suficiente e infraestrutura disponível, ou requisito explícito; `direto` nos demais casos. Cada task carrega critérios observáveis, risco vital quando houver, proteção existente a reutilizar e verificação proporcional. Não planeje teste novo por requisito, arquivo, método ou camada. Tasks técnicas internas não viram marcos humanos de conclusão.

Preserve instruções essenciais, mas permita ao executor escolher detalhes dentro da autonomia. Registre mudanças de plano e impactos reais. Mudança de contrato exige nova versão/decisão, nunca alteração silenciosa do objetivo. Paralelismo é opcional e depende de interfaces, arquivos e isolamento, não só de tasks sem dependência nominal.

## Passo 5 — Salvar a spec da entrega

Crie uma spec por entrega verificável; várias specs independentes podem ficar no mesmo escopo. Reserve cada ID por mkdir atômico conforme o contrato de equipe. Para pedidos com várias entregas, registre dependências qualificadas e interferências em arquivos, sem criar uma mestre apenas para agrupar a lista. Preserve IDs legados e use escopo qualificado. Specs continuam nos diretórios configurados, distintas dos contratos vivos.

```markdown
# [YYYY] [Comportamento entregue]

**Data:** [data real]
**Status:** Pendente
**Escopo:** [escopo]
**Responsável:** [pessoa/equipe]
**Contrato:** [id@versão]
**Regras:** [IDs estáveis]
**Spec mestre:** [ID ou —]
**Specs filhas:** [IDs ou —]
**Dependências:** [IDs ou —]
**Solicitação original:** [pedido]

## Objetivo e demonstração
[Antes/depois observável e como demonstrar a entrega]

## Impacto previsto
[Módulos, dados, interfaces, compatibilidade; limites herdados]

## Autonomia e decisões
[Referências às cláusulas; decisões abertas e origem das autorizações]

## Contexto técnico
[Fontes atuais, testes existentes, decisões, dependências clean-code/graphify]

## Tasks

### Task 01 — [Objetivo interno necessário à entrega]
**Regras:** [IDs]
**Modo:** [TDD | direto]
**Responsável:** [executor ou a atribuir]
**Arquivos:** [posse prevista e limites arquiteturais]
**Depende de:** [tasks/regras ou —]
**Verificação:** [Risco vital e proteção existente/lacuna; ou inspeção, build/demonstração adequados ao aceite]
**Instrução para o executor:**
> Spec escopo/YYYY — Task 01: [Objetivo, contrato fixado, aceite, fontes, limites, autonomia e validação. Permitir decisões técnicas internas, sem mudar o comportamento. Reportar fontes, evidências e deltas; não escrever estado compartilhado, índices ou grafo.]

## Validação e integração
[Critérios da entrega, regras para --ready, checks reais, destino e autorização de integração; publicação separada]

## Diferença entre plano e resultado
[Atualizada pelo coordenador: decisões técnicas, impacto real e desvios]

## Checklist de conclusão
- [ ] Task 01 — [Título]

## Execução
$run escopo/YYYY

## Estado
O ciclo normativo define o estado. Checkboxes não concluem a spec: exigir aceite, prova corrente e integração, inclusive das filhas. Publicação só se fizer parte do aceite.
```

Criar/atualizar `specs/index.md` apenas no escopo correspondente, sob a reserva do índice definida no contrato de equipe e sem apagar histórico. Releia o índice após adquirir a reserva para preservar specs criadas por outra sessão. Demandas entre módulos podem usar mestre e filhas com IDs e critérios de integração recíprocos, sem duplicar tasks. Não criar hierarquia de specs quando uma entrega pequena em master bastar.

## Passo 6 — Validar registros e entregar direção

Rodar `validate-lifecycle.py` e corrigir estrutura inválida; rascunho legítimo não é aprovação. Documentação e evidências são consultadas diretamente pelos arquivos; Graphify é usado somente sob demanda. Entregar uma lista curta com ID, objetivo e próxima ação de cada spec criada, links para os planos e somente as decisões humanas pendentes. Não reproduzir templates, contratos ou todas as tasks na conversa. O planejamento não executa nem publica a entrega.

## Fluxo de caso de uso

Quando um fluxo em `.centaur/use-cases/<id>.json` ajuda a explicar a jornada, proponha ou revise passos e conexões a partir do contrato. Descreva o fluxo em texto no terminal. Trate geração por IA como rascunho editável; não derive uma aprovação nova nem altere critérios de aceite a partir do desenho.
