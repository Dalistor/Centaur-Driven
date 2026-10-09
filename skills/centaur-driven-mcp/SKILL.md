---
name: centaur-driven-mcp
description: Ponte dinâmica entre um MCP server e o fluxo centaur - consulta a documentação/tools do MCP informado, extrai o que é relevante para a requisição do usuário e roteia para tdd, implement ou spec com esse contexto anexado. Também instala o MCP no escopo global quando recebe uma URL no lugar do nome. Uso - /centaur-driven-mcp Nome do MCP | URL do MCP [Requisição do usuário]. Não depende de nenhum MCP específico - descobre os disponíveis em tempo de execução.
metadata:
  version: 5.0.0
  dependencies: clean-code
  optional-dependencies: centaur-driven-graphify, centaur-driven-memory
---

# centaur-driven-mcp

## Uso no agente

Use esta skill no Codex, Claude Code ou Gemini CLI pelas ferramentas disponíveis na sessão. Leia referências e execute helpers a partir da pasta instalada desta skill. As chamadas `/centaur-driven-*` neste texto identificam skills: no Codex, use `$centaur-driven-*`; no Claude Code, `/centaur-driven-*`; no Gemini CLI, peça a ativação pelo nome. Não presuma ferramentas, modelos ou subagentes de outro cliente.

Para operações de memória, chame a [skill centaur-driven-memory](../centaur-driven-memory/SKILL.md): leia suas instruções, informe operação e escopo e use seu contrato. Ela encapsula a dependência ai-memory; consulta permanece somente leitura e registros respeitam a posse de executor/coordenador. Não configure nem migre o backend como efeito colateral.

## Ciclo por contratos — obrigatório

Leia o [ciclo por contratos e evidências](../centaur-driven-graphify/references/lifecycle.md) antes de planejar, executar ou declarar progresso. Ele é a fonte única de estados, aprovação, autonomia, rastreabilidade, gates e próximos passos. Contratos versionados definem o molde; specs planejam entregas; estado e evidências comprovam a realização. Preserve o histórico legado e nunca converta checklist em prova de comportamento.

## Memória de implementações

Leia o [contrato de memória](../centaur-driven-memory/references/contract.md) junto do contexto. O backend em `.centaur/workspace.json` determina o destino dos registros: `files` mantém os READMEs legados; `ai-memory` usa páginas verificadas e dispensa novas pastas `implements/`. As etapas de reserva numérica e escrita em `implements/status.md` abaixo são exclusivas de `files`; no modo ai-memory, aplique o registro, a fila e a consolidação definidos no contrato. Preserve specs e histórico existente.

## Contexto persistente — Graphify

Antes de explorar o projeto, siga o [contrato de contexto](../centaur-driven-graphify/references/context.md). Priorize busca textual e símbolos do editor. Graphify é opcional e sob demanda para relações amplas; consulte o índice existente apenas quando útil, confirmando as fontes atuais. Não inicialize nem sincronize o grafo como consequência de implementar ou consultar. Para histórico e decisões, consulte ai-memory quando configurado.

## Escopos e equipe

Antes do fluxo, leia o [contrato de módulos e equipe](../centaur-driven-graphify/references/team-workspace.md). Ele define resolução de caminhos, IDs qualificados, responsabilidade, concorrência e estados. Os exemplos legados abaixo usam o escopo selecionado; aplique o contrato também aos comandos e templates.

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (nos diretórios de skills do Codex, Claude Code ou Gemini CLI; veja os caminhos no README do Centaur) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Use os critérios de fronteiras e validação da dependência ao preparar o contexto da integração. O executor deve carregar `clean-code` na própria sessão. O dossiê obtido no MCP continua sendo a fonte sobre a API; a dependência não preenche lacunas nem autoriza implementação nesta skill.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

Você é a ponte entre um MCP server e o fluxo de implementação centaur. Sua função é **buscar conhecimento externo no MCP informado** e entregá-lo, já filtrado, para quem vai responder ou implementar.

**Invocação:** `/centaur-driven-mcp <Nome do MCP | URL do MCP> [Requisição do usuário]`

O primeiro argumento aceita duas formas:
- **Nome** de um MCP já registrado → `/centaur-driven-mcp <nome-do-mcp> <requisição>` (ex: `/centaur-driven-mcp asaas-docs criar cobrança pix com split`)
- **URL** de um MCP ainda não registrado → `/centaur-driven-mcp <url-do-mcp> <requisição>` (instala no escopo global antes de seguir — Passo 0)

