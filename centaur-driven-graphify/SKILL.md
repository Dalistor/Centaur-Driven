---
name: centaur-driven-graphify
description: Inicializa, sincroniza e repara o índice Graphify do Centaur; mantém mapas, drafts e perspectivas humanos. Use para manutenção do contexto persistente ou documentação visual. Consultas cotidianas já fazem parte de todas as skills Centaur.
metadata:
  version: 3.4.0
  dependencies: graphify
---

# centaur-driven-graphify

Leia o [contrato de contexto](references/context.md), aplicado por todas as skills Centaur. Esta skill concentra manutenção e documentação humana; não precisa ser invocada para cada consulta.

Use Graphify como índice técnico para a IA localizar arquivos, conceitos e relações antes de ler as fontes. Os registros em `AGENTS.md`, `.centaur/` e `docs/system/` são canônicos; o grafo é derivado e não decide status de entrega. Código e validação comprovam comportamento implementado. Leia [módulos e equipe](references/team-workspace.md) para resolver escopos e IDs.

O mapa apresentado ao usuário deve explicar **módulos → funcionalidades ou páginas → processos → etapas relevantes**. Use o grafo técnico do Graphify para investigar e sustentar essa leitura. Antes de gerar ou atualizar mapas e perspectivas, leia [mapas legíveis](references/readable-maps.md). Para pedidos de mapa ou visão visual, a entrega é o mapa funcional sintetizado em `docs/system/Mapa do sistema.md`, visível ao abrir a raiz do projeto como vault do Obsidian; a visualização bruta fica como evidência técnica opcional.

## Dependência e instalação

Localize e leia a skill oficial `graphify` e as referências pertinentes ao modo solicitado. Verifique `graphify --version` e o help da versão instalada antes de escolher flags. O pacote oficial é `graphifyy` (dois y), do [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify). Referência verificada: CLI 0.9.65; comandos podem evoluir.

Se necessário, instale com `uv tool install graphifyy` ou `pipx install graphifyy`, respeitando as permissões do ambiente. No Codex, use o destino `graphify install --platform agents` para registrar em `~/.agents/skills/`; na versão 0.9.65, o destino `codex` ainda usa `.codex/skills`. Em outros agentes, use a plataforma correspondente. Preserve uma única cópia ativa da skill. Não altere configurações de outros agentes nem instale hooks globais como efeito colateral. Sem a dependência, mantenha os registros e informe que a geração do grafo está pendente.

## Documentação e artefatos

Crie somente os documentos necessários, preservando conteúdo existente:

- `docs/system/Visão geral.md`: propósito, atores, capacidades, limites e links para fluxos, decisões e perspectivas. Diferencie o que existe do que está planejado.
- `docs/system/Mapa do sistema.md`: entrada visual principal, com hierarquia funcional em Mermaid e links para os processos detalhados.
- `docs/system/Glossário.md`: conceitos do domínio em linguagem humana.
- `docs/system/Drafts/<slug>.md`: objetivo, hipóteses, perguntas abertas e estado (`hipótese`, `confirmado`, `promovido`).
- `docs/system/Fluxos/<slug>.md`: jornadas e fluxos confirmados, com Mermaid quando útil.
- `docs/system/Perspectivas/<slug>.md`: pergunta, escopo, resposta, diagrama opcional e evidências.
- `docs/system/Decisões/<slug>.md`: decisões confirmadas e seus motivos.
- `graphify-out/graph.json`: índice técnico gerado; `GRAPH_REPORT.md`: análise técnica. Gere HTML técnico apenas quando solicitado para exploração visual.

Use links Markdown relativos e registre caminhos/linhas de evidência. Não gere quadro, Kanban ou cards de status. Consulte status diretamente nos READMEs e índices de specs/implements do escopo. Mantenha documentos humanos em `docs/system/`, fora de `graphify-out/` e da pasta oculta `.centaur/`. Ao abrir a raiz como vault no Obsidian, o usuário encontra a nota no explorador; abrir o vault não seleciona automaticamente essa nota. Não crie nem altere `.obsidian/` para forçar uma página inicial.

## Inicializar e sincronizar

`inicializar` reutiliza as fontes existentes, registra lacunas materiais, verifica dependências e executa a primeira extração. Crie documentos somente quando houver conteúdo durável a preservar; não exija mapa, glossário ou pastas vazias para gerar o índice. `sincronizar [escopo/id]` atualiza documentos afetados e o grafo depois de salvar os registros canônicos.

