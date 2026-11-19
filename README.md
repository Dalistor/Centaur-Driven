# Centaur Driven — skills

Conjunto de skills do fluxo Centaur para agentes de código como **Codex, Claude Code e Gemini CLI**. Esta branch, `skills-only-v2`, traz apenas os arquivos `SKILL.md`, suas referências, scripts e modelos, mais o instalador. O CLI do Centaur fica na branch `main`.

O humano define comportamento, limites e autonomia; a IA planeja e implementa dentro desse contrato; fontes, testes e evidências demonstram a realização. Contratos, specs, registros e evidências ficam em `.centaur/` no projeto atendido.

## Instalação

Requer Python 3.10+ para o instalador e os scripts das skills. Por rotina, as skills aplicam o resumo interno `_internal/essentials` (critérios de código, política de testes e uso do Graphify), instalado junto. Para arquitetura, concorrência ou projeto com `.clean/`, instale também a skill [clean-code](https://github.com/btseee/clean-code-skills), com suas referências, no diretório de skills de cada agente. Graphify e ai-memory são opcionais.

| Agente | Diretório | Invocação |
| --- | --- | --- |
| Codex | `~/.agents/skills/` | `$spec` |
| Claude Code | `~/.claude/skills/` | `/spec` |
| Gemini CLI | `~/.gemini/skills/` | pedir a skill `spec` pelo nome |

```bash
# Ver o plano, sem escrever nada:
python3 scripts/install.py --target ~/.agents/skills --target ~/.claude/skills
# Aplicar:
python3 scripts/install.py --target ~/.agents/skills --target ~/.claude/skills --apply
```

Informe só os `--target` dos agentes que usa; cada diretório precisa existir. O instalador:

- instala as skills com nomes curtos (`spec`, `run`, `check`...) e os recursos internos `_internal/memory` e `_internal/essentials`;
- remove as pastas de versões anteriores com prefixo `centaur-driven-`, incluindo as aposentadas `deploy` (substituída por `ops`) e `memory` (agora interna);
- salva backup do que substitui ou remove em `.centaur/backups/` e restaura tudo se algo falhar.

Instale o conjunto completo: as skills compartilham contratos por links relativos. Depois, recarregue as skills ou reinicie a sessão do agente.

## Skills

| Skill | Finalidade |
| --- | --- |
| [start-project](skills/start-project/SKILL.md) | Inicializar o contexto de um projeto existente: `AGENTS.md` curto, registros e especificação. |
| [spec](skills/spec/SKILL.md) | Definir ou evoluir contratos e planejar entregas pequenas com critérios de aceite. |
| [run](skills/run/SKILL.md) | Executar uma spec com posse explícita, evidências e revisão independente antes de consolidar. |
| [implement](skills/implement/SKILL.md) | Mudanças pontuais e diretas, com caminho curto para ajustes pequenos de baixo risco. |
| [tdd](skills/tdd/SKILL.md) | Mudança guiada por testes, para falha concreta em ponto vital ou por pedido explícito. |
| [check](skills/check/SKILL.md) | Responder sobre o projeto e o andamento das specs pelas fontes atuais, somente leitura. |
| [security](skills/security/SKILL.md) | Auditar segurança e verificar achados com evidências, sem corrigir o código. |
| [ops](skills/ops/SKILL.md) | Preparar CI, deploy com rollback, execução, segredos, observabilidade e backups; não publica nem acessa servidores. |
| [mcp](skills/mcp/SKILL.md) | Consultar um MCP server e encaminhar o trabalho à skill adequada. |
| [graphify](skills/graphify/SKILL.md) | Consultar relações do código e manter mapas sob demanda; guarda as referências compartilhadas. |
| [update](skills/update/SKILL.md) | Reconstruir ou migrar a estrutura gerada preservando contratos e histórico. |
| [skill](skills/skill/SKILL.md) | Baixar uma skill adicional de um repositório GitHub para `.centaur/skills/` do projeto. |

## Fluxo de trabalho

1. `start-project` documenta o projeto existente e seus limites.
2. `spec` define ou evolui o contrato e planeja entregas pequenas.
3. `run` executa uma spec pelo ID, como `master/0001`.
4. `check` consulta o progresso pelas fontes atuais.

Pedidos pontuais vão direto para `implement` ou `tdd`, conforme o risco e a proteção de testes existente.

As [referências compartilhadas](skills/graphify/references/shared.md) dizem qual contrato abrir e quando: [ciclo por contratos e evidências](skills/graphify/references/lifecycle.md), [contexto](skills/graphify/references/context.md), [módulos e equipe](skills/graphify/references/team-workspace.md) e [testes nos pontos vitais](skills/graphify/references/testing.md).

## Diferenças em relação ao Centaur CLI

Os textos indicam com "No Centaur CLI" o que é próprio dele (`read_skill`, `delegate_task`, `computer_start`, `view_image`). Em outros agentes, use o mecanismo equivalente: leia os arquivos da skill pelo caminho instalado e delegue com as ferramentas do próprio agente. A skill `skill` instala em `.centaur/skills/<nome>/`, pasta que outros agentes não descobrem sozinhos; use a skill baixada lendo seu `SKILL.md` pelo caminho retornado.

## Testes

```bash
python3 -m unittest discover -s tests -q
```
