---
name: centaur-driven-start-project
description: Documenta um projeto existente, cria AGENTS.md na raiz (incluindo a Arquitetura de Camadas) e inicializa implementações, specs e entradas do mapa semântico em .centaur/
version: 1.8.0
invocable: true
author: user
metadata:
  dependencies: clean-code
---

# centaur-driven-start-project

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Leia `references/architecture.md` da dependência ao documentar responsabilidades e direções de dependência. Descreva a arquitetura existente e registre desvios com evidência; este fluxo documenta um projeto existente, não executa o modo `new-project` nem refatora o código.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

Você é um assistente de documentação de projetos. Sua tarefa é entender completamente o projeto atual e criar uma documentação sólida que sirva de base para todos os chats futuros.

## Passo 1 — Verificar se há projeto

Verifique se o diretório de trabalho atual tem arquivos ou pastas de projeto (código fonte, configs, etc).

Se o diretório estiver vazio ou não tiver estrutura de projeto reconhecível, **pare aqui** e informe o usuário:

> "Não encontrei arquivos de projeto neste diretório. Crie ou abra o projeto na pasta correta antes de usar /centaur-driven-start-project."

Se já existir um `AGENTS.md` na raiz, **não prossiga automaticamente**. Pergunte ao usuário:
> "Este projeto já tem um AGENTS.md. O que deseja fazer? (1) Atualizar as seções desatualizadas, (2) Recriar do zero, (3) Cancelar"

- **(1) Atualizar:** este é o trabalho de `/centaur-driven-update`, que além de migrar as seções faltantes audita a integridade do histórico e resolve contradições entre documentação e código. Recomende-a e encerre. Só faça a atualização aqui se o usuário insistir em não usar a outra skill — nesse caso, leia o `AGENTS.md` atual por completo, execute a varredura do Passo 2, liste as seções que divergem do código e as que faltam em relação ao template do Passo 4, pergunte **apenas** sobre isso no Passo 3, edite as seções afetadas sem reescrever o arquivo inteiro e siga para o Passo 5 só para criar o que ainda não existir em `.centaur/`.
- **(2) Recriar:** siga o fluxo normal do zero; o arquivo atual será substituído.
- **(3) Cancelar:** encerre sem tocar em nada.

Se houver projeto e não houver AGENTS.md, continue.

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
5. **Testes**: Qual framework de teste o projeto usa (ou deve usar)? Qual o comando para rodar a suíte, um arquivo só e a cobertura? Onde ficam os arquivos de teste e qual a convenção de nome? Há meta de cobertura? Se a varredura já revelou isso (scripts do package.json, pytest.ini, pasta de testes), só confirme. Se o projeto não tem testes, pergunte se ele quer adotar TDD nas próximas implementações e qual framework.
6. **Padrões**: Há convenções ou regras que devem ser seguidas nas implementações (naming, estrutura de pastas, estilo)?
7. **Idioma e vocabulário do código**: Em que idioma são escritos os identificadores (nomes de variável, função, classe)? E os comentários? E as mensagens de commit? É comum o domínio ficar em português e a infraestrutura em inglês — se a varredura mostrou isso, confirme em vez de perguntar. Levante também os **termos do domínio** que já aparecem no código (as palavras que nomeiam as entidades centrais) e confirme se são as palavras corretas do negócio: elas viram o vocabulário obrigatório das próximas implementações. Um conceito, um nome, no projeto inteiro.
8. **Restrições**: Há limitações técnicas, de performance, de segurança ou de negócio?
9. **Ambiente**: Como rodar localmente? Como fazer deploy?
10. **Contexto extra**: Qualquer coisa que um dev novo precisaria saber antes de tocar no código?

Faça todas as perguntas de uma vez. Aguarde as respostas antes de continuar.

## Passo 4 — Criar AGENTS.md na raiz do projeto

Com as informações coletadas, crie o arquivo `AGENTS.md` na **raiz do projeto** (não dentro de .claude/). Este arquivo é o ponto de entrada para todos os chats/sessões futuras, de qualquer assistente de IA.

Estrutura do AGENTS.md:

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

## Testes

| Item | Valor |
|------|-------|
| Framework | [ex: Vitest, Pytest, JUnit 5] |
| Rodar tudo | [comando] |
| Rodar um arquivo | [comando] |
| Cobertura | [comando, ou "não configurado"] |
| Local e nome | [ex: `tests/**/*.spec.ts`] |
| Meta de cobertura | [ex: 80% linha, 100% em serviços críticos] |

[Como mockar dependências externas (banco, HTTP, relógio) neste projeto. Se o projeto não tem testes automatizados, registre isso explicitamente aqui.]

## Vocabulário e Idioma do Código

| Item | Valor |
|------|-------|
| Identificadores (variável, função, classe) | [ex: inglês; ou português no domínio e inglês na infraestrutura] |
| Comentários | [ex: português] |
| Mensagens de commit | [ex: português, prefixo convencional feat/fix/...] |

**Termos do domínio** — a palavra à esquerda é a única usada no código para esse conceito:

| Termo | Significa | Não use |
|-------|-----------|---------|
| [ex: `cobranca`] | [ex: uma ordem de pagamento emitida para um cliente] | [ex: `payment`, `fatura`, `charge`] |

