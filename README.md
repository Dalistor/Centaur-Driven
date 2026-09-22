# Centaur

Conjunto de skills para Codex e [Claude Code](https://claude.com/claude-code) que cria um fluxo de desenvolvimento documentado e rastreável: todo projeto tem contexto persistente, mudanças ficam registradas em ai-memory ou arquivos, o fluxograma semântico evolui junto do código e demandas grandes são decompostas em tasks executadas por subagentes.

## Por que "centaur"?

Centauro: metade humano, metade máquina. Você toma as decisões — o Claude executa com contexto completo e deixa trilha de tudo o que fez.

## Instalação

O conjunto depende de **Graphify** (CLI `graphify`, pacote `graphifyy`, e skill oficial `graphify`) para recuperar contexto persistente, e da skill **`clean-code`**, distribuída pelo projeto [Clean Code Skills](https://github.com/btseee/clean-code-skills). Ela fornece os critérios de qualidade de código e arquitetura usados pelas skills Centaur. A versão de referência desta integração é **3.2.0**.

Instale o CLI Graphify com `uv tool install graphifyy` (ou `pipx install graphifyy`). A versão local de referência desta integração é **0.9.65**; confira o help ao usar outra versão.

Para uma instalação nova, copie o conjunto e a dependência completa para o diretório global de skills do Claude Code:

```bash
git clone https://github.com/Dalistor/Centaur-Driven.git
git clone https://github.com/btseee/clean-code-skills.git
mkdir -p ~/.claude/skills
cp -r Centaur-Driven/centaur-driven-* ~/.claude/skills/
cp -r clean-code-skills/skills/clean-code ~/.claude/skills/
test -f ~/.claude/skills/clean-code/SKILL.md
test -f ~/.claude/skills/clean-code/references/session-protocol.md
test -f ~/.claude/skills/clean-code/references/architecture.md
test -f ~/.claude/skills/clean-code/references/tests.md
graphify install --platform claude
graphify --version
test -f ~/.claude/skills/graphify/SKILL.md
```

Para Codex, copie `centaur-driven-*` e `clean-code` para `~/.agents/skills/`, o [diretório padrão de skills do usuário](https://developers.openai.com/codex/skills). Registre Graphify com `graphify install --platform agents` e confira `~/.agents/skills/graphify/SKILL.md`. O destino `agents` do Graphify 0.9.65 usa esse diretório; o destino `codex` dessa versão usa o caminho legado `.codex/skills`. O comando registra a skill oficial com seus recursos; não copie apenas seu arquivo de entrada. Ao migrar uma instalação antiga, mantenha uma única cópia ativa por nome; guarde backups fora dos diretórios de skills para evitar duplicações.

Reinicie sessões abertas do Claude Code para que as skills apareçam. Elas ficam disponíveis em **todos** os projetos.

> Se preferir instalar apenas em um projeto, copie as pastas do Centaur **e** `clean-code` para `.claude/skills/` na raiz do projeto. Preserve `references/`, `scripts/` e `assets/` da dependência; copiar apenas o `SKILL.md` não basta. Registre também Graphify no projeto com `graphify install --platform claude --project` (para Codex, `graphify install --platform agents --project`, em `.agents/skills/`). Se as dependências já estiverem instaladas, confira suas versões e recursos antes de substituir pastas.

### Memória com ai-memory

O Centaur integra [ai-memory](https://github.com/akitaonrails/ai-memory) pela nova skill `/centaur-driven-memory`. A referência verificada é **2.3.2**. Instale o CLI/servidor conforme o [guia oficial](https://github.com/akitaonrails/ai-memory/blob/main/docs/install.md) e use a skill para configurar o cliente e a identidade do projeto. O modo sem LLM funciona sem chave de provedor. Copiar as skills Centaur não instala o serviço nem ativa captura automática.

Com CLI e servidor disponíveis, a configuração MCP pode ser inspecionada e aplicada assim:

```bash
ai-memory --version
ai-memory install-mcp --client codex
ai-memory install-mcp --client codex --apply
# Claude Code: substitua codex por claude-code.
```

Hooks são opcionais e separados da gravação explícita dos registros. Para captura automática autorizada, confira `ai-memory install-hooks --agent codex` antes de aplicar com `--apply`. Preserve a configuração existente e consulte o help da versão instalada.

Declare os nomes reais de `workspace` e `project` na `.ai-memory.toml`. Após verificar uma escrita útil, sua leitura e checkpoint, a skill adiciona `"memory": {"backend": "ai-memory"}` à raiz de `.centaur/workspace.json`, preservando os demais campos. Todas as chamadas de memória usam essa identidade explícita, inclusive em worktrees.

- **ai-memory:** histórico, decisões e resultados ficam em páginas verificadas. Novas mudanças não criam `.centaur/implements/XXXX/` nem `status.md`. Uma fila em `.centaur/memory-pending/` preserva registros quando o serviço falha.
- **files:** modo de compatibilidade quando `memory` está ausente ou o backend é `files`; mantém os registros numerados existentes. Nenhum projeto muda de backend silenciosamente.
- **Nos dois modos:** specs, checklists, regras e arquitetura atual permanecem no repositório. Graphify localiza código e documentos; ai-memory recupera histórico. Não é necessário copiar o grafo ou a wiki entre os serviços.

A migração importa registros selecionados com verificação e sem apagar pastas ou links antigos. Assim, `implements/` deixa de ser obrigatório para novas mudanças no modo ai-memory, mas seu histórico existente continua preservado. O [contrato de memória](centaur-driven-memory/references/contract.md) define falhas, retomada e execução paralela.

### Contrato da dependência

As skills que recuperam contexto técnico declaram Graphify em `metadata.dependencies`; as de desenvolvimento também declaram `clean-code`. A skill `memory` declara ai-memory; `security` usa Graphify com leitura direta em caso de indisponibilidade e ai-memory opcional. Esse metadado documenta o contrato, não instala pacotes automaticamente. O CLI e a skill oficial devem estar disponíveis no ambiente do agente. O [contrato de contexto](centaur-driven-graphify/references/context.md) define consultas, fontes canônicas, atualização e recuperação de falhas.

- `start-project` e `spec` usam os critérios de responsabilidade e direção de dependências na documentação e no planejamento.
- `implement`, `tdd` e `deploy` aplicam os critérios ao escrever e revisar código, testes, workflows e scripts.
- `run` e `mcp` garantem o carregamento também pelos executores.
- `check` e `update` usam os critérios na análise, preservando seus limites de leitura e documentação.

As instruções do usuário e do projeto prevalecem. O Centaur mantém seu roteamento entre TDD e modo direto, com validação proporcional ao risco. Graphify recupera relações no código; ai-memory, quando configurado, recupera decisões e histórico; `AGENTS.md`, `.centaur/` e `docs/system/` preservam instruções, decisões e histórico canônicos; `.clean/`, quando já existe, é consultado sem escritas por estes fluxos. Carregar `clean-code` não inicia auditoria ou refatoração geral.

Projetos já documentados recebem o contrato de contexto do novo template por `/centaur-driven-update`.

### Contexto com menos leitura

Após ler as instruções de `AGENTS.md`, a IA consulta ai-memory quando precisa de decisões anteriores e, para localizar código/documentos, executa `graphify query "<objetivo da tarefa>" --budget 1500` e abre as fontes relevantes. Decisões duráveis ficam nos documentos canônicos e entram no índice para recuperação em outras sessões. Histórico completo, grafo JSON e relatórios extensos não são carregados em toda tarefa. Código atual e validação confirmam o comportamento; o grafo pode conter planos ou inferências.

A inicialização gera o índice; os fluxos que alteram código ou documentação o atualizam após salvar os registros. Após cada `implement` ou `tdd` com alterações, a atualização é obrigatória na mesma tarefa, incluindo código, testes e registros, com consulta de verificação. No `run`, somente o coordenador sincroniza, cobrindo cada implementação ao fim da onda, antes da próxima onda ou da entrega. Consultas com `check` permanecem somente leitura. Falhas ou índice desatualizado geram uma limitação explícita e leitura direta focada; trabalho validado é preservado. O orçamento de consulta não garante um percentual de economia de tokens.

`centaur-driven-graphify` continua como manutenção do índice e autoria de mapas, drafts e perspectivas. Recuperar contexto já faz parte de cada skill, sem exigir uma invocação manual adicional.

## As skills

| Skill | O que faz |
|-------|-----------|
| `/centaur-driven-commitAndPush` | Cria commit e publica na main após buscar a branch remota, simular integração e validar; bloqueia em conflitos e sugere resolução |
| `/centaur-driven-start-project` | Cria o `AGENTS.md`, configura escopos, backend de registros e specs |
| `/centaur-driven-memory` | Configura ai-memory, consulta decisões, registra mudanças, reenvia pendências e importa histórico legado |
| `/centaur-driven-check` | Responde perguntas sobre o projeto com base na documentação e no código — sem alterar nada |
| `/centaur-driven-security` | Audita projeto ou diff, verifica achados e variantes e entrega relatório com evidências; não corrige código |
| `/centaur-driven-tdd` | Mudanças pontuais com **regra de negócio real**: teste antes do código, ciclo red-green-refactor, testes mínimos por risco e manutenção da suíte existente |
| `/centaur-driven-implement` | Mudanças pontuais **estruturais, de configuração ou de UI** — e projetos sem infraestrutura de teste |
| `/centaur-driven-spec` | Decompõe uma demanda grande em tasks atômicas por camada, cada uma marcada como TDD ou direta, salvas em `.centaur/specs/` |
| `/centaur-driven-run` | Executa uma spec: lança um subagente por task conforme o Modo, paraleliza as independentes e consolida o resultado |
| `/centaur-driven-graphify` | Inicializa, sincroniza e repara o índice; cria mapas, drafts e perspectivas sob demanda |
| `/centaur-driven-mcp` | Busca a documentação de uma API externa em um MCP server e roteia a requisição para tdd, implement ou spec com esse contexto anexado |
| `/centaur-driven-deploy` | Configura deploy contínuo para uma VPS (GitHub Actions + SSH + rsync): gera a chave, valida o acesso, cadastra os secrets e acompanha o primeiro run |
| `/centaur-driven-update` | Manutenção da documentação: migra o `AGENTS.md` quando as skills evoluem, audita o histórico, resolve contradições e consolida para agentes novos |

## Fluxo de trabalho

### 1. Comece documentando o projeto

```
/centaur-driven-start-project
```

A skill reutiliza o grafo existente para descobrir a estrutura e confirma as fontes atuais. Sem índice, faz uma inspeção focada de manifestos, documentação e pontos de entrada. Pergunta apenas sobre decisões e lacunas materiais, como intenção, restrições e colaboração ainda não definida.

O fluxo estabelece:

- `AGENTS.md` curto na raiz — regras, comandos essenciais, limites arquiteturais e recuperação de contexto.
- `.centaur/workspace.json` e índices de specs — escopos, responsáveis e backend de registros; índices de implementações somente em `files`, preservando os existentes.
- Documentos detalhados somente quando necessários — preferindo fontes existentes; arquitetura, operação, glossário e decisões podem ficar em `docs/system/`.
- `graphify-out/` — índice de código e documentos, gerado ou atualizado após salvar as fontes e verificado com consultas.

As seções **Arquitetura de Camadas**, **Testes** e **Vocabulário e Idioma do Código** continuam no `AGENTS.md` como instruções concisas e referências. A skill preserva a arquitetura real; ausência de testes é registrada sem obrigar adoção de framework ou meta de cobertura. Detalhes são consultados conforme a tarefa.

Mapas, perspectivas, glossários e pastas de drafts são criados quando há conteúdo ou necessidade concreta. O índice funciona com as fontes existentes. Um `AGENTS.md` anterior é preservado; projetos já inicializados seguem para `update` dentro do escopo autorizado.

### 2. Para mudanças com comportamento testável, use tdd

```
/centaur-driven-tdd adicionar validação de email no cadastro
```

Regra de negócio, validação com consequência, cálculo, correção de bug — o que tem comportamento com regra real entra por aqui, e **o teste vem antes do código**. Ser tecnicamente testável não basta: mapeamento direto, passthrough e fiação sem lógica vão pelo `implement`.

O fluxo usa ciclos pequenos inspirados no [TDD do Superpowers](https://github.com/obra/superpowers/blob/main/skills/test-driven-development/SKILL.md): identifica uma lacuna, observa o teste falhar, implementa o necessário e refatora com os testes verdes. Antes de acrescentar casos, confere a proteção existente. Cada teste novo precisa detectar uma falha concreta ainda não coberta; critérios de aceite não viram automaticamente uma bateria de testes.

Quando a regra muda, o teste antigo é atualizado junto. Casos redundantes podem ser consolidados e testes de funcionalidades removidas podem sair, sempre com motivo e preservando os cenários ainda válidos. Teste falhando não é considerado desatualizado só porque discorda do código. Não há meta automática de 100% de branches nem quota de testes; gates já exigidos pelo projeto continuam valendo.

Durante o ciclo, roda a seleção afetada; antes de entregar, executa a suíte e os checks previstos pelo projeto, reportando falhas e limitações. Registra a mudança e a manutenção dos testes no backend configurado e sincroniza os documentos locais no Graphify.

### 3. Para mudanças estruturais, use implement

```
/centaur-driven-implement renomear a pasta de handlers para controllers
```

O implement cobre o que não faz sentido testar primeiro: renomear, mover arquivo, configuração, scaffold, mudança só de UI/estilo — e projetos que ainda não têm infraestrutura de teste. Lê o contexto, explora o código afetado, **tira todas as dúvidas antes de escrever qualquer linha**, implementa respeitando a Arquitetura de Camadas do `AGENTS.md` (regra de negócio em service, query em repository, handler fino), **revisa a clareza do que escreveu** (nomes que revelam intenção, vocabulário do domínio, sem número mágico nem comentário que narra a linha), valida (testes, lint e revisão de violação de camadas) e entrega um registro verificado no backend configurado, atualizando o Graphify após salvar os registros.

Se a mudança pedida tiver regra de negócio relevante, ele mesmo redireciona para o `/centaur-driven-tdd`. Se a demanda for grande demais (muitas camadas, mais de ~4 arquivos), recusa e orienta a usar spec + run.

### 4. Para demandas grandes, use spec

```
/centaur-driven-spec migrar autenticação de sessão para JWT
```

A skill explora o código, resolve as ambiguidades com você **antes** de planejar e gera `.centaur/specs/YYYY/README.md` com tasks atômicas e ordenadas. A decomposição segue as camadas do projeto, de dentro para fora — models, DTOs, repositories, services, handlers, testes de integração — e cada task declara quais camadas toca e proíbe tocar as demais, o que permite paralelizar tasks de camadas independentes. Cada instrução é autocontida, com todas as decisões já tomadas.

Cada task carrega também um campo **`Modo`**: `TDD` para as que têm **regra de negócio real** (o teste nasce dentro da própria task, junto do código) e `direto` para as estruturais e para o que é trivial mesmo sendo testável — mapeamento de campos, fiação, CRUD sem regra. Testes de integração só entram como task quando há fluxo ponta a ponta que valha. Por isso não existe task de "escrever os testes da camada X" — o teste pertence à task que implementa o comportamento. Tasks `TDD` trazem critérios observáveis, riscos e compatibilidade a preservar. O executor pode reaproveitar ou atualizar testes existentes, mantendo esses critérios; a spec não exige uma quantidade fixa de testes novos.

### 5. Para executar a spec, use run

```
/centaur-driven-run 0001
```

O run é o orquestrador — e é **restrito a tasks de specs**: não implementa nada por conta própria e recusa qualquer pedido fora do que está planejado. Ele:

- Monta o plano em ondas — tasks com dependências satisfeitas rodam em paralelo, o resto aguarda — e apresenta o plano para você confirmar antes de iniciar
- Lança um subagente por task, escolhendo a skill pelo `Modo` da task (`TDD` → `/centaur-driven-tdd`, `direto` → `/centaur-driven-implement`) e passando a instrução da spec **verbatim** com o prefixo `Spec YYYY — Task NN`
- Esse prefixo ativa o **modo spec** da skill de execução dentro do subagente: não faz perguntas (as decisões já foram tomadas na spec) e encerra com um relatório estruturado, sem tocar nos arquivos compartilhados
- Se uma task bloquear, pula as dependentes, continua as demais e reporta o que precisa da sua decisão
- Execução paralela é segura: em ai-memory, o coordenador atribui UUIDs e publica os registros que os executores entregam na fila; em `files`, cada executor reserva seu número via `mkdir`. **Só o run escreve** no checklist da spec e nos índices compartilhados — a consolidação acontece ao fim de cada onda, a partir dos relatórios, com um coordenador responsável por consolidar os registros compartilhados
- Execução é retomável: rodar `/centaur-driven-run 0001` de novo continua de onde parou

### 6. Para consultar, use check

```
/centaur-driven-check como funciona o fluxo de pagamento?
/centaur-driven-check o que ainda falta na spec 0001?
```

Consulta primeiro o Graphify e confirma a resposta nas instruções, registros e trechos atuais pertinentes — apontando arquivo e linha quando fizer sentido.

### Auditoria de segurança

```
/centaur-driven-security auditar autorização e isolamento entre tenants
/centaur-driven-security revisar as mudanças da branch atual contra main
/centaur-driven-security verificar se o achado SEC-001 é um falso positivo
```

A skill adapta práticas de [auditoria da Trail of Bits](https://github.com/trailofbits/skills): primeiro entende o fluxo e suas proteções, depois verifica cada suspeita e procura variantes das causas confirmadas. Achados incluem localização, precondições, impacto, evidência, gravidade justificada e sugestão de correção. Hipóteses pendentes e falsos positivos ficam separados.

O resultado padrão é `.centaur/audits/<uuid>.md`; se você pedir somente leitura ou resposta na conversa, não grava o relatório. A auditoria preserva código e configuração, usa ferramentas disponíveis e não executa ataques contra serviços reais nem publica achados por efeito colateral. Correções seguem por `tdd`, `implement` ou `spec` + `run`, conforme o pedido. O [guia da skill](centaur-driven-security/SKILL.md) e sua [referência](centaur-driven-security/references/security-review.md) incluem a atribuição e a licença da adaptação.

### 7. Para integrar com API externa, use mcp

```
/centaur-driven-mcp asaas-docs criar cobrança pix com split
/centaur-driven-mcp https://docs.asaas.com/mcp criar cobrança pix com split
```

Quando a mudança depende de uma API de terceiros, o problema não é implementar — é saber o que a API espera. O `mcp` é a ponte: consulta um [MCP server](https://modelcontextprotocol.io) com a documentação oficial do serviço, extrai só o que a requisição precisa (autenticação, endpoints, request, response, erros, restrições) e monta um **dossiê** factual.

Ele **não implementa nada**. Classifica a requisição e roteia: pergunta pura ele responde na hora; comportamento testável vai para o `/centaur-driven-tdd`; estrutural vai para o `/centaur-driven-implement`; integração grande vai para o `/centaur-driven-spec`. A requisição original segue verbatim — o dossiê é anexado, não substitui.

O dossiê tem um campo obrigatório **"Não encontrado no MCP"**, listando tudo que foi procurado e não achado. É o que impede o subagente de completar lacuna com memória: nada é afirmado sobre a API externa sem ter vindo de uma resposta real de uma tool do MCP.

A skill é **agnóstica de MCP** — descobre os disponíveis em tempo de execução. Se o primeiro argumento for uma URL em vez de um nome, ela detecta o transporte, pede sua confirmação e instala o MCP no escopo global antes de seguir. Credenciais nunca entram em código ou em arquivo versionado: só o **nome** da variável de ambiente é documentado.

### 8. Para colocar no ar, use deploy

```
/centaur-driven-deploy
```

Configura deploy contínuo do projeto para uma **VPS que você controla**, via GitHub Actions + SSH + rsync. A regra da skill é entregar deploy **configurado e testado**, não instruções: ela inspeciona o projeto, gera o par de chaves SSH, instala a pública na VPS, coleta o `known_hosts`, **audita o que o `rsync --delete` apagaria antes de rodar**, escreve o workflow, cadastra secrets e variables pelo `gh` CLI e acompanha o primeiro run. Ação manual só quando o passo exige acesso que ela não tem (senha de sudo na VPS, botão sem equivalente em CLI).

Antes de qualquer comando que altere a VPS ou o GitHub, ela mostra o comando e pede confirmação. No fim, documenta o que ficou fora do repositório e **como revogar** o acesso.

Cobre Docker/Docker Compose e processo direto (systemd, pm2). Fora do escopo: PaaS (Vercel, Railway, Fly), Kubernetes, registry de imagem, blue-green e rollback automático.

### 9. Para manter a documentação viva, use update

```
/centaur-driven-update
```

Projetos envelhecem em duas direções. As skills ganham seções novas — Arquitetura de Camadas, stack de testes, Vocabulário e Idioma do Código — e o `AGENTS.md` escrito meses atrás não as tem. E o histórico acumula implementações que se contradizem: o que era verdade na `0003` foi desfeito na `0021`, mas o `AGENTS.md` ainda descreve a versão antiga. Um agente que chega lê tudo isso e age com informação errada.

O `update` resolve as duas. Ele lê o **carimbo de schema** na última linha do `AGENTS.md`, compara com a versão do `centaur-driven-start-project` instalado e migra o que ficou para trás — usando o template da skill instalada como fonte de verdade, e não uma tabela de migrações embutida que apodreceria. Seções customizadas por você nunca são apagadas.

Depois vem a parte que importa no dia a dia: audita a integridade dos registros (pasta sem README, linha fantasma no `status.md`, spec com todas as tasks feitas mas ainda `Em andamento`), cruza as implementações pelos arquivos afetados para achar onde uma desfez a outra, e detecta o que a documentação afirma e o código desmente. Cada conflito é apresentado com **evidência** — o que a doc diz, o que é verdade, e onde está a prova. Sem evidência não é conflito, é palpite.

Por fim consolida para quem chega depois: promove regras essenciais para o `AGENTS.md` e detalhes duráveis para documentos vinculados (como estratégias de mock e glossários) e, no histórico em arquivos, arquiva as linhas antigas do `status.md` em `.centaur/implements/arquivo.md`, marcando o que foi superado. As skills leem as instruções de `AGENTS.md`, consultam o Graphify e abrem histórico sob demanda; manter instruções curtas e índices focados reduz leituras repetidas.

Ele **não toca em código**: bug ou violação de camada que encontrar vira relatório com a skill certa para resolver. E nunca apaga pasta de implementação ou de spec — arquivar é mover linha de índice, o registro fica.

### 10. Para compreender e evoluir o sistema, use Graphify

```text
/centaur-driven-graphify inicializar
/centaur-driven-graphify criar draft da jornada de compra
/centaur-driven-graphify perspectiva fluxo de dados entre frontend e backend
/centaur-driven-graphify sincronizar frontend/0007
```

A skill usa o Graphify como índice para a IA localizar conceitos, arquivos e relações; depois confirma as respostas nas fontes. A visão geral, os fluxos, as decisões e as perspectivas humanas ficam em `docs/system/`. O mapa principal é `docs/system/Mapa do sistema.md`, organizado por **módulo → funcionalidade/página → processo**, com diagramas Mermaid pequenos e links para detalhes. Ao abrir a raiz do projeto como vault no Obsidian, essa nota aparece no explorador e o Mermaid é renderizado; abrir o vault não seleciona automaticamente o mapa. HTMLs técnicos do Graphify são opcionais para investigação.

Specs permanecem nos escopos de `.centaur/workspace.json`, com estado nos READMEs e índices. Implementações seguem o backend configurado; diretórios implements existentes são preservados. O quadro visual foi removido. A sincronização inclui código e documentos: atualização AST isolada não atualiza specs/implements. As skills consolidam os registros primeiro e depois atualizam o Graphify serialmente; falhas semânticas são reportadas como pendências.

O CLI e a skill oficial são dependências do conjunto; siga a seção Instalação acima e a [documentação oficial](https://github.com/Graphify-Labs/graphify).

No Codex, a skill oficial é invocada como `$graphify`. A integração Centaur orienta sua utilização e verifica se os diretórios ocultos de `.centaur/` entraram no corpus. O CLI local de referência é 0.9.65. Para migrar projetos existentes, `/centaur-driven-update` segue a [migração](centaur-driven-graphify/references/migration.md), preservando textos e registros legados.

## O código é a documentação

As skills de execução tratam o código como a documentação principal do projeto — o registro da implementação é trilha de auditoria, não explicação do código. Por isso o "porquê" tem uma ordem de precedência fixa:

1. **No próprio código**, sempre que couber — constante nomeada no lugar do número solto, função extraída cujo nome diz a intenção, tipo ou enum no lugar de string livre
2. **Em comentário curto ao lado**, só quando o porquê é externo ao código: regra de negócio arbitrária, limite de uma API, workaround de bug de terceiro. Comentário diz **por que**, nunca **o que**
3. **No registro da implementação** (wiki ou README), só o que não cabe num arquivo de código: alternativas descartadas, trade-off de arquitetura, contexto histórico

Quem abre o fonte não lê `.centaur/`, e o README envelhece enquanto o código muda — por isso o README nunca substitui código claro.

O `implement` tem uma etapa dedicada a isso (revisar a clareza antes de validar) e o `tdd` aplica o mesmo critério no ciclo REFACTOR: nome que revela intenção, vocabulário do domínio vindo do `AGENTS.md` ou do glossário vinculado, função que faz uma coisa só, sem número mágico, sem aninhamento profundo, sem comentário que narra a linha seguinte, sem código morto. E a regra que resume: **nome que precisa de comentário para ser entendido é nome errado — troque o nome**.

## Estrutura gerada no projeto

`implements/` e seus índices abaixo existem somente no modo `files` ou como histórico legado preservado. Em ai-memory, as páginas ficam no store do serviço; `.ai-memory.toml` identifica o projeto e `.centaur/memory-pending/<uuid>.md` só existe enquanto há registros a confirmar.

```
projeto/
├── AGENTS.md                        # Instruções essenciais e referências para contexto
│                                    # Última linha: carimbo de schema, usado pelo update
├── docs/system/                    # Detalhes e mapas quando necessários
├── graphify-out/                   # Índice derivado de código e documentos
└── .centaur/
    ├── workspace.json              # Escopos, caminhos e responsáveis
    ├── modules/
    │   ├── frontend/               # specs/index.md e implements/status.md próprios
    │   └── backend/                # specs/index.md e implements/status.md próprios
    ├── implements/                # Histórico mestre
    │   ├── status.md                # Tabela com as implementações recentes
    │   ├── arquivo.md               # Índice das antigas (criado pelo update quando cresce)
    │   └── 0001/
    │       └── README.md           # Trilha de auditoria da implementação
    ├── specs/
    │   ├── index.md                 # Tabela com todas as specs
    │   └── 0001/README.md           # Spec com tasks, dependências e checklist
    └── system/                      # sync.md: cobertura e pendências do índice
```

## Ciclo de vida

No diagrama, `registro` significa página ai-memory verificada ou README numerado no backend `files`. A manutenção de índices `implements/` aplica-se somente ao histórico em arquivos.

```
/centaur-driven-start-project          (uma vez por projeto)
        │
        ├── depende de API externa ──► /centaur-driven-mcp ──► dossiê da doc oficial
        │                                       │
        │                                       └── anexa o dossiê e roteia para um dos três abaixo
        │
        ├── pontual + testável ──► /centaur-driven-tdd ──────► registro
        │
        ├── pontual estrutural ──► /centaur-driven-implement ─► registro
        │
        ├── demanda grande ──► /centaur-driven-spec ──► .centaur/specs/YYYY/
        │                               │
        │                               └── /centaur-driven-run YYYY
        │                                       │
        │                                       ├── N subagentes (modo spec), por Modo da task
        │                                       │       ├── Modo TDD    ──► /centaur-driven-tdd
        │                                       │       ├── Modo direto ──► /centaur-driven-implement
        │                                       │       │
        │                                       │       └── implementa, documenta e reporta
        │                                       │
        │                                       └── consolida checklist, status da spec e registros
        │
        ├── desenhar/refinar sistema ──► /centaur-driven-graphify ──► Grafo, documentos e perspectivas
        │
        ├── subir para a VPS ──► /centaur-driven-deploy ──► .github/workflows/ + registro
        │
        └── doc envelhecida ──► /centaur-driven-update ──► AGENTS.md migrado e consolidado
                                        │
                                        ├── migra o schema (carimbo vs skill instalada)
                                        ├── audita integridade dos registros
                                        ├── resolve conflitos doc × código × histórico
                                        └── arquiva índice antigo em implements/arquivo.md
```

Specs seguem os status `Pendente`, `Em andamento`, `Bloqueada`, `Em revisão` e `Concluída`; conclusão exige validação e integração. Cada implementação referencia a spec/task de origem, e cada task concluída aponta para a implementação — trilha completa nos dois sentidos.

## Módulos e colaboração

O `start-project` pergunta explicitamente se o desenvolvimento será **individual ou em equipe** e registra a resposta. Ambos permitem módulos; no modo equipe, também define responsáveis por módulo e pela integração. No individual, o próprio desenvolvedor assume essas responsabilidades.

O `start-project` identifica os módulos reais e registra `.centaur/workspace.json`. A pasta mestre `.centaur/` conserva `specs/` e `implements/` existentes. Cada módulo tem suas próprias specs e, no modo files, implementações, por padrão em `.centaur/modules/<módulo>/`. Os caminhos podem ser configurados dentro do projeto. A configuração e as regras da equipe ficam vinculadas no `AGENTS.md`.

Uma demanda de todo o sistema recebe uma spec `master/0001`, ligada às specs `frontend/0001` e `backend/0001`, por exemplo. Use `/centaur-driven-run frontend/0001` para executar o escopo certo; números repetidos sem módulo exigem desambiguação. Cada task tem responsável, arquivos e dependências. Em clones diferentes, novos IDs podem receber sufixo único para evitar colisões. O contrato completo está em [módulos e equipe](centaur-driven-graphify/references/team-workspace.md).

Trabalho paralelo usa posse explícita de tasks e branches/worktrees por executor quando necessário. Um coordenador consolida arquivos compartilhados, integra as entregas e atualiza a spec mestre. Ela só conclui quando as specs filhas e os critérios de integração estiverem atendidos. Projetos legados mantêm seus caminhos; `/centaur-driven-update` adiciona os novos escopos e sincroniza o grafo sem mover o histórico.

## Commit e push na main

Use `/centaur-driven-commitAndPush` para publicar o trabalho solicitado. A skill revisa o escopo, cria o commit, busca a main remota, simula a integração e valida o resultado em worktree temporário. Se houver conflito, informa os arquivos e propõe resolução em branch de trabalho. Se estiver limpo, faz push normal do resultado validado para main; não força histórico nem ignora proteção de branch. Uma atualização concorrente exige nova checagem.

O nome `centaur-driven-commitAndPush` foi preservado conforme solicitado; validadores que exigem nomes exclusivamente em minúsculas com hífens podem rejeitá-lo.
