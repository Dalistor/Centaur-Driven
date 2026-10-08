# Changelog

## Não publicado

- Usar fundo e texto padrão do emulador em conversa, composer, startup, seleção e
  subagentes. Remover preenchimentos navy e alterações da paleta do terminal;
  destaques ANSI, atalhos discretos e seleção por seta/negrito, inclusive em NO_COLOR.

- Conservar a seleção de cada chat ao navegar, inclusive sessões sem primeiro
  turno; atualizar o contexto após `$config` sem reescrever workers anteriores.
- Retomar modelo, effort e velocidade do histórico compatível; permissões continuam
  sob a escolha da abertura. Novos chats seguem a seleção da sessão focada.
- Limpar cotas/créditos ao retornar a outro cliente e rejeitar atualizações atrasadas.
- Verificar o owner do runtime no menu, mesmo quando há contexto local lembrado.
- Validar principal/filho/neto, herança compatível e conversas simultâneas nos três
  adaptadores. Ver [evidências e limites](docs/validation-backend-routing-2026-10-08.md).

## 0.10.5 — 2026-10-08

- Substituir as instruções base de executor do Codex pelas instruções do harness,
  usando `model_instructions_file`, para solicitar somente a próxima etapa.
- Reconhecer envelopes terminais completos sem LF final, sem aceitar JSON parcial
  nem dispensar a validação das chamadas antes de concluir a inferência.
- Adicionar `$diagnose` durante o turno e `centaur diagnose [pasta] --json` sem
  autenticação/inferência. Preservar metadados após cancelamento e atualizar evento
  imediatamente; heartbeat e telemetria não contam como saída do modelo.
- Validar o contrato com Codex oficial 0.161.0 e servidor Responses local isolado,
  sem conta ou inferência paga, também como gate de CI. Reutilizar regressões vitais
  de encerramento e cancelamento. Ver [evidência e limites](docs/validation-native-bridge.md).

## 0.10.4 — 2026-10-08

- Tornar atômica a aquisição do desktop ao reiniciar computer use: o worker antigo
  não libera a posse da nova sessão enquanto seu backend é criado.
- Limitar a recuperação de conexão dos CLIs nativos a três minutos após erro de
  rede observado. Novos avisos, stderr e heartbeat não renovam esse prazo; saída
  real do modelo encerra a recuperação. Silêncio sem erro mantém o prazo total de
  30 minutos. `CENTAUR_NATIVE_RECOVERY_TIMEOUT=0` desativa apenas o limite de recuperação.
- Mostrar `Reconectando` e o tempo da recuperação no chat e nos cartões de agentes,
  retirando o aviso quando o modelo retoma. Diagnóstico seguro permanece no erro;
  não há replay automático nem execução de respostas parciais.
- Validar reconexões em stdout/stderr, prazo absoluto, cancelamento, compactação e
  resposta final após recuperação com processos locais controlados. Ver
  [evidência e limites](docs/validation-native-recovery.md).

## 0.10.3 — 2026-10-08

- Colar texto longo não encerra o CLI com `File name too long`; falhas ao reconhecer caminhos preservam o texto e o cursor, sem preparar anexos parciais.
- A mesma identificação segura atende colagem protegida, Ctrl+V e caminhos digitados; arquivos existentes com espaços e listas de URLs locais continuam anexando normalmente.

## 0.10.2 — 2026-10-08

- Desfocar o terminal pausa somente desenho e animações; eventos, respostas, agentes e heartbeat continuam em segundo plano, sem acumular saída em terminais ocultos.
- Eventos de foco são reconhecidos tanto por CSI quanto por teclas estendidas do curses, sem inserir códigos no rascunho.
- Retornar ao terminal redesenha o estado atual, inclusive após redimensionamento; digitar também recupera a tela se o evento de retorno for perdido.

## 0.10.1 — 2026-10-08

- Codex/Claude não aguardam EOF de processos descendentes após o CLI encerrar; respostas completas continuam validadas e respostas incompletas são rejeitadas.
- Evento terminal de sucesso com resposta válida libera a etapa após dois segundos de tolerância para encerramento do CLI, com limpeza limitada ao grupo daquela chamada e sem repetir ferramentas.
- Durante esperas longas, a atividade mantém o último evento público do CLI visível, inclusive quando nenhum evento completo foi recebido.

## 0.10.0 — 2026-10-07

