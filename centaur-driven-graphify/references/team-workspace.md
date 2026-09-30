# Trabalho por módulos e em equipe

Leia este contrato antes de localizar specs ou implementações. Os caminhos simples dos exemplos das skills representam o escopo selecionado; substitua-os pelos caminhos registrados, inclusive nos comandos de reserva, leitura, arquivamento e escrita. Resolva sempre a partir da raiz do projeto, mesmo ao executar dentro de uma subpasta.

O [contrato de memória](../../centaur-driven-memory/references/contract.md) determina o destino das implementações. Reserva numérica, pasta de implementações e seu índice abaixo só são obrigatórios no backend `files`. Em `ai-memory`, use UUID e referência de página; locks, IDs e pastas de specs permanecem iguais.

## Registro dos escopos

O start-project cria `.centaur/workspace.json`. Exemplo para um projeto com dois módulos:

```json
{
  "version": 1,
  "collaboration": "team",
  "scopes": {
    "master": {"code": ".", "specs": ".centaur/specs", "implements": ".centaur/implements", "owner": "equipe"},
    "frontend": {"code": "frontend", "specs": ".centaur/modules/frontend/specs", "implements": ".centaur/modules/frontend/implements", "owner": "a definir"},
    "backend": {"code": "backend", "specs": ".centaur/modules/backend/specs", "implements": ".centaur/modules/backend/implements", "owner": "a definir"}
  }
}
```

Todos os caminhos são relativos à raiz, ficam dentro do projeto e as pastas de registros dos escopos são distintas. `master` é obrigatório e contém specs principais do sistema, decisões de integração e implementações transversais. Os nomes dos módulos seguem as responsabilidades reais do projeto; frontend/backend são exemplos. Cada escopo tem `specs/index.md` e registros próprios. `implements/status.md` é criado somente no backend `files`. O campo opcional `memory` na raiz do JSON seleciona o backend; em `ai-memory`, omita `implements` nos escopos sem histórico legado. Preserve esse campo onde ainda aponta para histórico existente. Sem configuração, use somente `master` nos caminhos legados; nunca mova registros antigos automaticamente.

`collaboration` registra a resposta explícita do usuário: `individual` ou `team`. Ambos permitem múltiplos módulos e specs mestre. No modo individual, o desenvolvedor acumula responsabilidade e integração; não exija outros participantes ou revisão por outra pessoa. Havendo agentes/sessões simultâneos, as regras de concorrência continuam valendo. Em configurações antigas sem esse campo, preserve o funcionamento e pergunte o modo na próxima atualização de contexto, sem presumir equipe.

## Identidade e responsabilidade

- Use IDs qualificados em links, relatórios e comandos: `master/0001`, `frontend/0001`, `backend/0001`. Um número sem escopo só é aceito se resolver uma única spec entre todos os escopos; em caso de colisão, apresente as opções.
- Antes de criar, selecione o escopo pelo pedido e pelos arquivos afetados. Se houver ambiguidade real, pergunte. Uma entrega conjunta entre módulos pode criar uma spec mestre e specs filhas; entregas independentes mantêm specs próprias, e mudanças pequenas transversais podem ficar em master.
- Reserve IDs com `mkdir` sem `-p` no escopo selecionado. Em clones independentes, prefira IDs com sufixo único (ex.: `0001-ana-a7f2`) para novos registros: `mkdir` só protege concorrência no mesmo filesystem. Não renumere históricos para resolver colisões; ajuste novos IDs e seus links antes da integração.
- Cada spec registra `**Escopo:**`, `**Responsável:**`, `**Status:**`, `**Spec mestre:**` (ID ou `—`), `**Specs filhas:**` (IDs ou `—`) e `**Dependências:**` (IDs de specs/tasks ou `—`). Cada task registra responsável, arquivos de sua posse e dependências qualificadas. Implementações registram o ID completo da spec/task e sua validação.
- O prefixo de execução aceita `Spec frontend/0001 — Task 01` e o formato legado. O executor recebe caminhos absolutos do projeto, da spec e, em `files`, da pasta de implementações; em `ai-memory`, recebe identidade, ID e destino da página. Nunca deduza o módulo apenas do número.

## Várias specs no mesmo projeto

Specs independentes coexistem no mesmo escopo; módulos não precisam de uma spec mestre apenas para organizar a fila. Crie mestre/filhas quando houver critérios de entrega conjunta. Cada spec possui estado próprio: um bloqueio não suspende specs independentes, e executar uma spec não autoriza iniciar as demais.

