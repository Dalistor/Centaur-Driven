---
name: centaur-driven-check
description: Consulta o Graphify e confirma respostas nas instruções e fontes atuais do projeto, somente leitura.
version: 4.0.0
invocable: true
author: user
metadata:
  dependencies: clean-code, graphify
  optional-dependencies: ai-memory
---

# centaur-driven-check

## Ciclo por contratos — obrigatório

Leia o [ciclo por contratos e evidências](../centaur-driven-graphify/references/lifecycle.md) antes de planejar, executar ou declarar progresso. Ele é a fonte única de estados, aprovação, autonomia, rastreabilidade, gates e próximos passos. Contratos versionados definem o molde; specs planejam entregas; estado e evidências comprovam a realização. Preserve o histórico legado e nunca converta checklist em prova de comportamento.

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

Responder sobre comportamento, realização e próximos passos com base nas fontes atuais. Esta skill é somente leitura: não editar contratos, estado, specs, código, grafo ou HTML.

## Consultar

1. Ler AGENTS.md e resolver escopo. Recuperar contexto pelo Graphify e histórico pelo backend configurado quando necessário; confirmar as fontes atuais.
2. Para "o que faz", ler contrato aprovado e implementação pertinente. Distinguir desejo, hipótese e comportamento observado. Contrato não prova código.
3. Para "o que está feito", usar `scripts/validate-lifecycle.py` e a projeção em memória `load_project` de `scripts/volante.py` (ambos só leitura), conferindo fontes e evidências. Separar implementação, verificação e entrega registrada. Gate estrutural verde não significa projeto pronto. Não confiar num HTML antigo ou checklist.
4. Para "próximos passos", aplicar a tabela do ciclo: decisão material, dependência, implementação, prova, integração ou publicação sob autorização. Mostrar primeiro o bloqueio que o usuário precisa resolver e a próxima ação independente da IA. Não inventar planejamento fora do objetivo.
5. Para impacto de mudança, consultar relações no Graphify e confirmar consumidores, regras, testes/configuração e evidências afetados; relações inferidas precisam ser rotuladas. Apontar o que deve ser revalidado.

## Responder

Apresentar a capacidade e suas três dimensões, referência da regra/versão, prova disponível, limitações e próximo passo. Evidência válida para fontes selecionadas não garante ausência de efeitos indiretos. Specs legadas sem contrato ficam com verificação desconhecida, mesmo concluídas historicamente.

Apontar o Volante existente como navegação e informar se a captura está antiga. Para regenerar ou registrar alterações, encaminhar ao fluxo de escrita já autorizado (`graphify`, `update`, `spec`, `implement`/`tdd`), sem executar esse trabalho numa consulta pura. Não exigir inicialização ou migração para responder o que as fontes já comprovam.
