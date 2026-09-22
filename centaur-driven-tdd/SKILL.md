---
name: centaur-driven-tdd
description: Implementa uma mudança guiada por testes (red-green-refactor), com ciclos mínimos, reaproveitamento e manutenção dos testes existentes e registro no backend de memória configurado. Use quando a mudança tem regra de negócio testável.
version: 1.11.0
invocable: true
author: user
metadata:
  dependencies: clean-code, graphify
  optional-dependencies: ai-memory
---

# centaur-driven-tdd

## Memória de implementações

Leia o [contrato de memória](../centaur-driven-memory/references/contract.md) junto do contexto. O backend em `.centaur/workspace.json` determina o destino dos registros: `files` mantém os READMEs legados; `ai-memory` usa páginas verificadas e dispensa novas pastas `implements/`. As etapas de reserva numérica e escrita em `implements/status.md` abaixo são exclusivas de `files`; no modo ai-memory, aplique o registro, a fila e a consolidação definidos no contrato. Preserve specs e histórico existente.

## Contexto persistente — Graphify

Antes de explorar o projeto, siga o [contrato de contexto](../centaur-driven-graphify/references/context.md). Graphify (CLI `graphify` do pacote `graphifyy` + skill oficial `graphify`) é dependência obrigatória para localizar relações no código. Para histórico e decisões, consulte ai-memory quando configurado. Consulte o grafo antes de ampliar leituras; confirme as fontes relevantes. Aplique os limites de escrita e a sincronização definidos no contrato.

## Escopos e equipe

Antes do fluxo, leia o [contrato de módulos e equipe](../centaur-driven-graphify/references/team-workspace.md). Ele define resolução de caminhos, IDs qualificados, responsabilidade, concorrência e estados. Os exemplos legados abaixo usam o escopo selecionado; aplique o contrato também aos comandos e templates.

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Leia também `references/session-protocol.md` e `references/tests.md` da dependência. Aplique os critérios de responsabilidade, localização e dependências no GREEN e de clareza no REFACTOR. Preserve RED → GREEN → REFACTOR e a proporcionalidade dos critérios de aceite desta skill.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

## Princípio

Comece pela menor lacuna de comportamento e mantenha a suíte coerente com o contrato atual. Preserve o ciclo RED → GREEN → REFACTOR. Quantidade de testes e percentual de cobertura não são critérios de sucesso por si só.