O `run` executa uma spec por chamada, identificada por um único ID qualificado. Se faltar ID ou houver vários, apresente uma seleção curta para escolher uma antes de executar. Leia o README atual e consulte as dependências necessárias, ordenando as tasks da spec por dependências e interferência. Dependências e specs filhas são executadas em chamadas próprias; sua existência não amplia a execução da spec escolhida.

Antes de editar, registre na task a sessão/responsável, os arquivos de sua posse e branch/worktree quando usados. Antes de ampliar os arquivos afetados, compare com a posse das demais tasks ativas e coordene a transferência ou aguarde. Arquivos diferentes também podem ter interferência por interface, schema ou configuração; posse documental não é um bloqueio do filesystem nem prova de compatibilidade.

O coordenador escreve a posse no README antes de delegar; executores não editam a spec para se atribuir trabalho.

Ao retomar, confira reserva, README, diff, evidências e dependências integradas antes de repetir uma task. Preserve alterações de outra sessão. Se um executor interromper sem relatório, inspecione o trabalho preservado antes de reatribuir; ausência de resposta ou tempo decorrido não libera sua posse automaticamente.

## Concorrência e integração

Um coordenador por spec consolida seus registros. Specs simultâneas que atualizam o mesmo `.centaur/state/<contrato>.json` precisam de um único escritor/integração serial; lock só da spec não protege estado compartilhado. Reservar `.centaur/locks/contract-<id>` antes da consolidação no mesmo checkout, liberar somente o próprio lock e usar integração por Git entre clones. Defina quem integra specs mestre e mantém índices e grafo compartilhados; executores reportam deltas de estado, resultados e evidências imutáveis individuais; só editam seus arquivos e o registro individual (README em `files`, fila local em `ai-memory`). Em sessões no mesmo checkout, reserve a spec com `mkdir .centaur/locks/<escopo>-<id>` e registre responsável e sessão dentro; se já existir, não execute a mesma spec. Crie somente o pai `locks` com `-p`. Libere apenas o lock da própria sessão ao encerrar. Lock abandonado exige verificar a sessão e preservar seu trabalho antes de remover; não remover só por idade.

Distribua trabalho por pessoa/agente, branch e worktree/clone quando houver execução simultânea. Dependências concluídas precisam estar integradas no checkout do executor antes de liberá-lo. Tasks que editam os mesmos arquivos, contratos compartilhados, índices ou configuração executam serialmente ou em branches isoladas com integração sequencial. Não prometa exclusão entre clones por locks locais. Os responsáveis coordenam a posse das tasks no repositório compartilhado.

Quando várias reservas compartilhadas forem necessárias, adquira contrato e índice nessa ordem e libere na ordem inversa. Não aguarde outro recurso mantendo uma reserva parcial: libere suas reservas parciais e tente consolidar depois.

Índices de specs e implementações também são recursos compartilhados. No mesmo checkout, reserve `.centaur/locks/index-<escopo>` com `mkdir` antes de atualizar os índices do escopo, releia o conteúdo após obter a reserva e libere somente a reserva da própria sessão. Mantenha a reserva apenas durante a consolidação; uma sessão não segura o índice enquanto executa código. O lock da spec protege seu README, não os índices, arquivos de código ou outros contratos. Se a reserva não puder ser adquirida, preserve o delta para consolidar depois; não sobrescreva o índice. Entre clones/worktrees independentes, coordene responsáveis e integração Git; reservas locais não se tornam globais.

## Estado canônico e grafo

O README de cada spec é a fonte de seu estado; índices e o grafo são projeções. Estados e gates vêm exclusivamente do [ciclo normativo](lifecycle.md), incluindo `Cancelada` sob decisão explícita. O README governa o plano, não o comportamento: contrato, estado e evidências governam a realização. Uma task validada pode estar concluída localmente, mas a spec vai a `Em revisão` enquanto faltar integração ou aceite previsto. Aplicar os gates normativos antes de concluir. Registre motivo e ação necessária para bloqueios; quando resolvidos, retome `Em andamento`. Pendência apenas documental não reabre código validado.

A spec mestre só conclui após todas as filhas e seus critérios de integração. Não execute de novo as tasks de uma filha como tasks duplicadas da mestre. O run consulta o grafo de dependências da spec escolhida, detecta referências ausentes/ciclos antes de iniciar e retoma somente suas tasks pendentes. Após criar spec, consolidar onda, bloquear/desbloquear, revisar, integrar ou atualizar documentação: atualize README e índice do escopo. Graphify é sincronizado apenas sob demanda, por um único coordenador. Não infira conclusão da presença de um nó no grafo.
