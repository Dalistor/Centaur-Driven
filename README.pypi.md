# Centaur CLI

Harness de desenvolvimento assistido por IA com **OpenRouter, Codex e Claude**.
O humano define intenção, comportamentos e limites; o agente trabalha com specs,
contratos, ferramentas e evidências de entrega.

Requer **Python 3.10+** e terminal interativo em **Linux ou macOS**. Não possui
dependências Python obrigatórias de execução. Anexos visuais/capturas usam o extra `attachments`; computer use usa o extra `computer`. Codex e Claude são integrações opcionais que
precisam de seus próprios executáveis e login.

## Instalação

Para disponibilizar `centaur` globalmente, em um ambiente isolado:

```bash
pipx install centaur-cli
centaur --version
centaur /caminho/do/projeto
```

Também pode instalar com pip em um ambiente Python que permita instalações:

```bash
python3 -m pip install centaur-cli
centaur .
```

Em distribuições com Python gerenciado pelo sistema, use pipx ou um virtualenv.
Não é necessário usar sudo nem alterar o Python do sistema.

Para atualizar: `pipx upgrade centaur-cli`, ou `python3 -m pip install --upgrade centaur-cli`.

## Backends

```bash
# Abre a seleção inicial: backend, modelo padrão, effort, permissões e velocidade.
centaur .

codex login
centaur --backend codex .

claude auth login
centaur --backend claude .
```

Antes de abrir o chat, escolha **Backend → Modelo padrão → Effort → Permissões → Velocidade → Iniciar conversa**.
As preferências da pasta ficam pré-selecionadas. Flags como `--backend`, `--model` e
`--effort` também preenchem essas escolhas; `--no-setup` abre diretamente com elas.
↑/↓ navegam, Enter confirma e Esc volta ou cancela.

Modelo e effort definem o agente principal. Ao executar tasks com subagentes, o Centaur
escolhe modelos do mesmo backend conforme complexidade e risco. O modo padrão pede aprovação para gravações e comandos. O modo sem perguntar executa com
as permissões do usuário, sem sandbox. A conexão é validada antes
de salvar as preferências e abrir o chat; falhas preservam as escolhas.
Ao confirmar OpenRouter sem chave, o cadastro usa entrada oculta.

Uso dos modelos segue a autenticação, custos e limites do backend selecionado.
Mensagens e arquivos consultados pelo agente são enviados ao provedor.

## Anexos e capturas

```bash
pipx install --force 'centaur-cli[attachments] @ git+https://github.com/Dalistor/Centaur-Driven.git@cli-v0.10.5'
```

Ctrl+V cola imagem/texto/arquivos; arrastar ou colar caminhos insere marcadores atômicos
na mensagem. Backspace/Delete remove o anexo; ↑/↓ restaura prompts com anexos e volta ao
rascunho. Linux: xclip (X11) ou wl-clipboard (Wayland); macOS: Pillow/pbpaste.

No chat, cole/arraste um arquivo para preparar um anexo e Ctrl+S captura uma
vez o monitor principal após três segundos. Revise os nomes junto à mensagem;
`$attachments` lista a fila e `$detach <número|all>` remove anexos. Escreva o pedido e
pressione Enter para enviar; a preparação não chama a IA. Ctrl+C cancela a captura.

Texto UTF-8/código/logs funciona nos três backends (até 512 KiB); PNG/JPEG/WebP/GIF
estático exige modelo visual. PDF exige modalidade `file` nativa no OpenRouter.
Até oito anexos por mensagem, 8 MiB por arquivo, 25 megapixels por imagem. Binários não
suportados são recusados. Capacidades são revalidadas ao trocar modelo.
Capturas automáticas requerem X11 no Linux ou permissão de tela no macOS. Em Wayland,
anexe uma captura salva pelo sistema. O extra `computer` também inclui as dependências.