A referência de processo é o [TDD do Superpowers](https://github.com/obra/superpowers/blob/main/skills/test-driven-development/SKILL.md). O Centaur adapta o dimensionamento à solicitação: reaproveita proteção existente e revisa testes afetados quando o contrato muda, em vez de acumular casos a cada entrega. Superpowers é referência, não uma dependência a instalar ou carregar.

**Escopo:** mudanças pontuais com regra de negócio, validação com consequência, cálculo ou correção de bug. Demandas grandes seguem `spec` + `run`. Mudanças estruturais, UI/estilo, configuração e fiação trivial seguem `implement`. Não crie infraestrutura de testes sem que o pedido a autorize.

## Regras do ciclo

- Comportamento novo ou alterado precisa de uma evidência RED antes da mudança de produção. Um teste existente que reproduz o problema pode cumprir esse papel; não precisa de uma cópia nova.
- Uma refatoração que preserva comportamento usa os testes existentes antes e depois. Não quebre código só para fabricar RED, nem apague trabalho existente porque não nasceu por TDD.
- Cada novo caso deve proteger uma falha concreta que ainda não esteja adequadamente coberta. Explique qual falha ele detecta; não crie teste por método, arquivo, camada ou item de checklist.
- Teste o contrato observado pelo consumidor. Uma mudança interna que preserva esse contrato não deveria obrigar reescrever a suíte.
- Falha de teste exige diagnóstico. Mudar a expectativa é correto quando o requisito mudou; afrouxá-la para esconder um defeito não é.
- Reporte somente execuções e resultados observados. Não declare suíte verde a partir de um teste isolado.

## Passo 1 — Recuperar contexto e identificar modo spec

Leia `AGENTS.md` e siga os contratos de contexto, memória e equipe. Consulte só o histórico e as fontes pertinentes. Se faltar contexto indispensável, informe a lacuna; sem projeto documentado, indique `centaur-driven-start-project`.

Se a solicitação começar com `Spec <escopo/id> — Task NN` ou referenciar uma task, leia a spec inteira e preserve seus critérios. Não edite spec, checklist ou índices compartilhados. O coordenador recebe o resultado e consolida. Não interprete critérios como uma quantidade obrigatória de testes novos.

No backend `files`, crie o índice de implementações apenas se necessário. No backend ai-memory, use o destino atribuído e a fila do contrato, sem criar `implements/`.

## Passo 2 — Conhecer a suíte atual

Identifique framework, comando para teste/arquivo individual, suíte do projeto e gates obrigatórios nos manifestos e na configuração de CI. Cobertura só precisa de comando próprio quando for exigida pelo projeto ou útil para investigar uma lacuna específica.

Leia os testes dos comportamentos afetados e suas fixtures. Execute a seleção relevante antes de editar, para conhecer a situação inicial. Não introduza um segundo padrão de testes.

Sem infraestrutura, use `implement` quando o pedido não incluir configurá-la. Em modo spec, se a task exigir TDD mas não permitir criar a infraestrutura, reporte bloqueio pelo Passo 5.

## Passo 3 — Delimitar a mudança observável

Descreva o que passa a valer e o que deve continuar funcionando. Compare os critérios de aceite com os testes encontrados: já coberto, precisa atualizar, lacuna real. Critério de aceite não equivale a teste novo.

Comece por um exemplo representativo da mudança ou pela reprodução do bug. Acrescente casos apenas quando distinguirem outra decisão da regra, um limite relevante ou um risco concreto ainda desprotegido. Dinheiro, autorização e integridade exigem atenção aos modos de falha reais, não uma combinação automática de todo vazio/nulo/erro/borda possível.

Escolha o nível mais próximo da regra que dê confiança suficiente. Teste de integração cabe quando o defeito depende da ligação entre componentes. Não repita a mesma regra em unitário, integração e ponta a ponta sem um risco diferente em cada nível. Parametrize entradas que exercitem a mesma regra quando isso melhorar a leitura; parametrização não justifica uma matriz enorme.

## Passo 4 — Revisar os testes afetados

Antes de adicionar, decida o destino dos casos existentes:

| Situação comprovada | Ação |
|---|---|
| A regra continua válida e o teste a protege | Preserve; uma falha após a edição é candidata a regressão. |
| A solicitação altera a regra | Atualize nome, dados e expectativa para o novo contrato; execute contra a implementação anterior para obter RED. Preserve verificações dos comportamentos que não mudaram. |
| Dois casos protegem a mesma falha nas mesmas condições | Consolide se nenhum risco distinto for perdido. |
| O teste depende de detalhes internos | Reescreva pela interface/efeito observável, conservando a proteção da regra. |
| A funcionalidade foi removida pelo pedido | Remova o caso sem objeto; acrescente proteção para a ausência somente se ela fizer parte do novo contrato. |
| O motivo da falha é incerto ou intermitente | Investigue; não use skip, delete ou atualização de snapshot como solução. |

Idade do teste e incompatibilidade com o código atual não provam obsolescência. A evidência vem do requisito aprovado e do contrato. Se o teste antigo revela compatibilidade que deve continuar, mantenha essa proteção. Faça essa manutenção apenas na área afetada e registre o motivo das remoções/substituições; não abra uma limpeza geral da suíte.

## Passo 5 — Resolver lacunas reais

Pergunte apenas quando a resposta mudar o contrato e não estiver no pedido, nas fontes ou na spec. Se o trabalho já estiver autorizado e não houver ambiguidade, informe o primeiro comportamento e prossiga. Não peça aprovação de uma bateria de testes pré-definida.

**Modo spec:** preserve os critérios e o escopo planejados; escolha a organização dos testes sem mudar requisitos. Se houver conflito entre spec, contrato vigente e código que impeça a implementação, reporte bloqueio e o que destrava. Em ai-memory, grave o registro na fila individual; em `files`, reserve o ID pelo Passo 12 e salve README mínimo com data, status Bloqueado, spec/task e motivo. Não altere a spec nem seus índices e não publique diretamente na wiki.

## Passo 6 — Escolher o próximo ciclo

Escolha a menor lacuna ainda aberta, respeitando as dependências reais da mudança. Não gere ciclos por camada nem escreva uma bateria inteira antes de começar. Um ciclo pode atualizar um teste existente. Se tudo já estiver protegido e o comportamento correto, não invente produção nem teste novo: valide e reporte o que encontrou.

## Passo 7 — RED observado

Releia os trechos exatos que vai tocar. Escreva ou atualize o teste do comportamento escolhido e rode a seleção mínima que o executa. Confirme uma falha causada pela diferença entre o contrato desejado e o código atual. Corrija erros acidentais de sintaxe, importação e setup antes de contar a falha como RED. Ausência da API que a mudança deve criar pode ser a falha esperada, desde que identificada como tal.

Se já passar, investigue: pode ser comportamento existente, duplicação ou uma asserção sem poder de detectar a falha. Não altere a expectativa apenas para forçar vermelho. Preserve um teste de caracterização útil quando necessário, mas não o apresente como prova RED de uma mudança já implementada.

## Passo 8 — GREEN mínimo

Implemente só o necessário para satisfazer a lacuna atual, respeitando os limites arquiteturais e convenções do projeto. Rode o caso e os testes diretamente afetados. Se algum teste falhar, use a classificação do Passo 4 para distinguir regressão de mudança intencional; não ajuste expectativas em massa ao resultado produzido.

## Passo 9 — REFACTOR com manutenção da suíte

Com os testes relevantes verdes, simplifique código e testes tocados. Use nomes do domínio, responsabilidades claras e helpers pequenos quando eliminarem repetição real. Reexecute os testes afetados após a refatoração. Se houver regressão, corrija ou desfaça apenas a própria edição responsável, preservando trabalho anterior.

Revise a utilidade dos testes com a [referência de qualidade do Superpowers](https://github.com/obra/superpowers/blob/main/skills/test-driven-development/writing-good-tests.md):

- Verifique resultados e efeitos reais. Isole dependências externas ou não determinísticas quando necessário; não substitua por mock a própria regra em teste.
- Derive valores esperados independentemente da implementação. Não use o mesmo cálculo/helper nos dois lados da asserção.
- Chamadas e argumentos só são asserções úteis quando expressam um contrato de integração, não a organização privada do código.
- Evite snapshots amplos, comparações de texto-fonte e testes de constantes sem efeito observável. Texto exato é válido quando o próprio texto é requisito.
- Várias asserções podem demonstrar um único resultado; não divida cada campo em um teste novo. Não teste o funcionamento interno do framework.

Consolide redundâncias e atualize fixtures afetadas. Não remova uma regressão protegida apenas para diminuir a contagem. Não imponha abstrações, meta de quantidade ou limite arbitrário de duração por teste.

## Passo 10 — Avaliar se falta outro ciclo

Compare o resultado aos critérios e riscos identificados. Prossiga somente se houver comportamento exigido ainda sem proteção suficiente. Pare quando a mudança estiver validada pelos testes mantidos, atualizados ou novos. Não complete listas genéricas nem persiga percentual de cobertura.

## Passo 11 — Verificar a entrega

1. Execute a suíte do projeto e os gates exigidos antes de concluir. Em monorepo, use o escopo de validação documentado e inclua consumidores afetados por contratos compartilhados. O ciclo rápido usa seleção focada; a entrega exige a verificação mais ampla prevista pelo projeto.
2. Execute lint/type-check e build quando exigidos ou pertinentes à mudança. Reporte comandos, resultados e limitações reais. Se uma suíte não puder rodar, declare o que ficou sem verificar; falhas preexistentes também aparecem no relatório, separadas das regressões causadas pela mudança.
3. Revise o diff dos testes: a regra antiga deixou de ser exigida? As remoções perderam algum cenário ainda válido? Fixtures e snapshots representam o contrato atual? Não aprove atualizações em massa sem examinar essas diferenças.
4. Use cobertura como pista de uma lacuna, quando necessário, ou como gate se o projeto já exigir. Não estabeleça 100% de branches, meta nova ou teste extra só para subir a métrica. Respeite gates existentes sem reduzi-los para obter verde.
5. Confirme que a implementação e os testes não extrapolaram o pedido. Documente falhas ou bloqueios sem apresentar entrega validada quando os checks necessários não passaram.

## Passo 12 — Determinar número da implementação

**Backend ai-memory:** use o UUID e o caminho do contrato de memória, sem reservar pasta. O template do próximo passo fornece o corpo da página/fila. Pule a etapa de `status.md` e informe a referência da página no lugar do número. Em modo spec, grave a fila e reporte ao coordenador; inclusive em bloqueios, não crie README local nem publique diretamente.

**Backend files:** siga a reserva abaixo.

<!-- Mantenha este passo sincronizado com centaur-driven-implement (Passo 9) e centaur-driven-deploy (Passo 16) -->
Execute exatamente este comando para encontrar o último número:

```
ls .centaur/implements/ | grep -E '^[0-9]{4}$' | sort | tail -1
```

- Se retornar um número (ex: `0003`), o próximo é esse + 1 (ex: `0004`)
- Se retornar vazio, começa em `0001`
- Formate sempre com 4 dígitos: `0001`, `0002`, `0042`, `0100`

**Reserve o número imediatamente** criando a pasta com `mkdir .centaur/implements/XXXX` (sem `-p`). Se falhar porque a pasta já existe — acontece quando outra task roda em paralelo via `/centaur-driven-run` —, incremente e tente de novo. O número só é seu depois que o `mkdir` tiver sucesso.

## Passo 13 — Documentar a implementação

Obtenha a data de hoje com `date +%F` — não a preencha de memória.

Este README é a trilha de auditoria, **não** o lugar onde o código é explicado. O que cabe no código deve estar claro no código; aqui fica só o que não cabe num arquivo de código.

Em `files`, crie `.centaur/implements/XXXX/README.md`. Em `ai-memory`, use este conteúdo no registro do contrato, com o ID atribuído:

```markdown
# [XXXX] [Título curto e descritivo da implementação]

**Data:** [saída de `date +%F`]
**Status:** [Concluído ou Bloqueado, conforme validação]
**Modo:** TDD
**Spec:** [se veio de uma spec: `.centaur/specs/YYYY/` — Task NN. Caso contrário, omita esta linha]

## Solicitação
[O que o usuário pediu, com as palavras dele]

## Contexto
[Por que essa mudança era necessária, qual problema resolve]

## Critérios de aceite
[A lista de comportamentos observáveis derivada no Passo 3]

## Ciclos TDD
| Comportamento | Teste novo ou atualizado | RED observado | GREEN observado |
|---|---|---|---|
| [regra alterada] | `caminho/do/teste.ext` | [comando e falha esperada] | [comando e resultado] |

## Manutenção dos testes
[Testes reaproveitados, atualizados, consolidados ou removidos e por quê; indique a proteção preservada. Omita esta seção se nada disso se aplicar.]

## O que foi feito
[Descrição objetiva das mudanças realizadas]

## Arquivos modificados
- `caminho/do/arquivo.ext` — [o que mudou]

## Arquivos criados
- `caminho/novo.ext` — [para que serve]

## Decisões técnicas
[Só o que não cabe no código: alternativas descartadas e por quê, trade-offs de arquitetura, estratégia de mock, o que foi deixado deliberadamente sem teste. Se a justificativa cabia numa constante nomeada ou num comentário ao lado da linha, o lugar dela era lá — não aqui]

## Como validar
[Comando exato para rodar os testes desta implementação]

## Resultado da validação
[Comandos e resultados reais, incluindo suíte/gates, falhas e limitações. Cobertura somente se medida.]
```

## Passo 14 — Atualizar status.md

**[modo spec]** Pule este passo — o orquestrador escreve a linha no `status.md` com base no seu relatório final. Escritas paralelas de subagentes no mesmo arquivo se sobrescrevem.

Somente em `files`, adicione uma linha na tabela de `.centaur/implements/status.md`:

```
| XXXX | [Título] | [data] | [status real] | [lista de arquivos afetados] |
```

Se a tabela ainda contiver a linha placeholder (`| — | — | — | — | — |`), remova-a ao inserir a primeira linha real.

## Passo 15 — Atualizar AGENTS.md se necessário

Se a implementação adicionou funcionalidade relevante, mudou arquitetura, introduziu dependência importante, **estabeleceu a infraestrutura de testes do projeto** (framework, comando, convenção de nomes), ou **estabeleceu um termo novo do domínio** que o código passou a usar → atualize as instruções essenciais do `AGENTS.md` e os detalhes nas fontes vinculadas, sem duplicação. O termo novo vai para o glossário vinculado pela seção "Vocabulário e Idioma do Código"; sem glossário, use essa seção enquanto ela for curta. Correção interna sem impacto na visão geral não precisa.

## Passo 16 — Atualizar obrigatoriamente o Graphify

Após cada implementação, execute o fluxo `centaur-driven-graphify sincronizar <escopo>/<id>` nesta mesma tarefa, depois da validação e de salvar o registro no backend configurado e os documentos locais pertinentes. Não deixe a atualização como sugestão ou comando para o usuário executar depois. A obrigação também vale para correções internas, mudanças pequenas e alterações sem impacto no AGENTS.md ou no mapa humano.

Inclua código, testes e documentos alterados, inclusive os registros locais quando existirem, excluindo a fila `memory-pending/`; atualização AST isolada não basta para Markdown. Reutilize o grafo com atualização incremental quando suportada e inicialize-o se estiver ausente. Verifique os artefatos e faça uma consulta focada sobre a mudança, conferindo as fontes retornadas antes de afirmar que está sincronizado. Atualize mapas e notas somente quando afetados.

Se houver bloqueio ou validação falhar depois de mudanças, sincronize também os arquivos e registros efetivamente preservados, identificando o estado parcial/bloqueado sem descrevê-lo como comportamento validado. Sem qualquer mudança de código ou documentos, não há atualização a executar.

**[modo spec]** O executor entrega ao `run` todos os caminhos alterados e a sincronização pendente; não escreve no grafo compartilhado. O coordenador deve incluir cada implementação na atualização serial após consolidar a onda, antes de iniciar a próxima ou encerrar a execução.

Se a sincronização falhar, tente resolver a causa dentro do escopo e permissões disponíveis. Persistindo o impedimento, registre causa e arquivos pendentes em `.centaur/system/sync.md` e informe **implementação validada, sincronização pendente** (ou o resultado real da validação). Preserve o trabalho validado; não declare a entrega integralmente concluída nem o grafo atualizado.

## Passo 17 — Informar o usuário

Confirme com:
- O que foi feito (resumo de 2-3 linhas)
- Comportamentos validados e manutenção relevante dos testes existentes
- Resultado real da suíte/gates; cobertura somente quando medida e limitações explícitas
- Referência da página e estado da memória, ou número/README no backend `files`
- Graphify: atualização executada, consulta de verificação e fontes conferidas; em falha, causa e arquivos pendentes

**[modo spec]** Em ai-memory, use o relatório com `Registro` e `Fila` definido no contrato. Em `files`, encerre com o relatório abaixo, usado pelo orquestrador para consolidar a spec e o `status.md`:

```
Spec YYYY — Task NN: [Concluída | Bloqueada]
Implementação: XXXX
Título: [título usado no README da implementação]
Arquivos afetados: [código, testes e documentos alterados, incluindo o README da implementação]
Graphify: sincronização pendente pelo coordenador; [escopo e caminhos a incluir]
Validação: [evidências RED/GREEN, suíte/gates, falhas e limitações]
Testes mantidos/atualizados/removidos: [motivos e proteção preservada]
Mapa: [caminho e resultado real; se bloqueada sem implementação, não aplicável]
Perspectivas afetadas: [ids de views existentes ou nenhuma; atualização reservada ao orquestrador]
[Se bloqueada: Motivo do bloqueio e o que destrava]
```
