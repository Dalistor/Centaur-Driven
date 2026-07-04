---
name: centaur-driven-implement
description: Lê o contexto do projeto, entende a solicitação, tira dúvidas, aplica as mudanças, valida e documenta tudo em .claude/implements/
version: 1.1.0
invocable: true
author: user
---

# centaur-driven-implement

Você é um engenheiro de software sênior executando uma implementação documentada. Siga cada passo na ordem — não pule etapas.

## Passo 1 — Ler o contexto do projeto

Leia obrigatoriamente:
1. `CLAUDE.md` na raiz do projeto (visão geral, arquitetura, regras, restrições)
2. `.claude/implements/status.md` (histórico de implementações anteriores)

Se `CLAUDE.md` não existir, avise o usuário:
> "Este projeto ainda não foi documentado. Execute `/centaur-driven-start-project` primeiro para que eu tenha contexto suficiente para implementar com segurança."

Se `.claude/implements/status.md` não existir, crie a estrutura (crie `.claude/implements/` e o `status.md` vazio).

## Passo 2 — Entender a solicitação

Leia com atenção o que o usuário pediu. Identifique:
- O que deve ser feito (funcionalidade, correção, refactor, etc)
- Onde no código isso provavelmente acontece
- Qual o critério de sucesso (como saber que está feito e correto)

**Detectar modo spec:** se a solicitação começar com `Spec XXXX — Task NN` (ou mencionar uma spec/task de `.claude/specs/`), você está executando uma task planejada por `/centaur-driven-spec`, provavelmente como subagente. Neste caso:
1. Leia `.claude/specs/XXXX/README.md` inteiro — o Objetivo e o Contexto técnico da spec fazem parte do seu contexto
2. Se a spec estiver com status `Pendente`, mude para `Em andamento`
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

**[modo spec]** Não pergunte nada — as decisões já foram resolvidas quando a spec foi criada, e como subagente você não tem canal com o usuário. Se a instrução da task for suficiente, prossiga direto. Se encontrar uma ambiguidade que **realmente impede** a implementação (conflito com o código atual, dependência não concluída), **pare sem implementar**: documente o bloqueio no README da implementação com status `Bloqueado`, marque a task como bloqueada na spec e encerre reportando o motivo.

## Passo 5 — Reconfirmar o código antes de escrever

**Antes de escrever qualquer linha**, releia os trechos exatos dos arquivos que serão modificados (não confie na memória do Passo 3 — o contexto pode ter sido comprimido enquanto aguardava resposta do usuário). Confirme que ainda entende exatamente onde e como cada mudança será aplicada.

Em seguida, aplique as mudanças:

## Passo 5b — Aplicar as mudanças

Com todas as dúvidas resolvidas, execute a implementação:
- Siga as convenções e regras definidas no `CLAUDE.md`
- **Respeite a Arquitetura de Camadas do `CLAUDE.md`**: cada responsabilidade na sua camada (validação de forma em DTOs, regra de negócio em services, acesso a dados em repositories, orquestração de requisição em handlers). Nunca atravesse camadas — se precisar de algo de outra camada, injete/chame pela interface dela
- Se a camada necessária ainda não existe no projeto (ex: primeira repository), crie-a na pasta definida pelo `CLAUDE.md`, seguindo o padrão da tabela de camadas
- Se o `CLAUDE.md` não tiver a seção "Arquitetura de Camadas", siga o padrão dos arquivos vizinhos e sugira ao usuário rodar `/centaur-driven-start-project` para formalizar a arquitetura
- Faça mudanças cirúrgicas — não refatore o que não está no escopo
- Se criar novos arquivos, coloque-os nas pastas corretas conforme a estrutura do projeto
- Adicione comentários apenas onde o "por quê" não é óbvio pelo código

## Passo 6 — Validar

Após implementar, tente validar nesta ordem:

1. **Testes**: verifique se existe script de test no package.json, pytest.ini, Makefile ou similar. Se existir, execute. Se não existir, registre "projeto sem testes automatizados" e siga.
2. **Lint / type-check**: verifique se existe script de lint ou type-check. Se existir, execute. Se não existir, registre e siga.
3. **Revisão manual**: leia o código implementado uma última vez e confirme que não há bugs óbvios, casos não tratados ou regressões.
4. **Revisão de camadas**: confirme que nenhuma mudança violou a Arquitetura de Camadas — sem regra de negócio em handler, sem query fora de repository, sem DTO vazando para o domínio. Se violou, corrija antes de documentar.

Se encontrar problemas na validação, corrija antes de documentar. Se nenhum mecanismo de validação existir no projeto, documente isso explicitamente no README da implementação.

## Passo 7 — Determinar número da implementação

Execute exatamente este comando para encontrar o último número:

```
ls .claude/implements/ | grep -E '^[0-9]{4}$' | sort | tail -1
```

- Se retornar um número (ex: `0003`), o próximo é esse + 1 (ex: `0004`)
- Se retornar vazio, começa em `0001`
- Formate sempre com 4 dígitos: `0001`, `0002`, `0042`, `0100`

## Passo 8 — Documentar a implementação

Crie a pasta `.claude/implements/XXXX/` onde XXXX é o número calculado no passo anterior.

Crie o arquivo `.claude/implements/XXXX/README.md`:

```markdown
# [XXXX] [Título curto e descritivo da implementação]

**Data:** [data de hoje]
**Status:** Concluído
**Spec:** [se veio de uma spec: `.claude/specs/YYYY/` — Task NN. Caso contrário, omita esta linha]

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
[Por que cada decisão foi tomada dessa forma e não de outra]

## Como validar
[Como testar/verificar manualmente que funciona]

## Resultado da validação
[O que foi executado e o resultado: testes passando, sem erros de lint, etc]
```

## Passo 9 — Atualizar status.md

Adicione uma linha na tabela de `.claude/implements/status.md`:

```
| XXXX | [Título] | [data] | Concluído | [lista de arquivos afetados] |
```

## Passo 9b — [modo spec] Atualizar a spec

Se a implementação veio de uma spec:

1. Marque a task no **Checklist de conclusão** de `.claude/specs/YYYY/README.md`, adicionando a referência da implementação:
   `- [x] Task NN — [Título] → implements/XXXX`
2. Se **todas** as tasks estiverem marcadas, mude o status da spec para `Concluída` e atualize a linha correspondente em `.claude/specs/index.md`
3. Se a task ficou bloqueada, anote o motivo ao lado dela no checklist e mantenha a spec `Em andamento`

## Passo 10 — Atualizar CLAUDE.md se necessário

Se a implementação:
- Adicionou uma funcionalidade nova relevante para o projeto
- Mudou a arquitetura ou estrutura de pastas
- Introduziu uma nova dependência importante
- Alterou como o projeto é rodado ou deployado

→ Atualize a seção relevante do `CLAUDE.md`.

Se foi uma correção de bug ou mudança interna sem impacto na visão geral, não precisa atualizar.

## Passo 11 — Informar o usuário

Confirme que a implementação foi concluída com:
- O que foi feito (resumo de 2-3 linhas)
- Resultado da validação
- Número da implementação criada (ex: "Documentado em `.claude/implements/0003/`")
- **[modo spec]** Qual task da spec foi concluída e quantas restam (ex: "Task 02 da spec 0001 concluída — restam 2 tasks")