1. Leia `AGENTS.md`, `.centaur/workspace.json`, as specs e implementações relevantes e o código necessário para confirmar as mudanças. Para sincronização geral, percorra todos os escopos; IDs isolados precisam ser desambiguados.
2. Atualize Visão Geral, Fluxos, Decisões e Perspectivas afetados. Registre separadamente conteúdo planejado, implementado, histórico superado e inferência. Preserve READMEs de implementações concluídas como histórico.
3. Execute o pipeline da skill oficial `graphify` para o projeto na primeira execução e o modo `--update` da **skill** nas seguintes. No Codex, a invocação é `$graphify <raiz>` ou `$graphify <raiz> --update`; isso não é um comando de shell. Siga o fluxo oficial de extração AST e semântica, construção e relatório. Quando a versão permitir, omita a visualização HTML automática (`--no-viz`); preserve `graph.json` para consultas.
4. Garanta que o corpus contém **código + AGENTS.md + docs/system/ + specs/implements de todos os escopos**, inclusive arquivos ocultos de `.centaur/`. Confira o resultado da detecção e as origens no grafo; não suponha que escanear a raiz incluiu pastas ocultas. Quando necessário, forneça explicitamente os diretórios configurados ao fluxo multipasta da skill oficial (`references/github-and-merge.md`), mantendo caminhos de origem corretos. Não remova ignores globalmente para incluir a documentação. Exclua `.git`, credenciais, backups, artefatos gerados, `.obsidian/` e arquivos legados já migrados do corpus ativo.
5. **Código e documentos têm atualizações distintas.** `graphify update <raiz>` é atualização de código via AST; não basta para alterações de specs, implements ou Markdown. Use a extração semântica da skill oficial para esses documentos. A alternativa headless é `graphify extract <raiz> --backend <backend-configurado>`, somente com backend configurado para o projeto. Não invente credenciais nem envie documentos para um provedor diferente do autorizado. Sem extração semântica disponível, reporte explicitamente quais documentos ficaram pendentes.
6. Verifique os artefatos reais e consulte conceitos representativos do escopo alterado com `graphify query`. Confira se os resultados apontam para arquivos de código, uma spec e uma implementação do escopo com origem correta, quando existirem; abra essas fontes antes de afirmar comportamento. Arquivos vazios, fontes ausentes, nós removidos ainda presentes ou falhas de extração são pendências; não diga que está sincronizado apenas porque o comando terminou. Remoções exigem conferir a reconstrução conforme o help da versão instalada. Com o índice atualizado, revise o Mapa do sistema se existir e for afetado, conforme a hierarquia funcional; uma mudança interna sem efeito no processo não precisa criar novos nós no mapa humano.
7. Se o usuário pedir navegação técnica visual, gere `graphify tree --graph graphify-out/graph.json --output graphify-out/GRAPH_TREE.html` quando disponível. A árvore organiza arquivos e símbolos; ela não substitui o mapa funcional. Use `graph.html` apenas para investigar relações específicas.
8. Registre em `.centaur/system/sync.md` a versão do CLI, a revisão Git (e se havia mudanças locais), raízes incluídas, atualização de código/documentos, consultas de verificação e pendências. Não registre segredos. Exclua esse relatório operacional do corpus para evitar realimentação.

Em execução paralela, executores reportam arquivos/documentos afetados. O coordenador primeiro consolida specs, índices e implementações, depois sincroniza o grafo serialmente. Uma falha de sincronização não reabre código validado nem cria outra implementação.

## Visão geral e perspectivas

`visão geral` consulta o grafo e o relatório para explicar módulos, responsabilidades, relações e limites do sistema; apresenta o Mapa do sistema e atualiza `Visão geral.md` quando solicitado. Crie Visão geral e Mapa quando solicitados ou úteis para explicar relações; a inicialização técnica do índice não exige esses documentos. Para uma pergunta simples, responda sem criar documentos desnecessários.

`perspectiva <objetivo>` começa com `graphify query "<objetivo>"` para localizar conceitos e arquivos candidatos. Use `graphify path "A" "B"` ou `graphify explain "X"` quando a pergunta exigir caminhos ou detalhes. Confirme afirmações importantes nos arquivos apontados e registre a perspectiva em Markdown, com links para documentos, escopo e evidências. Marque inferências; uma relação extraída de uma spec planejada não comprova implementação. Se o grafo estiver ausente ou desatualizado, sincronize ou explicite a limitação antes de responder.

Exemplos: jornada do usuário, autenticação, fluxo de dados entre frontend/backend, dependências de um módulo e impacto de uma mudança. Gere um diagrama Mermaid legível na perspectiva solicitada, usando a referência de mapas; mantenha arquivos, símbolos e linhas na seção Evidências. Aponte primeiro para `docs/system/Mapa do sistema.md` ou para a perspectiva funcional. HTMLs do Graphify são opcionais e técnicos. A síntese funcional é trabalho do agente apoiado no índice; a exportação automática não garante essa organização.

## Drafts e execução

`criar draft <objetivo>` registra a intenção e lacunas. `refinar <slug>` preserva o original, consulta contexto e resolve ambiguidades materiais. `promover <slug>` exige confirmação do comportamento pelo usuário: atualize os documentos humanos, crie a spec com `centaur-driven-spec`, ligue a origem do draft e marque-o promovido. Sincronize os novos documentos. `implementar <escopo>/<id>` delega a spec confirmada a `centaur-driven-run`, preservando TDD/direto.

## Migração e entrega

Para projetos com documentação anterior, leia [migração](references/migration.md). Ao entregar, informe documentos e artefatos alterados, versão do Graphify, consultas executadas e o que continua pendente. Diferencie atualização de código de atualização semântica. Nunca afirme sincronização contínua: o fluxo padrão é explícito após alterações; hooks opcionais de código não substituem a atualização dos documentos.
