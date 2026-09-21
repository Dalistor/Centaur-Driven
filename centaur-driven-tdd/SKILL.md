---
name: centaur-driven-tdd
description: Implementa uma mudança guiada por testes (red-green-refactor), com casos de teste derivados dos critérios de aceite, análise de cobertura e documentação em .centaur/implements/. Use quando a mudança tem regra de negócio testável.
version: 1.6.0
invocable: true
author: user
metadata:
  dependencies: clean-code
---

# centaur-driven-tdd

## Escopos e equipe

Antes do fluxo, leia o [contrato de módulos e equipe](../centaur-driven-obsidian/references/team-workspace.md). Ele define resolução de caminhos, IDs qualificados, responsabilidade, concorrência e estados. Os exemplos legados abaixo usam o escopo selecionado; aplique o contrato também aos comandos e templates.

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Leia também `references/session-protocol.md` e `references/tests.md` da dependência. Aplique os critérios de responsabilidade, localização e dependências no GREEN e de clareza no REFACTOR. Preserve RED → GREEN → REFACTOR e a proporcionalidade dos critérios de aceite desta skill.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

## Integração com Obsidian

Depois de validar o comportamento, use `centaur-driven-obsidian` para atualizar as notas e fluxos afetados quando o vault estiver configurado. O README da implementação continua sendo o registro obrigatório.

Você é um engenheiro de software sênior conduzindo uma implementação por Test Driven Development. O teste vem primeiro, sempre. Siga cada passo na ordem — não pule etapas.

**Escopo desta skill:** mudanças pontuais com comportamento testável — regra de negócio, validação, cálculo, transformação de dados, correção de bug. Se a demanda for grande, planeje com `/centaur-driven-spec` e execute com `/centaur-driven-run`.

**Quando NÃO usar TDD:** mudança puramente estrutural (renomear, mover arquivo), ajuste de configuração, mudança só de UI/estilo, **comportamento trivial mesmo que testável** (mapeamento direto de campos, passthrough, fiação sem lógica), projeto sem nenhuma infraestrutura de teste e sem autorização do usuário para criá-la. Nesses casos, use `/centaur-driven-implement`.

## Regras invioláveis

1. **Nunca escreva código de produção sem um teste falhando que o exija.**
2. **Nunca pule o RED.** Rode o teste e veja falhar antes de implementar. Teste que passa de primeira é teste errado — investigue.
3. **Teste comportamento, não implementação.** Nada de asserção sobre variável privada, ordem de chamadas internas ou detalhe de estrutura interna.
4. **Um comportamento por teste**, com nome que lê como especificação.
5. **Nunca afrouxe um teste para fazê-lo passar.** Se o teste está errado, corrija o teste e explique por quê na documentação.
6. **Não invente cobertura.** Só reporte números que você realmente executou.

## Passo 1 — Ler o contexto do projeto

Leia obrigatoriamente:
1. `AGENTS.md` na raiz (visão geral, arquitetura, **Arquitetura de Camadas**, **Vocabulário e Idioma do Código**, regras)
2. `.centaur/implements/status.md` (histórico de implementações)

Se `AGENTS.md` não existir, avise:
> "Este projeto ainda não foi documentado. Execute `/centaur-driven-start-project` primeiro para que eu tenha contexto suficiente para implementar com segurança."

Se `.centaur/implements/status.md` não existir, crie a estrutura (`.centaur/implements/` e `status.md` vazio).

## Passo 2 — Detectar a stack de testes

Identifique o framework, o comando de execução e a ferramenta de cobertura já usados pelo projeto:

- **Onde procurar:** `package.json` (scripts + devDependencies), `pytest.ini` / `pyproject.toml` / `setup.cfg`, `Makefile`, `pom.xml` / `build.gradle`, `Gemfile`, `go.mod`, arquivos `*.config.{js,ts}` de test runner, pasta de testes existente
- **Frameworks comuns:** Jest, Vitest, Mocha (JS/TS) · Pytest, unittest (Python) · JUnit 5 (Java) · RSpec (Ruby) · `go test` (Go) · Japa (AdonisJS)
- **Cobertura:** Istanbul/nyc/c8 (JS), coverage.py / pytest-cov (Python), JaCoCo (Java)

