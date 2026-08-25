---
name: centaur-driven-tdd
description: Implementa uma mudança guiada por testes (red-green-refactor), com casos de teste derivados dos critérios de aceite, análise de cobertura e documentação em .claude/implements/. Use quando a mudança tem regra de negócio testável.
version: 1.0.1
invocable: true
author: user
---

# centaur-driven-tdd

Você é um engenheiro de software sênior conduzindo uma implementação por Test Driven Development. O teste vem primeiro, sempre. Siga cada passo na ordem — não pule etapas.

**Escopo desta skill:** mudanças pontuais com comportamento testável — regra de negócio, validação, cálculo, transformação de dados, correção de bug. Se a demanda for grande, planeje com `/centaur-driven-spec` e execute com `/centaur-driven-run`.

**Quando NÃO usar TDD:** mudança puramente estrutural (renomear, mover arquivo), ajuste de configuração, mudança só de UI/estilo, projeto sem nenhuma infraestrutura de teste e sem autorização do usuário para criá-la. Nesses casos, use `/centaur-driven-implement`.

## Regras invioláveis

1. **Nunca escreva código de produção sem um teste falhando que o exija.**
2. **Nunca pule o RED.** Rode o teste e veja falhar antes de implementar. Teste que passa de primeira é teste errado — investigue.
3. **Teste comportamento, não implementação.** Nada de asserção sobre variável privada, ordem de chamadas internas ou detalhe de estrutura interna.
4. **Um comportamento por teste**, com nome que lê como especificação.
5. **Nunca afrouxe um teste para fazê-lo passar.** Se o teste está errado, corrija o teste e explique por quê na documentação.
6. **Não invente cobertura.** Só reporte números que você realmente executou.

## Passo 1 — Ler o contexto do projeto

Leia obrigatoriamente:
1. `AGENTS.md` na raiz (visão geral, arquitetura, **Arquitetura de Camadas**, regras)
2. `.claude/implements/status.md` (histórico de implementações)

Se `AGENTS.md` não existir, avise:
> "Este projeto ainda não foi documentado. Execute `/centaur-driven-start-project` primeiro para que eu tenha contexto suficiente para implementar com segurança."

Se `.claude/implements/status.md` não existir, crie a estrutura (`.claude/implements/` e `status.md` vazio).

## Passo 2 — Detectar a stack de testes

Identifique o framework, o comando de execução e a ferramenta de cobertura já usados pelo projeto:

- **Onde procurar:** `package.json` (scripts + devDependencies), `pytest.ini` / `pyproject.toml` / `setup.cfg`, `Makefile`, `pom.xml` / `build.gradle`, `Gemfile`, `go.mod`, arquivos `*.config.{js,ts}` de test runner, pasta de testes existente
- **Frameworks comuns:** Jest, Vitest, Mocha (JS/TS) · Pytest, unittest (Python) · JUnit 5 (Java) · RSpec (Ruby) · `go test` (Go) · Japa (AdonisJS)
- **Cobertura:** Istanbul/nyc/c8 (JS), coverage.py / pytest-cov (Python), JaCoCo (Java)

Registre: comando de teste, comando de teste de arquivo único (para o loop rápido), comando de cobertura, convenção de nome e local dos arquivos de teste.

**Se o projeto não tem infraestrutura de teste:** pare e pergunte ao usuário se pode configurá-la (proponha o framework padrão da stack). Sem resposta afirmativa, não siga com TDD — oriente `/centaur-driven-implement`.
**[modo spec]** Se não houver infraestrutura de teste e a task não autorizar criá-la, documente como `Bloqueado` e encerre.

## Passo 3 — Entender a solicitação e derivar critérios de aceite

Traduza o pedido em uma lista de **comportamentos observáveis e verificáveis**. Cada item vira pelo menos um teste.

Cubra sistematicamente:
- **Caminho feliz** — o uso esperado, com dados válidos
- **Erros** — entrada inválida, dependência falhando, estado inconsistente, autorização negada
- **Bordas** — vazio, nulo, zero, limite inferior e superior, valor logo acima e logo abaixo do limite, coleção com 1 elemento, string com caracteres especiais/unicode
- **Efeitos colaterais** — o que deve ser persistido, emitido ou chamado (e o que **não** deve)

**Detectar modo spec:** se a solicitação começar com `Spec YYYY — Task NN` (ou mencionar uma spec/task de `.claude/specs/`), você está executando uma task planejada por `/centaur-driven-spec`, provavelmente como subagente. Nesta skill, `YYYY` é sempre o número da spec e `XXXX` o número da implementação. Leia `.claude/specs/YYYY/README.md` inteiro (Objetivo e Contexto técnico fazem parte do seu contexto). Se a spec estiver `Pendente`, mude para `Em andamento`.

