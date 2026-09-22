---
name: centaur-driven-memory
description: Integra ai-memory ao Centaur para consultar decisões, registrar mudanças e migrar o histórico de implements sem apagar registros existentes. Use para configurar a memória do projeto, recuperar contexto histórico ou reenviar registros pendentes.
metadata:
  version: 1.0.0
  dependencies: ai-memory
---

# centaur-driven-memory

Use [ai-memory](https://github.com/akitaonrails/ai-memory) para memória histórica e Graphify para localizar relações no código atual. Leia o [contrato de memória](references/contract.md) antes de operar. Instruções e specs continuam no repositório; a wiki não decide o estado atual do código.

## Configurar

1. Leia `AGENTS.md`, `.centaur/workspace.json` e a `.ai-memory.toml` aplicável. Reutilize servidor, cliente e identidade existentes. Não deduza workspace/projeto pelo nome da pasta nem altere outros projetos.
2. Descubra as ferramentas MCP disponíveis e seus schemas. Para instalação via CLI, confira `ai-memory --version` e o help dos subcomandos. Referência verificada: **2.3.2**, commit `5157c6be10b5830d7adc7e29b0a4358c3ecbe6a2`; confira a documentação da versão em uso antes de adaptar comandos.
3. Se CLI/servidor estiverem ausentes e o pedido incluir instalação, siga o [guia oficial](https://github.com/akitaonrails/ai-memory/blob/main/docs/install.md) para a plataforma real. Não copie credenciais para o repositório. Sem instalação autorizada ou acesso, informe o componente faltante e mantenha o modo atual. O modo sem LLM não requer chave de provedor.
4. No escopo de configuração autorizado, inspecione o resultado de `ai-memory install-mcp --client codex` antes de aplicar com `--apply`; para Claude Code, use `--client claude-code`. Preserve entradas existentes. Hooks são opcionais: somente se captura automática fizer parte do pedido, use `ai-memory install-hooks --agent codex` (ou `claude-code`) e depois `--apply`. Consulte as limitações de lifecycle da versão do cliente; instalar MCP não prova que hooks estão ativos.
5. Obtenha os nomes exatos de workspace e projeto da configuração existente ou do usuário. Preserve o marcador e seus demais campos. Se necessário, registre ambos na `.ai-memory.toml` da raiz e garanta a mesma identidade nos worktrees. Valide consulta no escopo explícito. Ao ativar registros, escreva uma página útil sobre a adoção, releia-a e confira o checkpoint; não use páginas fictícias como teste.
6. Só depois dessa verificação registre `memory.backend: "ai-memory"` no workspace e atualize o bloco de contexto em `AGENTS.md`. Preserve o backend anterior em caso de falha. Não migre todo o histórico como efeito colateral.

## Consultar e registrar

- Consultas históricas usam `memory_query` e leitura integral das páginas relevantes com `memory_read_page`. Passe `workspace` e `project` explicitamente. Confirme afirmações no checkout e nas specs atuais.
- Escritas de `implement`, `tdd`, `deploy` e `update` seguem o contrato: uma página por mudança com resultado real, sem criar `implements/XXXX/` no modo ai-memory. Hooks complementam essa página; não substituem validação nem comprovante de escrita.
- `sincronizar` reenvia apenas arquivos pendentes em `.centaur/memory-pending/`, usando a mesma identidade e caminho, sem reexecutar código. Confira o destino antes de reenviar e preserve divergências para resolução, sem sobrescrever páginas diferentes.
- Consulta somente leitura não instala nada, não escreve páginas, não envia feedback e não consome handoffs. Não use operações de claim/ack para descobrir contexto.

## Migrar histórico

Quando solicitado, inventarie os diretórios `implements` configurados e seus índices, inclusive IDs com sufixo. Importe cada README selecionado para `centaur/legacy/<escopo>/<id>.md`, com origem, revisão Git quando disponível e conteúdo histórico preservado. Releia antes de escrever: conteúdo equivalente é pulado; divergência exige comparação, sem sobrescrita automática. Use o protocolo de fila, pinning, leitura e checkpoint do contrato também para importações, mantendo o caminho `centaur/legacy/` como destino em vez de `centaur/changes/`. Reporte importados, já existentes e pendentes.

Não apague nem mova pastas, índices ou links antigos. Migrar autoriza importar e passar a registrar novas mudanças na wiki; não autoriza eliminar o histórico versionado. `bootstrap` captura histórico de agentes, mas não é prova de importação dos READMEs Centaur. A ativação não exige importar tudo: o histórico legado continua consultável no repositório.

## Entrega

Informe backend ativo, workspace/projeto, ferramentas verificadas e referências reais das páginas. Separe memória gravada, checkpoint pendente, fila local e Graphify atualizado. Em configuração, informe também se MCP e hooks foram efetivamente instalados ou apenas documentados.

Fontes: [uso e separação entre memória e código](https://github.com/akitaonrails/ai-memory/blob/main/docs/usage.md), [roteamento por marcador](https://github.com/akitaonrails/ai-memory/blob/main/docs/marker-file.md), [operações da wiki](https://github.com/akitaonrails/ai-memory/blob/main/docs/cookbook.md).
