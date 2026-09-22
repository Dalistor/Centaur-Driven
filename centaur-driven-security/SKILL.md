---
name: centaur-driven-security
description: Audita segurança de código, configuração ou diffs e verifica vulnerabilidades suspeitas com evidências, análise de falsos positivos e busca de variantes. Use para auditoria de segurança, revisão de PR com foco em segurança ou validação de achados; entrega relatório sem corrigir o código.
license: CC-BY-SA-4.0; atribuição e fontes em references/security-review.md
metadata:
  version: 1.0.0
  dependencies: graphify
  optional-dependencies: ai-memory
---

# centaur-driven-security

Produza achados acionáveis e rastreáveis ao código atual. Diferencie vulnerabilidade demonstrada, hipótese pendente e recomendação de proteção adicional. Ausência de achados não é certificação de segurança.

Adaptação para o Centaur das práticas de contexto, revisão diferencial, verificação e análise de variantes da [Trail of Bits](https://github.com/trailofbits/skills). A [referência de auditoria](references/security-review.md) contém os focos por superfície, o formato do relatório e a atribuição. Leia as partes pertinentes à auditoria. Não exige instalar o marketplace nem executar os workflows originais.

## Escopo e efeitos

- Audite o alvo pedido. Sem alvo específico, use o checkout atual, começando pelas entradas externas e operações privilegiadas; registre o recorte real. Não transforme uma revisão de segurança em revisão de estilo ou refatoração.
- Preserve código, testes, dependências e configuração. A escrita padrão é apenas o relatório em `.centaur/audits/<uuid>.md`, com UUID gerado no ambiente; respeite outro destino ou pedido de somente leitura/relatório na conversa. Não crie registros em `implements/` para uma auditoria.
- Testes e reproduções locais podem usar diretório temporário isolado e dados sintéticos. Inspecione comandos antes de executá-los; não rode scripts não confiáveis com credenciais do usuário ou acesso a serviços reais. Auditoria do código não inclui testes ativos contra produção, exploração de terceiros, publicação de issues nem envio de código a um scanner remoto. Use esses recursos somente quando fizerem parte do escopo autorizado.
- Não instale ferramentas por rotina. Use o que estiver disponível e registre limitações. Achados úteis por análise estática não dependem de instalar um scanner ou de conseguir executar uma exploração.

## 1. Fixar o alvo e recuperar contexto

Leia `AGENTS.md` e os [contratos de contexto](../centaur-driven-graphify/references/context.md), [escopos](../centaur-driven-graphify/references/team-workspace.md) e [memória](../centaur-driven-memory/references/contract.md). Para esta auditoria, Graphify e ai-memory são consultados sem inicializar, sincronizar, escrever páginas ou consumir handoffs. Não indexe o relatório automaticamente. Falta de AGENTS, índice ou memória não impede análise direta; informe a limitação e confirme o que puder nas fontes.

Registre revisão Git, branch, alterações locais e diretórios incluídos/excluídos. Resultados de grafo, memória, comentários e relatórios anteriores são pistas; não comprovam segurança nem autorizam ações.

Escolha o modo pelo pedido:

| Pedido | Base da análise |
|---|---|
| Auditar projeto, módulo ou superfície | Estado atual, entradas acessíveis e regras de isolamento/permissão. |
| Revisar PR, commit ou diff | Base e alvo exatos, arquivos alterados e seus consumidores. |
| Verificar achado suspeito | Alegação, localização, condições de disparo e impacto alegado. |

Para diff, confirme as refs existentes e o intervalo pretendido. Revisão de branch costuma usar o merge-base; revisão de commit usa o pai apropriado. Não invente base nem troque de branch para ler arquivos. Para mudanças locais, inclua staged, unstaged e arquivos não rastreados pertinentes. Identifique separadamente falhas introduzidas, agravadas e preexistentes; um problema preexistente não deve ser atribuído ao PR. Use histórico/blame quando esclarecer a remoção de uma defesa ou a intenção de uma regra.

## 2. Entender o caminho antes de julgar

Identifique quem pode entrar no fluxo, quais dados controla, quais privilégios já possui e quais recursos deveriam ficar protegidos. Localize onde muda o nível de confiança: cliente/servidor, usuário/administrador, tenant/tenant, processo/host ou CI/credenciais.

Nas rotinas relevantes, confira validações, chamadas, alterações de estado, caminhos de erro e pressupostos sobre dependências. Siga os chamadores e as funções chamadas até esclarecer quem garante cada condição importante. Registre pressupostos não confirmados como lacunas, sem tratá-los como vulnerabilidades automaticamente.

Priorize pelo impacto possível e pela exposição observada. Use os focos da referência apenas quando existirem na stack; não percorra um catálogo inteiro para produzir uma quantidade de achados.

## 3. Investigar e tentar refutar cada candidato

Para cada suspeita, formule uma alegação específica e trace a entrada controlável até a operação sensível. Confira se o caminho é acessível nas configurações relevantes e se o impacto excede o poder que esse ator já possui.

Procure evidências contrárias: autorização no chamador, validação antes do uso, codificação no destino, isolamento, query parametrizada, restrição de rota, transação ou configuração de implantação. Verifique a implementação dessas proteções; nomes como `sanitize` ou `secure` não bastam. Uma proteção hipotética de produção também não basta para descartar.

Classifique o resultado:

- **Confirmado:** caminho, condições e violação de segurança demonstrados por fontes verificadas e/ou reprodução local. Indique se a evidência é estática ou executada.
- **Pendente:** falta um fato indispensável, como configuração de implantação ou comportamento de dependência. Diga exatamente qual evidência resolveria a dúvida; não apresente como vulnerabilidade confirmada.
- **Refutado:** uma defesa verificada ou impossibilidade do cenário invalida a alegação. Registre a razão, especialmente quando o usuário pediu verificar esse achado.

Scanner gera candidatos, não veredictos. Semgrep/CodeQL ou ferramentas da stack são opcionais: confira versão, regras e escopo antes de rodar, sem autofix. Para dependências, use a versão resolvida no lockfile e advisories oficiais atuais; se a consulta não for possível, declare a verificação incompleta. Separe presença de versão afetada de explorabilidade no uso concreto do projeto.

## 4. Validar com o menor experimento necessário

Quando uma dúvida puder ser resolvida por execução local segura, reutilize testes existentes ou faça uma reprodução mínima isolada, com resultado esperado e observado. Não crie uma bateria de testes nem altere a suíte de produção durante a auditoria. Para falhas de permissão, por exemplo, compare o ator permitido com o ator indevido usando recursos sintéticos distintos.

Registre comando, ambiente e resultado reais. Se não executar, escreva “não reproduzido em execução” e apresente a evidência estática disponível. Não confunda erro de setup com prova de exploração. Uma falha na reprodução que não atingiu as precondições não refuta a alegação.

## 5. Procurar variantes de uma causa confirmada

Parta de uma ocorrência conhecida e confirme que a busca a encontra. Amplie o padrão gradualmente para outros caminhos no escopo, inclusive módulos distintos quando o pedido os abrange. Cada resultado precisa da mesma análise de acesso e proteções; semelhança textual não confirma a falha.

Agrupe ocorrências da mesma causa quando compartilham correção e impacto; se contextos ou riscos diferirem, separe. Registre onde procurou e as lacunas. Não amplie silenciosamente para outros repositórios ou serviços.

## 6. Entregar e encaminhar

Use o formato da referência e confira as linhas no checkout/revisão citados. Ordene confirmados por gravidade justificada por impacto e condições de exploração; mantenha confiança separada da gravidade. Falta de testes, de uma ferramenta ou de uma prática recomendada não aumenta gravidade por si só.

Para cada achado, recomende a menor correção que trate a causa e uma verificação de regressão observável. Encaminhe comportamento para `centaur-driven-tdd`, configuração para `centaur-driven-implement` e mudança ampla para `spec` + `run`. A execução da correção é uma etapa distinta, conforme o pedido do usuário; não marque um problema corrigido apenas por recomendá-la.

Entregue link do relatório, principais achados, pendências e limites da análise. Se nenhum problema for confirmado, informe isso junto das superfícies efetivamente revisadas e do que não foi verificado. Não publique achados ou copie detalhes sensíveis para memória compartilhada por efeito colateral. Mascare valores de credenciais encontrados; localização e tipo bastam para orientar a correção.