Não presuma que os MCPs dos exemplos existem — os disponíveis são descobertos em tempo de execução (Passo 1).

## Restrições absolutas

1. **Você NÃO implementa código.** Toda implementação acontece dentro de `/centaur-driven-tdd`, `/centaur-driven-implement` ou é planejada por `/centaur-driven-spec`. Você só pesquisa, filtra e roteia.
2. **Você não inventa API externa.** Tudo que você afirmar sobre o serviço do MCP (endpoints, campos, payloads, limites, códigos de erro) tem que ter vindo de uma resposta real de uma tool do MCP. Se o MCP não trouxe a informação, diga que não trouxe — nunca preencha com memória.
3. **Você é agnóstico de MCP.** Não presuma qual MCP está instalado nem quais tools ele expõe. Descubra em tempo de execução (Passo 1).

## Passo 0 — Instalar o MCP (só quando o argumento for uma URL)

Se o primeiro argumento não for uma URL HTTP/HTTPS, pule para o Passo 1. Confira o cliente em uso e sua configuração MCP existente. Consulte o help e a documentação da versão instalada antes de escolher comandos, transportes, escopo e autenticação. Use o mecanismo do Codex, Claude Code ou Gemini CLI; não execute comandos de outro cliente.

1. Verifique se a URL já está registrada. Reutilize o nome existente sem reinstalar.
2. Consulte a documentação do servidor e verifique seu transporte e disponibilidade com o handshake MCP compatível. Erro de conexão impede instalar; autenticação ausente exige resolver qual credencial/header usar sem inventar tokens ou expor valores.
3. Derive um nome curto do servidor, evitando colisões com registros existentes.
4. Mostre URL, nome, transporte, escopo global e exigências de autenticação antes da alteração persistente. Aplique somente conforme autorização existente; quando ela não abranger a configuração global, peça aprovação da ação concreta.
5. Instale pelo mecanismo MCP do cliente atual, preservando outras entradas e referenciando credenciais pela configuração de segredos suportada. Verifique conexão; em falha, reverta somente a entrada criada nesta operação.
6. Verifique se as ferramentas carregaram na sessão. Se estiverem disponíveis, continue. Caso contrário, informe o registro criado e a recarga/reinício exigido pelo cliente; encerre sem substituir a consulta por HTTP avulso ou memória.

## Passo 1 — Resolver o MCP

O primeiro argumento é o nome do servidor registrado. Descubra as ferramentas e schemas disponíveis no cliente atual. Se forem diferidas, use seu mecanismo de descoberta quando disponível. Prefixos e nomes de ferramentas variam entre clientes; não exija `ToolSearch` ou um prefixo fixo.

Se nenhuma ferramenta estiver disponível, confira os servidores registrados pelo mecanismo MCP do cliente. Um registro conectado sem ferramentas exige recarga conforme o cliente; um nome não registrado exige apresentar as opções e resolver qual usar. Se o usuário não informou um nome, apresente os servidores disponíveis e peça a seleção. Não presuma MCPs dos exemplos.

## Passo 2 — Ler o contexto do projeto

Leia `AGENTS.md` e recupere o contexto da solicitação pelo contrato Graphify acima. Consulte apenas os registros e trechos relevantes do escopo; para status, confirme o README canônico.

Se `AGENTS.md` não existir, avise:
> "Este projeto ainda não foi documentado. Execute `/centaur-driven-start-project` primeiro — sem isso não consigo decidir em qual camada a integração entra."

E pare. O valor desta skill é casar a doc externa com a arquitetura do projeto; sem arquitetura documentada, não há casamento.

Se já houver implementação anterior relacionada ao mesmo serviço em `status.md`, leia o `README.md` dela — convenções, cliente HTTP, tratamento de erro e credenciais já estabelecidos devem ser reaproveitados, não reinventados.

## Passo 3 — Consultar o MCP

Descubra o que as tools do MCP fazem e use as adequadas para responder à requisição.

- Comece por uma tool de busca/pesquisa, se houver. Consulte com os termos da requisição do usuário **e** com os termos técnicos equivalentes (português e inglês, quando o serviço for internacional).
- Faça consultas **em paralelo** quando forem independentes.
- Se a primeira consulta trouxer referências a outros recursos necessários (autenticação, webhooks, objetos relacionados, sandbox), consulte também — uma integração incompleta é pior que nenhuma.
- Pare de consultar quando tiver: endpoint(s), autenticação, formato de request, formato de response, erros relevantes e restrições (limites, sandbox, idempotência).

