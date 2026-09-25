---
name: centaur-driven-start-project
description: Inicializa o contexto de um projeto existente com AGENTS.md curto, registros Centaur e índice Graphify; reutiliza fontes e documenta detalhes sob demanda.
version: 3.5.0
invocable: true
author: user
metadata:
  dependencies: clean-code, graphify
  optional-dependencies: ai-memory
---

# centaur-driven-start-project

## Memória de implementações

Leia o [contrato de memória](../centaur-driven-memory/references/contract.md) junto do contexto. O backend em `.centaur/workspace.json` determina o destino dos registros: `files` mantém os READMEs legados; `ai-memory` usa páginas verificadas e dispensa novas pastas `implements/`. As etapas de reserva numérica e escrita em `implements/status.md` abaixo são exclusivas de `files`; no modo ai-memory, aplique o registro, a fila e a consolidação definidos no contrato. Preserve specs e histórico existente.

Estabeleça as instruções e fontes persistentes que os agentes consultarão nas próximas sessões. Documente o projeto existente, sem refatorar código nem impor uma arquitetura nova. Mantenha o contexto obrigatório curto e os detalhes recuperáveis pelo Graphify.

## Passo 1 — Verificar projeto e dependências

Verifique se há código, configurações ou documentação de projeto. Se o diretório estiver vazio, informe que é necessário criar ou abrir um projeto e encerre.

Leia as instruções aplicáveis em `AGENTS.md`, se existir, e preserve documentos e registros existentes. Se o projeto já foi inicializado pelo Centaur, siga `centaur-driven-update` para atualização dentro do pedido autorizado. Um `AGENTS.md` sem Centaur não impede a inicialização: acrescente apenas o necessário, preservando suas regras. Não recrie nem substitua conteúdo existente sem solicitação explícita.

Leia o [contrato de contexto](../centaur-driven-graphify/references/context.md) e o [contrato de módulos e equipe](../centaur-driven-graphify/references/team-workspace.md). Localize as skills oficiais `graphify` e `clean-code` no catálogo do agente, leia seus `SKILL.md` uma vez na sessão e confira `graphify --version`. Consulte apenas as referências necessárias ao modo em uso; use `references/architecture.md` de `clean-code` ao documentar responsabilidades. Se a dependência de qualidade estiver ausente, informe a instalação faltante antes do trabalho dependente dela. Para Graphify indisponível, aplique o modo degradado do contrato e reporte a indexação pendente.

As instruções do usuário e do projeto prevalecem. Consulte `.clean/` se existir, sem criar ou atualizar essa estrutura. Não instale hooks globais como efeito colateral.

## Passo 2 — Descobrir a estrutura

Se `graphify-out/graph.json` existir, consulte-o primeiro com perguntas focadas sobre módulos, responsabilidades e pontos de entrada, usando o orçamento do contrato. Confirme os resultados nos arquivos atuais; um índice antigo ou parcial exige busca focada para as lacunas.

Sem grafo, use `rg --files` com filtros para localizar manifestos, configurações, READMEs e pontos de entrada, excluindo dependências e artefatos gerados. Leia os manifestos raiz e dos módulos reais, comandos declarados e trechos pertinentes da documentação. Abra código representativo somente quando necessário para confirmar limites arquiteturais ou conceitos; não tente ler todo o negócio. Não limite a descoberta aos primeiros arquivos de uma listagem nem apenas à raiz de um monorepo.

Identifique stack, comandos de execução e testes, responsabilidades dos módulos e convenções comprovadas. Reutilize documentação válida e registre fontes para as conclusões. Pare quando houver evidência suficiente para inicializar o contexto. Sem grafo inicial, construa-o no Passo 6, depois de salvar os documentos, evitando duas extrações completas no mesmo fluxo.

## Passo 3 — Resolver decisões e lacunas

Pergunte apenas o que não estiver nas fontes ou nas instruções já fornecidas. Não peça confirmação de comandos, frameworks ou convenções que estão explícitos e consistentes. Agrupe as dúvidas materiais em um bloco curto:

- Propósito, restrições, limites arquiteturais ou decisões de produto que as fontes não esclarecem. Distinga arquitetura observada de uma proposta; documentar não exige adotar camadas novas.
- Idioma e vocabulário quando houver ambiguidade real. Preserve termos já estabelecidos; não invente um glossário completo.
- Testes ausentes: registre a ausência. Pergunte sobre adoção de TDD ou framework somente se essa decisão fizer parte do pedido; não bloqueie a documentação por falta de testes ou de meta de cobertura.
- Colaboração: obtenha explicitamente **individual ou equipe**, reutilizando resposta da sessão ou configuração explícita existente. Não deduza pelo número de módulos. No modo equipe, esclareça apenas responsáveis e integração ainda indefinidos; no individual, o desenvolvedor assume essas funções.

