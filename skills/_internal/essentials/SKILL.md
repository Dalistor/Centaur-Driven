---
name: essentials
description: Resumo operacional de clean-code, da política de testes e do uso de Graphify, aplicado por rotina no lugar da leitura integral dessas fontes.
metadata:
  version: 1.0.0
  visibility: internal
  optional-dependencies: clean-code, graphify
---

# Essenciais de código, testes e contexto

Resumo de `clean-code` (3.2) e de `graphify/references/testing.md`, para aplicar em toda mudança de código sem carregar as fontes inteiras. Instruções do usuário e do projeto prevalecem; o estilo local vence a preferência genérica.

## Código

- **Antes de editar:** defina o comportamento exato a mudar, o menor escopo útil e a verificação que o prova. Leia o entorno (nomes, layout, estilo de erros e de testes) e busque antes de escrever: a lógica pode já existir.
- **Lugar:** espelhe dois ou três artefatos parecidos (pasta, nome, estrutura, registro). Arquivo novo só quando não há dono coeso; nunca na raiz por omissão, nunca variante (`_v2`, `_new`, `_final`), nada em `utils`/`helpers`/`common` sem um conceito de domínio. Ligue por completo (imports, exports, rotas, injeção, migrações): arquivo que nada referencia é código morto.
- **Um trabalho por unidade:** descreva a unidade em uma frase sem "e", "também" ou "depois". Comportamento novo vai para a unidade dona da responsabilidade, não para o arquivo que está aberto. Separe validação de entrada, regra de domínio, persistência, chamadas externas, apresentação e montagem.
- **Dependências apontam para dentro:** regra de negócio não nomeia banco, framework, HTTP nem ORM; a interface fica do lado da regra e a implementação fora. Não pule a camada dona da regra: ela pode conter a única checagem de autorização. Sem ciclos. Sem camada, fronteira ou abstração para uma necessidade que ainda não existe. Deduplique só o que sempre muda junto.
- **Menor fatia:** cada linha alterada vem do pedido. Edição pontual em vez de reescrita; sem renomes, reformatação ou atualização de dependências de carona. Cheiro fora do escopo é relatado, não corrigido. Remova o que a sua mudança deixou sem uso.
- **Escrita:** nomes revelam a intenção no vocabulário do domínio; funções fazem uma coisa, com saídas antecipadas e poucos parâmetros; comentário explica o porquê. Erros são tratados onde há decisão a tomar, preservam a causa e nunca são engolidos. Validação e autorização ficam na fronteira, junto da operação protegida; segredos ficam fora do código e dos logs; dinheiro, tempo e unidades são exatos.
- **Nada inventado:** confira no código e nas versões instaladas toda API, opção e chave de configuração. Sem stubs, valores de demonstração ou "numa implementação real".
- **Verifique e relate:** rode a verificação proporcional ao risco, cite o resultado e diga o que não rodou. Nunca enfraqueça nem pule um teste para obter verde. Antes de concluir, releia o diff procurando edição alheia ao pedido, arquivo no lugar errado, unidade com dois trabalhos, dependência invertida, erro engolido e artefato não ligado.

## Testes

- **Padrão:** reaproveitar a proteção existente e não adicionar teste automaticamente. Toda entrega precisa de verificação; nem toda verificação vira teste permanente.
- **Teste novo ou ampliado só com as três condições:** há uma falha concreta identificada; ela atinge um ponto vital (autenticação, autorização e privacidade; integridade de dados e migrações; dinheiro; operação irreversível; invariante essencial do domínio; contrato crítico entre serviços; concorrência, idempotência e recuperação); nenhum teste existente a cobre. Atualizar um caso existente é preferível a criar outro.
- **Menor proteção suficiente:** o nível que detecta a falha real (unidade, integração ou contrato, ponta a ponta), sem repetir a mesma proteção em vários níveis; pela interface observável, sem testar detalhes privados nem mocks que só confirmam chamadas. Sem bateria por task, arquivo ou subagente; sem meta de contagem ou cobertura.
- **Verificação:** rode a seleção relacionada; a suíte completa só quando o projeto ou o CI exigir, ou o impacto for transversal. Build e lint não comprovam regra crítica. Não reduza um gate existente.

## Contexto

Comece por busca textual e leitura direta. Use Graphify só para relações amplas que elas não localizam, ou a pedido explícito; nunca inicialize, indexe ou sincronize o grafo como efeito colateral de uma tarefa.

## Quando abrir a fonte completa

- `clean-code/references/architecture.md`: a mudança cria camada, fronteira ou dependência nova, ou adota framework ou banco.
- `clean-code/references/concurrency.md`: código concorrente.
- `clean-code/SKILL.md` e demais referências: comandos `audit`, `clean-up`, `new-project` e `questions`, projeto com `.clean/`, ou dúvida que este resumo não resolve.
- `graphify/references/testing.md`: dúvida sobre se um comportamento é ponto vital, ou ao consolidar e remover testes.
- `graphify/SKILL.md`: antes de consultar, inicializar ou atualizar o grafo.