- Orientação durante execução entra após a etapa atual, com fila persistente por chat; ações restantes do lote antigo são reavaliadas e subagentes continuam trabalhando.
- Delegação em segundo plano, comunicação/progresso pelo harness e recursão com seis executores simultâneos na árvore do principal; relatórios retornam ao pai e à sessão de origem.
- Perguntas e permissões serializadas; encerramento, falhas de armazenamento/thread e proteção de históricos ativos não deixam vagas presas.
- Anexos pelo compositor, colagem/arrasto e Ctrl+S; comandos auxiliares attach/screenshot retirados.
- Computer use com quadro atual, foco único e até quatro passos no mesmo alvo; lote validado antes de input e falha parcial sem replay.
- OpenRouter valida todo o lote, rejeita respostas truncadas, preserva blocos necessários à continuidade e responde ao cancelamento local sem executar resposta tardia.
- Codex/Claude rejeitam finais vazios/incompletos, validam schemas aninhados e limpam processos em falhas locais; effort conhecido é respeitado.
- Fluxo de código concentra testes novos nos pontos vitais ainda sem proteção suficiente, reutiliza a suíte e evita baterias por método/task/camada.


## 0.9.4 — 2026-10-07

- Corrige a regressão da 0.9.3 que encerrava respostas Codex/Claude após cinco minutos sem saída parcial. Silêncio não interrompe por padrão; `CENTAUR_NATIVE_IDLE_TIMEOUT=0` desativa esse limite, e 30–3600s o ativam explicitamente.
- Prazo absoluto de 30min, orçamento de compactação, Ctrl+C, limpeza limitada e checkpoints continuam ativos. Testes cobrem resposta final após 301s de silêncio simulado, subagente e resumo sem falso erro, além de processos reais silenciosos.

## 0.9.3 — 2026-10-07

- Fundo navy, texto mais claro e superfícies consistentes no composer, mensagens e cartões. Tema programável restaura cores ao sair; fallback ANSI/NO_COLOR preservado.
- Subagentes mostram fase e tempo de espera; falhas permanecem no preview. Silêncio do CLI nativo por 300s encerra a chamada com diagnóstico e checkpoints, configurável por `CENTAUR_NATIVE_IDLE_TIMEOUT`; deadline total por chamada continua 30min. Cancelamento propaga ao coordenador e limpeza de pipes tem prazo.

- Computer use pede consentimento uma vez por chat para captura/controle, persistente entre turnos e reinício até revogação/exclusão; ações seguintes não abrem confirmações.
- Captura dura a tarefa sem expiração de 120s; menus/input/outro chat pausam e retorno retoma com quadros novos. Lock POSIX por usuário mantém controle exclusivo entre chats/processos/projetos.
- `$computer status/pause/resume/revoke` funciona durante execução; Ctrl+G revoga também em menus/input e cancela o turno. Ctrl+C e computer_stop encerram captura mantendo consentimento.
- Move/scroll atualizam captura sem espera de estabilização; cliques/texto/teclas/arrasto usam dois intervalos e orçamento de 1s. Verificação de alvo/resolução/idade e prevenção de replay permanecem.
- Autorização privada separada do transcript/imagens; exclusão/TTL a remove e ferramentas de arquivo do modelo não editam o registro. Ciclo de vida validado com worker real, pausa/retomada, revogação e lock entre processos.

## 0.9.2 — 2026-10-07

- Quadros laterais vivos para todos os subagentes ativos da pasta: tarefa, modelo, estado, tempo e últimos comentários públicos/ações. Fecham ao terminar; rolagem mantém acesso a todos e clique abre leitura/input.
- Layout responsivo em 112×18 ou mais; menu e indicador no rodapé quando não há espaço. Campo, conversa, perguntas e autocomplete respeitam a lateral.
- Clique move cursor em mensagem, renomeação e resposta livre, considerando Unicode, quebra de linha, scroll e anexos atômicos. Nenhum clique envia mensagens ou aprova ações.
- Histórico parado é filtrado antes de carregar mensagens; proteção de coordenador com subagentes vivos e timeout por inferência validados, incluindo espera superior a 30 minutos simulada.
- Testes de quadros/scroll/ciclo de vida e mouse em PTY curses real nos três modos de aparência.

## 0.9.1 — 2026-10-06

- Inferência Codex/Claude/OpenRouter e orçamento da compactação passam a 30 minutos por padrão, configuráveis de 30 a 3600 segundos.
- Resumos usam o orçamento restante, sem o teto antigo de 90s; subagentes roteados repassam prazo, effort e capacidades do backend. Cancelamento, checkpoints e retomada permanecem ativos.
- Rodapé respeita a largura do composer, resume erros já presentes na conversa e indica avisos truncados com reticências. Diagnósticos completos quebram por células do terminal, incluindo Unicode e caminhos longos.
- Falhas reais de compactação ficam salvas na conversa e são removidas após compactação bem-sucedida; interrupção do usuário não vira erro.

## 0.9.0 — 2026-10-06

