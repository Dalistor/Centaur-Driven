---
name: run
description: Coordena uma spec por execução pelo terminal, com posse explícita, execução adaptativa, evidências e integração conforme autorização.
metadata:
  version: 5.5.0
  dependencies: clean-code
  optional-dependencies: graphify, _internal/memory
---

# run

## Contratos compartilhados

As instruções do usuário e do projeto prevalecem. A tabela de [contratos compartilhados](../graphify/references/shared.md) diz qual referência abrir e quando (ciclo, contexto, memória, equipe); abra só a que o trabalho exigir. Valem sempre: contratos versionados definem o molde, specs planejam entregas e só estado e evidências comprovam a realização; preserve o histórico legado e nunca converta checklist em prova de comportamento.

### Dependência clean-code — obrigatória

Carregue `clean-code` antes de planejar ou escrever código; a [localização por agente](../graphify/references/shared.md) está nos contratos compartilhados. Se estiver ausente ou incompleta, informe a dependência faltante e não prossiga com o trabalho que depende dela.

Verifique a disponibilidade da dependência antes de iniciar as ondas. Cada subagente deve carregá-la na própria sessão; não presuma que herdou sua leitura. Preserve o objetivo, os critérios e o modo da task. Adaptações técnicas dentro da autonomia devem ser registradas; o coordenador só executa diretamente no modo de agente único, pela skill adequada.

Você coordena entregas verificáveis de uma spec por execução. A IA coordena; o Centaur fornece o protocolo. Siga a saída curta do contrato de contexto e consulte o contrato de equipe para posse, concorrência entre sessões e retomada. Execute com um agente ou vários conforme as ferramentas, risco e orçamento; mantenha responsabilidade explícita e um único escritor dos registros compartilhados.

Use `AGENTS.md` e `.centaur/` como contexto e registro; leia `.clean/` se existir, sem criá-lo nem atualizá-lo. Aplique a dependência só ao escopo pedido, sem auditoria ou limpeza geral, e reporte divergências com evidência.

## Passo 1 — Retomar pelo estado real

Resolver um único ID qualificado, por exemplo `/run master/0001`. Se houver vários IDs, pedir a escolha de uma spec antes de executar. Ler a spec escolhida e as dependências pertinentes, contrato fixado e versão vigente, estado e evidências necessários. Adquirir sua reserva pelo contrato de equipe; se outra sessão já a possui, informar a espera sem executar outra spec automaticamente. Ausência de ID pede seleção curta das pendentes para escolher uma. Dependências e specs filhas são consultadas para verificar elegibilidade e integração; sua execução ocorre em chamadas próprias. Spec legada continua utilizável; antes de novas afirmações de comportamento validado, vincular contrato conforme a migração normativa, preservando o histórico.

Se a spec referencia versão superada, comparar mudanças e replanejar com rastreabilidade antes de executar; não substituir o contrato silenciosamente. Não reexecutar código validado por falta de memória, documento ou grafo: resolver só a pendência. Checklist não substitui verificação de estado nem integração.

## Passo 2 — Delimitar autonomia e a próxima entrega

Confirmar contrato aprovado, lacunas materiais resolvidas e dependências necessárias integradas no checkout. Rodar `validate-lifecycle.py`; corrigir referências ausentes/ciclos antes das tasks afetadas. Apresentar comportamento da entrega, impacto previsto, verificações e eventuais decisões humanas. Autorização já presente permite prosseguir sem confirmação repetida.

Replanejar detalhes técnicos dentro dos limites delegados, registrando motivo e diff do plano; não alterar critérios de aceite ou limites. Pedido adicional dentro do contrato pode virar nova task documentada; fora dele, preparar proposta de contrato pela spec e pedir somente a decisão material ainda não autorizada. Não responder a toda descoberta com recusa ou recomeço.

## Passo 3 — Executar com isolamento proporcional

Agrupar as tasks da spec escolhida por dependências e interferência em arquivos/contratos compartilhados. Registrar posse e conferir tasks ativas de outras sessões antes de editar. Um bloqueio suspende apenas as tasks dependentes; continuar as independentes autorizadas dentro da mesma spec. Usar branches/worktrees se necessário. Selecionar skill por modo TDD/direto e executor por posse/capacidade. No backend OpenRouter, selecionar modelo por risco, incerteza e orçamento disponível; Codex/Claude permitem escolher modelos do mesmo backend conforme o catálogo de delegate_task. Não exigir ferramenta `Agent`, nome comercial ou paralelismo. Sem subagentes, executar sequencialmente pela skill adequada e separar execução/consolidação.