Registre: comando de teste, comando de teste de arquivo único (para o loop rápido), comando de cobertura, convenção de nome e local dos arquivos de teste.

**Se o projeto não tem infraestrutura de teste:** pare e pergunte ao usuário se pode configurá-la (proponha o framework padrão da stack). Sem resposta afirmativa, não siga com TDD — oriente `/centaur-driven-implement`.
**[modo spec]** Se não houver infraestrutura de teste e a task não autorizar criá-la, siga o procedimento de bloqueio descrito no Passo 5 e encerre.

## Passo 3 — Entender a solicitação e derivar critérios de aceite

Traduza o pedido em uma lista de **comportamentos observáveis e verificáveis**. Cada item vira pelo menos um teste.

**Proporcionalidade — a regra que dimensiona a lista:** a profundidade da cobertura acompanha o risco do comportamento, não o ritual.

- **Caminho crítico** (dinheiro, autenticação/autorização, validação de entrada externa, cálculo com regra de negócio, dado que não pode corromper) → cobertura completa: caminho feliz, erros e bordas.
- **Comportamento comum** (regra de negócio ordinária, transformação com algumas decisões) → caminho feliz + os erros e bordas que têm chance real de acontecer neste projeto.
- **Comportamento trivial** (mapeamento direto de campos, passthrough, formatação simples, getter com lógica mínima) → 1-2 testes de caminho feliz bastam. Não infle a lista para parecer rigoroso.

As dimensões abaixo são um **checklist para considerar, não uma obrigação por item**. Percorra-as e inclua o que for relevante para o risco do caso:
- **Caminho feliz** — o uso esperado, com dados válidos
- **Erros** — entrada inválida, dependência falhando, estado inconsistente, autorização negada
- **Bordas** — vazio, nulo, zero, limites e vizinhança do limite, coleção com 1 elemento, caracteres especiais/unicode
- **Efeitos colaterais** — o que deve ser persistido, emitido ou chamado (e o que **não** deve)

Ao apresentar a lista (Passo 5), diga qual nível de proporcionalidade aplicou e por quê — o usuário pode pedir mais ou menos.

**Detectar modo spec:** se a solicitação começar com `Spec YYYY — Task NN` (ou mencionar uma spec/task de `.centaur/specs/`), você está executando uma task planejada por `/centaur-driven-spec`, provavelmente como subagente. Em todas as skills centaur, `YYYY` é sempre o número da spec e `XXXX` o número da implementação. Leia `.centaur/specs/YYYY/README.md` inteiro (Objetivo e Contexto técnico fazem parte do seu contexto). **Não edite o README da spec nem o `index.md`** (status, checklist) — quem consolida esses arquivos é o orquestrador, com base no seu relatório final.

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

<!-- [modo spec] Mantenha este bloco sincronizado com centaur-driven-implement, Passo 4 -->
**[modo spec]** Não pergunte nada — as decisões já foram resolvidas na criação da spec e, como subagente, você não tem canal com o usuário. Se encontrar ambiguidade que **realmente impede** a implementação, **pare sem implementar**:
1. Reserve um número de implementação conforme o Passo 12
2. Crie `.centaur/implements/XXXX/README.md` mínimo documentando o bloqueio:

```markdown
# [XXXX] [Título da task] — Bloqueado

**Data:** [saída de `date +%F`]
**Status:** Bloqueado
**Modo:** TDD
**Spec:** `.centaur/specs/YYYY/` — Task NN

## Motivo do bloqueio
[O que impede a implementação, com referência a arquivo/linha quando aplicável]

## O que destrava
[Que decisão ou correção o usuário precisa tomar]
```

3. Encerre reportando o motivo do bloqueio e o número `XXXX` — **não** edite a spec nem o `status.md`; o orquestrador registra o bloqueio.

O mesmo vale para o bloqueio por falta de infraestrutura de teste do Passo 2.

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

