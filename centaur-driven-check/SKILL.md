---
name: centaur-driven-check
description: Lê o AGENTS.md do projeto e responde perguntas com base no contexto e sistema documentado
version: 1.2.0
invocable: true
author: user
---

# centaur-driven-check

Você é um assistente especialista neste projeto. Sua tarefa é responder perguntas com base no que está documentado e no código real — não em suposições genéricas.

**Restrição absoluta: esta skill é somente leitura.** Não edite nenhum arquivo do projeto nem de `.centaur/` — nem para "aproveitar e corrigir" algo que encontrar. Se o usuário pedir uma mudança, oriente: `/centaur-driven-tdd` (comportamento testável), `/centaur-driven-implement` (estrutural/config) ou `/centaur-driven-spec` (demanda grande).

## Passo 1 — Ler o contexto do projeto

Leia obrigatoriamente:
1. `AGENTS.md` na raiz do projeto
2. `.centaur/implements/status.md` (histórico de implementações — necessário para responder perguntas sobre o que já foi feito, o que mudou, ou o estado atual de funcionalidades)
3. `.centaur/specs/index.md`, se existir (specs planejadas — necessário para responder sobre o que está planejado, em andamento ou pendente)

Se `AGENTS.md` não existir, informe o usuário:
> "Este projeto ainda não foi documentado. Execute `/centaur-driven-start-project` para criar o AGENTS.md antes de usar `/centaur-driven-check`."

Se `status.md` não existir, prossiga apenas com o AGENTS.md e mencione que não há histórico de implementações registrado.

Se a pergunta for sobre uma spec ou task específica, leia também o `.centaur/specs/YYYY/README.md` correspondente. Se for sobre uma implementação específica (o que foi feito, por quê, como validar), leia o `.centaur/implements/XXXX/README.md` dela — o `status.md` só tem o resumo.

Se a implementação procurada não estiver no `status.md`, procure em `.centaur/implements/arquivo.md`: implementações antigas têm o índice arquivado lá por `/centaur-driven-update`, mas a pasta `XXXX/` continua no lugar.

## Passo 2 — Entender a pergunta

Leia o que o usuário perguntou. Identifique se a resposta está:
- Diretamente no `AGENTS.md`
- No código (precisa ler arquivos adicionais)
- Em ambos

Se precisar de mais contexto do código para responder com precisão, leia os arquivos relevantes antes de responder.

## Passo 3 — Responder

Responda de forma direta e específica para este projeto. Não dê respostas genéricas.

- Se a pergunta for sobre como algo funciona → explique com base no código e na arquitetura documentada
- Se for sobre onde algo está → aponte o arquivo e linha
- Se for sobre uma decisão técnica → explique o que está documentado e, se não estiver, diga claramente que não foi documentado
- Se a pergunta revelar algo que deveria estar no `AGENTS.md` mas não está → responda e sugira ao usuário atualizar a documentação com `/centaur-driven-start-project` ou manualmente
