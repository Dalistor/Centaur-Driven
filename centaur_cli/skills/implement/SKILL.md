---
name: implement
description: Implementa mudanças pontuais e diretas sem TDD (estruturais, config, UI, ou projetos sem testes) - lê o contexto, tira dúvidas, aplica, valida e registra no backend de memória configurado. Use tdd para lacunas de proteção em pontos vitais; para demandas grandes use spec + run.
metadata:
  version: 5.2.0
  dependencies: clean-code
  optional-dependencies: graphify, _internal/memory
---

# implement

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

Leia também `references/session-protocol.md` da dependência antes de editar. Aplique seus critérios de localização, responsabilidade única, nomes, erros e revisão do diff nos Passos 6–8. O roteamento e a proporcionalidade de testes desta skill prevalecem: carregar `clean-code` não transforma o modo direto em TDD.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

## Integração com Graphify

Depois da validação, atualize somente as notas e fluxos afetados; não exija indexação. O registro no backend configurado continua obrigatório; documentação do sistema não substitui validação de código.

Você é um engenheiro de software sênior executando uma implementação documentada. Siga cada passo na ordem — não pule etapas.

**Escopo desta skill: mudanças pontuais e diretas** — uma correção, um ajuste, uma feature pequena contida em poucas camadas. Se a solicitação for grande (exige vários comportamentos independentes, decisões de produto ou integração que precisam de planejamento), **não implemente**: oriente o usuário a planejar com `/spec` e executar com `/run`.

**Exceção:** em modo spec (solicitação com prefixo `Spec YYYY — Task NN`), execute sempre — a task já foi dimensionada na criação da spec.

**Roteamento para TDD:** leia a [política de testes nos pontos vitais](../graphify/references/testing.md). Use `/tdd` quando houver falha concreta em ponto vital ainda sem proteção suficiente e infraestrutura disponível. Reaproveite ou amplie testes existentes antes de criar outro. Ser testável, ser regra de negócio ou corrigir um bug de baixo impacto não obriga TDD. Mudanças sem lacuna vital seguem aqui com validação proporcional. Em modo spec, preserve requisitos explícitos de teste e o modo autorizado da task; não transforme um critério de aceite em uma bateria nova.

## Vínculo obrigatório à realização do contrato

Antes de editar, identificar contrato/versão/regras, limites herdados e autorização. Mudança pequena pode reutilizar contrato existente; sem contrato pertinente, registrar o molde mínimo pela spec (o pedido inequívoco serve de autorização), sem exigir planejamento extenso. Em legado, preservar histórico; evidência e estado novos não são inferidos de checklists antigos.

Executar uma entrega por comportamento, podendo atravessar camadas dentro da arquitetura e do escopo. Escolher detalhes técnicos dentro de `autonomy`. Mudança de regra, permissão, compatibilidade ou limite exige decisão/nova versão; não ajustar contrato ou testes para encobrir divergência.

Após validar, registrar fontes com caminhos/linhas e evidências conforme o ciclo normativo; incluir arquivos de produção, testes e configurações que sustentam o resultado. Manter implementação, verificação e entrega separadas. Sem prova, declarar não verificada. Não marcar integração/publicação a partir de execução local.

No modo direto, atualizar estado e evidências; a consulta usa diretamente os arquivos no terminal. Em modo spec, produzir evidência individual imutável e delta de estado no relatório; somente o coordenador consolida `.centaur/state/`, specs e índices. Antes de integrar, aplicar o gate `--ready` de cada regra e os checks reais. Ausência de Graphify não autoriza omitir estado ou evidência.

## Passo 1 — Ler o contexto do projeto

Leia `AGENTS.md` e recupere o contexto da solicitação pelo contrato Graphify acima. Consulte apenas os registros e trechos relevantes do escopo; para status, confirme o README canônico.

