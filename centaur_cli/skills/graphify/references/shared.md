# Contratos compartilhados das skills Centaur

As instruções do usuário e do projeto prevalecem. Abra cada referência quando o trabalho chegar ao que ela rege, não todas por rotina. Cada leitura fica no contexto e é reenviada a cada passo: leia uma vez por conversa e não releia o que ainda está visível.

| Referência | Leia quando |
|---|---|
| [Ciclo por contratos e evidências](../graphify/references/lifecycle.md) | o trabalho estiver em modo spec ou for criar ou alterar contrato, estado ou evidência. Mudança direta sem spec, que só grava o registro da própria skill, dispensa a leitura. É a fonte única de estados, aprovação, autonomia, rastreabilidade, gates e próximos passos. |
| [Contexto](../graphify/references/context.md) | a busca textual e a leitura direta não bastarem e for preciso usar Graphify ou memória para investigar. Busca textual e símbolos primeiro; Graphify só sob demanda para relações amplas, sem inicializar nem sincronizar o grafo como efeito colateral. |
| [Memória](../_internal/memory/SKILL.md) e [seu contrato](../_internal/memory/references/contract.md) | for consultar histórico, ou registrar o resultado com backend `ai-memory`. Com backend `files`, os passos de registro da própria skill bastam e dispensam a leitura. O backend em `.centaur/workspace.json` decide o destino: `files` usa `implements/` e `status.md` (inclusive a reserva numérica descrita abaixo); `ai-memory` usa páginas e fila, sem novas pastas. Consulta é somente leitura; não configure nem migre o backend por efeito colateral. |
| [Módulos e equipe](../graphify/references/team-workspace.md) | o projeto tiver módulos, mais de um responsável, IDs qualificados ou trabalho concorrente. Os exemplos abaixo usam o escopo selecionado. |

## Onde fica a dependência clean-code

Por rotina, aplique o [resumo essencial](../../_internal/essentials/SKILL.md) (código, testes e contexto), lido uma vez por conversa; ele diz quando abrir a dependência completa e qual referência. A `clean-code` inteira fica no contexto e é reenviada a cada passo, por isso não a carregue sem um desses motivos. No Centaur CLI, leia `clean-code/SKILL.md` com `read_skill` e resolva as referências pelo mesmo prefixo (`clean-code/references/...`). Em outros agentes, ela fica na pasta de skills do próprio agente (`~/.agents/skills/`, `~/.codex/skills/` ou `~/.claude/skills/`) ou em `.centaur/skills/clean-code/` do projeto. A instalação está descrita no README do Centaur. Nunca simule a aplicação de uma dependência ausente.

## Conferir o que tem interface

Quando a mudança altera algo que se vê ou se opera (tela, fluxo, saída de terminal), teste e lint não bastam: execute a aplicação e confira o resultado. No Centaur CLI, use `computer_start` com `display="virtual"` para operar a aplicação num display isolado, ou um script temporário que salve uma captura e `view_image` para vê-la. Em outros agentes, use o mecanismo equivalente. Se não houver como executar, declare a parte visual como não verificada em vez de presumir.
