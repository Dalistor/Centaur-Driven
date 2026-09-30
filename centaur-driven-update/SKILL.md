---
name: centaur-driven-update
description: Reconstrói a estrutura gerada do Centaur com staging, backup e verificação de dependências; migra artefatos legados para .centaur sem perder contratos, memória ou customizações.
metadata:
  version: 5.0.0
  dependencies: clean-code
  optional-dependencies: graphify, ai-memory
---

# centaur-driven-update

## Contratos e limites

Leia `AGENTS.md`, se existir, e os contratos de [ciclo](../centaur-driven-graphify/references/lifecycle.md), [equipe](../centaur-driven-graphify/references/team-workspace.md), [contexto](../centaur-driven-graphify/references/context.md) e [memória](../centaur-driven-memory/references/contract.md) conforme o escopo. Localize e leia a skill `clean-code`; ausência da dependência obrigatória bloqueia a atualização antes de substituir arquivos.

Esta skill mantém documentação e estrutura do Centaur. Não corrige código do produto, publica versões nem altera decisões aprovadas. A autorização para executar update cobre a manutenção mecânica; pergunte somente por conflitos de conteúdo, propriedade ambígua ou decisões novas. Preserve alterações locais e staging alheio.

Todos os artefatos gerados ficam em `.centaur/`. As exceções são entradas exigidas pelas ferramentas: `AGENTS.md`, workflows em `.github/workflows/` e os pontos de instalação das skills. Não mova código do produto ou documentos independentes do usuário. Não apague `.centaur/` para recriar: contratos, requisitos, decisões, evidências, configurações e memória são dados duráveis.

## 1. Inventariar e verificar dependências

1. Confira `git status --short`, backend e escopos em `.centaur/workspace.json`, schema instalado de `start-project` e conteúdo existente. Sem `AGENTS.md`, migre os artefatos conhecidos e informe que a inicialização documental ainda pode ser necessária; não invente informações do projeto.
2. Leia a versão instalada de `clean-code` e verifique suas referências usadas. Use busca e símbolos para localizar fontes. Graphify é opcional e sob demanda; nunca indexe o projeto inteiro como pré-condição do update.
3. Verifique `graphify --version` com `GRAPHIFY_OUT` absoluto em `.centaur/graphify`. Se existir índice, teste uma consulta pequena; durante a migração, a consulta pode ler o índice legado. Falha opcional mantém o índice preservado e vira pendência, sem forçar rebuild.
4. Se ai-memory estiver configurado, descubra as ferramentas reais da instalação. Valide uma leitura no workspace/project configurados (identidade explícita). CLI ausente não prova ausência do serviço MCP. Não invente um comando `ai-memory`. Falha de acesso impede substituir a estrutura nesta reconstrução; preserve dados e informe o bloqueio.
5. Não imprima segredos. Configuração de memória, logs e backup podem conter dados sensíveis; mantenha-os fora do Git conforme o contrato de memória.

## 2. Migração segura

O script desta skill inventaria por padrão, prepara arquivos em `.centaur/tmp/`, compara conteúdo, cria backup recuperável em `.centaur/backups/update-<id>/`, valida a transferência e só então remove as origens. Uma falha durante aplicação restaura os arquivos tocados. O manifesto contém arquivos originais e hashes; não contém os segredos dos arquivos. O backup `files/` preserva os bytes originais, incluindo configurações sensíveis, e deve permanecer privado. Uma interrupção abrupta deve ser recuperada desse backup antes de nova tentativa.

```bash
python3 <pasta-da-skill>/scripts/migrate.py --root <projeto> --clean-code <clean-code>/SKILL.md
```

Depois de revisar o inventário, repita com `--apply`. As duas chamadas conferem dependências. Uma segunda aplicação sem novas entradas não duplica arquivos nem cria novo backup.

| Origem reconhecida | Destino |
| --- | --- |
| `graphify-out/` | `.centaur/graphify/` |
| `.ai-memory.toml` | `.centaur/ai-memory/config.toml` |
| `.centaur/memory-pending/` | `.centaur/ai-memory/pending/` |
| Documento comprovadamente gerado em `docs/system/` | `.centaur/system/`, mesmo caminho relativo |