[Se o projeto ainda não tem vocabulário definido, registre isso e o combinado com o usuário. As skills de implementação consultam esta seção antes de nomear qualquer coisa nova, e acrescentam aqui os termos que estabelecerem.]

## Regras e Convenções
[O que seguir ao implementar: naming, estrutura de pastas, padrões de código, etc]

## Qualidade de Código e Arquitetura

O conjunto Centaur depende da skill `clean-code`. Antes de planejar, implementar ou revisar código com estas skills, carregue seu `SKILL.md` e as referências pertinentes a partir da instalação do agente. Se estiver ausente, informe a dependência faltante antes de executar trabalho que depende dela.

Siga as convenções e a Arquitetura de Camadas deste projeto: cada responsabilidade no módulo apropriado, dependências na direção declarada, nomes do vocabulário do domínio e mudanças limitadas à solicitação. Valide o resultado com os mecanismos disponíveis e reporte o que não foi verificado.

As instruções do usuário e deste projeto prevalecem. O Centaur define o modo TDD ou direto e a proporcionalidade dos testes. Contexto e decisões ficam neste `AGENTS.md`; o histórico fica em `.centaur/`. Se `.clean/` existir, consulte-o e reporte divergências, sem criar ou atualizar essa estrutura nos fluxos Centaur.

## Restrições e Cuidados
[O que não fazer, limitações, pontos sensíveis]

## Contexto Extra
[Qualquer coisa que um dev novo precisaria saber]

## Sistema no Obsidian

Use `/centaur-driven-obsidian` para manter drafts, fluxos, decisões e a visão humana do sistema no vault configurado. O vault contém intenção e documentação; o código e a validação continuam sendo a evidência de comportamento implementado. Em execuções paralelas, o orquestrador sincroniza notas compartilhadas serialmente.

## Implementações
[Atualizado automaticamente pelas skills /centaur-driven-tdd e /centaur-driven-implement]
Veja `.centaur/implements/status.md` para o histórico completo e `.centaur/specs/index.md` para as specs planejadas.

---

_Documentação centaur — schema `[versão desta skill, do frontmatter]`, gerada em `[saída de date +%F]`. Atualize com `/centaur-driven-update`._
```

A última linha é o **carimbo de schema**: é por ela que `/centaur-driven-update` sabe qual versão do template gerou este `AGENTS.md` e o que precisa migrar. Preencha com a versão declarada no frontmatter desta skill — não invente outro número.

## Passo 5 — Criar estrutura do Centaur

Crie o diretório `.centaur/implements/` e o arquivo `status.md` dentro dele:

```markdown
# Status das Implementações

Histórico de todas as implementações realizadas neste projeto.

| # | Título | Data | Status | Arquivos Afetados |
|---|--------|------|--------|-------------------|

---

_Atualizado automaticamente pelas skills `/centaur-driven-tdd` e `/centaur-driven-implement`_
```

Crie também o diretório `.centaur/specs/` e o arquivo `index.md` dentro dele:

```markdown
# Specs

Planejamentos de implementações complexas, decompostos em tasks para subagentes.

| # | Título | Data | Status | Tasks |
|---|--------|------|--------|-------|

---

_Atualizado automaticamente pelas skills `/centaur-driven-spec`, `/centaur-driven-tdd`, `/centaur-driven-implement` e `/centaur-driven-run`_
```

Crie também o vault local `.centaur/obsidian/` conforme `centaur-driven-obsidian`: inclua `.obsidian/app.json`, `Sistema/Visão geral.md`, as pastas Drafts, Fluxos, Decisões e Specs e a skill no escopo `.agents/skills/`. As notas iniciais devem ser marcadas como rascunho; não invente a descrição do sistema.

## Passo 6 — Confirmar

Informe ao usuário o que foi criado e o fluxo das skills centaur-driven:
- `AGENTS.md` criado na raiz — será lido pelas skills centaur em cada chat
- `.centaur/implements/status.md` criado — histórico de todas as implementações
- `.centaur/specs/index.md` criado — índice de specs planejadas
- `.centaur/obsidian/` criado — vault local para drafts, fluxos, decisões e referências das specs

Fluxo de trabalho:
- `/centaur-driven-check` — perguntar sobre o projeto sem alterar nada
- `/centaur-driven-tdd` — mudança pontual com comportamento testável (regra de negócio, validação, cálculo, bug): teste antes do código, ciclo red-green-refactor
- `/centaur-driven-implement` — mudança pontual estrutural, de configuração ou de UI, e projetos sem infraestrutura de teste
- `/centaur-driven-spec` — para demandas grandes: decompõe em tasks atômicas por camada, cada uma marcada como TDD ou direta
- `/centaur-driven-run` — executa uma spec: lança subagentes por task conforme o Modo, paraleliza e consolida
- `/centaur-driven-obsidian` — cria e refina drafts, fluxos e decisões no vault do Obsidian
- `/centaur-driven-update` — manutenção da documentação: migra o `AGENTS.md` quando as skills evoluem, audita o histórico e resolve contradições

Ambas as skills de execução documentam em `.centaur/implements/XXXX/` e reportam as notas do Obsidian afetadas para sincronização após a validação.