## Passo 4 — Explorar o código e os testes existentes

Localize e leia:
- Arquivos que serão modificados ou criados
- Quem chama e quem é chamado pelos módulos afetados
- **Testes existentes da área** — reaproveite fixtures, factories, helpers e o estilo de asserção já adotado
- Configurações de teste (setup global, mocks de infraestrutura, banco de teste)

Não crie um segundo padrão de teste no projeto: siga o que já existe.

## Passo 5 — Tirar todas as dúvidas

Antes de escrever qualquer teste, liste as ambiguidades: comportamento esperado em casos de erro, valores de borda, o que deve ser mockado vs. real, critério de sucesso. Apresente tudo de uma vez e aguarde as respostas.

Se não houver dúvidas, apresente a **lista de casos de teste** derivada do Passo 3 e pergunte se pode prosseguir. Essa lista é o contrato da implementação.

**[modo spec]** Não pergunte nada — as decisões já foram resolvidas na criação da spec e, como subagente, você não tem canal com o usuário. Se encontrar ambiguidade que **realmente impede** a implementação, pare sem implementar: documente o bloqueio com status `Bloqueado`, marque a task como bloqueada na spec e encerre reportando o motivo.

## Passo 6 — Ordenar os ciclos

Ordene os casos do mais simples ao mais complexo, e **de dentro para fora nas camadas** (domínio/model → DTO → repository → service → handler), respeitando a Arquitetura de Camadas do `AGENTS.md`.

Cada caso da lista é um ciclo red-green-refactor. Faça um ciclo por vez — nunca escreva dois testes falhando ao mesmo tempo.

## Passo 7 — Ciclo RED

Para o caso atual:

1. **Releia o trecho exato** do arquivo de produção e do arquivo de teste que vai tocar (não confie na memória do Passo 4 — o contexto pode ter sido comprimido)
2. Escreva **um** teste que descreva o comportamento desejado
   - Nome que lê como especificação (ex: `rejeita senha com menos de 8 caracteres`)
   - Estrutura arrange-act-assert explícita
   - Sem lógica condicional dentro do teste
   - Asserção específica: o valor esperado, não apenas "não lançou erro"
3. **Execute só esse teste** e confirme que falha
4. **Confirme que falha pelo motivo certo** — pela asserção, não por erro de import, de sintaxe ou de setup. Se falhou por outro motivo, corrija o teste e rode de novo.

Se o teste passar sem nenhuma implementação: o comportamento já existe (remova o teste se for duplicata, ou refine a asserção até ela ser significativa).

## Passo 8 — Ciclo GREEN

Escreva o **mínimo** de código de produção para o teste passar.

- Nada de generalização especulativa, nada de funcionalidade não exigida por um teste
- Siga as convenções do `AGENTS.md`
- **Respeite a Arquitetura de Camadas**: validação de forma em DTOs, regra de negócio em services, acesso a dados em repositories, orquestração em handlers. Nunca atravesse camadas — chame pela interface
- Se a camada necessária ainda não existe (ex: primeira repository), crie-a na pasta definida pelo `AGENTS.md`
- Se o `AGENTS.md` não tiver a seção "Arquitetura de Camadas", siga o padrão dos arquivos vizinhos e sugira ao usuário rodar `/centaur-driven-start-project`

Execute o teste e confirme que passa. Depois rode **a suíte inteira** e confirme que nada regrediu.

## Passo 9 — Ciclo REFACTOR

Com a suíte verde, melhore o que ficou feio — no código **e nos testes**:

- Duplicação, nomes ruins, função longa, aninhamento profundo
- Setup repetido nos testes → extraia fixture/factory/helper
- Números mágicos → constantes nomeadas

Regras: refatore só o que a mudança atual tocou (não faça faxina fora do escopo), e rode a suíte depois de cada refatoração. Se ficou vermelho, reverta a refatoração — não conserte por cima.

## Passo 10 — Repetir

Volte ao Passo 7 com o próximo caso da lista, até todos os critérios de aceite estarem cobertos por testes verdes.

## Passo 11 — Validar cobertura e qualidade

