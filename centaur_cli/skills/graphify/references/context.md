# Contexto do Centaur

## Fontes e recuperação

1. Leia as instruções aplicáveis em `AGENTS.md` e o escopo de `.centaur/workspace.json`.
2. Priorize `rg`, símbolos do editor e leitura dos trechos pertinentes. Para decisões históricas, chame a [subskill interna memory](../../_internal/memory/SKILL.md) quando o histórico for pertinente, respeitando o backend configurado e seu [contrato](../../_internal/memory/references/contract.md).
3. Use Graphify sob demanda para investigar relações amplas. O índice é derivado: confirme caminhos, comportamento e estado no código, contratos e evidências atuais. Ausência de resultado não comprova ausência de funcionalidade.
4. Registre definições duráveis nos contratos e em `.centaur/system/`; consulte histórico somente quando necessário. O [ciclo por contratos](lifecycle.md) governa aprovação, estado e evidências.

Graphify é opcional no fluxo comum. Não inicialize nem atualize o índice após cada edição, consulta, commit ou onda. Não instale hooks de indexação automática. Dependência ausente não impede trabalho que possa ser comprovado por leitura e testes. Um índice desatualizado deve ser identificado como tal; não declare contexto sincronizado sem verificar.

## Memória e relações do código

As duas capacidades são complementares e independentes. `memory` recupera decisões, motivos, restrições e resultados anteriores; Graphify localiza arquivos, símbolos, dependências e caminhos no código. Nenhuma delas determina o estado atual da spec ou comprova comportamento.

Escolha conforme a pergunta:

- Mudança localizada ou dúvida simples: comece com `rg`, símbolos e leitura direta. Não chame memória nem grafo sem uma necessidade concreta.
- Decisão, tentativa anterior ou retomada: chame a subskill `memory` para recuperar somente o histórico relevante. O backend `files` usa os registros locais; ai-memory só é consultado quando já configurado.
- Relações entre vários módulos ou impacto difícil de localizar por busca: chame `graphify` sob demanda. Consultar um índice existente não autoriza reconstruí-lo.
- Pergunta que envolve motivo e impacto: recupere a decisão com `memory`, use os caminhos e símbolos identificados para orientar a investigação e consulte Graphify apenas se a relação continuar ampla ou incerta. Confirme a conclusão abrindo as fontes, a spec e as evidências atuais.

Ao combinar as duas, preserve as referências de origem: página ou registro histórico para o motivo, arquivos e símbolos atuais para a relação observada. Divergência entre histórico, índice e checkout deve ser explicitada e resolvida pelas fontes atuais; não reescreva o histórico para fazê-lo concordar com o código.

A indisponibilidade de uma capacidade não exige instalar a outra nem mudar o backend. Use fontes locais para o que puder comprovar e informe a limitação quando afetar a resposta. Registre o resultado no fluxo de memória da skill chamadora; isso não dispara atualização do grafo. Não copie a wiki ou a fila de memória para o corpus Graphify.

## Graphify sob demanda

Quando solicitado ou necessário à investigação, carregue a skill oficial e somente as referências pertinentes. Use o adaptador local para que os artefatos permaneçam em `.centaur/graphify/`:

```bash
python3 /skill/graphify/scripts/graphify-local.py /projeto query "relação entre módulos" --budget 1500
```

O adaptador define `GRAPHIFY_OUT` absoluto, configura o diretório de trabalho e preserva os argumentos como lista. Consultas não inicializam índice ausente. Confirme `graphify --version` e o help ao mudar de versão. Não use caminhos padrão `graphify-out/` presentes em exemplos da skill oficial: adapte também scripts Python, caches e temporários para `.centaur/graphify/`.

Somente um coordenador escreve no índice. Quando a atualização for solicitada, incluir código e documentos pertinentes, verificar a cobertura de diretórios ocultos e registrar limitações em `.centaur/system/sync.md`. Extração apenas AST não cobre documentos. Não copie wiki, credenciais, filas, backups ou artefatos gerados para o corpus. Falha de índice não reabre implementação validada.

## Informação no terminal

O terminal/chat é a entrada principal. Recupere apenas instruções, spec/task selecionada, regras pertinentes e fontes necessárias; não leia todo o histórico ou todas as specs a cada turno. Reutilize contexto já lido na sessão e reconfirme fontes antes de escrever. Índices servem para localizar trabalho, nunca para comprovar conclusão.

Na conversa, apresente resultado, validação, bloqueio/decisão e próximo passo, com links para detalhes. Omita campos sem conteúdo, listas completas de arquivos, logs extensos e o estado de ferramentas opcionais que não foram usadas. Perguntas técnicas podem receber o detalhe necessário; simplificar a saída não dispensa inspeção, evidências ou registro de limitações materiais.

Para várias specs, mostre uma linha por spec selecionada: ID, estado real e próxima ação ou bloqueio. Informe mudanças de estado relevantes; não repita a fila inteira a cada task. Relatórios de executores mantêm os dados necessários à consolidação em seus registros; o coordenador resume para o humano.

## Projeções opcionais

Specs, contratos, fontes e evidências são acessíveis diretamente no terminal. Não exija abrir editor para planejar, executar ou consultar specs.

Valide registros com `validate-lifecycle.py` e os gates `--ready` antes de declarar integração. Consultas somente leitura não geram arquivos.

## Localização dos artefatos

Documentação gerada, índices, memória local, caches, evidências, logs, backups e temporários ficam sob `.centaur/`. Graphify usa `.centaur/graphify/`; ai-memory usa `.centaur/ai-memory/`; definições duráveis são versionadas, caches e segredos não.

Arquivos de descoberta exigidos por ferramentas mantêm seu local obrigatório: `AGENTS.md`, workflow em `.github/workflows/` e configurações do editor quando necessárias. Devem ser mínimos e referenciar `.centaur/`, sem duplicar a documentação. Código do produto e documentos independentes do usuário não são movidos. A skill `update` executa a migração segura dos artefatos legados.
