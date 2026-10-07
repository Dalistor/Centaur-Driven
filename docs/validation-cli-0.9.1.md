# Validação Centaur CLI 0.9.1

Data: 2026-10-06 (America/Sao_Paulo). Pedido: 30 minutos de timeout para resposta e
compactação; corrigir overflow do erro mostrado no rodapé da captura enviada.

- Codex/Claude: padrão 1800s, mantendo override CENTAUR_NATIVE_TIMEOUT (30–3600s),
  cancelamento e encerramento do grupo de processos quando o prazo termina.
- OpenRouter: padrão 1800s por inferência, override CENTAUR_OPENROUTER_TIMEOUT
  (30–3600s); catálogo/autenticação mantêm prazos curtos. Comandos locais continuam 60s.
- Compactação: orçamento compartilhado padrão 1800s, override CENTAUR_COMPACT_TIMEOUT
  (30–3600s), incluindo fragmentos e revisões. Cada resumo recebe o orçamento restante,
  limitado pelo timeout do backend; removido teto antigo de 90s. Checkpoints, pausas
  seguras e redução de fragmentos após timeout permanecem ativos.
- RoutedClient de subagentes repassa capacidades, catálogo e opções de resumo, mantendo
  session_id/cost_tier. Teste verifica prazo/effort forwarded sem alterar roteamento.
- Rodapé usa a largura exata do composer e reticências para avisos extensos. Erro já
  exibido na conversa tem aviso curto; erro local diferente mantém sua mensagem.
  Diagnósticos longos, Unicode, caminhos/palavras sem espaços quebram por células.
- Falha real de compactação fica persistida como compaction_error, pertence ao chat
  de origem e mostra o texto completo no transcript. Cancelamento/pausa não vira erro;
  sucesso remove o diagnóstico anterior apenas após salvar a nova memória.
- Suíte de 416 casos: 410 passaram localmente; seis opt-in de desktop/clipboard vão ao CI.
  Nove casos de timeout/layout, incluindo inferência nativa mock, prazos HTTP default/
  override, resumo simulado de 300s, deadline restante, Unicode sem perda, 40×12/80×24/
  140×30, falha/cancelamento/compactação em segundo plano. Testes existentes de deadline
  curto usam override explícito de 180s. PTY real continua nos três modos de aparência.
- Wheel/sdist, twine strict, 67 recursos conferidos e instalação limpa; compileall,
  diff check, auditoria UI strict e lint DESIGN. Workflow testa Linux 3.10/3.13, macOS
  3.13 e clipboard/captura real em ambientes descartáveis antes de publicar a release.

Prazos longos foram verificados com relógios/processos simulados; não foi aguardada
uma inferência autenticada de 30 minutos. Não houve chamadas pagas. No OpenRouter,
Ctrl+C bloqueia novas ações; a chamada HTTP pendente pode aguardar o timeout de rede.
PyPI depende do Trusted Publisher, conferido em job separado da release GitHub.
