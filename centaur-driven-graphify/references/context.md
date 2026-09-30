# Contexto do Centaur

## Fontes e recuperação

1. Leia as instruções aplicáveis em `AGENTS.md` e o escopo de `.centaur/workspace.json`.
2. Priorize `rg`, símbolos do editor e leitura dos trechos pertinentes. Para decisões históricas, use ai-memory quando configurado, conforme o [contrato de memória](../../centaur-driven-memory/references/contract.md).
3. Use Graphify sob demanda para investigar relações amplas. O índice é derivado: confirme caminhos, comportamento e estado no código, contratos e evidências atuais. Ausência de resultado não comprova ausência de funcionalidade.
4. Registre definições duráveis nos contratos e em `.centaur/system/`; consulte histórico somente quando necessário. O [ciclo por contratos](lifecycle.md) governa aprovação, estado e evidências.

Graphify é opcional no fluxo comum. Não inicialize nem atualize o índice após cada edição, consulta, commit ou onda. Não instale hooks de indexação automática. Dependência ausente não impede trabalho que possa ser comprovado por leitura e testes. Um índice desatualizado deve ser identificado como tal; não declare contexto sincronizado sem verificar.

## Graphify sob demanda

Quando solicitado ou necessário à investigação, carregue a skill oficial e somente as referências pertinentes. Use o adaptador local para que os artefatos permaneçam em `.centaur/graphify/`:

```bash
python3 /skill/centaur-driven-graphify/scripts/graphify-local.py /projeto query "relação entre módulos" --budget 1500
```

O adaptador define `GRAPHIFY_OUT` absoluto, configura o diretório de trabalho e preserva os argumentos como lista. Consultas não inicializam índice ausente. Confirme `graphify --version` e o help ao mudar de versão. Não use caminhos padrão `graphify-out/` presentes em exemplos da skill oficial: adapte também scripts Python, caches e temporários para `.centaur/graphify/`.

Somente um coordenador escreve no índice. Quando a atualização for solicitada, incluir código e documentos pertinentes, verificar a cobertura de diretórios ocultos e registrar limitações em `.centaur/system/sync.md`. Extração apenas AST não cobre documentos. Não copie wiki, credenciais, filas, backups ou artefatos gerados para o corpus. Falha de índice não reabre implementação validada.

## Informação no terminal

O terminal/chat é a entrada principal. Recupere apenas instruções, spec/task selecionada, regras pertinentes e fontes necessárias; não leia todo o histórico ou todas as specs a cada turno. Reutilize contexto já lido na sessão e reconfirme fontes antes de escrever. Índices servem para localizar trabalho, nunca para comprovar conclusão.

Na conversa, apresente resultado, validação, bloqueio/decisão e próximo passo, com links para detalhes. Omita campos sem conteúdo, listas completas de arquivos, logs extensos e o estado de ferramentas opcionais que não foram usadas. Perguntas técnicas podem receber o detalhe necessário; simplificar a saída não dispensa inspeção, evidências ou registro de limitações materiais.

Para várias specs, mostre uma linha por spec selecionada: ID, estado real e próxima ação ou bloqueio. Informe mudanças de estado relevantes; não repita a fila inteira a cada task. Relatórios de executores mantêm os dados necessários à consolidação em seus registros; o coordenador resume para o humano.

## Projeções opcionais

Specs, contratos, fontes e evidências são acessíveis diretamente no terminal. O explorador do editor e o painel são apoios opcionais; `.centaur/volante.html` é exportação, nunca fonte de verdade. Não exija abrir editor, instalar extensão ou gerar HTML para planejar, executar ou consultar specs.

Valide registros com `validate-lifecycle.py` e os gates `--ready` antes de declarar integração. Quando a exportação for solicitada, use `render-volante.py`; consultas somente leitura não geram arquivos.

## Localização dos artefatos

Documentação gerada, índices, memória local, caches, evidências, logs, backups e temporários ficam sob `.centaur/`. Graphify usa `.centaur/graphify/`; ai-memory usa `.centaur/ai-memory/`; definições duráveis são versionadas, caches e segredos não.

Arquivos de descoberta exigidos por ferramentas mantêm seu local obrigatório: `AGENTS.md`, workflow em `.github/workflows/` e configurações do editor quando necessárias. Devem ser mínimos e referenciar `.centaur/`, sem duplicar a documentação. Código do produto e documentos independentes do usuário não são movidos. A skill `update` executa a migração segura dos artefatos legados.
