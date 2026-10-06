---
name: graphify
description: Consulta, inicializa ou atualiza Graphify sob demanda; cria mapas e perspectivas em .centaur/system. Não é pré-requisito das tarefas comuns.
metadata:
  version: 5.2.0
  dependencies: graphify
  optional-dependencies: _internal/memory
---

# graphify

Para operações de memória, chame a [subskill interna memory](../_internal/memory/SKILL.md): leia suas instruções, informe operação e escopo e use seu contrato. Ela encapsula a dependência ai-memory; consulta permanece somente leitura e registros respeitam a posse de executor/coordenador. Não configure nem migre o backend como efeito colateral.


Leia [contexto](references/context.md), [ciclo](references/lifecycle.md) e [escopos](references/team-workspace.md). Fontes e testes confirmam comportamento; o grafo apenas localiza relações. Para histórico, consulte ai-memory conforme o [contrato de memória](../_internal/memory/references/contract.md).

## Quando usar

Use para uma investigação ampla que se beneficie do grafo ou para pedido explícito de indexação/manutenção. Nas tarefas comuns, priorize busca e símbolos. Não gere índice ou extração semântica automaticamente após editar arquivos. Não instale hooks automáticos de indexação. Atualizações automáticas exigem medição de benefício e escolha do usuário.

## Uso com memory

Siga o [fluxo compartilhado de contexto](references/context.md#memória-e-relações-do-código). Quando a investigação exigir o motivo de uma decisão, chame `memory` para recuperar o registro pertinente; use referências de arquivos e símbolos para orientar o grafo e abra as fontes atuais para confirmar o impacto. Uma consulta de relações sem necessidade histórica não exige chamar memória. Ao responder, distinga motivo histórico, relação observada e inferência.

Memória gravada não dispara indexação. Índice ausente ou desatualizado exige busca direta ou pedido explícito de manutenção, sem instalação, atualização ou extração automática. Ai-memory não é requisito para consultar o grafo.

## Dependência e caminhos

Carregue a skill oficial `graphify` e suas referências pertinentes uma vez na sessão. Confira `graphify --version` e o help; referência local verificada: 0.9.65. O pacote é `graphifyy`. Instalação explícita: `uv tool install graphifyy` e `graphify install --platform agents` (Codex) ou `--platform claude`. Preserve uma cópia ativa por plataforma.

**Todos os artefatos locais ficam em `.centaur/graphify/`.** Use o adaptador `scripts/graphify-local.py`, que define `GRAPHIFY_OUT` absoluto. Scripts Python da skill oficial também precisam receber esse ambiente antes de importar Graphify, e substituir seus caminhos literais `graphify-out/`. Não execute literalmente seus exemplos de geração na raiz.

```bash
python3 /skill/graphify/scripts/graphify-local.py /projeto query "Como estes módulos se relacionam?" --budget 1500
python3 /skill/graphify/scripts/graphify-local.py /projeto path "Entrada" "Persistência"
# Extração AST explicitamente solicitada; não cobre Markdown:
python3 /skill/graphify/scripts/graphify-local.py /projeto extract --code-only
```

## Inicializar ou sincronizar quando solicitado

1. Inventarie o corpus pertinente, índice e versão existentes. Preserve o índice antes de reconstrução que possa reduzi-lo; trate recusa de redução sem forçar silenciosamente.
2. Inclua código, testes, AGENTS e definições relevantes em `.centaur/`, verificando a detecção de diretórios ocultos. Não desative ignores globalmente para isso. Exclua `.centaur/graphify/`, backups, temporários, filas ai-memory, segredos e dependências.
3. Reutilize extrações quando suportado. `update` AST não substitui extração semântica de documentos; reporte a cobertura real. Para corpus misto, siga a extração oficial com os caminhos adaptados; sem provedor configurado, o agente hospedeiro pode extrair semântica. Não exija API key nem ative cobrança externa implicitamente.
4. Um único escritor consolida o índice. Verifique integridade do JSON, origens e consultas representativas, abrindo os arquivos retornados.
5. Após verificar a cobertura dos documentos migrados, remova `needs_sync` de `.centaur/graphify/migration.json` somente quando a sincronização efetiva os cobrir. Não limpe o marcador após atualização apenas AST. Registre cobertura, revisão, limitações e falhas em `.centaur/system/sync.md`, fora do corpus. Falha de indexação não reabre código validado. Sem índice, use leitura direta e não declare sincronização.

## Documentação humana

Quando necessária, crie em `.centaur/system/`: Visão geral, Mapa do sistema, Glossário, Fluxos, Perspectivas, Decisões e Drafts. Não crie pastas vazias. Reutilize fontes canônicas existentes e links relativos; mapas não duplicam status das specs.

Leia [mapas legíveis](references/readable-maps.md) antes de diagramar. Explique módulos → funcionalidades → processos, com diagramas pequenos e evidências. Diferencie comportamento observado, intenção e inferência. Use somente os formatos solicitados para os mapas.

Migrações seguem [migration.md](references/migration.md) e a skill `update`, sem apagar documentos independentes. Entregue fontes, resultado das verificações e limitações; não prometa economia de tokens sem medição.