Aguarde respostas necessárias antes de registrar uma decisão como confirmada. Lacunas não essenciais podem ficar identificadas no documento pertinente. Se não houver dúvidas materiais, prossiga sem entrevista.

## Passo 4 — Criar AGENTS.md curto na raiz

O arquivo contém instruções necessárias em toda sessão: regras, comandos essenciais, limites arquiteturais e recuperação de contexto. Detalhes de operação, justificativas, catálogo de arquivos, glossário extenso e histórico ficam em fontes vinculadas no Passo 5. Preserve os títulos Arquitetura de Camadas, Testes e Vocabulário e Idioma do Código usados pelas demais skills; preencha-os de forma concisa, com referências específicas quando necessário.

Adapte o template abaixo à estrutura real. Remova placeholders, não invente comandos, camadas ou documentos. Links devem apontar para arquivos existentes ou criados no Passo 5; não obrigue todos os documentos vinculados a serem lidos em toda sessão.

```markdown
# [Nome do projeto]

## Visão Geral
[Propósito e stack em poucas linhas. Link para visão detalhada existente, se necessário.]

## Contexto persistente com Graphify
Graphify é dependência do Centaur: CLI `graphify` (pacote `graphifyy`) e skill oficial `graphify`. Após ler estas instruções, consulte da raiz `graphify query "<objetivo da tarefa>" --budget 1500` e abra as fontes relevantes. Confirme conteúdo atual antes de editar; não carregue o grafo ou histórico completos. Sem índice confiável, informe a limitação e use busca focada.
Decisões ficam em documentos canônicos, indexados para próximas sessões. Código e validação comprovam comportamento; o grafo pode conter planos e inferências. Após mudanças e registros, sincronize pelo fluxo `centaur-driven-graphify`; em paralelo, somente o coordenador atualiza o índice. Consultas somente leitura não sincronizam.

## Memória de decisões e mudanças
[Backend confirmado em `.centaur/workspace.json`: files ou ai-memory.]
Com ai-memory, siga `centaur-driven-memory`: use workspace/projeto explícitos da `.ai-memory.toml`, consulte decisões relevantes e registre mudanças na wiki com leitura de confirmação. Sem serviço, preserve o registro em `.centaur/memory-pending/` e reporte pendência. Não crie novas pastas implements nesse modo. Memória histórica não substitui código, testes, regras ou o estado das specs.

## Comandos essenciais
[Comandos reais para executar, construir e validar, com diretório quando necessário. Link para instruções detalhadas de ambiente/deploy já existentes.]

## Arquitetura de Camadas
[Limites obrigatórios e direção das dependências. Tabela curta de camada/módulo, pasta, responsabilidade e proibições somente se útil. Preserve a arquitetura real, mesmo sem camadas convencionais. Referência para detalhes.]

## Testes
[Framework, comandos essenciais e local/convenção dos testes; ou ausência explícita. Gates e metas somente quando definidos. Referência para estratégias específicas de teste.]

## Vocabulário e Idioma do Código
[Idiomas e regras de nomenclatura. Termos críticos curtos ou referência ao glossário existente: consulte os conceitos relevantes antes de nomear código.]

## Regras e Restrições
[Convenções obrigatórias e limites específicos do projeto, sem repetir seções anteriores.]
Carregue `clean-code` e as referências pertinentes ao planejar, implementar ou revisar código. Preserve o modo TDD/direto e validação proporcional definidos pelo Centaur. As instruções do usuário e deste projeto prevalecem. Consulte `.clean/` se existir, sem escrevê-lo nestes fluxos.

## Módulos e Equipe
[Modo individual/equipe e regras essenciais de integração.]
Consulte `.centaur/workspace.json` para escopos, caminhos e responsáveis. Specs ficam nos diretórios configurados; implementações seguem o backend de memória, preservando os diretórios legados; leia seus índices sob demanda e confirme status nos READMEs canônicos. Use IDs qualificados ao trabalhar com módulos.

---
_Documentação centaur — schema `[versão desta skill, do frontmatter]`, gerada em `[saída de date +%F]`. Atualize com `/centaur-driven-update`._
```

