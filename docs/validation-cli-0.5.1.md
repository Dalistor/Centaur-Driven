# Verificação do CLI 0.5.1

Data: 2026-10-06. Escopo: turnos sem limite de 20 etapas, rolagem, perguntas interativas
e computer use com captura contínua local e autorização explícita.

- Suite Python: 257 testes, com 256 aprovados e o teste de desktop opt-in executado separadamente;
  regressões de permissões, ciclo de vida, backends, navegação e instalação,
  com testes de 25 etapas, cancelamento, perguntas, quadros efêmeros, aprovação por ação,
  arrays/coordenadas tipadas e retomada sem repetir ações.
- Terminal curses real via PTY: cor, `NO_COLOR` e movimento reduzido; pergunta em 40 × 12,
  resposta livre, pular, rascunho preservado, resize, rolagem durante trabalho, posição
  estável enquanto chegam mensagens, roda do mouse, Ctrl+C e saída.
- Desktop X11 descartável via Xvfb: screenshot real, clique recebido pela janela,
  digitação de `abc`, recusa quando o alvo muda e parada pelo fail-safe no canto.
  O teste `test_computer_desktop.py` é opt-in para impedir controle acidental do desktop
  normal; o workflow de release o executa somente em Xvfb.
- Transporte Codex/Claude: executáveis simulados receberam anexos PNG de arquivo ou blocos de imagem; temporários foram removidos; processo pendente foi
  encerrado no cancelamento. Payloads de tela não entram no histórico persistido.
- DESIGN.md lint e auditoria de UX em modo strict, sem erros ou avisos.
- Wheel e sdist: build, validação de metadados, instalação fora do checkout e integridade
  das skills e módulos pelo `scripts/check_dist.py`.

Essas verificações não representam um teste com contas autenticadas de Codex/Claude,
inferência multimodal paga, permissões de macOS ou desktop Windows/Wayland. Captura
contínua local a cerca de 2 quadros/s envia até três quadros por decisão; não é vídeo
contínuo enviado a um modelo em tempo real. O tempo de decisão depende do provedor.
