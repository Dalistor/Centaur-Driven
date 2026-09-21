---
name: centaur-driven-spec
description: Decompõe uma demanda grande em tasks atômicas por camada, salvas em .centaur/specs/, prontas para execução orquestrada com centaur-driven-run
version: 1.9.1
invocable: true
author: user
metadata:
  dependencies: clean-code
---

# centaur-driven-spec

## Escopos e equipe

Antes do fluxo, leia o [contrato de módulos e equipe](../centaur-driven-graphify/references/team-workspace.md). Ele define resolução de caminhos, IDs qualificados, responsabilidade, concorrência e estados. Os exemplos legados abaixo usam o escopo selecionado; aplique o contrato também aos comandos e templates.

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Leia `references/architecture.md` da dependência para decompor responsabilidades e explicitar a direção das dependências. Registre no contexto técnico da spec que cada executor deve carregar `clean-code`. Preserve os modos TDD/direto e planeje apenas as camadas necessárias à demanda.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

Você é um engenheiro sênior responsável por decompor uma solicitação complexa em tasks atômicas e independentes, documentadas em um arquivo de spec que será executado por subagentes via `/centaur-driven-tdd` (tasks com comportamento testável) ou `/centaur-driven-implement` (tasks estruturais).

## Passo 1 — Ler o contexto do projeto

Leia obrigatoriamente:
1. `AGENTS.md` na raiz do projeto (visão geral, arquitetura, regras, restrições)
2. `.centaur/implements/status.md` (histórico de implementações — evita duplicar o que já foi feito). Se existir `.centaur/implements/arquivo.md`, o histórico antigo está lá; consulte quando a demanda parecer tocar área já mexida no passado

Se `AGENTS.md` não existir, avise o usuário:
> "Este projeto ainda não foi documentado. Execute `/centaur-driven-start-project` primeiro."

Dê atenção especial a duas seções do `AGENTS.md`: **Arquitetura de Camadas**, que guia a decomposição no Passo 5, e **Vocabulário e Idioma do Código**, cujos termos você deve usar ao escrever as instruções das tasks — o subagente nomeia o código com as palavras que a instrução usar. Se a seção não existir, sugira ao usuário rodar `/centaur-driven-start-project` para formalizá-la antes de criar a spec (ou acorde as camadas com ele agora e inclua no contexto técnico da spec).

## Passo 2 — Entender a solicitação

Leia com atenção o que o usuário pediu. Identifique:
- O objetivo final (o que deve existir/funcionar ao término)
- O escopo: quais partes do sistema serão afetadas
- Dependências conhecidas entre as partes

## Passo 3 — Explorar o código relevante

Antes de explorar o código, leia `docs/system/Visão geral.md` e os Drafts, Fluxos, Perspectivas e Decisões relevantes, quando existirem. Eles são a referência humana da demanda; use o Graphify para localizar arquivos candidatos, confirme detalhes no código e separe hipótese de comportamento implementado. Registre no contexto técnico da própria `.centaur/specs/YYYY/README.md` quais notas originaram a spec. Após salvar a spec e seu índice, sincronize os documentos no Graphify; o README continua sendo a fonte canônica de status.

Localize e leia os arquivos que fornecem contexto suficiente para decompor a solicitação:
- Pontos de entrada relacionados
- Módulos, serviços ou componentes que serão afetados
- Testes existentes na área

Não implemente nada ainda — apenas mapeie o território.

## Passo 4 — Tirar todas as dúvidas

Antes de criar a spec, liste todas as ambiguidades:
- Comportamentos não especificados
- Decisões de design que dependem de preferência do usuário
- Edge cases que mudam o escopo

Apresente as dúvidas de uma vez e aguarde as respostas antes de continuar.

## Passo 5 — Decompor em tasks

Com todas as dúvidas resolvidas, quebre a solicitação em tasks **atômicas e executáveis**:

Critérios para uma boa task:
- Tem um único objetivo claro
- Pode ser implementada sem depender de tasks ainda não concluídas (ou tem dependência explícita)
- Pode ser descrita em 2-4 frases que, ao serem passadas à skill de execução (`/centaur-driven-tdd` ou `/centaur-driven-implement`), produzem o resultado esperado
- Não é grande demais (evite tasks que mexem em mais de ~4 arquivos distintos — o mesmo limiar que faz `/centaur-driven-implement` recusar uma solicitação)