O carimbo usa a versão do frontmatter desta skill, para `update` detectar migrações. Não remova regras customizadas para atingir um tamanho arbitrário; elimine duplicações e extraia detalhes preservando o significado.

## Passo 5 — Salvar detalhes e registros

Prefira atualizar ou vincular documentação existente a duplicá-la. Crie documentos em `docs/system/` somente quando houver conteúdo durável que não caiba nas instruções curtas: visão geral, arquitetura, operação, glossário ou decisões com motivos. Registre evidências e distinga fatos, planos e lacunas. Use caminhos reais e links Markdown relativos; mantenha esses documentos no corpus do Graphify. Se houver glossário, ele é a fonte dos termos e variações proibidas, acessada pela referência em AGENTS.md.

Mapa do sistema, Fluxos e Perspectivas são criados quando solicitados ou quando explicam relações que o texto não esclarece; siga a referência de mapas legíveis de `centaur-driven-graphify` nesses casos. Não gere pastas vazias de Drafts, Fluxos, Perspectivas ou Decisões, nem glossários e mapas apenas para cumprir uma estrutura. Preserve os que já existirem. A inicialização do índice funciona sem `docs/system/` quando as fontes existentes bastarem.

Crie ou complete `.centaur/workspace.json` conforme o contrato de módulos e equipe, preservando caminhos e registros. Registre `master` e os módulos reais, colaboração e responsáveis. Crie os índices abaixo em cada escopo somente quando ausentes; não sobrescreva histórico nem mova pastas existentes. Os caminhos dos exemplos representam o escopo selecionado.

Preserve o backend existente. Para adotar ai-memory, configure e verifique conforme `centaur-driven-memory` antes de selecionar esse backend; sem adoção configurada, use `files` e informe a opção disponível. No backend ai-memory, omita os diretórios de implementação sem histórico e pule o template a seguir.

Somente no backend `files`, crie o diretório `.centaur/implements/` e o arquivo `status.md` dentro dele:

```markdown
# Status das Implementações

Histórico de todas as implementações realizadas neste projeto.

| # | Título | Data | Status | Arquivos Afetados |
|---|--------|------|--------|-------------------|

---

_Atualizado automaticamente pelas skills `/centaur-driven-tdd` e `/centaur-driven-implement`_
```

Crie também o diretório `.centaur/specs/` e o arquivo `index.md` dentro dele:

```markdown
# Specs

Planejamentos de implementações complexas, decompostos em tasks para subagentes.

| # | Título | Data | Status | Tasks |
|---|--------|------|--------|-------|

---

_Atualizado automaticamente pelas skills `/centaur-driven-spec`, `/centaur-driven-tdd`, `/centaur-driven-implement` e `/centaur-driven-run`_
```

Gere `.centaur/andamento.html` com o script `scripts/render-dashboard.py` da skill `centaur-driven-graphify` após criar `workspace.json` e os índices. Passe a raiz do projeto como argumento. A página mostra todos os escopos, specs e tarefas pendentes a partir dos READMEs existentes; a área de notas é local ao navegador. Regere-a após mudanças nas specs conforme o contrato de contexto.

## Passo 6 — Indexar, verificar e entregar

Após salvar as fontes canônicas, siga **Inicializar e sincronizar** de `centaur-driven-graphify`. Reutilize o grafo existente e atualize apenas o necessário quando suportado. Na primeira execução, gere o índice de código e a extração semântica dos documentos; inclua AGENTS.md, documentação existente e registros de todos os escopos, verificando explicitamente a cobertura de `.centaur/`. Inicializar o índice não exige gerar mapas ou HTML.

Confira os artefatos reais, os links do AGENTS.md e os caminhos de workspace. Faça consultas representativas sobre uma responsabilidade do código e uma decisão/regra documentada, abrindo as fontes retornadas. Consulte specs/implementações se já existirem; índices vazios de um projeto novo não exigem registros fictícios. Registre cobertura e pendências em `.centaur/system/sync.md`, fora do corpus.

Se a indexação falhar ou ficar parcial, entregue os documentos preservados e diga quais fontes ainda não estão recuperáveis pelo grafo. Não declare contexto sincronizado apenas porque os arquivos foram criados.

Na entrega, informe arquivos criados/alterados, resultado das consultas e pendências. Indique somente os próximos comandos úteis ao pedido: `check` para consultar, `implement`/`tdd` para mudanças pontuais ou `spec`/`run` para demandas maiores. `update` mantém a documentação; `centaur-driven-graphify` mantém o índice e cria mapas e perspectivas sob demanda.
