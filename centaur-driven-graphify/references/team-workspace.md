# Trabalho por módulos e em equipe

Leia este contrato antes de localizar specs ou implementações. Os caminhos simples dos exemplos das skills representam o escopo selecionado; substitua-os pelos caminhos registrados, inclusive nos comandos de reserva, leitura, arquivamento e escrita. Resolva sempre a partir da raiz do projeto, mesmo ao executar dentro de uma subpasta.

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

Todos os caminhos são relativos à raiz, ficam dentro do projeto e as pastas de registros dos escopos são distintas. `master` é obrigatório e contém specs principais do sistema, decisões de integração e implementações transversais. Os nomes dos módulos seguem as responsabilidades reais do projeto; frontend/backend são exemplos. Cada escopo tem `specs/index.md`, `implements/status.md` e registros próprios. Sem configuração, use somente `master` nos caminhos legados; nunca mova registros antigos automaticamente.

`collaboration` registra a resposta explícita do usuário: `individual` ou `team`. Ambos permitem múltiplos módulos e specs mestre. No modo individual, o desenvolvedor acumula responsabilidade e integração; não exija outros participantes ou revisão por outra pessoa. Havendo agentes/sessões simultâneos, as regras de concorrência continuam valendo. Em configurações antigas sem esse campo, preserve o funcionamento e pergunte o modo na próxima atualização de contexto, sem presumir equipe.

## Identidade e responsabilidade

- Use IDs qualificados em links, relatórios e comandos: `master/0001`, `frontend/0001`, `backend/0001`. Um número sem escopo só é aceito se resolver uma única spec entre todos os escopos; em caso de colisão, apresente as opções.
- Antes de criar, selecione o escopo pelo pedido e pelos arquivos afetados. Se houver ambiguidade real, pergunte. Uma demanda entre módulos cria uma spec mestre e specs filhas por módulo; mudanças pequenas transversais podem ficar em master.
- Reserve IDs com `mkdir` sem `-p` no escopo selecionado. Em clones independentes, prefira IDs com sufixo único (ex.: `0001-ana-a7f2`) para novos registros: `mkdir` só protege concorrência no mesmo filesystem. Não renumere históricos para resolver colisões; ajuste novos IDs e seus links antes da integração.
- Cada spec registra `**Escopo:**`, `**Responsável:**`, `**Status:**`, `**Spec mestre:**` (ID ou `—`), `**Specs filhas:**` (IDs ou `—`) e `**Dependências:**` (IDs de specs/tasks ou `—`). Cada task registra responsável, arquivos de sua posse e dependências qualificadas. Implementações registram o ID completo da spec/task e sua validação.
- O prefixo de execução aceita `Spec frontend/0001 — Task 01` e o formato legado. O executor recebe caminhos absolutos do projeto, da spec e da pasta de implementações. Nunca deduza o módulo apenas do número.

## Concorrência e integração

Um coordenador por spec consolida seus registros. Defina quem integra specs mestre e mantém índices e grafo compartilhados; executores reportam resultados e só editam seus arquivos e README de implementação. Em sessões no mesmo checkout, reserve a spec com `mkdir .centaur/locks/<escopo>-<id>` e registre responsável e sessão dentro; se já existir, não execute a mesma spec. Crie somente o pai `locks` com `-p`. Libere apenas o lock da própria sessão ao encerrar. Lock abandonado exige verificar a sessão antes de remover.

Distribua trabalho por pessoa/agente, branch e worktree/clone quando houver execução simultânea. Dependências concluídas precisam estar integradas no checkout do executor antes de liberá-lo. Tasks que editam os mesmos arquivos, contratos compartilhados, índices ou configuração executam serialmente ou em branches isoladas com integração sequencial. Não prometa exclusão entre clones por locks locais. Os responsáveis coordenam a posse das tasks no repositório compartilhado.

## Estado canônico e grafo

O README de cada spec é a fonte de seu estado; índices e o grafo são projeções. Status: `Pendente`, `Em andamento`, `Bloqueada`, `Em revisão`, `Concluída`. Uma task validada pode estar concluída localmente, mas a spec vai a `Em revisão` enquanto faltar integração ou aceite previsto. `Concluída` exige tasks e dependências entregues, validação e integração confirmadas. Registre motivo e ação necessária para bloqueios; quando resolvidos, retome `Em andamento`. Pendência apenas documental não reabre código validado.

A spec mestre só conclui após todas as filhas e seus critérios de integração. Não execute de novo as tasks de uma filha como tasks duplicadas da mestre. O run resolve o grafo entre specs e tasks, detecta referências ausentes/ciclos antes de iniciar e retoma somente pendências. Após criar spec, consolidar onda, bloquear/desbloquear, revisar, integrar ou atualizar documentação: atualize README, índice do escopo e depois sincronize os documentos no Graphify serialmente. Não infira conclusão da presença de um nó no grafo.
