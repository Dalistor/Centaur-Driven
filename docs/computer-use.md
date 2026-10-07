# Computer use — pesquisa e implementação 0.6.0

Fontes primárias consultadas em 2026-10-06. A implementação do Centaur foi escrita
para seu próprio contrato de ferramentas; nenhum desses projetos virou dependência
obrigatória nem foi copiado para o pacote.

| Projeto | Padrão observado | Decisão para o Centaur |
| --- | --- | --- |
| [Anthropic computer-use-demo](https://github.com/anthropics/claude-quickstarts/blob/main/computer-use-demo/computer_use_demo/tools/computer.py) | Ações de mouse adicionais, arrasto, espera, zoom e resolução reduzida para visão. | Ampliar as ações tipadas e permitir recortes mantendo coordenadas explícitas. Não oferecer mouse-down separado que possa deixar um botão preso entre decisões. |
| [usecomputer](https://github.com/remorses/usecomputer#screenshot-scaling-and-coord-map) | Mapa entre imagem capturada e desktop, inclusive capturas de janelas. | Guardar origem/extensão física em cada quadro. O modelo usa pixels da imagem; o harness aplica a transformação. Validar resolução física mesmo quando o thumbnail tem o mesmo tamanho. |
| [Browser Use](https://github.com/browser-use/browser-use/blob/main/browser_use/browser/profile.py) | Esperas mínimas, intervalo entre ações e espera por rede no navegador. | No desktop genérico, procurar estabilidade visual com tempo limitado. Permitir espera explícita para carregamentos. Não chamar isso de network-idle ou prova de sucesso. |
| [Cua](https://github.com/trycua/cua#cua-sdk-and-cli) | Drivers separados, desktops em VMs/containers e benchmarks que verificam resultados. | Preservar backend injetável e testar input real em Xvfb descartável. Não anunciar sandbox, controle em segundo plano, streaming de vídeo ou suporte multi-OS que esta implementação não oferece. |

## Contrato das ferramentas

`computer_start(purpose)` pede uma autorização por chat para ver o monitor principal,
enviar quadros ao provedor/modelo e controlar mouse/teclado sem confirmação por ação.
O consentimento fica em registro privado por ID, separado do transcript/imagens; sobrevive
a turnos e reinício, até `$computer revoke`, Ctrl+G ou exclusão/limpeza do chat. Recusa
não carrega o backend e não repete a pergunta no mesmo turno. Todos os modos exigem o
consentimento inicial. Permissões de tela/acessibilidade do sistema continuam necessárias.

A captura dura a tarefa, sem expiração fixa de 120s. `computer_stop()` encerra a captura
e apaga imagens da memória, mantendo o consentimento. Menus/input/configuração e outro
chat pausam; retorno retoma com novos quadros e referências. Desktop tem lock POSIX por
usuário, compartilhado entre projetos/processos; subagentes não recebem computer use.
`$computer status/pause/resume/revoke` são comandos locais; Ctrl+G revoga em qualquer menu
ou input. Revogar interrompe o turno; Ctrl+C interrompe mantendo a autorização.

`computer_observe()` retorna ao monitor inteiro. Para ampliar:

```json
{"frame_id": 42, "region": [100, 50, 400, 300], "wait_seconds": 2}
```

`region` é `[x,y,largura,altura]` em pixels do último quadro enviado. Não representa uma
janela do sistema nem recorta por identidade de aplicativo. A imagem ampliada usa os
pixels disponíveis no screenshot original, sem criar detalhes artificiais. O recorte
permanece nas capturas seguintes até outra observação sem região ou fim da sessão.
Seu conteúdo pode mudar se outra janela aparecer no mesmo lugar.

`wait_seconds` aceita inteiros de 0 a 10. A espera não gera input e verifica interrupção
a cada 100ms. Não altera o consentimento do chat. Um quadro precisa ser enviado ao modelo depois
do zoom antes de qualquer ação; referências anteriores ficam inválidas.

`computer_action` sempre exige `action`, `frame_id`, `x` e `y` da última imagem recebida.

| Ação | Argumentos adicionais |
| --- | --- |
| `click`, `right_click`, `middle_click`, `double_click`, `triple_click`, `move` | Nenhum |
| `drag` | `end_x`, `end_y`, dentro da mesma imagem; origem e destino são verificados antes de input. |
| `scroll` | `amount` de -10 a 10, exceto zero; `direction`: `vertical` (padrão) ou `horizontal`. Positivo é cima/direita, negativo é baixo/esquerda. |
| `type_text` | `text`, 1–4000 caracteres; inclui clique para focar o destino. |
| `keypress` | `keys`, 1–4 teclas únicas; inclui clique para focar. Letras/dígitos, modificadores, navegação, F1–F12; aliases `cmd`, `control`, `option`, `escape`, `return`, `super`. |

Uma referência visual dura no máximo 60s e é consumida antes da operação. Input
parcial nunca é repetido automaticamente. Depois da ação, o harness procura dois
intervalos consecutivos sem mudança em PNGs capturados a cerca de 150ms, dentro de
aproximadamente 1s. Movimento/rolagem atualizam a captura sem essa espera. Não é detecção de rede ou reconhecimento de sucesso. Animações
podem atingir o timeout; o modelo deve observar/esperar novamente e conferir a tarefa.

Quadros são codificados uma vez durante a captura. Imagens idênticas no buffer são
deduplicadas por decisão mantendo a mais recente; alterações distintas permanecem
em ordem temporal, até três imagens. Metadados mostram área física, tamanho da imagem,
idade, referência e consentimento do chat. Imagens seguem efêmeras fora do ChatStore.

## Validação e limites

Fluxo atual 0.9.3: [registro de validação](validation-cli-0.9.3.md). O registro abaixo
descreve a validação histórica 0.6.0; a política de consentimento é a documentada acima.

Resultado local em 2026-10-06: suíte de 275 testes, 273 aprovados e dois testes de desktop
ignorados na execução base. Os dois foram executados separadamente e aprovados em Xvfb
800×600 com MSS, Pillow e PyAutoGUI reais. PTY passou em cores, `NO_COLOR` e movimento
reduzido, incluindo pergunta em 40×12, rolagem e Ctrl+C. Wheel/sdist 0.6.0 passaram no
`twine check --strict` e no `scripts/check_dist.py`, com 59 arquivos de pacote/recursos
comparados e instalação limpa fora do checkout. Não houve chamada autenticada a um
provedor nem execução em desktop macOS.

- Testes sem dependências de GUI: `python3 -m unittest discover -s tests -q`.
- Contratos específicos: `tests/test_computer_session.py` verifica zoom/mapeamento,
  imagens repetidas, ações, cancelamento, troca de sessão, resolução e falhas de input.
- Transporte nativo em `tests/test_interaction.py`: schemas de região/espera para
  Codex e Claude, bytes de PNG, temporários privados e descarte. CLIs são simulados;
  isso não comprova uma chamada autenticada a esses serviços.
- Desktop real descartável: `CENTAUR_TEST_DESKTOP=1 xvfb-run -a -s '-screen 0 800x600x24' python -m unittest discover -s tests -p test_computer_desktop.py -v`.
  Verifica pixel capturado, teclado, botões, arrasto/liberação, rolagem horizontal,
  zoom com posição real no X11, repaint atrasado, alvo alterado e fail-safe.
- Workflow executa suíte base em Linux/macOS, desktop Xvfb no Linux, build de
  wheel/sdist e instalação limpa. Testar no desktop real requer o extra `computer`.

Desktop local em primeiro plano, monitor principal, Linux X11 ou macOS com permissões
do sistema. Sem Windows/Wayland/múltiplos monitores/controle em segundo plano nesta
versão. O teste real executado aqui é X11; o backend macOS não foi exercitado em desktop.
O modelo recebe imagens por decisão, não vídeo contínuo em tempo real. Recortes e
comparações locais não identificam de forma confiável a aplicação nem bloqueiam
instruções maliciosas presentes na tela por si só; a instrução do agente trata tela
como dados não confiáveis. O consentimento inicial autoriza as ações seguintes; controle
de desktop não constitui sandbox nem identifica aplicações com garantia.