Se `AGENTS.md` não existir, avise o usuário:
> "Este projeto ainda não foi documentado. Execute `/start-project` primeiro para que eu tenha contexto suficiente para implementar com segurança."

No backend `files`, se `.centaur/implements/status.md` não existir, crie a estrutura (crie `.centaur/implements/` e o `status.md` vazio).

## Passo 2 — Entender a solicitação

Leia com atenção o que o usuário pediu. Identifique:
- O que deve ser feito (funcionalidade, correção, refactor, etc)
- Onde no código isso provavelmente acontece
- Qual o critério de sucesso (como saber que está feito e correto)

**Detectar modo spec:** se a solicitação começar com `Spec YYYY — Task NN` (ou mencionar uma spec/task de `.centaur/specs/`), você está executando uma task planejada por `/spec`, provavelmente como subagente. Em todas as skills centaur, `YYYY` é sempre o número da spec e `XXXX` o número da implementação. Neste caso:
1. Leia `.centaur/specs/YYYY/README.md` inteiro — o Objetivo e o Contexto técnico da spec fazem parte do seu contexto
2. **Não edite o README da spec nem o `index.md`** (status, checklist) — quem consolida esses arquivos é o orquestrador, com base no seu relatório final
3. Siga as regras do modo spec nos passos seguintes (marcadas com **[modo spec]**)

## Passo 3 — Explorar o código relevante

Localize e leia todos os arquivos que serão afetados ou que fornecem contexto para a implementação:
- Arquivos que serão modificados
- Arquivos que chamam ou são chamados pelos módulos afetados
- Testes existentes relacionados
- Configurações relevantes

Mapeie exatamente o que precisa mudar e onde.

## Passo 4 — Tirar todas as dúvidas

Antes de escrever, consulte contrato e fontes. Pergunte apenas sobre lacunas materiais de comportamento, limites ou integração que não estejam resolvidas; detalhes delegados pertencem à autonomia da IA.

Apresente as dúvidas de forma clara e objetiva. Aguarde as respostas do usuário antes de continuar.

Se não houver dúvidas materiais e o pedido já autorizar a mudança, informe o comportamento e prossiga sem reconfirmação.

<!-- [modo spec] Mantenha este bloco sincronizado com tdd, Passo 5 -->
**[modo spec]** Não pergunte nada — as decisões já foram resolvidas quando a spec foi criada, e como subagente você não tem canal com o usuário. Se a instrução da task for suficiente, prossiga direto. Se encontrar uma ambiguidade que **realmente impede** a implementação (conflito com o código atual, dependência não concluída), **pare sem implementar**:
No backend ai-memory, registre o bloqueio na fila e encerre com o relatório do contrato. No backend files:

1. Reserve um número de implementação conforme o Passo 9
2. Crie `.centaur/implements/XXXX/README.md` mínimo documentando o bloqueio:

```markdown
# [XXXX] [Título da task] — Bloqueado

**Data:** [saída de `date +%F`]
**Status:** Bloqueado
**Modo:** direto
**Spec:** `.centaur/specs/YYYY/` — Task NN

## Motivo do bloqueio
[O que impede a implementação, com referência a arquivo/linha quando aplicável]

## O que destrava
[Que decisão ou correção o usuário precisa tomar]
```

3. Encerre reportando o motivo do bloqueio e o número `XXXX` — **não** edite a spec nem o `status.md`; o orquestrador registra o bloqueio.

## Passo 5 — Reconfirmar o código antes de escrever

**Antes de escrever qualquer linha**, releia os trechos exatos dos arquivos que serão modificados (não confie na memória do Passo 3 — o contexto pode ter sido comprimido enquanto aguardava resposta do usuário). Confirme que ainda entende exatamente onde e como cada mudança será aplicada.

## Passo 6 — Aplicar as mudanças

