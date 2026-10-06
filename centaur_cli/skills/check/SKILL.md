---
name: check
description: Responde sobre o projeto e o andamento de uma ou várias specs pelas fontes atuais, somente leitura; Graphify sob demanda.
metadata:
  version: 5.2.0
  dependencies: clean-code
  optional-dependencies: graphify, _internal/memory
---

# check

Para operações de memória, chame a [subskill interna memory](../_internal/memory/SKILL.md): leia suas instruções, informe operação e escopo e use seu contrato. Ela encapsula a dependência ai-memory; consulta permanece somente leitura e registros respeitam a posse de executor/coordenador. Não configure nem migre o backend como efeito colateral.

## Ciclo por contratos — obrigatório

Leia o [ciclo por contratos e evidências](../graphify/references/lifecycle.md) antes de planejar, executar ou declarar progresso. Ele é a fonte única de estados, aprovação, autonomia, rastreabilidade, gates e próximos passos. Contratos versionados definem o molde; specs planejam entregas; estado e evidências comprovam a realização. Preserve o histórico legado e nunca converta checklist em prova de comportamento.

## Memória de implementações

Leia o [contrato de memória](../_internal/memory/references/contract.md) junto do contexto. O backend em `.centaur/workspace.json` determina o destino dos registros: `files` mantém os READMEs legados; `ai-memory` usa páginas verificadas e dispensa novas pastas `implements/`. As etapas de reserva numérica e escrita em `implements/status.md` abaixo são exclusivas de `files`; no modo ai-memory, aplique o registro, a fila e a consolidação definidos no contrato. Preserve specs e histórico existente.

## Contexto persistente — Graphify

Antes de explorar o projeto, siga o [contrato de contexto](../graphify/references/context.md). Priorize busca textual e símbolos do editor. Graphify é opcional e sob demanda para relações amplas; consulte o índice existente apenas quando útil, confirmando as fontes atuais. Não inicialize nem sincronize o grafo como consequência de implementar ou consultar. Para histórico e decisões, consulte ai-memory quando configurado.

## Escopos e equipe

Antes do fluxo, leia o [contrato de módulos e equipe](../graphify/references/team-workspace.md). Ele define resolução de caminhos, IDs qualificados, responsabilidade, concorrência e estados. Os exemplos legados abaixo usam o escopo selecionado; aplique o contrato também aos comandos e templates.

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Use os critérios da dependência quando a pergunta envolver qualidade, localização de código ou arquitetura; consulte `references/architecture.md` nesses casos. Preserve a consulta somente leitura: não execute `audit`, não crie `.clean/` e não corrija achados.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

Responder sobre comportamento, realização e próximos passos com base nas fontes atuais. Esta skill é somente leitura: não editar contratos, estado, specs, código ou grafo.

## Consultar

1. Ler AGENTS.md e resolver escopo. Recuperar contexto pelo Graphify e histórico pelo backend configurado quando necessário; confirmar as fontes atuais.
2. Para "o que faz", ler contrato aprovado e implementação pertinente. Distinguir desejo, hipótese e comportamento observado. Contrato não prova código.
3. Para "o que está feito", usar `scripts/validate-lifecycle.py` e a projeção em memória `load_project` de `scripts/lifecycle.py` (ambos só leitura), conferindo fontes e evidências. Separar implementação, verificação e entrega registrada. Gate estrutural verde não significa projeto pronto. Não confiar em checklist como prova.
4. Para "próximos passos", aplicar a tabela do ciclo: decisão material, dependência, implementação, prova, integração ou publicação sob autorização. Mostrar primeiro o bloqueio que o usuário precisa resolver e a próxima ação independente da IA. Não inventar planejamento fora do objetivo.
5. Para impacto de mudança, consultar relações no Graphify e confirmar consumidores, regras, testes/configuração e evidências afetados; relações inferidas precisam ser rotuladas. Apontar o que deve ser revalidado.

## Comando status no CLI

`/status` e `centaur status` exibem a projeção local em árvore, agrupando specs independentes pelo escopo e ligando mestre/filhas pelos IDs qualificados. `/status --ai` e `centaur status --ai` usam esta skill para recomendar conclusão e execução, sem alterar registros nem iniciar tasks.

Na análise, use `project_status` para localizar specs e `lifecycle_status` para conferir contratos, estado, dependências e hashes de evidências atuais. A projeção é paginada: continue a leitura até o fim. Ela reaproveita o leitor canônico, mas não executa testes nem comprova aceite externo. Abra também os READMEs, fontes e evidências necessários. Não tente usar shell, escrita ou subagentes: essas ferramentas ficam indisponíveis neste modo.

Apresente a árvore com estado registrado, recomendações de conclusão/execução, referências e gates pendentes. Dependências precisam estar integradas e verificadas; confira decisões, posse/locks e autorizações antes de recomendar execução. A mestre só pode concluir com filhas e integração comprovadas. Separe evidência estrutural corrente, resultado histórico de teste e validação que ainda precisa ser executada. Checkboxes não bastam para recomendar conclusão.

## Responder

Siga a saída curta do contrato de contexto. Para andamento de specs, mostre ID, estado canônico e próxima ação/bloqueio das specs solicitadas; consulte contratos/evidências quando a pergunta exigir comprovar realização. Não copie todas as regras, tasks e históricos para o terminal.

Apresentar a capacidade e suas três dimensões, referência da regra/versão, prova disponível, limitações e próximo passo. Evidência válida para fontes selecionadas não garante ausência de efeitos indiretos. Specs legadas sem contrato ficam com verificação desconhecida, mesmo concluídas historicamente.

Vincular os registros e fontes pertinentes. Para registrar alterações, encaminhar ao fluxo de escrita já autorizado (`graphify`, `update`, `spec`, `implement`/`tdd`), sem executar esse trabalho numa consulta pura. Não exigir inicialização ou migração para responder o que as fontes já comprovam.
