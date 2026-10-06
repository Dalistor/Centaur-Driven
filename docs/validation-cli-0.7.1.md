# Validação Centaur CLI 0.7.1

Data: 2026-10-06. Regressões reportadas: “Resumo excedeu o limite” ao compactar,
`[A` ao pressionar ↑, navegação até o rascunho atual e ausência de autocompact.

- Suíte Python: 319 testes; dois testes de desktop opt-in são reservados ao CI.
- Regressão de resumo longo: o primeiro resumo é reescrito de forma mais concisa;
  revisões são limitadas a duas, canceláveis e sem ferramentas. Resposta inválida,
  memória sem redução ou falha de gravação não altera o estado anterior.
- Adaptador Codex: executável simulado produz `reply.json` longo e depois um resumo
  válido. Verifica schema com zero chamadas, isolamento de chaves e histórico intacto.
- Autocompact: dispara antes da chamada a 80% da janela conhecida, usa resumo sem
  ferramentas, persiste memória e preserva todo o histórico. Janela desconhecida,
  desativação explícita e ausência de prefixo elegível não causam loops.
- Curses real em PTY: setas CSI (`ESC [ A/B`) e SS3 (`ESC O A/B`), prompts multilinha,
  retorno ao campo vazio e nenhuma alteração nos prompts salvos. Exercitado em
  cores, monocromático e movimento reduzido, incluindo resize 40 × 12.
- Navegação unitária também preserva o cursor de um rascunho preenchido e a prioridade
  de listas; editar uma cópia encerra navegação sem modificar mensagens originais.
- Diagnóstico lê somente eventos públicos de erro/resultados de falha; raciocínio,
  conteúdo das mensagens e detalhes de conta não são exibidos no erro classificado.
- Build wheel/sdist, `twine check --strict`, instalação limpa, conferência dos 64
  recursos, `compileall`, `git diff --check`, auditoria strict e lint DESIGN.

Contas Codex/Claude autenticadas e chamadas pagas não foram usadas localmente. O
adaptador foi exercitado com executável/respostas simulados; curses e PTY são reais.
Os testes de CI incluem Linux/Python 3.10 e 3.13, macOS/Python 3.13 e desktop Xvfb.
Autocompact depende de uma janela conhecida e de chamadas de resumo válidas; não
garante que anexos ou um lote recente muito grande caibam na próxima requisição.
