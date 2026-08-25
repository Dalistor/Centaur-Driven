# Centaur

Conjunto de skills para o [Claude Code](https://claude.com/claude-code) que cria um fluxo de desenvolvimento documentado e rastreável: todo projeto tem contexto persistente, toda implementação fica registrada e demandas grandes são decompostas em tasks executadas por subagentes.

## Por que "centaur"?

Centauro: metade humano, metade máquina. Você toma as decisões — o Claude executa com contexto completo e deixa trilha de tudo o que fez.

## Instalação

Copie as pastas das skills para o diretório global de skills do Claude Code:

```bash
git clone https://github.com/Dalistor/Centaur-Driven.git
cp -r Centaur-Driven/centaur-driven-* ~/.claude/skills/
```

Reinicie sessões abertas do Claude Code para que as skills apareçam. Elas ficam disponíveis em **todos** os projetos.

> Se preferir instalar apenas em um projeto, copie as pastas para `.claude/skills/` na raiz do projeto.

## As skills

| Skill | O que faz |
|-------|-----------|
| `/centaur-driven-start-project` | Documenta o projeto: cria o `AGENTS.md` na raiz e inicializa as estruturas de implementações e specs |
| `/centaur-driven-check` | Responde perguntas sobre o projeto com base na documentação e no código — sem alterar nada |
| `/centaur-driven-tdd` | Mudanças pontuais com **comportamento testável**: teste antes do código, ciclo red-green-refactor, análise de cobertura |
| `/centaur-driven-implement` | Mudanças pontuais **estruturais, de configuração ou de UI** — e projetos sem infraestrutura de teste |
| `/centaur-driven-spec` | Decompõe uma demanda grande em tasks atômicas por camada, cada uma marcada como TDD ou direta, salvas em `.claude/specs/` |
| `/centaur-driven-run` | Executa uma spec: lança um subagente por task conforme o Modo, paraleliza as independentes e consolida o resultado |
| `/centaur-driven-mcp` | Busca a documentação de uma API externa em um MCP server e roteia a requisição para tdd, implement ou spec com esse contexto anexado |
| `/centaur-driven-deploy` | Configura deploy contínuo para uma VPS (GitHub Actions + SSH + rsync): gera a chave, valida o acesso, cadastra os secrets e acompanha o primeiro run |

## Fluxo de trabalho

### 1. Comece documentando o projeto

```
/centaur-driven-start-project
```

A skill varre o projeto, faz perguntas sobre o que não está evidente no código (propósito, arquitetura, convenções, restrições) e cria:

- `AGENTS.md` na raiz — contexto do projeto, lido pelas skills centaur no início de cada chat
- `.claude/implements/status.md` — histórico de implementações
- `.claude/specs/index.md` — índice de specs planejadas

Entre as perguntas está a **stack de testes** (framework, comando de rodar a suíte, local e convenção dos arquivos, meta de cobertura) — é o que decide se uma mudança futura vai por TDD ou não. Se o projeto ainda não tem testes, a skill pergunta se você quer adotar TDD dali em diante e com qual framework.

Também entre as perguntas está a **Arquitetura de Camadas**: se o projeto já segue um padrão (models, DTOs, handlers, repositories, services...), ela é documentada; se não segue, a skill propõe uma separação adequada à stack para você aprovar. O resultado vira uma tabela no `AGENTS.md` dizendo, para cada camada, sua pasta, sua responsabilidade e o que é proibido nela — e todas as implementações futuras obedecem a essa tabela.

### 2. Para mudanças com comportamento testável, use tdd

```
/centaur-driven-tdd adicionar validação de email no cadastro
```

Regra de negócio, validação, cálculo, transformação de dados, correção de bug — tudo que tem comportamento observável entra por aqui, e **o teste vem antes do código**.

A skill lê o contexto, detecta a stack de testes, transforma a solicitação em **critérios de aceite** (caminho feliz, erros, bordas), tira todas as dúvidas e então roda os ciclos: **RED** (escreve o teste, roda, vê falhar — teste que passa de primeira é teste errado), **GREEN** (o mínimo de código de produção para passar), **REFACTOR** (limpa com a suíte verde). Um ciclo por comportamento. No fim, analisa cobertura, valida lint e camadas, e documenta em `.claude/implements/XXXX/README.md` — incluindo a lista de ciclos executados.

### 3. Para mudanças estruturais, use implement

```
/centaur-driven-implement renomear a pasta de handlers para controllers
```

O implement cobre o que não faz sentido testar primeiro: renomear, mover arquivo, configuração, scaffold, mudança só de UI/estilo — e projetos que ainda não têm infraestrutura de teste. Lê o contexto, explora o código afetado, **tira todas as dúvidas antes de escrever qualquer linha**, implementa respeitando a Arquitetura de Camadas do `AGENTS.md` (regra de negócio em service, query em repository, handler fino), valida (testes, lint e revisão de violação de camadas) e documenta em `.claude/implements/XXXX/README.md`.

Se a mudança pedida tiver comportamento testável, ele mesmo redireciona para o `/centaur-driven-tdd`. Se a demanda for grande demais (muitas camadas, mais de ~4 arquivos), recusa e orienta a usar spec + run.

### 4. Para demandas grandes, use spec

```
/centaur-driven-spec migrar autenticação de sessão para JWT
```

A skill explora o código, resolve as ambiguidades com você **antes** de planejar e gera `.claude/specs/XXXX/README.md` com tasks atômicas e ordenadas. A decomposição segue as camadas do projeto, de dentro para fora — models, DTOs, repositories, services, handlers, testes de integração — e cada task declara quais camadas toca e proíbe tocar as demais, o que permite paralelizar tasks de camadas independentes. Cada instrução é autocontida, com todas as decisões já tomadas.

Cada task carrega também um campo **`Modo`**: `TDD` para as que têm comportamento testável (o teste nasce dentro da própria task, junto do código) e `direto` para as estruturais. Por isso não existe task de "escrever os testes da camada X" — o teste pertence à task que implementa o comportamento. Tasks `TDD` trazem os critérios de aceite já escritos como comportamentos observáveis, porque o subagente que as executa não pode perguntar nada.

### 5. Para executar a spec, use run

```
/centaur-driven-run 0001
```

O run é o orquestrador — e é **restrito a tasks de specs**: não implementa nada por conta própria e recusa qualquer pedido fora do que está planejado. Ele:

- Monta o plano em ondas — tasks com dependências satisfeitas rodam em paralelo, o resto aguarda — e apresenta o plano para você confirmar antes de iniciar
- Lança um subagente por task, escolhendo a skill pelo `Modo` da task (`TDD` → `/centaur-driven-tdd`, `direto` → `/centaur-driven-implement`) e passando a instrução da spec **verbatim** com o prefixo `Spec XXXX — Task NN`
- Esse prefixo ativa o **modo spec** da skill de execução dentro do subagente: não faz perguntas (as decisões já foram tomadas na spec), marca a task no checklist ao concluir e, quando a última fecha, muda a spec para `Concluída`
- Se uma task bloquear, pula as dependentes, continua as demais e reporta o que precisa da sua decisão
- Execução paralela é segura: cada subagente reserva seu número de implementação atomicamente (via `mkdir`), e ao fim de cada onda o run confere o checklist da spec e o `status.md`, reparando registros que se perderam em escritas simultâneas
- Execução é retomável: rodar `/centaur-driven-run 0001` de novo continua de onde parou

### 6. Para consultar, use check

```
/centaur-driven-check como funciona o fluxo de pagamento?
/centaur-driven-check o que ainda falta na spec 0001?
```

Responde com base no `AGENTS.md`, no histórico de implementações, nas specs e no código real — apontando arquivo e linha quando fizer sentido.

### 7. Para integrar com API externa, use mcp

```
/centaur-driven-mcp asaas-docs criar cobrança pix com split
/centaur-driven-mcp https://docs.asaas.com/mcp criar cobrança pix com split
```

Quando a mudança depende de uma API de terceiros, o problema não é implementar — é saber o que a API espera. O `mcp` é a ponte: consulta um [MCP server](https://modelcontextprotocol.io) com a documentação oficial do serviço, extrai só o que a requisição precisa (autenticação, endpoints, request, response, erros, restrições) e monta um **dossiê** factual.

Ele **não implementa nada**. Classifica a requisição e roteia: pergunta pura ele responde na hora; comportamento testável vai para o `/centaur-driven-tdd`; estrutural vai para o `/centaur-driven-implement`; integração grande vai para o `/centaur-driven-spec`. A requisição original segue verbatim — o dossiê é anexado, não substitui.

O dossiê tem um campo obrigatório **"Não encontrado no MCP"**, listando tudo que foi procurado e não achado. É o que impede o subagente de completar lacuna com memória: nada é afirmado sobre a API externa sem ter vindo de uma resposta real de uma tool do MCP.

A skill é **agnóstica de MCP** — descobre os disponíveis em tempo de execução. Se o primeiro argumento for uma URL em vez de um nome, ela detecta o transporte, pede sua confirmação e instala o MCP no escopo global antes de seguir. Credenciais nunca entram em código ou em arquivo versionado: só o **nome** da variável de ambiente é documentado.

### 8. Para colocar no ar, use deploy

```
/centaur-driven-deploy
```

Configura deploy contínuo do projeto para uma **VPS que você controla**, via GitHub Actions + SSH + rsync. A regra da skill é entregar deploy **configurado e testado**, não instruções: ela inspeciona o projeto, gera o par de chaves SSH, instala a pública na VPS, coleta o `known_hosts`, **audita o que o `rsync --delete` apagaria antes de rodar**, escreve o workflow, cadastra secrets e variables pelo `gh` CLI e acompanha o primeiro run. Ação manual só quando o passo exige acesso que ela não tem (senha de sudo na VPS, botão sem equivalente em CLI).

Antes de qualquer comando que altere a VPS ou o GitHub, ela mostra o comando e pede confirmação. No fim, documenta o que ficou fora do repositório e **como revogar** o acesso.

Cobre Docker/Docker Compose e processo direto (systemd, pm2). Fora do escopo: PaaS (Vercel, Railway, Fly), Kubernetes, registry de imagem, blue-green e rollback automático.

## Estrutura gerada no projeto

```
projeto/
├── AGENTS.md                        # Contexto do projeto (lido pelas skills a cada chat)
└── .claude/
    ├── implements/
    │   ├── status.md                # Tabela com todas as implementações
    │   └── 0001/README.md           # Documentação de cada implementação
    └── specs/
        ├── index.md                 # Tabela com todas as specs
        └── 0001/README.md           # Spec com tasks, dependências e checklist
```

## Ciclo de vida

```
/centaur-driven-start-project          (uma vez por projeto)
        │
        ├── depende de API externa ──► /centaur-driven-mcp ──► dossiê da doc oficial
        │                                       │
        │                                       └── anexa o dossiê e roteia para um dos três abaixo
        │
        ├── pontual + testável ──► /centaur-driven-tdd ──────► .claude/implements/XXXX/
        │
        ├── pontual estrutural ──► /centaur-driven-implement ─► .claude/implements/XXXX/
        │
        ├── demanda grande ──► /centaur-driven-spec ──► .claude/specs/XXXX/
        │                               │
        │                               └── /centaur-driven-run XXXX
        │                                       │
        │                                       └── N subagentes (modo spec), por Modo da task
        │                                               ├── Modo TDD    ──► /centaur-driven-tdd
        │                                               ├── Modo direto ──► /centaur-driven-implement
        │                                               │
        │                                               ├── implementa e documenta
        │                                               └── atualiza checklist da spec
        │
        └── subir para a VPS ──► /centaur-driven-deploy ──► .github/workflows/ + .claude/implements/XXXX/
```

Specs seguem os status `Pendente` → `Em andamento` → `Concluída`. Cada implementação referencia a spec/task de origem, e cada task concluída aponta para a implementação — trilha completa nos dois sentidos.
