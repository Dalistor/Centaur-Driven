---
name: centaur-driven-implement
description: Implementa mudanças pontuais e diretas sem TDD (estruturais, config, UI, ou projetos sem testes) - lê o contexto, tira dúvidas, aplica, valida e documenta em .centaur/implements/. Para comportamento testável use centaur-driven-tdd; para demandas grandes use centaur-driven-spec + centaur-driven-run.
version: 1.8.0
invocable: true
author: user
metadata:
  dependencies: clean-code
---

# centaur-driven-implement

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Leia também `references/session-protocol.md` da dependência antes de editar. Aplique seus critérios de localização, responsabilidade única, nomes, erros e revisão do diff nos Passos 6–8. O roteamento e a proporcionalidade de testes desta skill prevalecem: carregar `clean-code` não transforma o modo direto em TDD.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

Você é um engenheiro de software sênior executando uma implementação documentada. Siga cada passo na ordem — não pule etapas.

**Escopo desta skill: mudanças pontuais e diretas** — uma correção, um ajuste, uma feature pequena contida em poucas camadas. Se a solicitação for grande (afeta muitas camadas, exige vários passos independentes, mexeria em mais de ~4 arquivos distintos), **não implemente**: oriente o usuário a planejar com `/centaur-driven-spec` e executar com `/centaur-driven-run`.

**Exceção:** em modo spec (solicitação com prefixo `Spec YYYY — Task NN`), execute sempre — a task já foi dimensionada na criação da spec.

**Roteamento para TDD:** se a mudança tem **regra de negócio relevante** (decisão, validação com consequência, cálculo, correção de bug) **e** o projeto tem infraestrutura de teste, use `/centaur-driven-tdd` no lugar desta skill — o teste vem antes do código. Continue aqui quando a mudança for estrutural (renomear, mover arquivo), de configuração, só de UI/estilo, **comportamento trivial mesmo que testável** (mapeamento direto de campos, passthrough, fiação sem lógica), ou quando o projeto não tiver testes automatizados. Ser tecnicamente testável não obriga TDD — teste desnecessário custa em toda execução futura da suíte. Em modo spec, obedeça ao que a task manda: se a instrução da task pedir TDD, invoque `/centaur-driven-tdd`.

## Passo 1 — Ler o contexto do projeto

Leia obrigatoriamente:
1. `AGENTS.md` na raiz do projeto (visão geral, arquitetura, **Arquitetura de Camadas**, **Vocabulário e Idioma do Código**, regras, restrições)
2. `.centaur/implements/status.md` (histórico de implementações anteriores)

Se `AGENTS.md` não existir, avise o usuário:
> "Este projeto ainda não foi documentado. Execute `/centaur-driven-start-project` primeiro para que eu tenha contexto suficiente para implementar com segurança."

Se `.centaur/implements/status.md` não existir, crie a estrutura (crie `.centaur/implements/` e o `status.md` vazio).

## Passo 2 — Entender a solicitação

Leia com atenção o que o usuário pediu. Identifique:
- O que deve ser feito (funcionalidade, correção, refactor, etc)
- Onde no código isso provavelmente acontece
- Qual o critério de sucesso (como saber que está feito e correto)

**Detectar modo spec:** se a solicitação começar com `Spec YYYY — Task NN` (ou mencionar uma spec/task de `.centaur/specs/`), você está executando uma task planejada por `/centaur-driven-spec`, provavelmente como subagente. Em todas as skills centaur, `YYYY` é sempre o número da spec e `XXXX` o número da implementação. Neste caso:
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

Antes de escrever qualquer código, liste todas as dúvidas que ainda existem. Se houver qualquer ambiguidade sobre comportamento, edge cases, integração com outras partes, ou preferências de implementação — pergunte agora.

Apresente as dúvidas de forma clara e objetiva. Aguarde as respostas do usuário antes de continuar.

Se não houver dúvidas, confirme o plano de implementação em uma ou duas frases e pergunte se pode prosseguir.

<!-- [modo spec] Mantenha este bloco sincronizado com centaur-driven-tdd, Passo 5 -->
**[modo spec]** Não pergunte nada — as decisões já foram resolvidas quando a spec foi criada, e como subagente você não tem canal com o usuário. Se a instrução da task for suficiente, prossiga direto. Se encontrar uma ambiguidade que **realmente impede** a implementação (conflito com o código atual, dependência não concluída), **pare sem implementar**:
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
- **Respeite a Arquitetura de Camadas do `AGENTS.md`**: cada responsabilidade na sua camada (validação de forma em DTOs, regra de negócio em services, acesso a dados em repositories, orquestração de requisição em handlers). Nunca atravesse camadas — se precisar de algo de outra camada, injete/chame pela interface dela
- Se a camada necessária ainda não existe no projeto (ex: primeira repository), crie-a na pasta definida pelo `AGENTS.md`, seguindo o padrão da tabela de camadas
- Se o `AGENTS.md` não tiver a seção "Arquitetura de Camadas", siga o padrão dos arquivos vizinhos e sugira ao usuário rodar `/centaur-driven-start-project` para formalizar a arquitetura
- **Escreva para quem vai ler**: siga o princípio de expressividade do Passo 7 enquanto escreve, não só na revisão
- Faça mudanças cirúrgicas — não refatore o que não está no escopo
- Se criar novos arquivos, coloque-os nas pastas corretas conforme a estrutura do projeto