Se o MCP não expuser tool de busca e sim tools de operação (criar recurso, listar dados etc): **não execute operações de escrita**. Use só as de leitura para inspecionar formatos, e trate os schemas das próprias tools como a documentação.

## Passo 4 — Montar o dossiê

Consolide o que veio do MCP em um bloco curto e factual. Nada de copiar a doc inteira — só o que a implementação vai usar:

```markdown
### Contexto obtido via MCP `<nome>`

**Requisição:** [o que o usuário pediu]

**Autenticação:** [como autentica, qual header, onde a credencial deve ficar]
**Endpoints:** [método + caminho, um por linha]
**Request:** [campos obrigatórios e opcionais que importam, com tipo]
**Response:** [campos que o projeto vai consumir]
**Erros:** [códigos e situações que precisam de tratamento]
**Restrições:** [sandbox, rate limit, idempotência, valores mínimos, o que for aplicável]

**Não encontrado no MCP:** [tudo que você procurou e não achou — ou "nada"]
```

O campo **Não encontrado no MCP** é obrigatório. É ele que impede o executor de assumir que o dossiê é completo.

## Passo 5 — Classificar a requisição

Decida o destino:

| Situação | Destino |
|---|---|
| Usuário só perguntou (como funciona, quais campos, existe suporte a X) | Responda direto no Passo 6a |
| Mudança pontual com regra de negócio real (cálculo, validação com consequência, tratamento de erro com decisão) **e** projeto tem testes | `/centaur-driven-tdd` |
| Mudança pontual estrutural/config (adicionar client, variável de ambiente, tipagem), mapeamento trivial de payload, ou projeto sem testes | `/centaur-driven-implement` |
| Integração grande (múltiplos comportamentos, decisões de produto ou dependências que exigem planejamento) | `/centaur-driven-spec` |

Apresente ao usuário: o dossiê do Passo 4, a classificação e o destino escolhido. Prossiga conforme autorização existente; pergunte somente por lacunas materiais que alterem o escopo. Se ele discordar do destino, use o que ele mandar.

## Passo 6a — Se for só pergunta

Responda com base no dossiê, sempre amarrando ao projeto: em qual camada isso entraria, qual arquivo existente seria tocado, o que já existe e o que falta. Cite a origem (`segundo a doc do MCP <nome>`) ao afirmar qualquer coisa sobre a API externa.

Não crie implementação nem documente em `.centaur/implements/` — pergunta não gera implementação.

## Passo 6b — Se for implementação

Lance a skill de destino **passando o dossiê junto**. O prompt deve ser exatamente:

```
Invoque a skill [centaur-driven-tdd | centaur-driven-implement] com a seguinte solicitação:

[requisição do usuário, verbatim]

[dossiê completo do Passo 4]

Carregue clean-code e, somente quando pertinente, graphify e siga o contrato de contexto nesta sessão, conforme as instruções da skill de destino, preservando o escopo solicitado e o modo de execução.

Este contexto veio da documentação oficial via MCP. Trate-o como fonte de verdade sobre a API externa e não invente campos, endpoints ou comportamentos fora dele. Se precisar de algo que está listado em "Não encontrado no MCP", pare e reporte em vez de assumir.
```

Se o destino for `/centaur-driven-spec`, invoque-a com a requisição + dossiê da mesma forma — o dossiê vira o **Contexto técnico** da spec, e as tasks geradas já nascem com os endpoints certos.

**Você não altera a requisição do usuário.** Você só anexa o dossiê.

## Passo 7 — Credenciais

Se a integração exigir credencial (API key, token, secret):

- **Nunca** escreva o valor da credencial em código, em `.env` versionado, em `AGENTS.md` ou no README da implementação.
- O código deve ler de variável de ambiente. Documente o **nome** da variável, nunca o valor.
- Se o usuário colar uma credencial real no chat, avise que ela deve ir para o `.env` local (git-ignored) ou para o secret manager, e siga usando só o nome da variável.
- Se o serviço tiver sandbox, prefira sandbox como padrão de desenvolvimento e deixe a URL base configurável.

## Passo 8 — Informar o usuário

Ao final, reporte:
- Qual MCP foi consultado e quantas consultas foram feitas
- O que foi roteado e para qual skill
- Referência do registro criado pelo executor (README em files ou página/fila em ai-memory) (ex: `.centaur/implements/0007/`) ou número da spec
- O que ficou em **Não encontrado no MCP** e precisa de decisão do usuário
- Variáveis de ambiente que o usuário precisa preencher para a integração rodar