**Decomponha ao longo da Arquitetura de Camadas do `AGENTS.md`.** Uma feature vertical vira uma sequência de tasks por camada, de dentro para fora — a ordem natural de dependência:

1. Models / entidades de domínio
2. DTOs / contratos de entrada e saída
3. Repositories / acesso a dados (migrations incluídas)
4. Services / regras de negócio
5. Handlers / controllers / rotas
6. Testes de integração da feature completa

**Marque cada task como TDD ou direta — com proporcionalidade.** `**Modo:** TDD` é reservado a tasks com **regra de negócio real**: decisão, cálculo, validação com consequência, correção de bug. Ser tecnicamente testável não basta — mapeamento direto de campos, fiação de rota, scaffold, migration, config e CRUD sem regra vão de `**Modo:** direto` para `/centaur-driven-implement`, mesmo que dê para escrever teste. Teste desnecessário custa em toda execução futura da suíte.

Não crie tasks separadas de "escrever testes da camada X": o teste pertence à task que implementa o comportamento. A task de **testes de integração é opcional** — inclua só quando existe um fluxo ponta a ponta com valor real que nenhuma task unitária cobre (ex: requisição atravessando handler → service → repository com regra no meio). Não a inclua por hábito.

Toda task TDD deve trazer, na instrução do subagente, os **critérios de aceite em forma de comportamentos observáveis** — é o que o subagente vai transformar em casos de teste sem poder perguntar nada. **Dimensione a lista você mesmo, aqui:** caminho crítico (dinheiro, auth, validação de entrada externa) recebe caminho feliz + erros + bordas; comportamento comum recebe caminho feliz + erros prováveis; nada além disso. O subagente implementa exatamente os casos listados — se você listar bordas exóticas, ele vai testá-las; liste só o que importa.

Nem toda spec precisa de todas as camadas — inclua só as afetadas. Tasks de camadas independentes (ex: dois repositories que não se tocam) podem ser marcadas como paralelizáveis. Cada task deve declarar quais camadas toca, e a instrução deve proibir explicitamente tocar camadas fora do escopo dela.

Ordene as tasks pela sequência de execução recomendada. Marque dependências explicitamente quando existirem.

## Passo 6 — Determinar número da spec

Em todas as skills centaur, `YYYY` é o número da spec e `XXXX` o número de uma implementação.

Para IDs sequenciais legados, este comando encontra o último número; adapte o caminho ao escopo. Em clones independentes use o sufixo único definido no contrato:

```
ls .centaur/specs/ 2>/dev/null | grep -E '^[0-9]{4}$' | sort | tail -1
```

- Se retornar um número (ex: `0002`), o próximo é esse + 1 (ex: `0003`)
- Se retornar vazio ou o diretório não existir, começa em `0001`
- Formate a base numérica com 4 dígitos: `0001`, `0002`, `0042`, `0100`

Crie o diretório `.centaur/specs/` se não existir.

## Passo 7 — Criar o arquivo de spec

Obtenha a data de hoje com `date +%F` — não a preencha de memória.

Reserve atomicamente a pasta `.centaur/specs/YYYY/` com `mkdir` sem `-p` (se existir, escolha outro ID). Crie então o arquivo `.centaur/specs/YYYY/README.md`:

```markdown
# [YYYY] [Título curto e descritivo]

**Data:** [saída de `date +%F`]
**Status:** Pendente
**Escopo:** [escopo]
**Responsável:** [pessoa/equipe]
**Spec mestre:** [ID qualificado ou —]
**Specs filhas:** [IDs qualificados ou —]
**Dependências:** [IDs qualificados ou —]
**Solicitação original:** [o que o usuário pediu, com as palavras dele]

## Objetivo

[O que deve existir/funcionar ao término de todas as tasks]

## Contexto técnico

[Arquivos, módulos e decisões relevantes para quem vai executar as tasks]

**Dependência de execução:** cada executor deve carregar a skill `clean-code` e as referências pertinentes, seguindo o contrato de `/centaur-driven-tdd` ou `/centaur-driven-implement`. Preserve o Modo de cada task e registre decisões em `.centaur/`, sem escritas em `.clean/`.

## Tasks

### Task 01 — [Título]

**Objetivo:** [O que esta task entrega]
**Camadas:** [ex: Models, DTOs]
**Modo:** [TDD | direto]
**Depende de:** —
**Instrução para o subagente:**
> Spec YYYY — Task 01: [Instrução completa e autocontida. Como o subagente não pode fazer perguntas, inclua TODAS as decisões já tomadas: comportamento esperado, edge cases, arquivos envolvidos e critério de sucesso. Se `Modo: TDD`, liste os critérios de aceite como comportamentos observáveis — dimensionados pela proporcionalidade do Passo 5, só o que importa — e comece a instrução com "Implemente por TDD:". Termine com: "Toque apenas nas camadas [X]; não modifique arquivos de outras camadas."]

---

### Task 02 — [Título]

**Objetivo:** [O que esta task entrega]
**Camadas:** [ex: Services]
**Modo:** [TDD | direto]
**Depende de:** Task 01
**Instrução para o subagente:**
> Spec YYYY — Task 02: [Instrução completa e autocontida, com todas as decisões já tomadas e a restrição de camadas.]

---

[... demais tasks ...]

## Como executar

Recomendado — orquestração automática:

```
/centaur-driven-run YYYY
```

O run lança um subagente por task, paraleliza as independentes, respeita as dependências e consolida checklist, status e `status.md` ao fim de cada onda.

Alternativa manual — para cada task, abra um subagente e invoque a skill correspondente ao `Modo` da task:

```
/centaur-driven-tdd [instrução da task, se Modo: TDD]
/centaur-driven-implement [instrução da task, se Modo: direto]
```

Execute as tasks na ordem indicada, respeitando as dependências. Na execução manual, o subagente **não** escreve neste README nem no `status.md` — ao fim de cada task, quem orquestra marca o checklist, adiciona a linha no `status.md` e atualiza o status da spec com base no relatório do subagente.

## Ciclo de vida

- `Pendente` → nenhuma task iniciada
- `Em andamento` → definido por quem orquestra (`/centaur-driven-run` ao montar o plano, ou quem executa manualmente ao iniciar a primeira task)
- `Concluída` → definido por quem orquestra quando a última task do checklist for marcada
- Tasks bloqueadas ficam anotadas no checklist com o motivo

## Checklist de conclusão

_Atualizado por quem orquestra a execução (`/centaur-driven-run` ou execução manual), a partir do relatório de cada subagente._

- [ ] Task 01 — [Título]
- [ ] Task 02 — [Título]
[... demais tasks ...]
```

## Passo 8 — Atualizar o índice de specs

Se não existir, crie `.centaur/specs/index.md`:

```markdown
# Specs

| # | Título | Data | Status | Tasks |
|---|--------|------|--------|-------|
```

Adicione uma linha:

```
| YYYY | [Título] | [data] | Pendente | [N tasks] |
```

Se a tabela ainda contiver uma linha placeholder (`| — | — | — | — | — |`), remova-a ao inserir a primeira linha real.

## Passo 9 — Informar o usuário

Confirme a criação com:
- Número e título da spec (ex: "Spec criada em `.centaur/specs/0001/`")
- Quantas tasks foram criadas e a ordem de execução recomendada
- Como executar: `/centaur-driven-run YYYY` orquestra tudo automaticamente (subagentes, paralelismo, dependências, checklist). A alternativa manual é abrir um subagente por task com a skill do `Modo` dela (`/centaur-driven-tdd` ou `/centaur-driven-implement`) e a instrução da task

Exemplo de mensagem final:

> Spec `0001` criada com 4 tasks (Task 02 e 03 paralelizáveis). Para executar:
>
> `/centaur-driven-run 0001`

Ao concluir o planejamento, sincronize os documentos pela skill Graphify. Para demandas entre módulos, registre primeiro a mestre e as filhas com links recíprocos; só libere execução após conferir todas as referências.