## Passo 7 — Revisar a clareza do código

<!-- Mantenha este passo sincronizado com centaur-driven-tdd, Passo 9 (REFACTOR) -->
O código é a documentação principal do projeto. Antes de validar, releia o que você escreveu como se estivesse chegando nele pela primeira vez, sem o contexto desta conversa. Corrija o que só faz sentido para quem acabou de escrever.

**Critério de bom nome:**
- Revela a **intenção** — o que a coisa faz ou representa, não como está implementada (`precoComDesconto`, não `p2`; `buscarPorEmail`, não `query2`)
- Usa o **vocabulário do domínio** do projeto — a palavra registrada na seção "Vocabulário e Idioma do Código" do `AGENTS.md` (ou, se a seção não existir, a que o resto do código já usa). Um conceito, um nome, no código inteiro. O idioma dos identificadores e dos comentários também sai dessa seção
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

1. **Testes**: verifique se existe script de test no package.json, pytest.ini, Makefile ou similar. Se existir, execute. Se não existir, registre "projeto sem testes automatizados" e siga. Se a mudança acabou introduzindo comportamento testável sem teste, aplique proporcionalidade: **regra de negócio relevante** ganha o teste agora (e registre no README que ele veio depois do código, não por TDD); **comportamento trivial** (mapeamento direto, passthrough, formatação simples) não precisa — registre "sem teste — comportamento trivial" no README e siga. Não escreva teste por ritual.
2. **Lint / type-check**: verifique se existe script de lint ou type-check. Se existir, execute. Se não existir, registre e siga.
3. **Revisão manual**: leia o código implementado uma última vez e confirme que não há bugs óbvios, casos não tratados ou regressões.
4. **Revisão de camadas**: confirme que nenhuma mudança violou a Arquitetura de Camadas — sem regra de negócio em handler, sem query fora de repository, sem DTO vazando para o domínio. Se violou, corrija antes de documentar.

Se encontrar problemas na validação, corrija antes de documentar. Se nenhum mecanismo de validação existir no projeto, documente isso explicitamente no README da implementação.

## Passo 9 — Determinar número da implementação

<!-- Mantenha este passo sincronizado com centaur-driven-tdd (Passo 12) e centaur-driven-deploy (Passo 16) -->
Execute exatamente este comando para encontrar o último número:

```
ls .centaur/implements/ | grep -E '^[0-9]{4}$' | sort | tail -1
```

- Se retornar um número (ex: `0003`), o próximo é esse + 1 (ex: `0004`)
- Se retornar vazio, começa em `0001`
- Formate sempre com 4 dígitos: `0001`, `0002`, `0042`, `0100`

**Reserve o número imediatamente** criando a pasta com `mkdir .centaur/implements/XXXX` (sem `-p`). Se o comando falhar porque a pasta já existe — acontece quando outra task roda em paralelo via `/centaur-driven-run` —, incremente o número e tente de novo até conseguir. Só considere o número seu depois que o `mkdir` tiver sucesso.

## Passo 10 — Documentar a implementação

Obtenha a data de hoje com `date +%F` — não a preencha de memória.

Este README é a trilha de auditoria, **não** o lugar onde o código é explicado. O que dá para expressar no próprio código já foi expresso no Passo 7; aqui fica só o que não cabe num arquivo de código.

Crie o arquivo `.centaur/implements/XXXX/README.md`:

```markdown
# [XXXX] [Título curto e descritivo da implementação]

**Data:** [saída de `date +%F`]
**Status:** Concluído
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

## Resultado da validação
[O que foi executado e o resultado: testes passando, sem erros de lint, etc]
```

## Passo 11 — Atualizar status.md

**[modo spec]** Pule este passo — o orquestrador escreve a linha no `status.md` com base no seu relatório final. Escritas paralelas de subagentes no mesmo arquivo se sobrescrevem.

Adicione uma linha na tabela de `.centaur/implements/status.md`:

```
| XXXX | [Título] | [data] | Concluído | [lista de arquivos afetados] |
```

Se a tabela ainda contiver a linha placeholder (`| — | — | — | — | — |`), remova-a ao inserir a primeira linha real.

## Passo 12 — Atualizar AGENTS.md se necessário

Se a implementação:
- Adicionou uma funcionalidade nova relevante para o projeto
- Mudou a arquitetura ou estrutura de pastas
- Introduziu uma nova dependência importante
- Alterou como o projeto é rodado ou deployado
- **Estabeleceu um termo novo do domínio** que o código passou a usar → registre na seção "Vocabulário e Idioma do Código", para que a próxima implementação use a mesma palavra

→ Atualize a seção relevante do `AGENTS.md`.

Se foi uma correção de bug ou mudança interna sem impacto na visão geral, não precisa atualizar.

## Passo 13 — Informar o usuário

Confirme que a implementação foi concluída com:
- O que foi feito (resumo de 2-3 linhas)
- Resultado da validação
- Número da implementação criada (ex: "Documentado em `.centaur/implements/0003/`")

**[modo spec]** Encerre com um relatório estruturado — é dele que o orquestrador consolida a spec e o `status.md`:

```
Spec YYYY — Task NN: [Concluída | Bloqueada]
Implementação: XXXX
Título: [título usado no README da implementação]
Arquivos afetados: [lista]
Validação: [resultado resumido]
[Se bloqueada: Motivo do bloqueio e o que destrava]
```
