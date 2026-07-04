# Centaur

Conjunto de skills para o [Claude Code](https://claude.com/claude-code) que cria um fluxo de desenvolvimento documentado e rastreável: todo projeto tem contexto persistente, toda implementação fica registrada e demandas grandes são decompostas em tasks executadas por subagentes.

## Por que "centaur"?

Centauro: metade humano, metade máquina. Você toma as decisões — o Claude executa com contexto completo e deixa trilha de tudo o que fez.

## Instalação

Copie as pastas das skills para o diretório global de skills do Claude Code:

```bash
git clone https://github.com/SEU-USUARIO/centaur.git
cp -r centaur/centaur-driven-* ~/.claude/skills/
```

Reinicie sessões abertas do Claude Code para que as skills apareçam. Elas ficam disponíveis em **todos** os projetos.

> Se preferir instalar apenas em um projeto, copie as pastas para `.claude/skills/` na raiz do projeto.

## As skills

| Skill | O que faz |
|-------|-----------|
| `/centaur-driven-start-project` | Documenta o projeto: cria o `CLAUDE.md` na raiz e inicializa as estruturas de implementações e specs |
| `/centaur-driven-check` | Responde perguntas sobre o projeto com base na documentação e no código — sem alterar nada |
| `/centaur-driven-implement` | Mudanças **pontuais e diretas**: lê o contexto, tira dúvidas, aplica, valida e documenta em `.claude/implements/` |
| `/centaur-driven-spec` | Decompõe uma demanda grande em tasks atômicas por camada, salvas em `.claude/specs/` |
| `/centaur-driven-run` | Executa uma spec: lança um subagente por task, paraleliza as independentes e consolida o resultado |

## Fluxo de trabalho

### 1. Comece documentando o projeto

```
/centaur-driven-start-project
```

A skill varre o projeto, faz perguntas sobre o que não está evidente no código (propósito, arquitetura, convenções, restrições) e cria:

- `CLAUDE.md` na raiz — carregado automaticamente em todo chat futuro
- `.claude/implements/status.md` — histórico de implementações
- `.claude/specs/index.md` — índice de specs planejadas

Entre as perguntas está a **Arquitetura de Camadas**: se o projeto já segue um padrão (models, DTOs, handlers, repositories, services...), ela é documentada; se não segue, a skill propõe uma separação adequada à stack para você aprovar. O resultado vira uma tabela no `CLAUDE.md` dizendo, para cada camada, sua pasta, sua responsabilidade e o que é proibido nela — e todas as implementações futuras obedecem a essa tabela.

### 2. Para mudanças pontuais, use implement

```
/centaur-driven-implement adicionar validação de email no cadastro
```

A skill lê o contexto, explora o código afetado, **tira todas as dúvidas antes de escrever qualquer linha**, implementa respeitando a Arquitetura de Camadas do `CLAUDE.md` (regra de negócio em service, query em repository, handler fino), valida (testes, lint e revisão de violação de camadas) e documenta tudo em `.claude/implements/XXXX/README.md`: o que foi pedido, o que mudou, quais arquivos, quais decisões e como validar.

O implement é para **updates básicos** — correções, ajustes, features pequenas. Se a demanda for grande demais (muitas camadas, mais de ~4 arquivos), ele mesmo recusa e orienta a usar spec + run.

### 3. Para demandas grandes, use spec

```
/centaur-driven-spec migrar autenticação de sessão para JWT
```

A skill explora o código, resolve as ambiguidades com você **antes** de planejar e gera `.claude/specs/XXXX/README.md` com tasks atômicas e ordenadas. A decomposição segue as camadas do projeto, de dentro para fora — models → DTOs → repositories → services → handlers → testes de integração — e cada task declara quais camadas toca e proíbe tocar as demais, o que permite paralelizar tasks de camadas independentes. Cada instrução é autocontida, com todas as decisões já tomadas.

### 4. Para executar a spec, use run

```
/centaur-driven-run 0001
```

O run é o orquestrador — e é **restrito a tasks de specs**: não implementa nada por conta própria e recusa qualquer pedido fora do que está planejado. Ele:

- Monta o plano em ondas — tasks com dependências satisfeitas rodam em paralelo, o resto aguarda — e apresenta o plano para você confirmar antes de iniciar
- Lança um subagente por task, passando a instrução da spec **verbatim** com o prefixo `Spec XXXX — Task NN`
- Esse prefixo ativa o **modo spec** do implement dentro do subagente: não faz perguntas (as decisões já foram tomadas na spec), marca a task no checklist ao concluir e, quando a última fecha, muda a spec para `Concluída`
- Se uma task bloquear, pula as dependentes, continua as demais e reporta o que precisa da sua decisão
- Execução paralela é segura: cada subagente reserva seu número de implementação atomicamente (via `mkdir`), e ao fim de cada onda o run confere o checklist da spec e o `status.md`, reparando registros que se perderam em escritas simultâneas
- Execução é retomável: rodar `/centaur-driven-run 0001` de novo continua de onde parou

### 5. Para consultar, use check

```
/centaur-driven-check como funciona o fluxo de pagamento?
/centaur-driven-check o que ainda falta na spec 0001?
```

Responde com base no `CLAUDE.md`, no histórico de implementações, nas specs e no código real — apontando arquivo e linha quando fizer sentido.

## Estrutura gerada no projeto

```
projeto/
├── CLAUDE.md                        # Contexto do projeto (carregado em todo chat)
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
        ├── mudança pontual ──► /centaur-driven-implement ──► .claude/implements/XXXX/
        │
        └── demanda grande ──► /centaur-driven-spec ──► .claude/specs/XXXX/
                                        │
                                        └── /centaur-driven-run XXXX
                                                │
                                                └── N subagentes ──► /centaur-driven-implement (modo spec)
                                                                            │
                                                                            ├── implementa e documenta
                                                                            └── atualiza checklist da spec
```

Specs seguem os status `Pendente` → `Em andamento` → `Concluída`. Cada implementação referencia a spec/task de origem, e cada task concluída aponta para a implementação — trilha completa nos dois sentidos.
