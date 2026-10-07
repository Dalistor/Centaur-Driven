# Validação Centaur CLI 0.9.0

Data: 2026-10-06 (America/Sao_Paulo). Pedidos: anexos no composer como Codex,
estados dos agentes, retenção de 64h e múltiplos chats trabalhando no mesmo processo.

- Ctrl+V lê clipboard apenas quando solicitado; colagem de caminhos/URIs e arquivos
  arrastados prepara marcadores atômicos no cursor, sem enviar ao modelo. Backspace/Delete
  remove o elemento inteiro. ↑/↓ restaura arquivos enviados ou o rascunho atual.
- Leitores nativos com prazo de 4s, limite de bytes, cancelamento e saída em arquivo
  temporário privado. AppKit preserva URLs de arquivos Finder, Pillow lê imagem macOS,
  xclip/wl-paste negociam formatos Linux e preferem arquivos a thumbnails. Caracteres de
  controle não entram no campo; resultado tardio não sobrescreve texto modificado.
- N cria novo chat no menu; seleção de outra conversa mantém workers anteriores. Chat,
  client, modelo, permissões, token de cancelamento, pergunta/aprovação, progresso,
  compactação e título são vinculados à origem. Testes executam dois workers reais
  com ferramentas/modelo simulados e alternam entre os dois pedidos pendentes.
- Runtime privado separado dos JSONs de conversa: estados Trabalhando, Aguardando input
  e Parado, heartbeat 20s, PID e lease 120s; menu atualizado 500ms. Agentes de outro
  processo são observados sem assumir input. Subagente tem preview somente leitura,
  com Enter para o coordenador local. Renomeação mantém prioridade sobre input do pai.
- Criação imutável entre gravações, rename e geração de título. Legado migra updated
  sem alterar o timestamp. Limite estrito >64h; limpeza remove anexos/runtime/filhos.
  Sessões vivas, input pendente e rascunhos/anexos são preservados até ficarem livres.
  Sessão com filho vivo também é protegida. Datas inválidas não causam exclusão.
- Computer use para ao mudar de chat; sair aguarda todos os workers. Não há execução
  após fechar o terminal nem isolamento dos arquivos compartilhados entre agentes.
- 407 testes locais: 401 passaram; seis opt-in de desktop/clipboard reservados ao CI.
  PTY real em cores, NO_COLOR e movimento reduzido, resize 40×12, colagem por caminho,
  Ctrl+V, remoção do marcador e recuperação de anexo por ↑/↓.
- CI: Linux Python 3.10/3.13, macOS Python 3.13; screenshot e clipboard X11 reais em
  Xvfb descartável; clipboard AppKit/Finder e imagem reais no runner macOS. Computer
  use continua verificado em Xvfb pelo job específico.
- Wheel/sdist, twine strict, 67 recursos conferidos contra fontes e instalação limpa;
  compileall, diff check, auditoria UI strict e lint DESIGN sem erros/avisos.

Fontes: implementação oficial openai/codex chat_composer.rs e clipboard_paste.rs;
Pillow ImageGrab; AppKit NSPasteboard.PasteboardType.fileURL. Transporte autenticado
Codex/Claude e inferência paga não foram utilizados. Suporte visual depende do modelo.
Publicação PyPI exige Trusted Publisher configurado; consulte o job separado.
