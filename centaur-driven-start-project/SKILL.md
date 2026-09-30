---
name: centaur-driven-start-project
description: Inicializa o contexto de um projeto existente com AGENTS.md curto, registros e especificação Centaur; usa busca direta e Graphify opcional sob demanda.
metadata:
  version: 5.1.0
  dependencies: clean-code
  optional-dependencies: graphify, ai-memory
---

# centaur-driven-start-project

## Base conceitual

Leia a [especificação do sistema](../centaur-driven-graphify/references/specification.md). Registre requisitos funcionais e não funcionais em `rules`, e atores, casos de uso e modelo de dados em `specification` no contrato. Evite duplicar a definição; conecte regras a código, testes e evidências.

## Ciclo por contratos — obrigatório

Leia o [ciclo por contratos e evidências](../centaur-driven-graphify/references/lifecycle.md) antes de planejar, executar ou declarar progresso. Ele é a fonte única de estados, aprovação, autonomia, rastreabilidade, gates e próximos passos. Contratos versionados definem o molde; specs planejam entregas; estado e evidências comprovam a realização. Preserve o histórico legado e nunca converta checklist em prova de comportamento.

## Memória de implementações

Leia o [contrato de memória](../centaur-driven-memory/references/contract.md) junto do contexto. O backend em `.centaur/workspace.json` determina o destino dos registros: `files` mantém os READMEs legados; `ai-memory` usa páginas verificadas e dispensa novas pastas `implements/`. As etapas de reserva numérica e escrita em `implements/status.md` abaixo são exclusivas de `files`; no modo ai-memory, aplique o registro, a fila e a consolidação definidos no contrato. Preserve specs e histórico existente.

Estabeleça as instruções e fontes persistentes que os agentes consultarão nas próximas sessões. Documente o projeto existente, sem refatorar código nem impor uma arquitetura nova. Mantenha o contexto obrigatório curto e os detalhes vinculados em .centaur/.

## Passo 1 — Verificar projeto e dependências

Verifique se há código, configurações ou documentação de projeto. Se o diretório estiver vazio, informe que é necessário criar ou abrir um projeto e encerre.

Leia as instruções aplicáveis em `AGENTS.md`, se existir, e preserve documentos e registros existentes. Se o projeto já foi inicializado pelo Centaur, siga `centaur-driven-update` para atualização dentro do pedido autorizado. Um `AGENTS.md` sem Centaur não impede a inicialização: acrescente apenas o necessário, preservando suas regras. Não recrie nem substitua conteúdo existente sem solicitação explícita.

Leia o [contrato de contexto](../centaur-driven-graphify/references/context.md) e o [contrato de módulos e equipe](../centaur-driven-graphify/references/team-workspace.md). Localize e carregue `clean-code` uma vez na sessão; use sua referência de arquitetura ao documentar responsabilidades. Graphify é opcional: carregue sua skill e verifique o CLI somente se for usar o índice. Ausência de Graphify não bloqueia a inicialização.

As instruções do usuário e do projeto prevalecem. Consulte `.clean/` se existir, sem criar ou atualizar essa estrutura. Não instale hooks globais como efeito colateral.

## Passo 2 — Descobrir a estrutura

Use `rg --files`, símbolos e leituras focadas de manifestos, configurações, documentação e pontos de entrada. Para relações amplas, consulte o índice existente sob demanda com `graphify-local.py`. Confirme os resultados no código. Não tente ler todo o negócio nem inicialize índice como efeito colateral.

Identifique stack, comandos de execução e testes, responsabilidades dos módulos e convenções comprovadas. Reutilize documentação válida e registre fontes para as conclusões. Pare quando houver evidência suficiente para inicializar o contexto. A inicialização não exige construir grafo.

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

## Recuperação de contexto
Priorize busca e símbolos do editor. Graphify é opcional para relações amplas; consulte `.centaur/graphify/graph.json` pelo adaptador da skill apenas quando útil. Confirme fontes atuais. Não indexe automaticamente após mudanças. Decisões e documentação gerada ficam em `.centaur/`; código e testes comprovam comportamento.

