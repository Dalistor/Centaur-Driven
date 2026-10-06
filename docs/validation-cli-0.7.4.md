# Validação Centaur CLI 0.7.4

Data: 2026-10-06. Pedido: distinguir a coloração das ações e dos comentários da IA.

- Comentários e `report_progress`: texto normal branco; ações: azul/negrito;
  falhas/interrupções/recusas: âmbar. Trabalho/espera continuam secundários.
- `TranscriptLine` carrega o papel visual definido na origem, preservado após quebra,
  rolagem e alternância dos detalhes. Conteúdo que imita marcadores de ação/autor
  continua com o estilo de sua origem; código indentado permanece texto normal.
- Paleta e desenho seguem `appearance.Palette` e `TerminalView.put`; nenhum par de cor
  novo ou mudança na paleta global. ANSI de 8 cores conserva os fallbacks existentes;
  `NO_COLOR` distingue ação em negrito de comentário em peso normal.
- Regressão de comentários com `✓`, caminho de ação longo, falha/recusa, código literal
  e desenho completo da conversa. PTY real verifica estilos distintos nos três modos:
  cores, monocromático e movimento reduzido; resize, compactação e retomada preservados.
- 337 testes na suíte local, dois testes de desktop opt-in reservados ao CI.
- Build wheel/sdist, `twine check --strict`, instalação limpa e conferência dos 64
  recursos; `compileall`, `git diff --check`, auditoria strict e lint DESIGN.

Contas e respostas de IA do teste de terminal são simuladas. Mudança somente de
apresentação: dados salvos, execução e permissões das ferramentas mantêm o contrato.
