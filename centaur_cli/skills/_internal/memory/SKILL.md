---
name: memory
description: Subskill interna chamada por outras skills para consultar e registrar memória, configurar ai-memory e migrar histórico sem apagar registros existentes.
metadata:
  version: 5.2.0
  visibility: internal
  dependencies: ai-memory
---

# memory

## Chamada por outras skills

Esta subskill não integra o catálogo de comandos do usuário. A skill chamadora lê `_internal/memory/SKILL.md` via `read_skill` no CLI, ou este arquivo pelo caminho relativo da instalação, e informa a operação, o escopo autorizado e a identidade configurada. Leia também `references/contract.md`. Retorne o resultado à chamadora, que continua responsável pela entrega e pelas evidências.

Consulta e registro fazem parte do fluxo da skill chamadora; não há um serviço automático de memória em segundo plano no CLI. Configuração, sincronização e migração exigem um pedido que inclua essas operações. A dependência externa ai-memory e suas regras de integração ficam encapsuladas nesta subskill; o serviço continua instalado e administrado separadamente.

## Ciclo por contratos — obrigatório

Leia o [ciclo por contratos e evidências](../../graphify/references/lifecycle.md) antes de planejar, executar ou declarar progresso. Ele é a fonte única de estados, aprovação, autonomia, rastreabilidade, gates e próximos passos. Contratos versionados definem o molde; specs planejam entregas; estado e evidências comprovam a realização. Preserve o histórico legado e nunca converta checklist em prova de comportamento.

Use [ai-memory](https://github.com/akitaonrails/ai-memory) para memória histórica; Graphify é opcional para relações amplas no código atual. Leia o [contrato de memória](references/contract.md) antes de operar. Instruções e specs continuam no repositório; a wiki não decide o estado atual do código.

## Uso com Graphify

Siga o [fluxo compartilhado de contexto](../../graphify/references/context.md#memória-e-relações-do-código). Recupere decisões e resultados relevantes e devolva suas referências à skill chamadora. Se a pergunta também exigir investigar relações amplas no código, ela pode chamar `graphify` sob demanda, usando os arquivos e símbolos mencionados no histórico como pistas, e confirmar tudo no checkout atual.

Graphify é opcional e não é dependência desta subskill. Não consulte o grafo apenas para registrar uma mudança e não indexe após gravar memória. Histórico não prova que arquivos, símbolos ou comportamento ainda existem. Sem grafo, a chamadora usa busca e leitura direta; sem ai-memory configurado, preserve o backend `files`.

## Configurar

1. Leia `AGENTS.md`, `.centaur/workspace.json` e a `.centaur/ai-memory/config.toml` aplicável. Reutilize servidor, cliente e identidade existentes. Não deduza workspace/projeto pelo nome da pasta nem altere outros projetos.
2. Descubra as ferramentas MCP disponíveis e seus schemas. Para instalação via CLI, confira `ai-memory --version` e o help dos subcomandos. Referência verificada: **2.3.2**, commit `5157c6be10b5830d7adc7e29b0a4358c3ecbe6a2`; confira a documentação da versão em uso antes de adaptar comandos.
3. Se CLI/servidor estiverem ausentes e o pedido incluir instalação, siga o [guia oficial](https://github.com/akitaonrails/ai-memory/blob/main/docs/install.md) para a plataforma real. Não copie credenciais para o repositório. Sem instalação autorizada ou acesso, informe o componente faltante e mantenha o modo atual. O modo sem LLM não requer chave de provedor.
4. No escopo de configuração autorizado, inspecione o resultado de `ai-memory install-mcp --client codex` antes de aplicar com `--apply`; para Claude Code, use `--client claude-code`. Preserve entradas existentes. Hooks são opcionais: somente se captura automática fizer parte do pedido, use `ai-memory install-hooks --agent codex` (ou `claude-code`) e depois `--apply`. Consulte as limitações de lifecycle da versão do cliente; instalar MCP não prova que hooks estão ativos.
5. Obtenha os nomes exatos de workspace e projeto da configuração existente ou do usuário. Preserve a identidade e os demais campos da configuração. O caminho Centaur não depende da descoberta automática de `.ai-memory.toml`: leia a configuração e passe workspace/project explicitamente em cada chamada. Hooks de terceiros só podem ser ativados se suportarem essa identidade explícita, sem recriar arquivos na raiz. Se necessário, registre ambos em `.centaur/ai-memory/config.toml` e garanta a mesma identidade nos worktrees. Valide consulta no escopo explícito. Ao ativar registros, escreva uma página útil sobre a adoção, releia-a e confira o checkpoint; não use páginas fictícias como teste.
6. Só depois dessa verificação registre `memory.backend: "ai-memory"` no workspace e atualize o bloco de contexto em `AGENTS.md`. Preserve o backend anterior em caso de falha. Não migre todo o histórico como efeito colateral.

## Consultar e registrar

- Consultas históricas usam `memory_query` e leitura integral das páginas relevantes com `memory_read_page`. Passe `workspace` e `project` explicitamente. Confirme afirmações no checkout e nas specs atuais.
- Escritas de `implement`, `tdd`, `deploy` e `update` seguem o contrato: uma página por mudança com resultado real, sem criar `implements/XXXX/` no modo ai-memory. Hooks complementam essa página; não substituem validação nem comprovante de escrita.
- `sincronizar` reenvia apenas arquivos pendentes em `.centaur/ai-memory/pending/`, usando a mesma identidade e caminho, sem reexecutar código. Confira o destino antes de reenviar e preserve divergências para resolução, sem sobrescrever páginas diferentes.
- Consulta somente leitura não instala nada, não escreve páginas, não envia feedback e não consome handoffs. Não use operações de claim/ack para descobrir contexto.

## Migrar histórico

Quando solicitado, inventarie os diretórios `implements` configurados e seus índices, inclusive IDs com sufixo. Importe cada README selecionado para `centaur/legacy/<escopo>/<id>.md`, com origem, revisão Git quando disponível e conteúdo histórico preservado. Releia antes de escrever: conteúdo equivalente é pulado; divergência exige comparação, sem sobrescrita automática. Use o protocolo de fila, pinning, leitura e checkpoint do contrato também para importações, mantendo o caminho `centaur/legacy/` como destino em vez de `centaur/changes/`. Reporte importados, já existentes e pendentes.

Não apague o histórico. Movimentação de artefatos locais para `.centaur/` é responsabilidade do `update`, com backup e correção de referências. Migrar autoriza importar e passar a registrar novas mudanças na wiki; não autoriza eliminar o histórico versionado. `bootstrap` captura histórico de agentes, mas não é prova de importação dos READMEs Centaur. A ativação não exige importar tudo: o histórico legado continua consultável no repositório.

## Entrega

Informe backend ativo, workspace/projeto, ferramentas verificadas e referências reais das páginas. Separe memória gravada, checkpoint pendente, fila local e Graphify atualizado. Em configuração, informe também se MCP e hooks foram efetivamente instalados ou apenas documentados.

Fontes: [uso e separação entre memória e código](https://github.com/akitaonrails/ai-memory/blob/main/docs/usage.md), [roteamento por marcador](https://github.com/akitaonrails/ai-memory/blob/main/docs/marker-file.md), [operações da wiki](https://github.com/akitaonrails/ai-memory/blob/main/docs/cookbook.md).
