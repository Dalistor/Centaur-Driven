# Validação Centaur CLI 0.7.2

Data: 2026-10-06. Sintoma informado: compactação não inicia ou não termina.

Falha reproduzida: `$compact` + Enter era capturado pelo autocomplete e apenas inseria
`$compact `, sem iniciar o worker. O teste anterior de PTY pressionava Enter duas vezes.
A versão atual inicia com um único Enter; o teste real de curses também usa somente um.

- 324 testes na suíte local; dois testes de desktop opt-in reservados ao CI.
- PTY real em cores, monocromático e movimento reduzido: início com um Enter, conclusão,
  memória persistida, continuação com resumo e histórico completo, resize até 40 × 12.
- Comandos locais completos/abreviados executam diretamente; Tab só completa. Menções
  no meio de uma frase e skills não executam ao completar.
- Compactação exibe fragmento atual/total e revisão. Janela ampla reduz a quantidade
  de chamadas pequenas; o maior fragmento é limitado a 120 mil caracteres.
- Effort baixo só é usado quando anunciado; sem metadados usa o padrão. A preferência
  e as mensagens da conversa não são modificadas pela escolha interna do resumo.
- Cancelamento, falha de gravação, lotes de ferramentas e revisão limitada continuam
  cobertos pelas regressões das versões anteriores.
- Build, `twine check --strict`, conferência de 64 recursos e instalação limpa;
  `compileall`, `git diff --check`, auditoria strict e lint DESIGN.

O cliente IA do teste de terminal é simulado. A integração Codex é exercitada com
executável simulado; contas autenticadas reais e requisições pagas não foram usadas.
Latência do provedor permanece variável; os novos estados mostram quando o resumo
está em execução. O CI valida Linux/Python 3.10 e 3.13, macOS/Python 3.13 e Xvfb.
