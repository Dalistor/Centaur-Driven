# Validação Centaur CLI 0.9.4

Data: 2026-10-07. A captura do proprietário mostra o erro introduzido na 0.9.3:
"codex: sem nova saída do CLI por 300 segundos". O harness classificava silêncio
como falha antes do prazo total, embora a resposta estruturada pudesse sair só no fim.

- Regressão reproduzida antes da correção: fixture de Codex/Claude fica 301s sem saída
  em relógio simulado e entrega resposta final válida. Turno e resumo eram interrompidos;
  o subagente retornava failed. Não se trata de teste com uma conta/modelo autenticado.
- Padrão de CENTAUR_NATIVE_IDLE_TIMEOUT agora é 0, desativado. Ausência de bytes não
  cancela por padrão. Zero explícito é aceito; 30–3600s continua disponível como opt-in;
  negativos, valores menores que 30 (exceto 0), acima de 3600 ou não inteiros são rejeitados.
- As quatro novas regressões cobrem Codex/Claude, turno/resumo após 301s, subagente
  retornando reported e processos Python reais sem saída até a resposta final.
  Prazo absoluto e Ctrl+C continuam encerrando um processo silencioso com idle desativado.
- O prazo total continua em 1800s por padrão, sem renovação por atividade. Chamadas de
  resumo respeitam o menor entre esse prazo e seu orçamento restante. Subagentes não
  impõem prazo global ao coordenador. Limpeza limitada, validação integral da resposta,
  ausência de execução de fragmentos e checkpoints continuam ativos.
- Suíte completa: 465 casos, 459 aprovados localmente e seis opt-in de desktop/clipboard.
  Os 13 casos de watchdog incluem os limites explicitamente habilitados, saída crescente,
  cancelamento, descendente segurando pipes e fase separada de heartbeat.
- Wheel/sdist validados com twine strict e check_dist (68 recursos e instalação limpa).
  Compileall e git diff --check passaram. CI Linux 3.10/3.13, macOS 3.13 e desktop Xvfb
  executa as mesmas verificações antes da release GitHub; PyPI é um job separado.

Não há garantia de que uma inferência silenciosa concluirá: o limite total continua
produzindo timeout quando atingido. Esta correção remove o cancelamento prematuro por
silêncio, sem retry automático de ferramentas nem perda do histórico. Não altera o
timeout de rede do OpenRouter ou o tema/consentimento de computer use da 0.9.3.
