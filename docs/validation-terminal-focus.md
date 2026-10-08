# Execução com o terminal sem foco

Data: 2026-10-08 UTC. Release 0.10.2, sobre a 0.10.1.

## Reprodução

O teste usa um processo real com curses em um PTY descartável. Uma chamada ao
modelo simulado aguarda liberação enquanto o usuário escreve um rascunho. O teste
envia perda de foco, deixa de consumir a saída do terminal e redimensiona a janela.
Redesenhos completos forçados tornam o acúmulo de saída reproduzível em poucos
segundos, sem esperar uma sessão longa nem acessar contas de IA.

Na 0.10.1, o ciclo continua desenhando e deixa de avançar quando a saída do PTY
acumula. O teste falha por falta de novas verificações de atividade. Isso reproduz
uma causa possível do sintoma relatado; não permite identificar qual emulador ou
política de renderização está em uso na máquina do usuário.

## Correção e verificação

- Solicitar eventos de foco e desativá-los ao sair, inclusive após exceção.
- Reconhecer CSI I/O e as teclas estendidas kxIN/kxOUT sem depender de seus números.
- Ao perder foco, continuar drenando eventos, salvando respostas e executando
  housekeeping/heartbeat. Pausar somente desenho, cursor visual e animação.
- Remover marcações de desenho pendente antes da leitura do teclado, pois curses
  pode redesenhar implicitamente a janela durante get_wch, inclusive após resize.
- Ao voltar, redesenhar integralmente; uma tecla também recupera o desenho se o
  terminal perder a notificação de retorno. Preservar rascunho e posição do cursor.

O teste de regressão confere a conclusão da resposta e pelo menos 40 novos ciclos
sem consumir o PTY: nenhum quadro ou byte adicional é produzido durante a perda
de foco. Confere também resize em segundo plano, retorno, preservação do rascunho,
recuperação por tecla e restauração do protocolo ao sair. Executa em xterm-256color
e xterm-color; a cobertura de teclado inclui os dois formatos de evento de foco.

O foco da janela é independente da seleção de chat e da autorização de computer
use. Perguntas e permissões continuam pendentes até uma resposta explícita. Em
terminais sem suporte a eventos de foco, o ciclo mantém o comportamento normal.
A correção não controla suspensão do processo imposta pelo sistema operacional.

## Resultado local

- `python3 -m unittest discover -s tests -v`: 536 testes, 530 aprovados e 6 ignorados
  por dependerem de desktop/clipboard específicos; sem falhas.
- Build de wheel/sdist, `twine check --strict` e `scripts/check_dist.py`: pacote
  0.10.2 válido, todos os 73 recursos presentes e instalação limpa conferida.
- Auditoria estática `frontend-design-premium` em modo strict: zero findings.
  A validação de interação utiliza curses/PTY reais, pois a interface não tem DOM.

Referências: [eventos de foco do xterm](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-FocusIn_FocusOut)
e [leitura e atualização implícita do ncurses](https://invisible-island.net/ncurses/man/curs_getch.3x.html).
