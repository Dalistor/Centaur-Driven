# Validação Centaur CLI 0.8.0

Data: 2026-10-06. Pedido: anexar arquivos e capturas de tela conforme suporte do modelo.

- Preparação local em worker, revisão de nomes/tipos/tamanhos, remoção e envio posterior.
  Captura única com atraso de 0–10s, cancelamento e descarte de eventos obsoletos;
  não inicia computer use nem libera ações de controle.
- Gate de modalidades com catálogo OpenRouter/cache Codex e famílias Claude conhecidas;
  revalidação após troca de modelo. Texto UTF-8 nos três; imagens normalizadas PNG;
  PDF apenas OpenRouter file nativo e parser native explicitamente configurado.
- Cópias 0600, diretórios 0700, hash e referências confinadas: original apagado não impede
  retomada, cópia alterada/ausente/symlink bloqueia envio. Arquivos especiais e binários
  desconhecidos são recusados; gravação recusada conserva rascunho/fila/histórico.
- Compactação inclui textos e manifesto; não inclui base64 ou inventa leitura visual.
  Originais visuais permanecem arquivados. Fila separada por chat e preservada no config;
  contexto considera texto pendente, sem alegar precisão de consumo visual.
- 366 testes locais, três opt-in de desktop reservados ao CI. 20 casos de anexos, incluindo
  transporte nativo/API simulado; PTY real em colorido, NO_COLOR e movimento reduzido,
  resize 40 × 12, preparação por caminho com espaços e envio revisado de texto anexado.
- O desktop Xvfb local não iniciou os sockets de captura. O workflow executa o teste
  de screenshot real 800 × 600 com dependências opcionais em desktop descartável.
- Build wheel/sdist, twine strict, 65 recursos conferidos contra fontes e instalação
  limpa sem dependências; compileall, diff check, auditoria UI strict e lint DESIGN.

Não foram usadas contas autenticadas Codex/Claude nem requisições pagas. Testes de
transporte não provam disponibilidade de cada modelo/versão CLI. Captura automática
anunciada para X11/macOS; Wayland usa arquivos de captura do sistema. Filas não enviadas
não são persistidas após encerrar. Documentos binários diversos/áudio/vídeo não suportados
produzem diagnóstico explícito. Publicação PyPI exige Trusted Publisher configurado.
