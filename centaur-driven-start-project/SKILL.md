---
name: centaur-driven-start-project
description: Documenta um projeto existente, cria CLAUDE.md na raiz e inicializa a estrutura de implementações em .claude/implements/
version: 1.0.0
invocable: true
author: user
---

# centaur-driven-start-project

Você é um assistente de documentação de projetos. Sua tarefa é entender completamente o projeto atual e criar uma documentação sólida que sirva de base para todos os chats futuros.

## Passo 1 — Verificar se há projeto

Verifique se o diretório de trabalho atual tem arquivos ou pastas de projeto (código fonte, configs, etc).

Se o diretório estiver vazio ou não tiver estrutura de projeto reconhecível, **pare aqui** e informe o usuário:

> "Não encontrei arquivos de projeto neste diretório. Crie ou abra o projeto na pasta correta antes de usar /centaur-driven-start-project."

Se já existir um `CLAUDE.md` na raiz, **não prossiga automaticamente**. Pergunte ao usuário:
> "Este projeto já tem um CLAUDE.md. O que deseja fazer? (1) Atualizar as seções desatualizadas, (2) Recriar do zero, (3) Cancelar"

Se houver projeto e não houver CLAUDE.md, continue.

## Passo 2 — Varredura do projeto

**Importante: priorize profundidade sobre amplitude.** Não tente ler todos os arquivos — leia os mais importantes para entender a estrutura geral.

Execute `find . -not \( -path '*/node_modules/*' -o -path '*/.git/*' -o -path '*/dist/*' -o -path '*/build/*' -o -path '*/__pycache__/*' -o -path '*/.next/*' -o -path '*/coverage/*' \) -type f | head -80` para ter uma visão do projeto.

Em seguida, leia apenas:
1. Arquivos de configuração raiz (package.json, pyproject.toml, Cargo.toml, go.mod, composer.json — **só um nível de profundidade**)
2. O arquivo de entrada/bootstrap principal (main, index, app, server — **apenas o principal**)
3. READMEs existentes, se houver

Pare de ler quando tiver entendimento suficiente da stack e estrutura. Não leia código de negócio nesta etapa.

Identifique: linguagem(ns), framework(s), banco de dados, dependências principais, scripts disponíveis.

## Passo 3 — Perguntas ao usuário

Após a varredura, faça perguntas para preencher o que não está claro no código. Adapte as perguntas ao que você encontrou — não pergunte o que já está evidente. Cubra:

1. **Propósito**: O que este projeto faz? Para quem é?
2. **Status atual**: Em que fase está? (MVP, produção, refactor, etc)
3. **Arquitetura**: Há decisões arquiteturais importantes que não estão no código?
4. **Camadas**: O projeto segue (ou deve seguir) separação em camadas? Se você identificou um padrão na varredura (models, DTOs, handlers/controllers, repositories, services, etc.), confirme com o usuário. Se não há padrão definido, proponha a separação em camadas adequada à stack e pergunte se ele aprova — ela será a regra para todas as implementações futuras.
5. **Padrões**: Há convenções ou regras que devem ser seguidas nas implementações (naming, estrutura de pastas, estilo)?
6. **Restrições**: Há limitações técnicas, de performance, de segurança ou de negócio?
7. **Ambiente**: Como rodar localmente? Como fazer deploy?
8. **Contexto extra**: Qualquer coisa que um dev novo precisaria saber antes de tocar no código?

Faça todas as perguntas de uma vez. Aguarde as respostas antes de continuar.

## Passo 4 — Criar CLAUDE.md na raiz do projeto

Com as informações coletadas, crie o arquivo `CLAUDE.md` na **raiz do projeto** (não dentro de .claude/). Este arquivo é o ponto de entrada para todos os chats futuros do Claude Code.

Estrutura do CLAUDE.md:

```markdown
# [Nome do Projeto]

## Visão Geral
[O que é, para que serve, para quem]

## Stack Técnica
[Linguagem, framework, banco, infra, principais libs]

## Estrutura do Projeto
[Mapa das pastas e responsabilidades]

## Como Rodar
[Passos para rodar localmente]

## Como Fazer Deploy
[Passos ou referência]

## Arquitetura e Decisões Técnicas
[Decisões importantes, padrões adotados, por quê]

## Arquitetura de Camadas
[A separação de camadas acordada com o usuário no Passo 3. Para cada camada: nome, pasta, responsabilidade e o que é PROIBIDO nela. Exemplo (adapte à stack e ao acordado):]

| Camada | Pasta | Responsabilidade | Proibido |
|--------|-------|------------------|----------|
| Models | `src/models/` | Entidades de domínio | Lógica de negócio, acesso a dados |
| DTOs | `src/dtos/` | Contratos de entrada/saída (validação de forma) | Regras de negócio |
| Repositories | `src/repositories/` | Acesso a dados (queries, ORM) | Regras de negócio, HTTP |
| Services | `src/services/` | Regras de negócio | Acesso direto ao banco, detalhes de HTTP |
| Handlers/Controllers | `src/handlers/` | Receber requisição, chamar service, retornar resposta | Regras de negócio, queries |

[Regras de dependência entre camadas — exemplo: handler → service → repository → model; nunca no sentido inverso; DTOs apenas nas bordas]

## Regras e Convenções
[O que seguir ao implementar: naming, estrutura de pastas, padrões de código, etc]

## Restrições e Cuidados
[O que não fazer, limitações, pontos sensíveis]

## Contexto Extra
[Qualquer coisa que um dev novo precisaria saber]

## Implementações
[Atualizado automaticamente pela skill /centaur-driven-implement]
Veja `.claude/implements/status.md` para o histórico completo e `.claude/specs/index.md` para as specs planejadas.
```

## Passo 5 — Criar estrutura de implementações e specs

Crie o diretório `.claude/implements/` e o arquivo `status.md` dentro dele:

```markdown
# Status das Implementações

Histórico de todas as implementações realizadas neste projeto.

| # | Título | Data | Status | Arquivos Afetados |
|---|--------|------|--------|-------------------|
| — | — | — | — | — |

---

_Atualizado automaticamente pela skill `/centaur-driven-implement`_
```

Crie também o diretório `.claude/specs/` e o arquivo `index.md` dentro dele:

```markdown
# Specs

Planejamentos de implementações complexas, decompostos em tasks para subagentes.

| # | Título | Data | Status | Tasks |
|---|--------|------|--------|-------|
| — | — | — | — | — |

---

_Atualizado automaticamente pelas skills `/centaur-driven-spec` e `/centaur-driven-implement`_
```

## Passo 6 — Confirmar

Informe ao usuário o que foi criado e o fluxo das skills centaur-driven:
- `CLAUDE.md` criado na raiz — será carregado automaticamente em todos os chats
- `.claude/implements/status.md` criado — histórico de todas as implementações
- `.claude/specs/index.md` criado — índice de specs planejadas

Fluxo de trabalho:
- `/centaur-driven-check` — perguntar sobre o projeto sem alterar nada
- `/centaur-driven-implement` — implementação direta, documentada em `.claude/implements/`
- `/centaur-driven-spec` — para demandas grandes: decompõe em tasks que subagentes executam com `/centaur-driven-implement`