- Composer com Ctrl+V de imagens, texto e caminhos/URIs locais; drag-and-drop, marcadores atômicos, remoção inteira e recuperação de anexos com ↑/↓. Rascunhos e filas separados por conversa.
- Menu de chats/agentes atualizado ao vivo: Trabalhando, Aguardando input e Parado. N cria outra conversa durante execuções ou pedidos de input; múltiplos chats podem trabalhar simultaneamente.
- Eventos, modelo, permissões, perguntas/aprovações, compactação, cancelamento e título pertencem à sessão de origem. Histórico de subagentes pode ser consultado e seu coordenador aberto para responder.
- Limpeza automática após 64h da criação, incluindo anexos/subagentes; data imutável e migração legada sem tocar atividade. Sessões ativas e rascunhos são preservados até ficarem livres. Captura para ao trocar de chat.
- Testes de clipboard, PTY real, sessões concorrentes e retenção; CI inclui colagem real de imagem em Xvfb.

## 0.8.0 — 2026-10-06

- `$attach`, `$screenshot [0–10]`, `$attachments` e `$detach <número|all>` preparam anexos revisáveis antes do envio; captura única, espera cancelável e fila separada por chat.
- Texto UTF-8 nos três backends; imagens estáticas com suporte visual anunciado; PDFs nativos OpenRouter com modalidade file e sem OCR externo automático. Extra opcional `attachments`.
- Cópias privadas verificadas por SHA-256 preservam anexos enviados em retomadas e `/retry`; modelo incompatível, gravação recusada e cópia ausente/alterada produzem diagnóstico sem descartar a mensagem.
- Campo de mensagem mostra quantidade e nomes; barra de contexto considera texto pendente. Compactação inclui textos/identidades sem base64 e arquiva originais visuais sem inventar seu conteúdo.
- Cobertura de transporte, preparação/cancelamento, persistência e terminal real; CI verifica captura única em desktop Xvfb descartável.

## 0.7.5 — 2026-10-06

- Autocompact recupera espaço para continuar o turno (alvo estimado de 60% da janela, incluindo prompt/ferramentas), sem exigir resumir todo o prefixo antigo.
- Ao atingir 180s, usa o resumo validado até uma divisão segura e mantém todas as mensagens restantes integrais. Nunca divide um lote de ferramentas nem elimina texto ainda não processado.
- Sem divisão segura ou espaço suficiente, o turno fica pausado, com `$compact` e `/retry`, sem registrar o prazo como falha do modelo. Checkpoints continuam retomáveis.
- O erro legado de orçamento de compactação aparece como pausa anterior; erros reais permanecem visíveis e preservados para retomada.

## 0.7.4 — 2026-10-06

- Comentários públicos da IA ficam em branco; ações de ferramentas em azul/negrito e falhas, interrupções ou recusas em âmbar.
- Cores seguem a origem da mensagem e permanecem nas linhas quebradas, sem confundir comentários ou código indentado com ações. Em `NO_COLOR`, ações usam negrito e comentários peso normal.

## 0.7.3 — 2026-10-06

- Compactação tem orçamento total de 180 segundos, separado do timeout do chat; chamadas de resumo recebem até 90 segundos, respeitando o tempo restante. `CENTAUR_COMPACT_TIMEOUT` configura o orçamento (30–3600).
- Fragmentos têm teto de 48 mil caracteres. Timeout reduz o fragmento pela metade e tenta novamente dentro do mesmo orçamento, sem cortar material do histórico.
- Cada fragmento validado salva progresso em disco; `$compact` e autocompact retomam após falha, cancelamento ou reinício, sem refazer os fragmentos concluídos. Alterações no prefixo, modelo ou memória invalidam o rascunho.
- Progresso parcial não substitui a memória ativa. Somente um resumo completo, válido e que reduza contexto é aplicado; o histórico e os lotes de ferramentas continuam intactos.

## 0.7.2 — 2026-10-06

- `$compact` inicia com um único Enter mesmo com autocomplete aberto; comandos locais também executam diretamente, enquanto Tab continua apenas completando.
- Compactação manual/automática informa fragmento atual, total de fragmentos e revisões; Ctrl+C continua cancelando sem aplicar resumo parcial.
- Fragmentos usam o orçamento da janela conhecida, com teto de 120 mil caracteres, evitando muitas chamadas pequenas em modelos de contexto amplo.
- Resumos usam effort `low` apenas quando anunciado pelo modelo; sem metadados, usam o padrão do provedor, preservando o effort do chat principal.

## 0.7.1 — 2026-10-06

- Compactação refaz resumos longos em até duas revisões canceláveis, sem truncar memória ou disponibilizar ferramentas; falha conserva o estado anterior.
- Autocompact habilitado antes da próxima chamada a 80% da janela conhecida, inclusive entre etapas; gravação atômica e histórico completo preservado. `CENTAUR_AUTOCOMPACT=0` desativa.
- Decodificação de setas CSI/SS3 impede inserir `[A`/`[B` no campo. ↑ recupera prompts anteriores; ↓ avança até o rascunho atual, inclusive vazio, mantendo o cursor e mensagens originais.
- Chamadas nativas sem ferramentas restringem o lote a zero chamadas no schema; diagnósticos distinguem TLS/configuração de autenticação.

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