## Memória de decisões e mudanças
[Backend confirmado em `.centaur/workspace.json`: files ou ai-memory.]
Com ai-memory, siga `centaur-driven-memory`: use workspace/projeto explícitos da `.centaur/ai-memory/config.toml`, consulte decisões relevantes e registre mudanças na wiki com leitura de confirmação. Sem serviço, preserve o registro em `.centaur/ai-memory/pending/` e reporte pendência. Não crie novas pastas implements nesse modo. Memória histórica não substitui código, testes, regras ou o estado das specs.

## Contratos e realização
Contratos em `.centaur/contracts/<id>/vNNN.json` definem o comportamento desejado e a autonomia. Estado em `.centaur/state/` e evidências em `.centaur/evidence/` registram a realização; o ciclo normativo de `centaur-driven-graphify` define formatos e gates. Contratos aprovados são versionados, não reescritos. Antes de editar, consultar apenas as regras e limites pertinentes. Checklist de spec não comprova comportamento. Consulte specs, fontes e evidências diretamente no terminal. Apresente resultado, validação e próxima ação com links; detalhes ficam nos registros. Editor e HTML são opcionais.

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
Consulte `.centaur/workspace.json` para escopos, caminhos e responsáveis. Specs ficam nos diretórios configurados; implementações seguem o backend de memória, preservando os diretórios legados; leia seus índices sob demanda e confirme status nos READMEs canônicos. Use IDs qualificados para specs. Várias specs independentes podem coexistir no mesmo escopo; antes de editar, reserve a spec e registre a posse dos arquivos conforme o contrato de equipe da skill. Consolide índices e estado compartilhado serialmente.

---
_Documentação centaur — schema `[metadata.version desta skill]`, gerada em `[saída de date +%F]`. Atualize com `/centaur-driven-update`._
```

O carimbo usa metadata.version desta skill, para `update` detectar migrações. Não remova regras customizadas para atingir um tamanho arbitrário; elimine duplicações e extraia detalhes preservando o significado.

## Passo 5 — Salvar detalhes e registros

Prefira atualizar ou vincular documentação existente a duplicá-la. Crie documentos em `.centaur/system/` somente quando houver conteúdo durável que não caiba nas instruções curtas: visão geral, arquitetura, operação, glossário ou decisões com motivos. Registre evidências e distinga fatos, planos e lacunas. Use caminhos reais e links Markdown relativos; mantenha esses documentos no corpus do Graphify. Se houver glossário, ele é a fonte dos termos e variações proibidas, acessada pela referência em AGENTS.md.

Mapa do sistema, Fluxos e Perspectivas são criados quando solicitados ou quando explicam relações que o texto não esclarece; siga a referência de mapas legíveis de `centaur-driven-graphify` nesses casos. Não gere pastas vazias de Drafts, Fluxos, Perspectivas ou Decisões, nem glossários e mapas apenas para cumprir uma estrutura. Preserve os que já existirem. A inicialização do índice funciona sem `.centaur/system/` quando as fontes existentes bastarem.

Adicione ao `.gitignore`, preservando regras existentes, os diretórios operacionais gerados: `.centaur/tmp/`, `backups/`, `build/`, `graphify/`, `worktrees/`, `ai-memory/pending/` e diretórios privados de deploy (todos sob `.centaur/`). Nunca versione chaves, caches ou backups. Definições e evidências duráveis continuam versionadas.

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

Leia também a [base conceitual](../centaur-driven-graphify/references/specification.md) e integre requisitos funcionais/não funcionais, casos de uso e relações de dados ao contrato, sem duplicar regras. Comece por uma funcionalidade.

Defina com o usuário o molde geral: responsabilidades dos módulos, invariantes, limites e decisões delegadas. Reutilize autorização explícita; inferências sobre o código são rascunhos. Registre o primeiro contrato útil pelo formato de `references/lifecycle.md`; não crie contratos vazios nem marque comportamento existente como verificado sem evidência. Acrescente `"lifecycle": 1` ao workspace preservando campos. Contratos/estado/evidências pertencem ao repositório em ambos os backends de memória.

Valide os registros com `validate-lifecycle.py`. No terminal, apresente um resumo com os comandos essenciais e links para os registros criados. Gere HTML somente a pedido.

## Passo 6 — Verificar e entregar

Confira links, caminhos do workspace e registros reais. Não crie evidências fictícias nem inicialize Graphify automaticamente. Entregue arquivos alterados e pendências, com próximos comandos pertinentes. Indexação e mapas permanecem sob demanda.