- Para cada documento gerado confirmado, passe `--owned-doc docs/system/<arquivo>`. Não migre toda `docs/system/` pela aparência do nome: documentos manuais ou de origem incerta permanecem. Inventarie arquivos gerados adicionais fora desses caminhos e migre-os com o mesmo protocolo de staging, backup, comparação e remoção validada; não faça varredura destrutiva por extensão.
- Para cada arquivo vivo autorizado, passe `--reference <caminho-relativo>`. O script reescreve apenas os caminhos efetivamente migrados nesses arquivos. O script recalcula links Markdown locais dos documentos movidos e das referências explícitas. Revise os resultados e referências em scripts/configurações; não reescreva contratos aprovados, evidências ou registros históricos. Referências históricas podem apontar para o caminho antigo, conservado no manifesto de migração.
- Conflitos com conteúdos diferentes bloqueiam antes de aplicação; preserve ambos e obtenha a decisão de qual conteúdo deve prevalecer. Arquivos idênticos podem ser consolidados. Links simbólicos exigem análise manual.
- HTMLs `andamento.html`, `acompanhamento.html` e `volante.html` são removidos somente quando reconhecidos como gerados pelo Centaur, com backup. HTML personalizado permanece intacto. Não regenerar o visor HTML.
- Ai-memory configurado exige `--memory-check '["executável", "argumento", ...]'`, um comando real de leitura previamente inspecionado que valide conexão e acesso à identidade correta; executado sem shell, com timeout e sem imprimir saída. Quando só houver MCP, faça a leitura pela ferramenta disponível e execute a migração pelo mesmo protocolo manual após essa verificação; não passe `true` ou uma verificação fictícia para contornar o gate.

## 3. Reconstruir apenas o necessário

Use o template de `centaur-driven-start-project` instalado como fonte do schema. Prepare as mudanças adicionais em `.centaur/tmp/`, mantendo cópia dos arquivos anteriores em `.centaur/backups/`. Preserve seções personalizadas do `AGENTS.md`, backend, IDs, escopos, histórico, requisitos aprovados, evidências e fila de memória. Não converta specs antigas em contratos aprovados automaticamente.

Compare seção a seção, acrescente apenas informações úteis comprovadas no projeto e substitua referências antigas por `.centaur/system/`, `.centaur/graphify/` e `.centaur/ai-memory/`. O conceito, RF, RNF, casos de uso e modelo de dados integram os contratos existentes: alterações conceituais geram revisão explícita; não duplique uma fonte de verdade.

Ajuste `.gitignore` para caches, temporários, backups, worktrees e arquivos privados de deploy/memória dentro de `.centaur/`, preservando regras existentes e o versionamento de definições duráveis. Não remova do Git documentos canônicos por um ignore genérico de `.centaur/`.

Audite índices contra registros, vínculos com código/testes, dependências entre escopos e evidências desatualizadas. Registro órfão, conflito ou informação ausente precisa ser reportado; ausência de `implements/` no backend ai-memory é normal. Não apague pastas históricas nem reescreva relatos concluídos. Corrigir um índice não comprova implementação ou validação de comportamento.

## 4. Validar antes de substituir

- Confira sintaxe dos JSON/TOML alterados, caminhos/links vivos, comandos e funcionamento das integrações configuradas. Use os validadores do ciclo instalados; não invente comandos.
- Confira os diffs: nenhuma perda de conteúdo durável, nenhum arquivo independente movido e nenhum segredo adicionado ao Git.
- Aplique somente o lote validado, após backup. Falha obrigatória deixa a instalação anterior utilizável; restaure o lote se houver falha na troca. Não apague backups automaticamente.
- Confira os caminhos de navegação entre funcionalidade, código e testes nos registros atuais. O update não deve exigir abrir HTML nem indexação Graphify.
- Preserve índice existente. Se documentos indexados mudarem de caminho, `.centaur/graphify/migration.json` sinaliza `needs_sync` e mapeia os destinos, sem reescrever IDs históricos. Sincronização/reindexação Graphify só quando explicitamente solicitada ou necessária a uma investigação autorizada.

## 5. Registrar e entregar

Atualize o carimbo de schema com a versão real do `start-project` instalado e a data atual. Registre a mudança conforme o backend, sem gerar `implements/` no modo ai-memory. Informe caminhos migrados, customizações preservadas, backup e forma de recuperação, verificações realizadas, dependências opcionais indisponíveis e conflitos pendentes. Não declare instalação funcional só porque os arquivos foram copiados.

Para recuperar um lote do script, leia `manifest.json`: restaure cada entrada de `before` com hash não nulo a partir de `files/<caminho>`; remova somente destinos com hash anterior nulo, após conferir que não receberam novas edições. Verifique hashes e referências antes de retomar. Não restaure por cima de alterações posteriores sem revisão.
