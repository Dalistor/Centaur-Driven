# Centaur Driven — skills

Conjunto de skills para **Codex, Claude Code e Gemini CLI**. Esta branch, `skills-only`, distribui o fluxo Centaur em arquivos `SKILL.md`, referências e helpers próprios das skills. O agente em uso executa o trabalho com suas ferramentas nativas.

A essência permanece: o humano define comportamento, limites e autonomia; a IA planeja e implementa dentro desse contrato; fontes, testes e evidências demonstram a realização. Contratos, specs, posse de arquivos, retomada e consolidação continuam em `.centaur/` no projeto atendido.

## Instalação

Use Python 3.10+ para o instalador e os helpers. Instale também a skill completa [clean-code](https://github.com/btseee/clean-code-skills), incluindo suas referências, no diretório de skills de cada agente que vai usar o conjunto. Graphify e ai-memory são opcionais; busca direta e registros em arquivos funcionam sem eles.

Os diretórios de instalação por usuário são:

| Agente | Diretório | Invocação |
| --- | --- | --- |
| Codex | `~/.agents/skills/` | `$centaur-driven-spec` |
| Claude Code | `~/.claude/skills/` | `/centaur-driven-spec` |
| Gemini CLI | `~/.gemini/skills/` | Pedir a ativação de `centaur-driven-spec` pelo nome |

Claude Code e Gemini CLI documentam a descoberta de skills em seus [diretórios pessoais](https://code.claude.com/docs/en/skills#choose-where-skills-load) e [diretórios de skills](https://geminicli.com/docs/cli/creating-skills/). Os exemplos com `/centaur-driven-*` nos fluxos indicam a skill a usar; adapte a invocação ao cliente atual.

No checkout local desta branch:

```bash
mkdir -p ~/.agents/skills ~/.claude/skills ~/.gemini/skills
# Inspecionar o plano:
python3 scripts/install.py --target ~/.agents/skills --target ~/.claude/skills --target ~/.gemini/skills
# Aplicar a instalação completa:
python3 scripts/install.py --target ~/.agents/skills --target ~/.claude/skills --target ~/.gemini/skills --apply
```

Escolha somente os `--target` dos agentes desejados. A cópia manual também funciona: copie todas as pastas `skills/centaur-driven-*` para o diretório de skills do agente, preservando referências, scripts e templates. Instale o conjunto completo, pois as skills compartilham contratos por links relativos.

O instalador substitui apenas as skills com nomes `centaur-driven-*` presentes neste conjunto e remove a antiga `centaur-driven-commitAndPush`. Antes de substituir ou remover, salva backup em `.centaur/backups/`; falhas restauram todos os destinos já alterados. O dry-run não escreve arquivos. A mesma instalação pode ser repetida sem mudanças adicionais. Destinos precisam existir, estar fora da árvore fonte e no mesmo filesystem para permitir substituições atômicas.

Nomes curtos de instalações anteriores, como `run`, `spec` e `memory`, e recursos antigos em `_internal/` são preservados: podem pertencer a outra instalação ou ao CLI. Se quiser desativá-los, revise sua origem e remova somente os que forem seus. Recarregue as skills ou reinicie a sessão conforme o cliente.

## Skills

| Skill | Finalidade |
| --- | --- |
| [centaur-driven-start-project](skills/centaur-driven-start-project/SKILL.md) | Inicializar instruções, escopos e conceito do projeto. |
| [centaur-driven-spec](skills/centaur-driven-spec/SKILL.md) | Definir contratos e planejar entregas verificáveis. |
| [centaur-driven-run](skills/centaur-driven-run/SKILL.md) | Executar uma spec, consolidar evidências e integrar conforme autorização. |
| [centaur-driven-implement](skills/centaur-driven-implement/SKILL.md) | Mudanças diretas com validação proporcional. |
| [centaur-driven-tdd](skills/centaur-driven-tdd/SKILL.md) | TDD por pedido explícito ou falha concreta em ponto vital ainda sem proteção suficiente. |
| [centaur-driven-check](skills/centaur-driven-check/SKILL.md) | Responder sobre o projeto e specs pelas fontes atuais, somente leitura. |
| [centaur-driven-security](skills/centaur-driven-security/SKILL.md) | Auditar segurança e relatar evidências. |
| [centaur-driven-mcp](skills/centaur-driven-mcp/SKILL.md) | Consultar serviços MCP e encaminhar o trabalho à skill apropriada. |
| [centaur-driven-graphify](skills/centaur-driven-graphify/SKILL.md) | Consultar relações e manter índices/mapas sob demanda. |
| [centaur-driven-memory](skills/centaur-driven-memory/SKILL.md) | Consultar e registrar memória histórica, configurar ai-memory e sincronizar pendências. |
| [centaur-driven-update](skills/centaur-driven-update/SKILL.md) | Reconstruir/migrar a estrutura gerada preservando definições e histórico. |
| [centaur-driven-deploy](skills/centaur-driven-deploy/SKILL.md) | Preparar GitHub Actions, scripts e acessos para deploy. |

`centaur-driven-memory` é uma skill pública e também atende chamadas das demais skills. A dependência ai-memory continua instalada e administrada separadamente. A antiga skill `skill`, que atendia o autocomplete e o catálogo do CLI Centaur, sai desta distribuição.

## Fluxo de trabalho

1. Use `centaur-driven-start-project` para documentar o projeto existente e seus limites.
2. Use `centaur-driven-spec` para definir ou evoluir o contrato e planejar entregas pequenas.
3. Use `centaur-driven-run` com o ID qualificado, como `master/0001`, para executar uma spec. O cliente pode delegar quando suas ferramentas permitirem; execução sequencial também preserva o protocolo.
4. Use `centaur-driven-check` para consultar progresso pelas fontes atuais. Checklist e relatório de executor não substituem evidência de comportamento.

Pedidos pontuais podem seguir diretamente para `centaur-driven-implement` ou `centaur-driven-tdd`, conforme risco, proteção existente e instruções do usuário. Autorização já presente continua válida; dúvidas materiais de contrato voltam ao humano.

O coordenador registra posse, passa limites e critérios para cada executor e consolida registros compartilhados como único escritor. Cada executor altera somente seus arquivos e produz evidências individuais. Retomadas consultam estado, trabalho preservado e pendências antes de repetir operações. Seleção de modelos e delegação usam somente capacidades reais do cliente atual.

A [base conceitual](skills/centaur-driven-graphify/references/specification.md) integra conceito, requisitos funcionais/não funcionais, casos de uso e relações de dados. O [ciclo por contratos e evidências](skills/centaur-driven-graphify/references/lifecycle.md) mantém implementação, verificação e entrega separadas. Fontes ou contratos alterados tornam evidências anteriores desatualizadas. Veja também [posse e concorrência](skills/centaur-driven-graphify/references/team-workspace.md) e [testes nos pontos vitais](skills/centaur-driven-graphify/references/testing.md).

## Contexto do projeto atendido

```text
projeto/
├── AGENTS.md                    # Instruções essenciais e fontes vinculadas
├── CLAUDE.md / GEMINI.md         # Entradas do cliente, quando necessárias
├── .github/workflows/           # Integração de deploy no caminho do GitHub
└── .centaur/
    ├── workspace.json          # Escopos, responsáveis e backend de memória
    ├── contracts/<id>/vNNN.json # Comportamento e limites versionados
    ├── state/                  # Realização atual por regra
    ├── evidence/               # Verificações imutáveis
    ├── specs/                  # Planos de entrega
    ├── system/                 # Documentação e decisões
    ├── use-cases/              # Rascunhos de fluxos
    ├── implements/             # Registros files ou histórico legado
    ├── graphify/               # Índice e caches opcionais
    ├── ai-memory/              # Configuração e fila local de memória
    ├── deploy/                 # Helpers de deploy
    ├── worktrees/              # Execuções isoladas
    ├── backups/                # Recuperação
    └── tmp/                    # Preparação temporária
```

Versione definições, specs, estado e evidências do projeto atendido. Ignore caches, backups, temporários, worktrees e segredos. Neste repositório de distribuição, `.centaur/` é contexto local e fica fora do Git.

`AGENTS.md` concentra as instruções compartilhadas. Quando o cliente usa `CLAUDE.md` ou `GEMINI.md`, mantenha uma entrada curta que oriente a leitura de `AGENTS.md`, preservando instruções existentes e evitando cópias divergentes.

## Memória e relações do código

Busca textual e leitura de fontes são a primeira opção. Graphify ajuda em relações amplas, sob demanda; não há indexação automática após cada edição. A skill Centaur que o integra tem nome `centaur-driven-graphify`; a skill externa oficial continua chamada `graphify`.

Os helpers estão na pasta instalada da skill. Exemplos a partir deste checkout:

```bash
python3 skills/centaur-driven-graphify/scripts/validate-lifecycle.py /projeto
python3 skills/centaur-driven-graphify/scripts/validate-lifecycle.py /projeto --ready contrato/REGRA
python3 skills/centaur-driven-graphify/scripts/graphify-local.py /projeto query "dependências do módulo" --budget 1500
```

Ai-memory é opcional. Sua [skill](skills/centaur-driven-memory/SKILL.md) verifica serviço, cliente e identidade antes de ativar `memory.backend: ai-memory`. O [contrato de memória](skills/centaur-driven-memory/references/contract.md) determina registros, fila, checkpoint e consolidação. Sem backend configurado, use `files`; uma falha de memória mantém a pendência separada do estado do código.

## Atualização e deploy

`centaur-driven-update` inventaria e valida antes de substituir estrutura gerada. O [migrador](skills/centaur-driven-update/scripts/migrate.py) conserva contratos, evidências, decisões e configurações, com backup e rollback. Arquivos gerados em `docs/system/` devem ter propriedade confirmada; documentos manuais são preservados.

```bash
python3 skills/centaur-driven-update/scripts/migrate.py --root /projeto
python3 skills/centaur-driven-update/scripts/migrate.py --root /projeto --apply
```

`centaur-driven-deploy` prepara o workflow e seus helpers, sem publicar como parte da preparação. O [template estático](skills/centaur-driven-deploy/templates/deploy-vps.yml) transfere uma release isolada, valida integridade e saúde, troca tráfego atomicamente e preserva rollback. Serviços dinâmicos exigem estratégia adequada ao projeto. Publicação depende da autorização e do ambiente reais.

## Manutenção deste conjunto

```text
skills/centaur-driven-*/  # SKILL.md, referências e helpers do fluxo
scripts/install.py       # Instalação independente do agente
tests/                  # Contratos, evidências, instalação, migração e deploy
.github/workflows/       # Validação do conjunto de skills
```

Execute:

```bash
python3 -m unittest discover -s tests -v
```

Os testes validam helpers e instalação em diretórios temporários dos três clientes. A ativação de skills em sessões reais depende da versão, permissões e configuração de cada agente; os testes locais não executam sessões de Codex, Claude ou Gemini, nem deploy remoto.
