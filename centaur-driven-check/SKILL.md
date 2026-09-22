---
name: centaur-driven-check
description: Consulta o Graphify e confirma respostas nas instruções e fontes atuais do projeto, somente leitura.
version: 1.7.0
invocable: true
author: user
metadata:
  dependencies: clean-code, graphify
  optional-dependencies: ai-memory
---

# centaur-driven-check

## Memória de implementações

Leia o [contrato de memória](../centaur-driven-memory/references/contract.md) junto do contexto. O backend em `.centaur/workspace.json` determina o destino dos registros: `files` mantém os READMEs legados; `ai-memory` usa páginas verificadas e dispensa novas pastas `implements/`. As etapas de reserva numérica e escrita em `implements/status.md` abaixo são exclusivas de `files`; no modo ai-memory, aplique o registro, a fila e a consolidação definidos no contrato. Preserve specs e histórico existente.

## Contexto persistente — Graphify

Antes de explorar o projeto, siga o [contrato de contexto](../centaur-driven-graphify/references/context.md). Graphify (CLI `graphify` do pacote `graphifyy` + skill oficial `graphify`) é dependência obrigatória para localizar relações no código. Para histórico e decisões, consulte ai-memory quando configurado. Consulte o grafo antes de ampliar leituras; confirme as fontes relevantes. Aplique os limites de escrita e a sincronização definidos no contrato.

## Escopos e equipe

Antes do fluxo, leia o [contrato de módulos e equipe](../centaur-driven-graphify/references/team-workspace.md). Ele define resolução de caminhos, IDs qualificados, responsabilidade, concorrência e estados. Os exemplos legados abaixo usam o escopo selecionado; aplique o contrato também aos comandos e templates.

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Use os critérios da dependência quando a pergunta envolver qualidade, localização de código ou arquitetura; consulte `references/architecture.md` nesses casos. Preserve a consulta somente leitura: não execute `audit`, não crie `.clean/` e não corrija achados.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

Você é um assistente especialista neste projeto. Sua tarefa é responder perguntas com base no que está documentado e no código real — não em suposições genéricas.

**Restrição absoluta: esta skill é somente leitura.** Não edite nenhum arquivo do projeto nem de `.centaur/` — nem para "aproveitar e corrigir" algo que encontrar. Se o usuário pedir uma mudança, oriente: `/centaur-driven-tdd` (comportamento testável), `/centaur-driven-implement` (estrutural/config) ou `/centaur-driven-spec` (demanda grande).

## Passo 1 — Ler o contexto do projeto

Leia `AGENTS.md` e recupere o contexto da solicitação pelo contrato Graphify acima. Consulte apenas os registros e trechos relevantes do escopo; para status, confirme o README canônico.

Quando a pergunta envolver capacidades, responsabilidades ou um fluxo ponta a ponta, use `graphify query` para localizar fontes e leia a documentação correspondente em `docs/system/`,. Confirme detalhes no código e nos READMEs de implementação; o índice não comprova comportamento por si só. Se não houver nota, deixe claro que a documentação do fluxo ainda não foi criada.

Se `AGENTS.md` não existir, informe o usuário:
> "Este projeto ainda não foi documentado. Execute `/centaur-driven-start-project` para criar o AGENTS.md antes de usar `/centaur-driven-check`."

No backend ai-memory, leia a página indicada e a fila relevante; ausência de `implements/status.md` é esperada. As consultas a `implements/` abaixo servem ao histórico legado. No backend files, se `status.md` não existir, consulte as fontes disponíveis e mencione a ausência do índice quando ela afetar a resposta; registros individuais ainda podem existir.

Se a pergunta for sobre uma spec ou task específica, leia também o `.centaur/specs/YYYY/README.md` correspondente. Se for sobre uma implementação específica (o que foi feito, por quê, como validar), leia o `.centaur/implements/XXXX/README.md` dela — o `status.md` só tem o resumo.

Se a implementação procurada não estiver no `status.md`, procure em `.centaur/implements/arquivo.md`: implementações antigas têm o índice arquivado lá por `/centaur-driven-update`, mas a pasta `XXXX/` continua no lugar.

## Passo 2 — Entender a pergunta

Para uma pergunta sobre um fluxo, consulte o índice e a nota correspondente em `docs/system/`. Se o usuário pedir criar ou alterar um fluxograma, indique `/centaur-driven-graphify`; este comando continua somente leitura.

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
