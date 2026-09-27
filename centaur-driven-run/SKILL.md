---
name: centaur-driven-run
description: Coordena entregas de specs dentro de contratos aprovados, com execução adaptativa, evidências, integração e próximos passos; funciona com um ou vários agentes e modelos.
version: 4.0.0
invocable: true
author: user
metadata:
  dependencies: clean-code, graphify
  optional-dependencies: ai-memory
---

# centaur-driven-run

## Ciclo por contratos — obrigatório

Leia o [ciclo por contratos e evidências](../centaur-driven-graphify/references/lifecycle.md) antes de planejar, executar ou declarar progresso. Ele é a fonte única de estados, aprovação, autonomia, rastreabilidade, gates e próximos passos. Contratos versionados definem o molde; specs planejam entregas; estado e evidências comprovam a realização. Preserve o histórico legado e nunca converta checklist em prova de comportamento.

## Memória de implementações

Leia o [contrato de memória](../centaur-driven-memory/references/contract.md) junto do contexto. O backend em `.centaur/workspace.json` determina o destino dos registros: `files` mantém os READMEs legados; `ai-memory` usa páginas verificadas e dispensa novas pastas `implements/`. As etapas de reserva numérica e escrita em `implements/status.md` abaixo são exclusivas de `files`; no modo ai-memory, aplique o registro, a fila e a consolidação definidos no contrato. Preserve specs e histórico existente.

## Contexto persistente — Graphify

Antes de explorar o projeto, siga o [contrato de contexto](../centaur-driven-graphify/references/context.md). Graphify (CLI `graphify` do pacote `graphifyy` + skill oficial `graphify`) é dependência obrigatória para localizar relações no código. Para histórico e decisões, consulte ai-memory quando configurado. Consulte o grafo antes de ampliar leituras; confirme as fontes relevantes. Aplique os limites de escrita e a sincronização definidos no contrato.

## Escopos e equipe

Antes do fluxo, leia o [contrato de módulos e equipe](../centaur-driven-graphify/references/team-workspace.md). Ele define resolução de caminhos, IDs qualificados, responsabilidade, concorrência e estados. Os exemplos legados abaixo usam o escopo selecionado; aplique o contrato também aos comandos e templates.

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Verifique a disponibilidade da dependência antes de iniciar as ondas. Cada subagente deve carregá-la na própria sessão; não presuma que herdou sua leitura. Preserve o objetivo, os critérios e o modo da task. Adaptações técnicas dentro da autonomia devem ser registradas; o coordenador só executa diretamente no modo de agente único, pela skill adequada.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

Você coordena entregas verificáveis de uma spec existente. Execute com um agente ou vários conforme as ferramentas, risco e orçamento; mantenha responsabilidade explícita e um único escritor dos registros compartilhados.

## Passo 1 — Retomar pelo estado real

Resolver ID qualificado, ler spec, contrato fixado e versão vigente, estado, evidências e registros anteriores. Adquirir a reserva da spec pelo contrato de equipe. Ausência de spec pede seleção das pendentes. Spec legada continua utilizável; antes de novas afirmações de comportamento validado, vincular contrato conforme a migração normativa, preservando o histórico.

Se a spec referencia versão superada, comparar mudanças e replanejar com rastreabilidade antes de executar; não substituir o contrato silenciosamente. Não reexecutar código validado por falta de memória, documento ou grafo: resolver só a pendência. Checklist não substitui verificação de estado nem integração.

## Passo 2 — Delimitar autonomia e a próxima entrega

Confirmar contrato aprovado, lacunas materiais resolvidas e dependências necessárias integradas no checkout. Rodar `validate-lifecycle.py`; corrigir referências ausentes/ciclos antes das tasks afetadas. Apresentar comportamento da entrega, impacto previsto, verificações e eventuais decisões humanas. Autorização já presente permite prosseguir sem confirmação repetida.

