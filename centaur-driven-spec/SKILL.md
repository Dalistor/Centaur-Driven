---
name: centaur-driven-spec
description: Decompõe uma demanda grande em tasks atômicas por camada, salvas em .claude/specs/, prontas para execução orquestrada com centaur-driven-run
version: 1.1.0
invocable: true
author: user
---

# centaur-driven-spec

Você é um engenheiro sênior responsável por decompor uma solicitação complexa em tasks atômicas e independentes, documentadas em um arquivo de spec que será executado por subagentes via `/centaur-driven-implement`.

## Passo 1 — Ler o contexto do projeto

Leia obrigatoriamente:
1. `CLAUDE.md` na raiz do projeto (visão geral, arquitetura, regras, restrições)
2. `.claude/implements/status.md` (histórico de implementações — evita duplicar o que já foi feito)

Se `CLAUDE.md` não existir, avise o usuário:
> "Este projeto ainda não foi documentado. Execute `/centaur-driven-start-project` primeiro."

Dê atenção especial à seção **Arquitetura de Camadas** do `CLAUDE.md` — ela guia a decomposição no Passo 5. Se a seção não existir, sugira ao usuário rodar `/centaur-driven-start-project` para formalizá-la antes de criar a spec (ou acorde as camadas com ele agora e inclua no contexto técnico da spec).

## Passo 2 — Entender a solicitação

Leia com atenção o que o usuário pediu. Identifique:
- O objetivo final (o que deve existir/funcionar ao término)
- O escopo: quais partes do sistema serão afetadas
- Dependências conhecidas entre as partes

## Passo 3 — Explorar o código relevante

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
- Pode ser descrita em 2-4 frases que, ao serem passadas ao `/centaur-driven-implement`, produzem o resultado esperado
- Não é grande demais (evite tasks que mexem em mais de 3-4 arquivos distintos)

**Decomponha ao longo da Arquitetura de Camadas do `CLAUDE.md`.** Uma feature vertical vira uma sequência de tasks por camada, de dentro para fora — a ordem natural de dependência:

1. Models / entidades de domínio
2. DTOs / contratos de entrada e saída
3. Repositories / acesso a dados (migrations incluídas)
4. Services / regras de negócio
5. Handlers / controllers / rotas
6. Testes de integração da feature completa

Nem toda spec precisa de todas as camadas — inclua só as afetadas. Tasks de camadas independentes (ex: dois repositories que não se tocam) podem ser marcadas como paralelizáveis. Cada task deve declarar quais camadas toca, e a instrução deve proibir explicitamente tocar camadas fora do escopo dela.

Ordene as tasks pela sequência de execução recomendada. Marque dependências explicitamente quando existirem.

## Passo 6 — Determinar número da spec

Execute exatamente este comando para encontrar o último número:

```
ls .claude/specs/ 2>/dev/null | grep -E '^[0-9]{4}$' | sort | tail -1
```

- Se retornar um número (ex: `0002`), o próximo é esse + 1 (ex: `0003`)
- Se retornar vazio ou o diretório não existir, começa em `0001`
- Formate sempre com 4 dígitos: `0001`, `0002`, `0042`, `0100`

Crie o diretório `.claude/specs/` se não existir.

## Passo 7 — Criar o arquivo de spec

Crie a pasta `.claude/specs/XXXX/` e o arquivo `.claude/specs/XXXX/README.md`:

```markdown
# [XXXX] [Título curto e descritivo]

**Data:** [data de hoje]
**Status:** Pendente
**Solicitação original:** [o que o usuário pediu, com as palavras dele]

## Objetivo

[O que deve existir/funcionar ao término de todas as tasks]

## Contexto técnico

[Arquivos, módulos e decisões relevantes para quem vai executar as tasks]

## Tasks

### Task 01 — [Título]

**Objetivo:** [O que esta task entrega]
**Camadas:** [ex: Models, DTOs]
**Depende de:** —
**Instrução para o subagente:**
> Spec XXXX — Task 01: [Instrução completa e autocontida. Como o subagente não pode fazer perguntas, inclua TODAS as decisões já tomadas: comportamento esperado, edge cases, arquivos envolvidos e critério de sucesso. Termine com: "Toque apenas nas camadas [X]; não modifique arquivos de outras camadas."]

---

### Task 02 — [Título]

**Objetivo:** [O que esta task entrega]
**Camadas:** [ex: Services]
**Depende de:** Task 01
**Instrução para o subagente:**
> Spec XXXX — Task 02: [Instrução completa e autocontida, com todas as decisões já tomadas e a restrição de camadas.]

---

[... demais tasks ...]

## Como executar

Recomendado — orquestração automática:

```
/centaur-driven-run XXXX
```

O run lança um subagente por task, paraleliza as independentes e respeita as dependências.

Alternativa manual — para cada task, abra um subagente e invoque:

```
/centaur-driven-implement [cole aqui a instrução da task]
```

Execute as tasks na ordem indicada, respeitando as dependências.

## Ciclo de vida

- `Pendente` → nenhuma task iniciada
- `Em andamento` → definido pelo /centaur-driven-implement ao iniciar a primeira task
- `Concluída` → definido pelo /centaur-driven-implement quando a última task do checklist for marcada
- Tasks bloqueadas ficam anotadas no checklist com o motivo

## Checklist de conclusão

_Atualizado automaticamente pelo /centaur-driven-implement ao concluir cada task._

- [ ] Task 01 — [Título]
- [ ] Task 02 — [Título]
[... demais tasks ...]
```

## Passo 8 — Atualizar o índice de specs

Se não existir, crie `.claude/specs/index.md`:

```markdown
# Specs

| # | Título | Data | Status | Tasks |
|---|--------|------|--------|-------|
```

Adicione uma linha:

```
| XXXX | [Título] | [data] | Pendente | [N tasks] |
```

## Passo 9 — Informar o usuário

Confirme a criação com:
- Número e título da spec (ex: "Spec criada em `.claude/specs/0001/`")
- Quantas tasks foram criadas e a ordem de execução recomendada
- Como executar: `/centaur-driven-run XXXX` orquestra tudo automaticamente (subagentes, paralelismo, dependências, checklist). A alternativa manual é abrir um subagente por task com `/centaur-driven-implement` e a instrução da task

Exemplo de mensagem final:

> Spec `0001` criada com 4 tasks (Task 02 e 03 paralelizáveis). Para executar:
>
> `/centaur-driven-run 0001`