Com todas as dúvidas resolvidas, execute a implementação:
- Siga as convenções e regras definidas no `AGENTS.md`
- **Respeite a arquitetura real registrada no `AGENTS.md` e no contrato**: manter responsabilidades e direção de dependências. DTO/services/repositories/handlers são exemplos quando adotados pelo projeto, não camadas obrigatórias
- Criar uma responsabilidade/camada nova somente se prevista pelo contrato e pela arquitetura autorizada; não introduzir repository ou service só para cumprir um exemplo
- Se o `AGENTS.md` não tiver a seção "Arquitetura de Camadas", siga o padrão dos arquivos vizinhos e sugira ao usuário rodar `/start-project` para formalizar a arquitetura
- **Escreva para quem vai ler**: siga o princípio de expressividade do Passo 7 enquanto escreve, não só na revisão
- Faça mudanças cirúrgicas — não refatore o que não está no escopo
- Se criar novos arquivos, coloque-os nas pastas corretas conforme a estrutura do projeto

## Passo 7 — Revisar a clareza do código

<!-- Os mesmos princípios de clareza orientam o REFACTOR de tdd; aquela skill também define manutenção dos testes. -->
O código é a documentação principal do projeto. Antes de validar, releia o que você escreveu como se estivesse chegando nele pela primeira vez, sem o contexto desta conversa. Corrija o que só faz sentido para quem acabou de escrever.

**Critério de bom nome:**
- Revela a **intenção** — o que a coisa faz ou representa, não como está implementada (`precoComDesconto`, não `p2`; `buscarPorEmail`, não `query2`)
- Usa o **vocabulário do domínio** do projeto — a palavra registrada na seção "Vocabulário e Idioma do Código" do `AGENTS.md` ou no glossário ali vinculado, consultando os conceitos relevantes (sem registro, use a convenção existente no código). Um conceito, um nome, no código inteiro. O idioma dos identificadores e dos comentários também sai dessa seção
- Sem abreviação (`calc`, `usr`, `tmp`, `res`) e sem sufixo redundante de tipo (`listaDeUsuariosArray`, `DataManager`)
- Função é verbo, valor é substantivo, booleano lê como afirmação (`estaAtivo`, `temPermissao`)
- **Nome que precisa de comentário para ser entendido é nome errado** — troque o nome, não adicione o comentário

**Onde o "porquê" mora — nesta ordem de precedência:**
1. **No próprio código**, sempre que couber: constante nomeada no lugar do número/string solto, função extraída cujo nome diz a intenção, tipo ou enum no lugar de string livre, guarda explícita no lugar de condição implícita
2. **Em comentário curto ao lado**, quando o porquê é externo ao código e não há como expressá-lo nele: regra de negócio arbitrária, limite imposto por uma API, workaround de bug de terceiro, decisão contraintuitiva. Comentário explica **por que**, nunca **o que** a linha faz
3. **No README da implementação** (Passo 10), só o que não cabe no arquivo: alternativas descartadas, trade-off de arquitetura, contexto histórico

Nunca use o README como substituto de código claro: quem abre o fonte não lê `.centaur/`, e o README envelhece enquanto o código muda.

**Cheiros que esta revisão precisa pegar:**
- Nome que não revela intenção, ou que usa palavra diferente da que o resto do projeto usa para o mesmo conceito
- Número ou string mágico sem constante nomeada
- Função que faz mais de uma coisa (se descrever exige um "e", separe)
- Aninhamento além de 2-3 níveis — inverta a condição, extraia função ou use retorno antecipado
- Parâmetro booleano que troca o comportamento da função (dois nomes explícitos são mais legíveis)
- Comentário que narra a linha seguinte — apague, ou renomeie o que está sendo narrado
- Código morto ou comentado — apague, o histórico está no Git

Corrija dentro do escopo que você tocou; não faça faxina no resto do arquivo.

## Passo 8 — Validar

Após implementar, tente validar nesta ordem:

1. **Verificação proporcional**: consulte os testes existentes dos comportamentos afetados e execute a seleção pertinente. Adicione ou amplie proteção apenas para falha concreta em ponto vital ainda sem teste suficiente, conforme a política normativa. Se o teste vier depois do código, registre isso sem alegar TDD. Fora dos pontos vitais, use inspeção, build/lint ou demonstração conforme o aceite; não crie teste por ritual. Sem infraestrutura, não a instale como efeito colateral. Rode suíte completa quando exigida pelos gates ou pelo impacto transversal, sem repeti-la a cada ajuste.
2. **Lint / type-check**: verifique se existe script de lint ou type-check. Se existir, execute. Se não existir, registre e siga.
3. **Revisão manual**: leia o código implementado uma última vez e confirme que não há bugs óbvios, casos não tratados ou regressões.
4. **Revisão de arquitetura**: conferir as fronteiras e dependências efetivamente adotadas pelo projeto. Em arquitetura em camadas, verificar suas separações; em organização por capacidades ou outro modelo, aplicar os limites correspondentes. Não inventar camadas nem refatorar arquitetura fora do contrato.

Se encontrar problemas na validação, corrija antes de documentar. Se nenhum mecanismo de validação existir no projeto, documente isso explicitamente no README da implementação.

## Passo 9 — Determinar número da implementação

**Backend ai-memory:** use o UUID e o caminho do contrato de memória, sem reservar pasta. O template do próximo passo fornece o corpo da página/fila. Pule a etapa de `status.md` e informe a referência da página no lugar do número. Em modo spec, grave a fila e reporte ao coordenador; inclusive em bloqueios, não crie README local nem publique diretamente.

**Backend files:** siga a reserva abaixo.

<!-- Mantenha este passo sincronizado com tdd (Passo 12) -->
Execute exatamente este comando para encontrar o último número:

```
ls .centaur/implements/ | grep -E '^[0-9]{4}$' | sort | tail -1
```

- Se retornar um número (ex: `0003`), o próximo é esse + 1 (ex: `0004`)
- Se retornar vazio, começa em `0001`
- Formate sempre com 4 dígitos: `0001`, `0002`, `0042`, `0100`

**Reserve o número imediatamente** criando a pasta com `mkdir .centaur/implements/XXXX` (sem `-p`). Se o comando falhar porque a pasta já existe — acontece quando outra task roda em paralelo via `/run` —, incremente o número e tente de novo até conseguir. Só considere o número seu depois que o `mkdir` tiver sucesso.

## Passo 10 — Documentar a implementação

Obtenha a data de hoje com `date +%F` — não a preencha de memória.

Este README é a trilha de auditoria, **não** o lugar onde o código é explicado. O que dá para expressar no próprio código já foi expresso no Passo 7; aqui fica só o que não cabe num arquivo de código.

Em `files`, crie `.centaur/implements/XXXX/README.md`. Em `ai-memory`, use este conteúdo no registro do contrato, com o ID atribuído:

```markdown
# [XXXX] [Título curto e descritivo da implementação]

**Data:** [saída de `date +%F`]
**Status:** [Concluído ou Bloqueado, conforme resultado real]
**Modo:** direto
**Spec:** [se veio de uma spec: `.centaur/specs/YYYY/` — Task NN. Caso contrário, omita esta linha]

## Solicitação
[O que o usuário pediu, com as palavras dele]

## Contexto
[Por que essa mudança era necessária, qual problema resolve]

## O que foi feito
[Descrição objetiva das mudanças realizadas]

## Arquivos modificados
- `caminho/do/arquivo.ext` — [o que mudou]
- `outro/arquivo.ext` — [o que mudou]

## Arquivos criados
- `caminho/novo.ext` — [para que serve]

## Decisões técnicas
[Só o que não cabe no código: alternativas descartadas e por quê, trade-offs de arquitetura, contexto histórico. Se a justificativa cabia numa constante nomeada ou num comentário ao lado da linha, o lugar dela era lá — não aqui]

## Como validar
[Como testar/verificar manualmente que funciona]

## Contrato e realização
[Contrato/versão/regras; fontes com linhas; IDs de evidências; implementação/verificação/entrega; decisões autônomas, impacto previsto × real e próximo passo]

## Resultado da validação
[O que foi executado e o resultado: testes passando, sem erros de lint, etc]
```

