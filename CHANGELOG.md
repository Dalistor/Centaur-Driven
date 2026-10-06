# Changelog

## 0.7.0 — 2026-10-06

- Entrada multilinha com quebra visual por células Unicode, Shift+Enter (Kitty/xterm), Ctrl+J e colagem protegida sem envio automático.
- Campo de mensagem com três linhas iniciais, expansão até oito e rolagem interna acompanhando o cursor; setas editam linhas e PgUp/PgDn continuam rolando o chat.
- Barra de contexto restante no rodapé, com estimativas explícitas, contagens informadas pelo provedor e limites do catálogo; limite desconhecido não recebe porcentagem inventada.
- `$compact` (alias `/compact`) resume o contexto antigo com IA, sem ferramentas, preserva o histórico completo e mantém intactos os lotes de chamadas e a recuperação por `/retry`.
- Compactação em fragmentos, cancelável e salva atomicamente; falhas ou resumos sem redução preservam o contexto anterior.
- Timeout nativo padrão de 600 segundos, configurável por `CENTAUR_NATIVE_TIMEOUT` (30–3600), substitui o limite fixo de 180 segundos.

- Cotas e créditos nativos do Codex via App Server somente em leitura; Claude usa eventos públicos de limite, com estado em cache e ausência de dados explícita. `$credits` é alias de `/credits`.
- Velocidade Padrão/Rápido no seletor inicial e `$config`, separada de effort e limitada a capacidades anunciadas; `--speed` e `CENTAUR_SPEED` também configuram.
- Trocar modelo, effort ou velocidade no mesmo backend preserva ID, título, histórico e memória compactada; somente trocar backend abre outro chat.

## 0.6.0 — 2026-10-06

- Computer use: zoom de regiões com mapeamento de coordenadas de volta ao desktop e retorno ao monitor inteiro.
- Novas ações: clique direito/meio/triplo, arrasto e rolagem horizontal; teclas F1–F12 e aliases de modificadores.
- Espera cancelável de até 10s para observar carregamentos e estabilização visual limitada após input, sem alegar sucesso da tarefa.
- Quadros idênticos são enviados uma vez por decisão; PNGs são codificados durante a captura e incluem área física, idade e autorização restante.
- Troca de sessão atômica, proteção contra encerramento por workers antigos e diagnóstico de captura interrompida.
- Digitação em blocos verifica cancelamento; teclas e botão de arrasto são liberados mesmo após falha/fail-safe.
- Pesquisa comparativa de Anthropic, Cua, Browser Use e usecomputer; novos testes de contrato e desktop Xvfb real.

## 0.5.1 — 2026-10-06

- Retomar um turno com `content=null` recupera chamadas pendentes sem repetir ações.
- `/retry` mantém `$status --ai` em somente leitura, mesmo após resultados de ferramentas.

## 0.5.0 — 2026-10-06

- Turnos sem limite fixo de 20 etapas; Ctrl+C interrompe comandos/CLIs locais e bloqueia novas ações.
- Rolagem por setas, PgUp/PgDn e roda do mouse, preservando leitura durante novas mensagens; Ctrl+E volta ao fim.
- Perguntas interativas da IA, com até três opções, resposta livre, pular e preservação do rascunho; também em subagentes.
- Extra `computer`: captura contínua do monitor principal e quadros recentes por decisão para OpenRouter/Codex/Claude.
- Computer use com autorização temporária, confirmação por ação em todos os modos, referência visual, verificação do alvo e fail-safe ativo.
- Layout compacto utilizável em 40 × 12 e nova validação de desktop descartável no workflow da release.


## 0.4.1 — 2026-10-06

- `$status` e `$status --ai` no autocomplete, tela inicial e instruções do agente.
- `/status` e `/status --ai` preservados como aliases; análise com IA continua somente leitura.
- Modo automático reconhece o validador de ciclo de vida incluído, documentos de `.centaur`, caminhos absolutos dentro do projeto, consultas com glob e leitura por intervalos.
- Validador usa Python sem hooks de site/ambiente e Git do sistema, sem fsmonitor.

## 0.4.0 — 2026-10-06

- Modos ask, auto e never na abertura, `$config`, flags e preferências da pasta.
- Política compartilhada com subagentes; modo automático libera edições comuns e consultas restritas.
- Mudar apenas permissões preserva a conversa; chats antigos não ampliam permissões ao retomar.
- Argumentos JSON tipados, respostas nativas até 8 MB e fallback do Codex por eventos finais concluídos.
- Diagnósticos específicos e completos no histórico; `/retry` retoma sem repetir ações já registradas.
- `/wide` alterna a largura da conversa e seletores compactos preservam acesso ao salvamento.

## 0.3.0 — 2026-10-06

- Seleção inicial de OpenRouter, Codex ou Claude antes da autenticação e do chat.
- Escolha do modelo padrão e effort, com preferências da pasta pré-selecionadas.
- Explicação da escolha de modelos por complexidade e risco para subagentes.
- Revisão antes de iniciar, cancelamento sem chat e recuperação de falhas de conexão.
- `--no-setup` para abrir diretamente com flags, ambiente ou preferências salvas.

## 0.2.0 — 2026-10-06

- Conversa em coluna de leitura, título destacado e mensagens do usuário com contraste.
- Resumos públicos do trabalho antes da resposta e ferramentas compactas; Ctrl+O abre os detalhes.
- Título gerado com IA após a primeira resposta, sem bloquear a conversa ou sobrescrever nomes manuais.
- Markdown básico legível, preservando código literal.
- Testes multiplataforma e integração da CLI na branch main.

## 0.1.0 — 2026-10-06

Primeira distribuição pública do Centaur CLI.

- Backends OpenRouter, Codex e Claude com catálogo de skills incorporado.
- Configuração por seletor, escolha de modelo e esforço de raciocínio por conversa.
- Histórico por pasta, Shift+←, edição de entrada e renomeação de chats.
- Aprovação de ferramentas e validação de contratos/evidências no ciclo de desenvolvimento.
- Emblema Convergência com curvas finas e flecha, iluminação e renderização Braille.
- Distribuições wheel/sdist, comando `centaur --version` e publicação automatizada.