Replanejar detalhes técnicos dentro dos limites delegados, registrando motivo e diff do plano; não alterar critérios de aceite ou limites. Pedido adicional dentro do contrato pode virar nova task documentada; fora dele, preparar proposta de contrato pela spec e pedir somente a decisão material ainda não autorizada. Não responder a toda descoberta com recusa ou recomeço.

## Passo 3 — Executar com isolamento proporcional

Agrupar tasks por dependências e interferência em arquivos/contratos compartilhados. Usar branches/worktrees se necessário. Selecionar skill por modo TDD/direto e executor/modelo por capacidade, risco, incerteza e orçamento disponível. Não exigir ferramenta `Agent`, nome comercial ou paralelismo. Sem subagentes, executar sequencialmente pela skill adequada e separar execução/consolidação.

Cada executor recebe: spec/task, contrato/versão/regras, objetivo observável, fontes atuais, limites/autonomia, posse de arquivos, dependências integradas, modo, critérios de aceite e destino do registro. Carregar clean-code/graphify na própria sessão quando aplicáveis. Preservar o sentido das instruções; registrar adaptações técnicas autorizadas. Nunca relaxar o contrato para acomodar resultado.

Executores não alteram contrato aprovado, spec, índices, estado consolidado ou grafo compartilhado. Escrevem só arquivos sob sua responsabilidade e registros/evidências individuais com IDs únicos. Reportam deltas para o coordenador. Sem canal direto com usuário, ambiguidade que mude contrato volta como bloqueio com alternativas e consequências.

## Passo 4 — Consolidar cada entrega/onda

1. Conferir diff, fontes e resultados reais; relatório de executor isolado não é prova. Falha sem relatório exige inspecionar trabalho preservado antes de qualquer tentativa nova.
2. Registrar decisões técnicas e comparar impacto previsto/real. Desvio de limite bloqueia a parte afetada; manter trabalho independente.
3. Consolidar memória conforme backend (`files`: README/índice; ai-memory: publicar fila serialmente e verificar). Memória pendente é separada do estado do código.
4. Atualizar `.centaur/state/<id>.json`, vincular evidências individuais correntes e preservar histórico. Regra só recebe implementada se fontes atuais sustentarem; verificação é derivada por hashes e resultados. Não inferir entrega de um teste verde.
5. Atualizar tasks e índice da spec. Marcar task executada não conclui automaticamente a capacidade. Em falta de validação/integração, usar Em revisão; bloqueio registra causa, dependências e decisão necessária.
6. Rodar validação de registros e regenerar Volante. Sincronizar Graphify serialmente, incluindo contratos, estado e evidências, excluindo HTML gerado e filas. Falha em índice/visor deve aparecer separadamente, sem reexecutar código pronto.

## Passo 5 — Demonstrar e integrar

Apresentar antes/depois, critérios atendidos, evidências, limitações, decisões autônomas e desvios. Para cada regra da entrega, executar `validate-lifecycle.py <raiz> --ready <contrato/REGRA>` e os gates reais do projeto no candidato integrado. Evidência inválida ou desatualizada impede declarar pronta para integração.

Integrar apenas conforme autorização existente; quando não houver, preparar candidato revisável e apresentar a ação concreta. Registrar `delivery.stage: integrated` só depois de confirmar revisão e destino; incluir referência/data. Publicação permanece separada e depende do pedido, nunca da conclusão automática das tasks. Não disparar deploy como consequência de atualizar estado.

## Passo 6 — Encerrar e apontar o próximo passo

`Concluída` exige todas as tasks e dependências entregues, critérios do contrato verificados e integração confirmada, inclusive specs filhas. Publicação só é requisito se estiver no aceite. Caso contrário usar Em revisão/Bloqueada/Em andamento conforme o ciclo; nunca concluir pela última checkbox.

Regenerar Volante após o estado final e liberar somente a reserva da sessão. Entregar resumo por comportamento: implementação, verificação, entrega, decisões que faltam, próximo passo executável e links para fontes/evidências. Informar limitações de memória/grafo/visor separadamente. Selecionar próxima lacuna pelo ciclo normativo, sem criar tarefas especulativas.