## Passo 11 — Atualizar status.md

**[modo spec]** Pule este passo — o orquestrador escreve a linha no `status.md` com base no seu relatório final. Escritas paralelas de subagentes no mesmo arquivo se sobrescrevem.

Somente em `files`, adicione uma linha na tabela de `.centaur/implements/status.md`:

```
| XXXX | [Título] | [data] | Concluído | [lista de arquivos afetados] |
```

Se a tabela ainda contiver a linha placeholder (`| — | — | — | — | — |`), remova-a ao inserir a primeira linha real.

## Passo 12 — Atualizar AGENTS.md se necessário

**Modo spec:** só editar AGENTS.md, glossário ou documento compartilhado se a task possuir esses arquivos explicitamente. Caso contrário entregar o delta documental ao coordenador; não criar obrigação implícita de escrita concorrente.

Se a implementação:
- Adicionou uma funcionalidade nova relevante para o projeto
- Mudou a arquitetura ou estrutura de pastas
- Introduziu uma nova dependência importante
- Alterou como o projeto é rodado ou deployado
- **Estabeleceu um termo novo do domínio** que o código passou a usar → registre no glossário vinculado pela seção "Vocabulário e Idioma do Código"; sem glossário, mantenha o termo nessa seção enquanto ela for curta

→ Atualize as instruções essenciais na seção relevante do `AGENTS.md`; detalhes de arquitetura, operação ou domínio vão para as fontes vinculadas, sem duplicação.

Se foi uma correção de bug ou mudança interna sem impacto na visão geral, não precisa atualizar.

## Passo 13 — Consolidar documentação e contexto

Atualize documentação, estado e evidências afetados. Graphify permanece opcional: não inicialize nem sincronize após cada implementação. Quando houver pedido explícito de indexação, siga `graphify`, registre cobertura e falhas separadamente e mantenha um único escritor no coordenador. Ausência de índice não impede concluir código validado.

## Passo 14 — Informar o usuário

Siga a saída curta do contrato de contexto: resultado, validação, pendência material e próximo passo, com link para o registro. O relatório de modo spec abaixo é destinado ao coordenador; mantenha-o no registro individual e envie sua referência com o delta necessário, sem reproduzir todos os campos para o humano. Omita Mapa/Perspectivas/Graphify quando não envolvidos.

Informe o resultado real da implementação com:
- O que foi feito (resumo de 2-3 linhas)
- Resultado da validação
- Referência da página e estado da memória, ou número/README no backend `files`
- Graphify, se solicitado: resultado da consulta/atualização e limitações

**[modo spec]** Em ai-memory, use o relatório com `Registro` e `Fila` definido no contrato. Em `files`, encerre com o relatório abaixo, usado pelo orquestrador para consolidar a spec e o `status.md`:

```
Spec YYYY — Task NN: [Concluída | Bloqueada]
Implementação: XXXX
Título: [título usado no README da implementação]
Arquivos afetados: [código, testes e documentos alterados, incluindo o README da implementação]
Graphify: não solicitado | consultado | atualizado | pendente após solicitação explícita
Contrato/regras: [IDs e versão]
Realização: [implementação, evidências selecionadas, entrega local e delta de estado]
Impacto: [previsto × real, decisões e desvios]
Próximo passo: [ação ou decisão necessária]
Validação: [resultado resumido]
Mapa: [caminho e resultado real; se bloqueada sem implementação, não aplicável]
Perspectivas afetadas: [ids de views existentes ou nenhuma; atualização reservada ao orquestrador]
[Se bloqueada: Motivo do bloqueio e o que destrava]
```