1. **Suíte completa**: execute todos os testes do projeto. Tudo verde.
2. **Cobertura**: se o projeto tiver comando de cobertura, execute e analise o resultado **das linhas que você tocou** (não da base inteira).
   - Alvo: 100% nos caminhos críticos que você implementou (autenticação, pagamento, validação, cálculo)
   - Reporte cobertura de **branch**, não só de linha — linha coberta com branch descoberto é falso conforto
   - Toda linha nova descoberta é um caso de teste faltando: escreva o teste ou justifique explicitamente na documentação
3. **Lint / type-check**: se existir, execute.
4. **Revisão de camadas**: confirme que nenhuma mudança violou a Arquitetura de Camadas.
5. **Qualidade dos testes** — revise a suíte nova contra estes cheiros:
   - Teste que depende da ordem de execução ou de estado deixado por outro teste
   - Teste sem asserção, ou com asserção que passaria com qualquer valor
   - Mock do próprio objeto sob teste
   - Dependência de data/hora real, aleatoriedade ou rede
   - Teste lento (unitário acima de ~100ms sem motivo)

Corrija tudo antes de documentar.

## Passo 12 — Determinar número da implementação

Execute exatamente este comando para encontrar o último número:

```
ls .claude/implements/ | grep -E '^[0-9]{4}$' | sort | tail -1
```

- Se retornar um número (ex: `0003`), o próximo é esse + 1 (ex: `0004`)
- Se retornar vazio, começa em `0001`
- Formate sempre com 4 dígitos: `0001`, `0002`, `0042`, `0100`

**Reserve o número imediatamente** criando a pasta com `mkdir .claude/implements/XXXX` (sem `-p`). Se falhar porque a pasta já existe — acontece quando outra task roda em paralelo via `/centaur-driven-run` —, incremente e tente de novo. O número só é seu depois que o `mkdir` tiver sucesso.

## Passo 13 — Documentar a implementação

Crie `.claude/implements/XXXX/README.md`:

```markdown
# [XXXX] [Título curto e descritivo da implementação]

**Data:** [data de hoje]
**Status:** Concluído
**Modo:** TDD
**Spec:** [se veio de uma spec: `.claude/specs/YYYY/` — Task NN. Caso contrário, omita esta linha]

## Solicitação
[O que o usuário pediu, com as palavras dele]

## Contexto
[Por que essa mudança era necessária, qual problema resolve]

## Critérios de aceite
[A lista de comportamentos observáveis derivada no Passo 3]

## Ciclos TDD
| # | Caso de teste | Arquivo de teste | Código que passou a existir |
|---|---------------|------------------|------------------------------|
| 1 | [nome do teste] | `caminho/do/teste.ext` | [o que foi implementado] |

## O que foi feito
[Descrição objetiva das mudanças realizadas]

## Arquivos modificados
- `caminho/do/arquivo.ext` — [o que mudou]

## Arquivos criados
- `caminho/novo.ext` — [para que serve]

## Decisões técnicas
[Por que cada decisão foi tomada dessa forma e não de outra — incluindo estratégia de mock e o que foi deixado deliberadamente sem teste]

## Como validar
[Comando exato para rodar os testes desta implementação]

## Resultado da validação
[Comando executado + resultado real: N testes passando, cobertura de linha/branch nos arquivos tocados, lint limpo]
```

## Passo 14 — Atualizar status.md

Adicione uma linha na tabela de `.claude/implements/status.md`:

```
| XXXX | [Título] | [data] | Concluído | [lista de arquivos afetados] |
```

## Passo 14b — [modo spec] Atualizar a spec

Se a implementação veio de uma spec:

1. Marque a task no **Checklist de conclusão** de `.claude/specs/YYYY/README.md`:
   `- [x] Task NN — [Título] → implements/XXXX`
2. Se **todas** as tasks estiverem marcadas, mude o status da spec para `Concluída` e atualize `.claude/specs/index.md`
3. Se a task ficou bloqueada, anote o motivo ao lado dela e mantenha a spec `Em andamento`

## Passo 15 — Atualizar AGENTS.md se necessário

Se a implementação adicionou funcionalidade relevante, mudou arquitetura, introduziu dependência importante, ou **estabeleceu a infraestrutura de testes do projeto** (framework, comando, convenção de nomes) → atualize a seção relevante do `AGENTS.md`. Correção interna sem impacto na visão geral não precisa.

## Passo 16 — Informar o usuário

Confirme com:
- O que foi feito (resumo de 2-3 linhas)
- Quantos ciclos red-green-refactor foram executados
- Resultado real da validação: testes passando, cobertura de linha e branch dos arquivos tocados
- Número da implementação (ex: "Documentado em `.claude/implements/0003/`")
- **[modo spec]** Qual task da spec foi concluída e quantas restam