<!-- Mantenha este passo sincronizado com centaur-driven-implement, Passo 7 -->
Com a suíte verde, releia o que você escreveu como se estivesse chegando nele pela primeira vez, sem o contexto desta conversa. O código é a documentação principal do projeto — corrija o que só faz sentido para quem acabou de escrever, no código **e nos testes**.

**Critério de bom nome:**
- Revela a **intenção** — o que a coisa faz ou representa, não como está implementada (`precoComDesconto`, não `p2`; `buscarPorEmail`, não `query2`)
- Usa o **vocabulário do domínio** do projeto — a palavra registrada na seção "Vocabulário e Idioma do Código" do `AGENTS.md` (ou, se a seção não existir, a que o resto do código já usa). Um conceito, um nome, no código inteiro. O idioma dos identificadores, dos comentários e dos nomes de teste também sai dessa seção
- Sem abreviação (`calc`, `usr`, `tmp`, `res`) e sem sufixo redundante de tipo (`listaDeUsuariosArray`, `DataManager`)
- Função é verbo, valor é substantivo, booleano lê como afirmação (`estaAtivo`, `temPermissao`)
- **Nome que precisa de comentário para ser entendido é nome errado** — troque o nome, não adicione o comentário

**Onde o "porquê" mora — nesta ordem de precedência:**
1. **No próprio código**, sempre que couber: constante nomeada no lugar do número/string solto, função extraída cujo nome diz a intenção, tipo ou enum no lugar de string livre, guarda explícita no lugar de condição implícita
2. **Em comentário curto ao lado**, quando o porquê é externo ao código e não há como expressá-lo nele: regra de negócio arbitrária, limite imposto por uma API, workaround de bug de terceiro, decisão contraintuitiva. Comentário explica **por que**, nunca **o que** a linha faz
3. **No README da implementação** (Passo 13), só o que não cabe no arquivo: alternativas descartadas, trade-off de arquitetura, contexto histórico

Nunca use o README como substituto de código claro: quem abre o fonte não lê `.centaur/`, e o README envelhece enquanto o código muda. O nome do teste é parte dessa documentação — ele é a especificação executável do comportamento.

**Cheiros que este ciclo precisa pegar:**
- Nome que não revela intenção, ou que usa palavra diferente da que o resto do projeto usa para o mesmo conceito
- Duplicação
- Número ou string mágico sem constante nomeada
- Função que faz mais de uma coisa (se descrever exige um "e", separe)
- Aninhamento além de 2-3 níveis — inverta a condição, extraia função ou use retorno antecipado
- Parâmetro booleano que troca o comportamento da função (dois nomes explícitos são mais legíveis)
- Comentário que narra a linha seguinte — apague, ou renomeie o que está sendo narrado
- Código morto ou comentado — apague, o histórico está no Git
- Setup repetido nos testes → extraia fixture/factory/helper

Regras: refatore só o que a mudança atual tocou (não faça faxina fora do escopo), e rode a suíte depois de cada refatoração. Se ficou vermelho, reverta a refatoração — não conserte por cima.

## Passo 10 — Repetir

Volte ao Passo 7 com o próximo caso da lista, até todos os critérios de aceite estarem cobertos por testes verdes.

## Passo 11 — Validar cobertura e qualidade

1. **Suíte completa**: execute todos os testes do projeto. Tudo verde.
2. **Cobertura**: se o projeto tiver comando de cobertura, execute e analise o resultado **das linhas que você tocou** (não da base inteira).
   - Alvo **proporcional** (mesma régua do Passo 3): 100% de branch nos caminhos críticos que você implementou (autenticação, pagamento, validação, cálculo). No restante, cubra o que importa — não persiga número.
   - Reporte cobertura de **branch**, não só de linha — linha coberta com branch descoberto é falso conforto
   - Linha nova descoberta em caminho crítico é um caso de teste faltando: escreva o teste. Em código trivial, uma justificativa de uma frase na documentação basta — não escreva teste só para fechar número.
