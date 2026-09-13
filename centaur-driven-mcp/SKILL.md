---
name: centaur-driven-mcp
description: Ponte dinâmica entre um MCP server e o fluxo centaur - consulta a documentação/tools do MCP informado, extrai o que é relevante para a requisição do usuário e roteia para centaur-driven-tdd, centaur-driven-implement ou centaur-driven-spec com esse contexto anexado. Também instala o MCP no escopo global quando recebe uma URL no lugar do nome. Uso - /centaur-driven-mcp <Nome do MCP | URL do MCP> [Requisição do usuário]. Não depende de nenhum MCP específico - descobre os disponíveis em tempo de execução.
version: 1.3.0
invocable: true
author: user
metadata:
  dependencies: clean-code
---

# centaur-driven-mcp

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

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

Se o primeiro argumento **não** for uma URL (`http://` ou `https://`), pule direto para o Passo 1.

Instalar um MCP server dá a ele acesso ao seu ambiente de trabalho a cada sessão, e é uma mudança global que persiste fora desta conversa. Trate como ação que exige confirmação explícita.

**1. Verificar se já está instalado.** Rode `claude mcp list`. Se a URL já aparecer registrada sob algum nome, não reinstale — use esse nome e siga para o Passo 1.

**2. Descobrir o transporte.** Teste HTTP primeiro:

```bash
curl -s -X POST '<URL>' \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"centaur","version":"1.0"}}}' \
  --max-time 25 | head -c 2000
```

- Resposta JSON-RPC com `result.serverInfo` → transporte `http`
- HTTP 401/403 → o server exige autenticação. **Pare e pergunte ao usuário** qual credencial usar e em qual header. Nunca chute e nunca invente um token.
- HTTP 405, 404 ou resposta vazia → tente `--transport sse`
- Erro de conexão, DNS ou timeout → informe que a URL não respondeu e pare. Não instale server que não responde.

**3. Definir o nome.** Derive do host + caminho, em kebab-case, curto e legível (`https://docs.asaas.com/mcp` → `asaas-docs`; `https://mcp.stripe.com` → `stripe`). Use o `serverInfo.name` devolvido no handshake como pista. Se o nome já existir em `claude mcp list` apontando para outra URL, sufixe para não colidir.

**4. Confirmar com o usuário.** Antes de instalar, mostre: URL, nome escolhido, transporte detectado, `serverInfo` retornado, escopo (`user` — vale para todos os projetos) e se exige auth. Pergunte se pode instalar. **Não instale sem resposta afirmativa.**

**5. Instalar no escopo global.**

```bash
claude mcp add --transport <http|sse> --scope user <nome> '<URL>'
```

Com autenticação, acrescente `--header "Authorization: Bearer $VAR"` — referencie a variável de ambiente, **nunca** o valor literal da credencial no comando.

**6. Validar.** Rode `claude mcp list` e confirme `✔ Connected` na linha do novo server. Se falhar, mostre a linha do erro, desfaça com `claude mcp remove --scope user <nome>` e pare.

**7. Avisar sobre a sessão.** As tools do MCP recém-instalado **não ficam disponíveis nesta sessão** — o registro é lido na inicialização. Informe:

> "MCP `<nome>` instalado no escopo global e conectado. As tools só carregam depois de reiniciar o Claude Code. Reinicie e rode `/centaur-driven-mcp <nome> [sua requisição]` para continuar."

E encerre. Não tente consultar o MCP nesta sessão nem substituir a consulta por `curl`, `WebFetch` ou memória — o dossiê do Passo 4 só vale se vier das tools reais.

**Exceção:** se, após a instalação, as tools `mcp__<nome>__*` aparecerem disponíveis (o ambiente pode ter carregado a quente), siga normalmente para o Passo 1 em vez de encerrar.

## Passo 1 — Resolver o MCP

O primeiro argumento é o nome do MCP server (ou o nome definido no Passo 0).

1. Verifique se existem tools disponíveis com prefixo `mcp__<nome>__*` (o nome do server aparece normalizado no prefixo — `asaas-docs` vira `mcp__asaas-docs__*`, `flutter-docs` vira `mcp__flutter-docs__*`).
2. Se as tools do MCP estiverem diferidas (não carregadas), carregue-as com `ToolSearch` usando a query `+<nome>` em **uma única chamada**, pedindo `max_results` alto o suficiente para trazer o conjunto todo.
3. Se não achar nenhuma tool do MCP, rode `claude mcp list` para ver o que está registrado:
   - **MCP registrado mas sem tools nesta sessão** → informe: "O MCP `<nome>` está registrado e conectado, mas as tools não estão disponíveis nesta sessão. Reinicie o Claude Code e rode o comando de novo."
   - **MCP não registrado** → liste os MCPs disponíveis e pergunte qual usar. Não prossiga chutando.

Se o usuário não informou nome nenhum, liste os MCPs de `claude mcp list` e pergunte qual usar antes de seguir.

## Passo 2 — Ler o contexto do projeto

Leia obrigatoriamente:
1. `AGENTS.md` na raiz do projeto (arquitetura, camadas, convenções, restrições)
2. `.centaur/implements/status.md` (histórico — o serviço do MCP pode já ter sido integrado antes)
3. `.centaur/specs/index.md`, se existir

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

O campo **Não encontrado no MCP** é obrigatório. É ele que impede o subagente de assumir que o dossiê é completo.

## Passo 5 — Classificar a requisição

Decida o destino:

| Situação | Destino |
|---|---|
| Usuário só perguntou (como funciona, quais campos, existe suporte a X) | Responda direto no Passo 6a |
| Mudança pontual com regra de negócio real (cálculo, validação com consequência, tratamento de erro com decisão) **e** projeto tem testes | `/centaur-driven-tdd` |
| Mudança pontual estrutural/config (adicionar client, variável de ambiente, tipagem), mapeamento trivial de payload, ou projeto sem testes | `/centaur-driven-implement` |
| Integração grande (vários endpoints, webhooks, persistência, mais de ~4 arquivos) | `/centaur-driven-spec` |

Apresente ao usuário: o dossiê do Passo 4, a classificação e o destino escolhido. **Confirme antes de seguir.** Se ele discordar do destino, use o que ele mandar.

## Passo 6a — Se for só pergunta

Responda com base no dossiê, sempre amarrando ao projeto: em qual camada isso entraria, qual arquivo existente seria tocado, o que já existe e o que falta. Cite a origem (`segundo a doc do MCP <nome>`) ao afirmar qualquer coisa sobre a API externa.

Não crie implementação nem documente em `.centaur/implements/` — pergunta não gera implementação.

## Passo 6b — Se for implementação

Lance a skill de destino **passando o dossiê junto**. O prompt deve ser exatamente:

```
Invoque a skill [centaur-driven-tdd | centaur-driven-implement] com a seguinte solicitação:

[requisição do usuário, verbatim]

[dossiê completo do Passo 4]

Carregue a dependência clean-code nesta sessão, conforme as instruções da skill de destino, preservando o escopo solicitado e o modo de execução.

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
- Número da implementação criada pelo subagente (ex: `.centaur/implements/0007/`) ou número da spec
- O que ficou em **Não encontrado no MCP** e precisa de decisão do usuário
- Variáveis de ambiente que o usuário precisa preencher para a integração rodar
