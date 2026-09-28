# Contrato de interface do Volante

Fontes de negócio: pedido de tornar o HTML visor do código e molde da IA; protocolo em `centaur-driven-graphify/references/lifecycle.md`. A interface projeta regras desse protocolo; não inventa autoridade ou muda estado do produto.

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Navegação | hash + render no template | Ciclo e DESIGN.md | lista/detalhe | browser: voltar, link profundo |
| Search | filtro local global | DESIGN.md | texto + módulo | busca, limpar, sem resultados |
| Select/Listbox | select nativo de módulo | DESIGN.md | popup do sistema | teclado + viewport estreito |
| Scrollbar | CSS global | DESIGN.md | código/documento com overflow próprio | screenshot e estilo computado |
| Toast | notify + região status | esta tabela | exportação | download + anúncio |
| Form | notes + bindNotes | ciclo, notas locais | armazenamento disponível/indisponível | recarga, erro de storage |

Contratos, código, evidências e specs são projeções de leitura. Casos de uso são um espaço separado de edição de rascunho; o navegador avulso baixa o JSON e a extensão salva em `.centaur/use-cases/<id>.json` após validar schema, vínculo com contrato, limites e hash da versão corrente. Notas são salvas no navegador sob a chave do antigo andamento.html; mudanças não são enviadas a agente. Exportar Markdown preserva notas e contexto selecionado. Falha de armazenamento mantém o texto na sessão e avisa para exportar. Não há autenticação, cobrança, exclusão, API remota ou mutação de contratos nesta interface.

Busca e módulo persistem no hash; pesquisa local imediata, composição IME respeitada e botão de limpar com foco devolvido ao campo. Detalhes de contrato exibem a versão vigente mesmo se filtro global mudar: identidade selecionada prevalece no detalhe; listas aplicam filtros. Documentos gerais pertencem ao sistema e não são filtrados por módulo.

Nenhum resultado é inventado em vazio. Registros inválidos produzem aviso visível e deixam a regra não pronta. Falha do JSON principal faz o CLI encerrar sem substituir o snapshot anterior; o operador informa a falha. Não há loading remoto: payload já vem no HTML.

Documento principal usa scroll natural; código e documentos extensos têm scroll próprio e limites de prévia. Links e details nativos operam por teclado. O foco de navegação chega ao conteúdo; há skip link, nomes acessíveis e status de exportação. Conteúdo importado é texto escapado. Não abrir paths externos ao projeto ou arquivos reservados no gerador.

Menu, chips, evidências e estados compartilham primitivas em todas as visões. Verificar contrato, código e evidências como telas irmãs; versão mobile mantém as mesmas ações. Datas usam pt-BR no fuso do navegador, com data ISO preservada na exportação. O snapshot informa explicitamente que não acompanha o checkout em tempo real.

O resumo da visão geral oferece links reais para contratos, código e evidências, preservando filtros. Segmentos do mapa representam a quantidade real de regras e não uma porcentagem de conclusão; o texto informa a contagem verificada. Decisões apontam ao contrato correspondente. SVGs decorativos ficam ocultos de tecnologias assistivas.

No VS Code, `vscode-extension/extension.js` é a ponte canônica para salvar fluxo, pedir proposta ao modelo disponível e iniciar perfis locais de agente. Ações de IA partem de um clique, não são disparadas pela geração do snapshot. O perfil de CLI usa argumentos sem shell e gera branch/worktree por execução; recusa regra sem contrato aprovado ou com decisão/dependência pendente. O painel mostra andamento da sessão, preserva worktrees para revisão e não integra/publica. Falha de modelo, conflito de JSON ou processo é mostrada no status; notas e rascunhos permanecem na aba até o usuário agir.
