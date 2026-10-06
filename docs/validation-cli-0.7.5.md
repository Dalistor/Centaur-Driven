# Validação Centaur CLI 0.7.5

Data: 2026-10-06. Imagem: autocompact excedeu 180s e a nova tentativa já retomava em
19/26; o erro anterior seguia na tela. O orçamento e checkpoint funcionavam, mas exigir
o prefixo inteiro transformava operações longas em falhas sucessivas do turno.

- Autocompact tem alvo de 60% da janela na estimativa, descontando prompt/ferramentas/
  observações. Termina ao recuperar espaço, preservando o restante do histórico ativo.
- Ao esgotar prazo, retorna um resumo válido com fronteira de mensagens completamente
  lidas, rebobinando qualquer lote de ferramentas incompleto. Texto não processado
  nunca sai do contexto ativo; o histórico em disco continua inteiro. Memória só muda
  após gravação atômica e comprovação da redução.
- Sem divisão segura/espaço suficiente, `CompactionPaused` pausa o turno; não vira
  `last_error`. `$compact` continua e `/retry` retoma sem duplicar a mensagem. Erros
  reais continuam falhas. O diagnóstico legado de orçamento é exibido como pausa
  anterior, preservado para `/retry`, sem aparentar erro da compactação atual.
- Regressões: prazo com prefixo útil, mensagem única enorme sem divisão segura,
  resultados de ferramentas cruzando fragmentos, alvo automático com continuação,
  pausa persistida/retomada e visualização do erro legado. Cancelamento, falha real,
  reparo de resumo e gravação recusada mantêm as proteções anteriores.
- 346 testes na suíte local, dois de desktop opt-in reservados ao CI; PTY real em três
  modos e resize 40 × 12. Build, `twine check --strict`, 64 recursos e instalação limpa;
  `compileall`, `git diff --check`, auditoria strict e lint DESIGN.

Estimativa de tokens não garante a janela real do provedor. Uma mensagem enorme sem
fronteira segura pode exigir mais de uma operação. Contas/IA no teste são simuladas;
nenhuma requisição paga ou conta Codex/Claude autenticada real foi usada.
