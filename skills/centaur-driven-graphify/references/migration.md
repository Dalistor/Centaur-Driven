# Migração para .centaur

Execute a migração pela skill `centaur-driven-update`, preservando conteúdo durável e validando antes de remover origens.

- `graphify-out/` → `.centaur/graphify/`, reaproveitando índice e caches.
- `.ai-memory.toml` → `.centaur/ai-memory/config.toml`; passar identidade explícita aos clientes, sem depender da descoberta automática na raiz.
- `.centaur/memory-pending/` → `.centaur/ai-memory/pending/`.
- Documentação gerada em `docs/system/` e notas Centaur legadas → `.centaur/system/`, somente após confirmar a propriedade dos arquivos; preservar documentos independentes.
- Remover páginas de acompanhamento geradas conhecidas (`andamento.html`/`acompanhamento.html`); HTML personalizado não deve ser apagado pelo nome.

Atualize links relativos, referências e configurações; trate conflitos sem sobrescrever divergências. Backups e relatórios ficam dentro de `.centaur/`. Não mova o store global de um serviço ai-memory compartilhado nem configure outro projeto como efeito colateral.

Não recrie índice como parte da migração. Valide caminhos e consultas quando houver índice; a documentação continua utilizável sem Graphify. Não altere `.obsidian/` nem exija que o Obsidian exiba diretórios ocultos: o editor é a entrada principal.