3. **Lint / type-check**: se existir, execute.
4. **Revisão de camadas**: confirme que nenhuma mudança violou a Arquitetura de Camadas.
5. **Clareza**: confirme que o resultado final passa nos critérios do Passo 9 — os ciclos foram muitos e a última refatoração pode ter deixado nome ou estrutura para trás.
6. **Qualidade dos testes** — revise a suíte nova contra estes cheiros:
   - Teste que depende da ordem de execução ou de estado deixado por outro teste
   - Teste sem asserção, ou com asserção que passaria com qualquer valor
   - Mock do próprio objeto sob teste
   - Dependência de data/hora real, aleatoriedade ou rede
   - Teste lento (unitário acima de ~100ms sem motivo)

Corrija tudo antes de documentar.

## Passo 12 — Determinar número da implementação

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

Este README é a trilha de auditoria, **não** o lugar onde o código é explicado. O que dá para expressar no próprio código já foi expresso no Passo 9; aqui fica só o que não cabe num arquivo de código.

Crie `.centaur/implements/XXXX/README.md`:

```markdown
# [XXXX] [Título curto e descritivo da implementação]

**Data:** [saída de `date +%F`]
**Status:** Concluído
**Modo:** TDD
**Spec:** [se veio de uma spec: `.centaur/specs/YYYY/` — Task NN. Caso contrário, omita esta linha]

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
[Só o que não cabe no código: alternativas descartadas e por quê, trade-offs de arquitetura, estratégia de mock, o que foi deixado deliberadamente sem teste. Se a justificativa cabia numa constante nomeada ou num comentário ao lado da linha, o lugar dela era lá — não aqui]

## Como validar
[Comando exato para rodar os testes desta implementação]

## Resultado da validação
[Comando executado + resultado real: N testes passando, cobertura de linha/branch nos arquivos tocados, lint limpo]
```

## Passo 14 — Atualizar status.md

**[modo spec]** Pule este passo — o orquestrador escreve a linha no `status.md` com base no seu relatório final. Escritas paralelas de subagentes no mesmo arquivo se sobrescrevem.

Adicione uma linha na tabela de `.centaur/implements/status.md`:

```
| XXXX | [Título] | [data] | Concluído | [lista de arquivos afetados] |
```

Se a tabela ainda contiver a linha placeholder (`| — | — | — | — | — |`), remova-a ao inserir a primeira linha real.

## Passo 15 — Atualizar AGENTS.md se necessário

Se a implementação adicionou funcionalidade relevante, mudou arquitetura, introduziu dependência importante, **estabeleceu a infraestrutura de testes do projeto** (framework, comando, convenção de nomes), ou **estabeleceu um termo novo do domínio** que o código passou a usar → atualize a seção relevante do `AGENTS.md`. O termo novo vai para a seção "Vocabulário e Idioma do Código", para que a próxima implementação use a mesma palavra. Correção interna sem impacto na visão geral não precisa.

## Passo 16 — Sincronizar o Obsidian

Use `/centaur-driven-obsidian sincronizar XXXX` depois da validação. Registre capacidades e fluxos confirmados em linguagem humana; arquivos e testes são evidência, nunca o assunto principal. **[modo spec]** apenas reporte as notas afetadas para consolidação serial.

## Passo 17 — Informar o usuário

Confirme com:
- O que foi feito (resumo de 2-3 linhas)
- Quantos ciclos red-green-refactor foram executados
- Resultado real da validação: testes passando, cobertura de linha e branch dos arquivos tocados
- Número da implementação (ex: "Documentado em `.centaur/implements/0003/`")
- Notas do Obsidian atualizadas, ou pendência explícita quando o vault não estiver configurado

**[modo spec]** Encerre com um relatório estruturado — é dele que o orquestrador consolida a spec e o `status.md`:

```
Spec YYYY — Task NN: [Concluída | Bloqueada]
Implementação: XXXX
Título: [título usado no README da implementação]
Arquivos afetados: [lista]
Validação: [ciclos executados, testes passando, cobertura de linha/branch dos arquivos tocados]
Mapa: [caminho e resultado real; se bloqueada sem implementação, não aplicável]
Perspectivas afetadas: [ids de views existentes ou nenhuma; atualização reservada ao orquestrador]
[Se bloqueada: Motivo do bloqueio e o que destrava]
```
