# Validação Centaur CLI 0.7.3

Data: 2026-10-06. Imagem informada: `fragmento 1/9`, ainda em execução após 202s.
O fluxo anterior fazia chamadas sequenciais com timeout nativo de 600s por chamada,
sem orçamento total e sem persistir os fragmentos já concluídos em caso de falha.

- Orçamento de compactação: 180s por operação, incluindo revisões e tentativas;
  `CENTAUR_COMPACT_TIMEOUT` aceita 30–3600. Cada requisição de resumo recebe até 90s,
  respeitando o tempo restante e o timeout original do backend.
- Fragmento de até 48 mil caracteres; timeout reduz o tamanho pela metade, até 512,
  dentro do mesmo orçamento. Todos os caracteres elegíveis são percorridos; não há
  amostragem ou descarte silencioso de requisitos e logs.
- Progresso validado salvo atomicamente. Retomada após falha/reinício não repete trechos
  concluídos, aceita mensagens novas e invalida rascunhos se prefixo/modelo/memória mudam.
  Timeout no primeiro trecho salva o tamanho menor, mesmo sem resumo concluído.
- Rascunho não entra em `active_messages`. Histórico, memória anterior, erros e lotes
  de ferramentas preservados. Resumo final sem redução não é salvo como trabalho pronto.
- Regressões de limite total, revisões compartilhando orçamento, retomada manual e
  automática, gravação recusada, cancelamento e adaptação do tamanho. Executável nativo
  real simulado dorme 30s e é encerrado por uma requisição com prazo de 0,1s; o timeout
  do chat principal permanece igual. OpenRouter recebe o prazo reduzido na camada HTTP.
- 336 testes locais, dois de desktop opt-in reservados ao CI. Inclui curses em PTY real,
  início com um Enter, redução persistida e continuação com memória, em três modos visuais.
- Build wheel/sdist, `twine check --strict`, instalação limpa e conferência dos 64 recursos;
  `compileall`, `git diff --check`, auditoria strict e lint DESIGN.

O cliente IA do PTY e o executável Codex são simulados. Não houve chamada paga ou
validação com conta Codex/Claude autenticada real. A correção limita/retoma o trabalho;
não garante sucesso do provedor indisponível. OpenRouter usa timeout de rede, portanto
encerramento/gravação e comportamento de transporte podem acrescentar tempo ao orçamento.
O CI cobre Linux/Python 3.10 e 3.13, macOS/Python 3.13 e desktop Xvfb.