Cada executor recebe: spec/task, contrato/versão/regras, objetivo observável, fontes atuais, limites/autonomia, posse de arquivos, dependências integradas, modo, critérios de aceite, decisão de verificação e destino do registro. Aplique a [política de testes nos pontos vitais](../graphify/references/testing.md): indique o risco vital e testes existentes a reutilizar, ou verificação proporcional sem teste novo. O coordenador resolve sobreposição de proteção entre tasks; subagentes não criam baterias próprias por rotina. Carregar clean-code/graphify na própria sessão quando aplicáveis. Preservar o sentido das instruções; registrar adaptações técnicas autorizadas. Nunca relaxar o contrato para acomodar resultado.

### Subagentes e escolha de modelos no CLI Centaur

No CLI Centaur, **delegue cada task elegível com `delegate_task`**. O coordenador organiza
dependências, confere resultados e consolida a spec; não executa todas as tasks sozinho.
A ferramenta cria uma sessão independente, com histórico próprio, sem herdar o chat inteiro.
Informe `title` com o ID qualificado e `task` com o pacote completo do executor descrito acima.
Inclua expressamente os arquivos que ele pode editar, o modo TDD/direto, o aceite e a estratégia mínima de verificação. Novos testes exigem falha concreta em ponto vital ainda sem proteção suficiente; não delegue uma bateria genérica.

**Confira primeiro o backend conectado e os campos de `delegate_task`.** Com Codex ou Claude, mantenha o backend e escolha `model` dentre os valores listados pela ferramenta, conforme complexidade, risco e as descrições do catálogo: modelo rápido para tarefas simples, modelo de maior capacidade para incerteza ou risco alto. Se não houver catálogo, omita `model` para manter o principal. Não use `cost_tier` nesses backends. O Codex lê seu catálogo local; Claude oferece aliases `haiku`, `sonnet` e `opus`. O acesso depende da conta: falha de modelo deve ser relatada, sem trocar de provedor ou repetir alterações cegamente. Preserve coordenação, posse e verificação no fluxo Centaur; não crie agentes nativos fora da ferramenta de delegação.