Anexos enviados têm cópias privadas em `.centaur/attachments`, usadas na retomada e
`/retry`; arquivos não são descartados na compactação. O prefixo compactado passa a usar
texto/descrições resumidos, sem reenviar as imagens/PDFs arquivados. Filas não enviadas
não sobrevivem ao encerramento do CLI. Veja formatos, limites e detalhes no README.

## Recursos

- `$config`: backend, modelo, effort, permissões e velocidade; alterações no mesmo backend preservam o chat.
- Fast quando anunciado pelo modelo, independente de effort; pode consumir mais créditos. `--speed fast` e `CENTAUR_SPEED` também configuram.
- `$credits`: cotas e créditos Codex via App Server; Claude usa eventos públicos da resposta com indicação de cache. Dados ausentes não recebem saldos inventados.
- `$status`: árvore local das specs; `$status --ai` analisa evidências somente em leitura. `/status` permanece como alias.
- `Shift+←` ou `/chats`: histórico por pasta; `/rename` renomeia a conversa.
- Skills distribuídas no pacote: `$spec`, `$run`, `$check`, `$skill` e outras.
- Permissões por seletor: pedir aprovação, automático de baixo risco ou sem perguntar; subagentes herdam o modo.
- Automático reconhece o validador de ciclo de vida incluído, documentos de `.centaur` e consultas com glob ou leitura por intervalos.
- `/wide` amplia o chat; erros completos e `/retry` preservam o turno e os resultados anteriores. Rodapé limitado à largura do campo; diagnósticos longos/Unicode quebram na conversa sem overflow.
- Entrada com quebra automática, Shift+Enter/Ctrl+J para nova linha e campo de três a oito linhas; colagem protegida não envia automaticamente.
- Barra de contexto livre estimado; `$compact` resume mensagens antigas com IA sem apagar o histórico ou repetir ferramentas. `/compact` é alias.
- Timeout de inferência e compactação de 30min por padrão; `CENTAUR_NATIVE_TIMEOUT`, `CENTAUR_OPENROUTER_TIMEOUT` e `CENTAUR_COMPACT_TIMEOUT` ajustam (30–3600s). Cada resumo usa o orçamento restante, sem teto de 90s. `CENTAUR_CONTEXT_WINDOW` informa a janela real quando não consta no catálogo.
- Turnos sem limite fixo de etapas; Ctrl+C interrompe comandos e bloqueia novas ações.
- ↑/↓ recuperam prompts anteriores e avançam até o rascunho atual, inclusive vazio; prompts salvos não são alterados. PgUp/PgDn e roda do mouse rolam a conversa; Ctrl+E volta ao fim.
- Autocompact a 80% da janela conhecida, sem apagar histórico; `CENTAUR_AUTOCOMPACT=0` desativa. Resumos longos recebem até duas revisões sem truncar a memória.
- `$compact` inicia com um único Enter e mostra progresso por fragmento; o resumo usa effort baixo anunciado ou padrão do provedor sem mudar o effort do chat.
- Perguntas interativas da IA, com opções ou resposta livre e preservação do rascunho.
- Computer use opcional: captura contínua local e até três quadros recentes por decisão da IA, mouse/teclado com confirmação em todos os modos.
- Validação do ciclo intenção → contrato → implementação → evidência → integração.
- Emblema Convergência em Braille, com curvas finas, flecha verde, luz e animação.
- `CENTAUR_REDUCED_MOTION=1` reduz movimento; `CENTAUR_GRAPHICS=0` usa blocos/ASCII.

