---
name: centaur-driven-spec
description: Decompõe uma demanda grande em tasks atômicas por camada, salvas em .centaur/specs/, prontas para execução orquestrada com centaur-driven-run
version: 1.13.0
invocable: true
author: user
metadata:
  dependencies: clean-code, graphify
  optional-dependencies: ai-memory
---

# centaur-driven-spec

## Memória de implementações

Leia o [contrato de memória](../centaur-driven-memory/references/contract.md) junto do contexto. O backend em `.centaur/workspace.json` determina o destino dos registros: `files` mantém os READMEs legados; `ai-memory` usa páginas verificadas e dispensa novas pastas `implements/`. As etapas de reserva numérica e escrita em `implements/status.md` abaixo são exclusivas de `files`; no modo ai-memory, aplique o registro, a fila e a consolidação definidos no contrato. Preserve specs e histórico existente.

## Contexto persistente — Graphify

Antes de explorar o projeto, siga o [contrato de contexto](../centaur-driven-graphify/references/context.md). Graphify (CLI `graphify` do pacote `graphifyy` + skill oficial `graphify`) é dependência obrigatória para localizar relações no código. Para histórico e decisões, consulte ai-memory quando configurado. Consulte o grafo antes de ampliar leituras; confirme as fontes relevantes. Aplique os limites de escrita e a sincronização definidos no contrato.

## Escopos e equipe

Antes do fluxo, leia o [contrato de módulos e equipe](../centaur-driven-graphify/references/team-workspace.md). Ele define resolução de caminhos, IDs qualificados, responsabilidade, concorrência e estados. Os exemplos legados abaixo usam o escopo selecionado; aplique o contrato também aos comandos e templates.

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Leia `references/architecture.md` da dependência para decompor responsabilidades e explicitar a direção das dependências. Registre no contexto técnico da spec que cada executor deve carregar `clean-code` e `graphify`, consultar o grafo e confirmar as fontes atuais. Preserve os modos TDD/direto e planeje apenas as camadas necessárias à demanda.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

Você é um engenheiro sênior responsável por decompor uma solicitação complexa em tasks atômicas e independentes, documentadas em um arquivo de spec que será executado por subagentes via `/centaur-driven-tdd` (tasks com comportamento testável) ou `/centaur-driven-implement` (tasks estruturais).

## Passo 1 — Ler o contexto do projeto

Leia `AGENTS.md` e recupere o contexto da solicitação pelo contrato Graphify acima. Consulte apenas os registros e trechos relevantes do escopo; para status, confirme o README canônico.

Se `AGENTS.md` não existir, avise o usuário:
> "Este projeto ainda não foi documentado. Execute `/centaur-driven-start-project` primeiro."

Dê atenção especial a duas seções do `AGENTS.md`: **Arquitetura de Camadas**, que guia a decomposição no Passo 5, e **Vocabulário e Idioma do Código**, incluindo o glossário nela vinculado. Consulte os termos relevantes e use-os ao escrever as instruções das tasks — o subagente nomeia o código com as palavras que a instrução usar. Se a seção não existir, sugira ao usuário rodar `/centaur-driven-start-project` para formalizá-la antes de criar a spec (ou acorde as camadas com ele agora e inclua no contexto técnico da spec).

## Passo 2 — Entender a solicitação

Leia com atenção o que o usuário pediu. Identifique:
- O objetivo final (o que deve existir/funcionar ao término)
- O escopo: quais partes do sistema serão afetadas
- Dependências conhecidas entre as partes

## Passo 3 — Explorar o código relevante

Consulte primeiro o Graphify e leia apenas a Visão geral, Drafts, Fluxos, Perspectivas e Decisões pertinentes à demanda em `docs/system/`. Eles são a referência humana da demanda; use o Graphify para localizar arquivos candidatos, confirme detalhes no código e separe hipótese de comportamento implementado. Registre no contexto técnico da própria `.centaur/specs/YYYY/README.md` quais notas originaram a spec. Após salvar a spec e seu índice, sincronize os documentos no Graphify; o README continua sendo a fonte canônica de status.

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

Toda task TDD deve trazer os **critérios de aceite em forma de comportamentos observáveis**, os riscos concretos e o que deve permanecer compatível. Aponte testes existentes relevantes e autorize sua manutenção nos arquivos da task. Critérios não impõem uma quantidade de testes novos: o executor reaproveita proteção existente, atualiza casos quando a regra muda e acrescenta somente lacunas distintas. Não prescreva baterias genéricas de erros/bordas, testes por camada ou metas de cobertura novas. Casos explicitamente exigidos continuam obrigatórios; dúvidas sobre o contrato bloqueiam a task, não autorizam remover proteção.

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
> Spec YYYY — Task 01: [Instrução completa e autocontida. Como o subagente não pode fazer perguntas, inclua TODAS as decisões já tomadas: comportamento esperado, riscos/limites relevantes, compatibilidade a preservar, arquivos de código/testes envolvidos e critério de sucesso. Se `Modo: TDD`, liste os critérios de aceite como comportamentos observáveis — conforme o Passo 5, permitindo reaproveitar/atualizar testes sem mudar requisitos — e comece a instrução com "Implemente por TDD:". Termine com: "Toque apenas nas camadas [X]; não modifique arquivos de outras camadas."]

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

Execute as tasks na ordem indicada, respeitando as dependências. Na execução manual, o subagente **não** escreve neste README nem no `status.md` — ao fim de cada task, quem orquestra marca o checklist, registra a referência da página (ai-memory) ou a linha no `status.md` (files) e atualiza o status da spec com base no relatório do subagente.

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

Após salvar o README e o índice, regenere `.centaur/andamento.html` conforme o contrato de contexto, para que o novo trabalho apareça no painel local.

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