**Somente com OpenRouter:** Use `model: openrouter/auto` por padrão. O [Auto Router](https://openrouter.ai/docs/guides/routing/routers/auto-router)
classifica o trabalho e seleciona modelos conforme o tipo de task, capacidade, suporte às
ferramentas e faixa de custo. Não escolha nomes comerciais fixos por familiaridade. Modelo
explícito é reservado a uma instrução do usuário ou da própria task.

Defina `cost_tier` conforme o trabalho: `low` para leitura/ajuste simples; `medium` para
implementação comum; `high` para investigação difícil ou maior risco; `xhigh`/`max` somente
quando a complexidade justificar e o limite configurado permitir. Essa é uma faixa de
roteamento, não um teto de gasto em dinheiro. O padrão do CLI permite até `high`;
`--max-subagent-tier` ajusta o máximo. Não aumente a faixa só porque existem créditos.

No chat Centaur, iniciar tasks independentes em segundo plano, respeitando dependências e posse.
`delegate_task` com `status=started` confirma início, não conclusão. Consultar `agent_status`
para fase e progresso público; enviar orientação via `send_agent_message`; usar `wait_agents`
para aguardar sem inferências repetitivas. Reavaliar novas mensagens do usuário após a etapa atual. Cada
subagente OpenRouter recebe uma `session_id` própria; nesse backend, o roteador pode manter ou trocar o modelo durante
a task. O campo `models_used` registra modelos efetivamente informados nas respostas; Codex/Claude preservam o modelo solicitado e não inventam o ID efetivo quando o CLI não o fornece. Persistem em
`.centaur/agents/<chat-coordenador>/<id>.json`, separados dos chats principais.
Gravações e comandos seguem o modo de permissões selecionado, identificando o subagente.
Executores podem delegar partes independentes sem ampliar posse ou permissões. Há até seis
subagentes simultâneos em toda a árvore do principal, incluindo descendentes; não existe
um teto fixo de etapas. Aguardar os relatórios de descendentes antes de consolidar.

O resultado `reported` significa relatório entregue, **não aceite nem integração**.
Confira diff, critérios e evidências antes de marcar a task. Em `failed`, leia o histórico
e o trabalho preservado antes de reatribuir; não repita ações por falta de resposta.
Em outros clientes, use os mecanismos de subagentes/seleção de modelos disponíveis;
ausência dessas ferramentas mantém a alternativa sequencial descrita acima.

Executores não alteram contrato aprovado, spec, índices, estado consolidado ou grafo compartilhado. Escrevem só arquivos sob sua responsabilidade e registros/evidências individuais com IDs únicos. Reportam deltas para o coordenador. Sem canal direto com usuário, ambiguidade que mude contrato volta como bloqueio com alternativas e consequências.

## Passo 4 — Revisar com contexto novo e consolidar cada entrega/onda

**Revisão independente antes de consolidar.** Quem escreveu o código, e o coordenador que acompanhou o raciocínio, tendem a confirmar o próprio caminho. Para cada entrega com mudança de código, delegue a revisão a um executor **novo** (`delegate_task` no Centaur CLI; o mecanismo de subagentes do cliente nos demais), com modelo de capacidade igual ou maior que a do executor:

- Entregue **somente**: spec/task, contrato e regras com seus aceites, limites, o diff a revisar (intervalo do Git ou lista de arquivos) e o comando de verificação. Não envie o relatório do executor, o histórico da conversa nem a sua conclusão: o revisor deve ler o código, não a justificativa.
- Peça que ele confira, nesta ordem: a mudança faz o que o aceite pede (não só o que a task literalmente disse)? Algum comportamento existente quebrou? Há erro de lógica, borda ou segurança nas linhas alteradas? Os testes novos falhariam sem a correção? Algo extrapolou o escopo?
- O revisor **não edita**: devolve achados com `arquivo:linha`, o cenário concreto de falha, a classificação (**bloqueia o aceite** ou melhoria) e o que não conseguiu verificar. Sem achados, diz o que conferiu.
- O relatório do revisor também é dado a conferir: reproduza ou leia o trecho antes de agir. Achado que bloqueia o aceite volta ao executor responsável (ou vira task); depois da correção, revise só a correção. Melhorias fora do aceite são registradas, não executadas por conta própria.
- Dispensa: mudanças só de documentação, texto ou configuração trivial. Sem subagentes disponíveis, releia o diff a partir da spec numa etapa separada e registre que a revisão **não foi independente**.

**Tamanho.** No Centaur CLI, o resultado de `delegate_task` traz `changed` (arquivos e linhas alterados pelas ferramentas de arquivo) e, acima de ~400 linhas, `review_note`. Entrega grande é revisada por partes coesas, uma delegação de revisão por parte; se as partes forem independentes, registre no plano que a task deveria ter sido dividida.

Depois da revisão:

1. Conferir diff, fontes e resultados reais; relatório de executor isolado não é prova. No diff de testes, confirmar qual falha vital cada adição protege e eliminar duplicações entre executores sem perder proteção existente. Falha sem relatório exige inspecionar trabalho preservado antes de qualquer tentativa nova.
2. Registrar decisões técnicas e comparar impacto previsto/real. Desvio de limite bloqueia a parte afetada; manter trabalho independente.
3. Consolidar memória conforme backend (`files`: README/índice; ai-memory: publicar fila serialmente e verificar). Memória pendente é separada do estado do código.
4. Atualizar `.centaur/state/<id>.json`, vincular evidências individuais correntes e preservar histórico. Regra só recebe implementada se fontes atuais sustentarem; verificação é derivada por hashes e resultados. Não inferir entrega de um teste verde.
5. Atualizar tasks e índice da spec com as reservas de spec, contrato e índice pertinentes; reler dados compartilhados antes de consolidar. Não manter a reserva do índice durante execução de código. Marcar task executada não conclui automaticamente a capacidade. Em falta de validação/integração, usar Em revisão; bloqueio registra causa, dependências e decisão necessária.
6. Rodar validação de registros. Atualizar Graphify somente quando solicitado; nesse caso, o coordenador é o único escritor do índice. Falha no índice deve aparecer separadamente, sem reexecutar código pronto.

## Passo 5 — Demonstrar e integrar

Apresentar antes/depois, critérios atendidos, evidências, limitações, decisões autônomas e desvios. Para cada regra da entrega, executar `validate-lifecycle.py <raiz> --ready <contrato/REGRA>` e os gates reais do projeto no candidato integrado. Evidência inválida ou desatualizada impede declarar pronta para integração.

Integrar apenas conforme autorização existente; quando não houver, preparar candidato revisável e apresentar a ação concreta. Registrar `delivery.stage: integrated` só depois de confirmar revisão e destino; incluir referência/data. Publicação permanece separada e depende do pedido, nunca da conclusão automática das tasks. Não disparar deploy como consequência de atualizar estado.

## Passo 6 — Encerrar e apontar o próximo passo

`Concluída` exige todas as tasks e dependências entregues, critérios do contrato verificados e integração confirmada, inclusive specs filhas. Publicação só é requisito se estiver no aceite. Caso contrário usar Em revisão/Bloqueada/Em andamento conforme o ciclo; nunca concluir pela última checkbox.

Antes de declarar conclusão, executar `validate-lifecycle.py <raiz> --complete <escopo/spec>`; resolver as pendências retornadas, sem reescrever o contrato ou promover status para satisfazer o gate. Validar registros após o estado final e liberar somente as reservas da sessão quando seus executores tiverem encerrado ou devolvido a posse. Entregar o estado da spec executada e sua próxima ação/bloqueio, seguida da validação e links relevantes. Detalhes de regras, arquivos e evidências ficam nos registros; informar pendências materiais de memória ou ferramentas somente quando aplicáveis. Selecionar próxima lacuna pelo ciclo normativo, sem criar tarefas especulativas.