[Documentação completa](https://github.com/Dalistor/Centaur-Driven/tree/main)
· [Código-fonte](https://github.com/Dalistor/Centaur-Driven)
· [Reportar problema](https://github.com/Dalistor/Centaur-Driven/issues)

Para instalar diretamente do Git com computer use:

```bash
pipx install --force 'centaur-cli[computer] @ git+https://github.com/Dalistor/Centaur-Driven.git@main'
```

Requer modelo com visão e desktop Linux X11 ou macOS com permissões de tela/acessibilidade.
Uma autorização por chat para captura/controle, persistente até revogar ou excluir.
A captura dura a tarefa, cerca de 2 quadros/s; ações seguintes não pedem confirmação.
Menus/outro chat pausam e retorno retoma com quadros novos. Controle exclusivo entre
chats/processos. `$computer status/pause/resume/revoke` funciona durante a execução;
Ctrl+G revoga também nos menus. `computer_stop` e fim do turno descartam os quadros.
Zoom de áreas pequenas, arrasto, cliques adicionais, rolagem horizontal e teclas F1–F12.
Quadros repetidos são deduplicados. Esperas canceláveis e estabilização visual após input
ajudam a observar carregamentos; o modelo ainda precisa verificar o resultado da tarefa.
Ctrl+C para a captura. Não é inferência contínua por vídeo; as decisões seguem a latência
do modelo. Quadros não ficam no histórico; Codex usa anexos temporários apagados após
a requisição. No Linux, texto Unicode precisa de xclip/xsel.

Versão inicial experimental. A instalação não substitui os CLIs nativos opcionais,
não configura servidores externos e não inicia chamadas pagas automaticamente.

## Chats e agentes simultâneos

Shift+← abre o menu; **N cria outro chat**, **Enter abre** e **Tab mostra todos os agentes**.
Estados: Trabalhando, Aguardando input e Parado. Conversas deste processo continuam
executando ao trocar de chat, com perguntas/aprovações e Ctrl+C separados. Enter em um
subagente permite ler; outro Enter abre seu coordenador para responder. Agentes usam a
mesma pasta: distribua arquivos/tarefas entre eles. Captura de computer use para ao trocar.

Subagentes ativos aparecem em quadros laterais quando há espaço (112×18 ou mais), com
tarefa, modelo, estado, tempo e últimas ações/comentários públicos. Fecham ao terminar;
a roda na lateral percorre todos e clique abre leitura ou input no coordenador deste
processo. Em telas menores use Shift+←, Tab. Cliques no campo de mensagem movem o cursor
em texto multilinha/Unicode, preservando os marcadores de anexos e sem enviar mensagens.
O timeout de 30 minutos é por inferência: a espera de subagentes não expira o coordenador;
subagentes vivos também protegem o chat pai da limpeza.

Chats com mais de **64h desde a criação** são apagados com anexos e subagentes na limpeza
periódica. Sessões ativas ou com rascunho/anexos aguardam ficar livres para a limpeza.
Atividade e renomeação não reiniciam o prazo. Não há execução após fechar o terminal.

### Aparência e subagentes

O fundo agora é azul-marinho; composer, mensagens e cartões usam uma superfície azul
um pouco mais clara. O título mantém destaque e comentários/ações continuam distintos.
Cores programáveis são restauradas ao sair; terminais ANSI fixos usam uma aproximação
e `NO_COLOR` preserva marcadores e negrito.

Preview do renderer real, com dados demonstrativos:

![Centaur CLI com tema navy e subagente](https://raw.githubusercontent.com/Dalistor/Centaur-Driven/cli-v0.9.3/docs/images/cli-0.9.3.svg)

Os cartões e o preview informam **Aguardando modelo**, **Executando comando**,
**Lendo arquivo** ou **Compactando**, com tempo nessa fase. Heartbeat não é prova
de progresso. Falhas encerram o cartão, mantêm o diagnóstico no histórico do agente
e devolvem o controle ao coordenador; Ctrl+C também cancela o subagente.

Desde a **0.9.4**, silêncio de Codex/Claude não encerra a chamada por padrão:
respostas estruturadas podem aparecer apenas ao final. O prazo total por inferência
continua em **30 minutos**, controlado por `CENTAUR_NATIVE_TIMEOUT`; Ctrl+C continua
cancelando. Isso vale também para subagentes e chamadas de compactação.

`CENTAUR_NATIVE_IDLE_TIMEOUT` tem padrão **0 (desativado)**. Aceita 0 ou 30–3600s
para quem quiser ativar explicitamente um limite de silêncio. Atividade renova esse
limite opcional, mas nunca prolonga o prazo total. Para desativá-lo explicitamente:

```sh
CENTAUR_NATIVE_IDLE_TIMEOUT=0 centaur --backend codex .
```

Após um erro, abra a mesma conversa em Shift+← e use `/retry` para continuar com os
checkpoints existentes. A retomada não reenvia o prompt e não repete ferramentas já
respondidas. Chamadas interrompidas exigem conferir o estado antes de tentar novamente.
Na **0.9.3**, que não aceita zero, `CENTAUR_NATIVE_IDLE_TIMEOUT=1800` evita o corte
prematuro de cinco minutos enquanto você atualiza.


### Diagnóstico de chamadas nativas (0.9.5)

Um erro de `tempo limite de 1800 segundos` significa que **uma chamada ao CLI** não
terminou em 30 minutos; não é um limite da tarefa inteira nem de todos os subagentes.
A barra de contexto não informa se a rede está funcionando ou se o modelo está pensando.
Aumentar o prazo ou usar `/retry` com o mesmo contexto não resolve necessariamente a causa.

Desde a 0.9.5, o timeout informa o último tipo de evento completo, o tamanho da entrada,
stdout e stderr, e uma categoria de aviso do CLI quando houver evidência: conexão,
TLS, cota, contexto, schema ou configuração. Esses dados ficam no erro persistido do
chat; nenhum log bruto, token, texto de raciocínio ou chamada parcial é exibido. Um
aviso pode ter sido recuperado; ele não confirma sozinho a causa final. Sem evidência,
o erro informa explicitamente **causa não confirmada**.

`turn.failed` do Codex e resultados de erro do Claude encerram a chamada sem esperar o
prazo inteiro, mesmo se o processo permanecer aberto. Um aviso `error` recuperável do
Codex não invalida uma resposta final válida. Arquivo final não sobrepõe `turn.failed`.
Respostas parciais nunca executam ferramentas; `/retry` continua com os checkpoints.

O adaptador usa uma execução efêmera e saída estruturada por etapa; ele não retoma a
sessão interna do Codex interativo. Portanto, o CLI interativo funcionar não comprova
que uma chamada estruturada com todo o contexto ativo concluirá. Para investigar uma
falha recorrente, confira `centaur --version` e `codex --version`, e o novo diagnóstico
no chat. Se a conversa estiver grande, `$compact` antes de `/retry` reduz o contexto
ativo sem apagar o histórico. Não há retry automático de ações.

Referências consultadas: [modo não interativo](https://developers.openai.com/codex/noninteractive/),
[configuração de rede/retries](https://developers.openai.com/codex/config-reference/) e
[processador JSONL oficial](https://github.com/openai/codex/blob/main/codex-rs/exec/src/event_processor_with_jsonl_output.rs).
A configuração documenta idle de stream de 300000ms e até cinco retries; uma sequência
de interrupções pode ocupar grande parte dos 30 minutos. Isso é uma hipótese de
investigação, não um diagnóstico confirmado da máquina do usuário.


### Hierarquia e espera dos subagentes (0.9.6)

O menu de agentes agrupa cada principal com seus filhos, em árvore com `├─↳` e
`└─↳`, inclusive históricos com vários níveis. Os cartões mostram nome/ID do principal
antes da task. O preview informa o principal e o pai imediato; Enter retorna ao
principal deste processo. A árvore tolera pais ausentes/ciclos e preserva seleção por
ID. A release 0.9.6 não habilitava delegação recursiva; a versão 0.10.0 acrescenta delegação recursiva com seis vagas simultâneas por principal.

O transcript distingue `Subagente falhou`, `Subagente interrompido` e `Relatório recebido`.
Receber o relatório ainda exige conferência pelo coordenador; falha não recebe marca de sucesso.

A barra do preview agora pertence ao **subagente** e usa o rótulo `Agente`; não conta
o histórico nem o rascunho do principal. A barra `Contexto` do chat principal permanece
independente. Uma porcentagem livre no principal não informa a janela do executor.

Durante inferência nativa, cartões/preview mostram eventos públicos do CLI e o tempo
sem nova saída. Avisos de rede, TLS, cota, contexto, schema e configuração são categorias
fixas, sem logs brutos ou raciocínio privado. Heartbeat não renova esse tempo nem o
prazo da inferência. Ausência de saída não confirma travamento: silêncio continua
permitido até o deadline, com Ctrl+C para cancelar pelo principal. Na 0.9.6, a nova
telemetria começa na próxima chamada; não é inserida em uma execução já iniciada.

Subagentes herdam effort e velocidade do chat quando compatíveis com o modelo escolhido.
Se o catálogo não aceitar o effort, usam o default do modelo; Fast só é enviado quando
anunciado. O preview exibe essas escolhas. O modelo/backend não é trocado automaticamente.
A instrução do adaptador reforça que cada chamada produz somente a próxima etapa.

A limpeza de `run_command` agora aguarda no máximo dois segundos após o sinal, inclusive
em timeout/cancelamento e na corrida em que o processo já terminou. Saída não confirmada
é informada explicitamente; nenhuma ação é repetida automaticamente. O limite de execução
de comando continua 60s; inferência continua 30min por chamada. Não há limite global da
espera do coordenador por tasks.

Demonstrações com dados sintéticos do renderer real:
[cartões e árvore](docs/images/cli-agent-tree-0.9.6.svg) ·
[menu de agentes](docs/images/cli-agent-menu-0.9.6.svg).

### Coordenação e testes por criticidade (0.10.0)

Enter durante execução enfileira orientação entregue entre etapas. Subagentes continuam
trabalhando, podem delegar e trocam mensagens pelo harness; até seis executores
simultâneos na árvore inteira do principal. Relatórios retornam à sessão de origem.

Anexos são preparados por colagem/arrasto, Ctrl+V e captura Ctrl+S. Computer use usa
um quadro atual e lotes curtos no mesmo alvo, mantendo consentimento próprio do chat.

Testes novos protegem falhas concretas em pontos vitais ainda sem proteção suficiente;
reaproveite testes existentes e use validação proporcional nos ajustes simples.
Gates e requisitos explícitos do projeto continuam obrigatórios.


### Encerramento das chamadas nativas (0.10.1)

Codex/Claude deixam de aguardar EOF de processos descendentes após o CLI encerrar.
Uma resposta integral validada, acompanhada de evento terminal de sucesso, também
libera a etapa após dois segundos de tolerância para o encerramento do CLI. A limpeza
afeta somente o grupo daquela chamada, sem repetir comandos ou cancelar outros agentes.
Respostas parciais, lotes inválidos e falhas continuam rejeitados. Em esperas longas,
a interface mantém visível o último evento público do CLI, ou informa que nenhum
evento completo foi recebido. O limite de inferência continua 30 minutos; silêncio
sozinho não comprova travamento. Veja [validação e limites](docs/validation-native-shutdown.md).

## Diagnóstico de espera

Use `$diagnose` durante a execução, ou `centaur diagnose --json` em outro terminal
na mesma pasta. Consulta versão, fase, eventos públicos e contagem de bytes sem
inferência, prompts ou logs brutos. O último estado permanece após Ctrl+C. A versão
0.10.5 também usa instruções base do harness no Codex e reconhece eventos terminais
completos sem quebra de linha final. Isso não determina o estado remoto do modelo.
