---
name: check
description: Responde sobre o projeto e o andamento de uma ou várias specs pelas fontes atuais, somente leitura; Graphify sob demanda.
metadata:
  version: 5.2.1
  optional-dependencies: clean-code, graphify, _internal/memory
---

# check

## Contratos compartilhados

As instruções do usuário e do projeto prevalecem. A tabela de [contratos compartilhados](../graphify/references/shared.md) diz qual referência abrir e quando (ciclo, contexto, memória, equipe); abra só a que o trabalho exigir. Valem sempre: contratos versionados definem o molde, specs planejam entregas e só estado e evidências comprovam a realização; preserve o histórico legado e nunca converta checklist em prova de comportamento.

### Dependência clean-code — recomendada

No Centaur CLI, leia `clean-code/SKILL.md` com `read_skill` e resolva as referências pelo mesmo prefixo (`clean-code/references/...`). Em outros agentes, ela fica na pasta de skills do próprio agente (`~/.agents/skills/`, `~/.codex/skills/` ou `~/.claude/skills/`) ou em `.centaur/skills/clean-code/` do projeto. Se estiver ausente, informe isso e prossiga sem os critérios dela; não simule sua aplicação.

Use os critérios da dependência quando a pergunta envolver qualidade, localização de código ou arquitetura; consulte `references/architecture.md` nesses casos. Preserve a consulta somente leitura: não execute `audit`, não crie `.clean/` e não corrija achados.

Responder sobre comportamento, realização e próximos passos com base nas fontes atuais. Esta skill é somente leitura: não editar contratos, estado, specs, código ou grafo.

Use `AGENTS.md` e `.centaur/` como contexto e registro; leia `.clean/` se existir, sem criá-lo nem atualizá-lo. Aplique a dependência só ao escopo pedido, sem auditoria ou limpeza geral, e reporte divergências com evidência.

## Consultar

1. Ler AGENTS.md e resolver escopo. Recuperar contexto pelo Graphify e histórico pelo backend configurado quando necessário; confirmar as fontes atuais.
2. Para "o que faz", ler contrato aprovado e implementação pertinente. Distinguir desejo, hipótese e comportamento observado. Contrato não prova código.
3. Para "o que está feito", usar `scripts/validate-lifecycle.py` e a projeção em memória `load_project` de `scripts/lifecycle.py` (ambos só leitura), conferindo fontes e evidências. Separar implementação, verificação e entrega registrada. Gate estrutural verde não significa projeto pronto. Não confiar em checklist como prova.
4. Para "próximos passos", aplicar a tabela do ciclo: decisão material, dependência, implementação, prova, integração ou publicação sob autorização. Mostrar primeiro o bloqueio que o usuário precisa resolver e a próxima ação independente da IA. Não inventar planejamento fora do objetivo.
5. Para impacto de mudança, consultar relações no Graphify e confirmar consumidores, regras, testes/configuração e evidências afetados; relações inferidas precisam ser rotuladas. Apontar o que deve ser revalidado.

## Comando status no CLI

`$status` e `centaur status` exibem a projeção local em árvore, agrupando specs independentes pelo escopo e ligando mestre/filhas pelos IDs qualificados. `$status --ai` e `centaur status --ai` usam esta skill para recomendar conclusão e execução, sem alterar registros nem iniciar tasks.

Na análise, use `project_status` para localizar specs e `lifecycle_status` para conferir contratos, estado, dependências e hashes de evidências atuais. A projeção é paginada: continue a leitura até o fim. Ela reaproveita o leitor canônico, mas não executa testes nem comprova aceite externo. Abra também os READMEs, fontes e evidências necessários. Não tente usar shell, escrita ou subagentes: essas ferramentas ficam indisponíveis neste modo.

Apresente a árvore com estado registrado, recomendações de conclusão/execução, referências e gates pendentes. Dependências precisam estar integradas e verificadas; confira decisões, posse/locks e autorizações antes de recomendar execução. A mestre só pode concluir com filhas e integração comprovadas. Separe evidência estrutural corrente, resultado histórico de teste e validação que ainda precisa ser executada. Checkboxes não bastam para recomendar conclusão.

## Responder

Siga a saída curta do contrato de contexto. Para andamento de specs, mostre ID, estado canônico e próxima ação/bloqueio das specs solicitadas; consulte contratos/evidências quando a pergunta exigir comprovar realização. Não copie todas as regras, tasks e históricos para o terminal.

Apresentar a capacidade e suas três dimensões, referência da regra/versão, prova disponível, limitações e próximo passo. Evidência válida para fontes selecionadas não garante ausência de efeitos indiretos. Specs legadas sem contrato ficam com verificação desconhecida, mesmo concluídas historicamente.

Vincular os registros e fontes pertinentes. Para registrar alterações, encaminhar ao fluxo de escrita já autorizado (`graphify`, `update`, `spec`, `implement`/`tdd`), sem executar esse trabalho numa consulta pura. Não exigir inicialização ou migração para responder o que as fontes já comprovam.
