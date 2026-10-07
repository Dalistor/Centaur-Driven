# Validação Centaur CLI 0.9.2

Data: 2026-10-07 (UTC). Pedido: quadros laterais para subagentes em execução,
fechamento automático, timeout considerando subagentes e cursor por clique.

- Runtime ativo de todos os subagentes da pasta alimenta a lateral a cada 500ms.
  Estados parados são filtrados antes de desserializar o histórico; registros/mensagens
  são preservados ao fechar o quadro. Tarefa, modelo efetivo quando informado, estado,
  duração e ações/comentários públicos usam o renderer de transcript existente.
- Geometria validada em 112/120/140/191/240 colunas × 18/24/32/48 linhas; vários
  agentes, roda separada da conversa, modo wide, pergunta/aprovação e autocomplete.
  Todos os sete filhos distribuídos entre dois coordenadores são alcançáveis por rolagem.
  Em 40×12, indicador/menu preservam o acesso sem sobrepor campos.
- Clique abre histórico de leitura, ou o coordenador deste processo que aguarda input;
  nenhum clique responde pergunta, confirma ação, envia prompt ou cancela executor.
- Composer, renomeação e resposta livre convertem coordenadas por células para índices.
  Casos de Unicode largo/acentos combinados, quebras reais/visuais, limite de wrap,
  scroll vertical/horizontal, margens/linhas vazias e marcadores atômicos de anexos.
  Eventos atrasados de outro chat/texto e mouse release são ignorados.
- Delegação real em thread com latch: painel abre durante complete, permanece vivo após
  heartbeat com relógio avançado 1900s, protege coordenador criado há 65h e fecha após
  sucesso/falha/cancelamento. Cada inferência conserva seu prazo; não há deadline global
  do coordenador para a espera de filhos. Não se aguardou uma chamada real de 30min.
- PTY curses real envia press/release SGR, clica no prompt multilinha e insere no índice
  escolhido antes de resize/envio/compactação/retomada. Executa em cor, NO_COLOR e
  reduced motion, sem inserir escape no prompt nem acionar o modelo pelo clique.
- Suíte: 431 casos, 425 aprovados localmente e seis opt-in de desktop/clipboard no CI;
  15 casos dedicados a painéis/mouse, além do PTY e da cobertura de sessões/prazos.
- Wheel/sdist, twine strict, check_dist com 67 recursos e instalação isolada; compileall,
  diff check, auditoria UI strict sem achados e lint DESIGN sem erros/avisos.
  CI testa Linux 3.10/3.13, macOS 3.13 e clipboard/captura em desktop descartável.

Nenhuma chamada paga foi feita. Codex/Claude/OpenRouter autenticados não foram utilizados
nos testes. O publish PyPI depende do Trusted Publisher; publicação da release GitHub é
separada desse job e não equivale a disponibilidade no índice PyPI.
