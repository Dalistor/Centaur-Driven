# Coordenação concorrente e computer use — alterações locais

Data: 2026-10-07. Base: commit 8cb8d5c27c2ffa2e3787621125ffe4f5cf03409c,
release publicada 0.9.6. Estas alterações ainda não foram publicadas. Não há push,
tag, release, deploy, atualização PyPI ou instalação na máquina do proprietário.

## Decisões de execução

O limite solicitado foi interpretado como **seis executores simultâneos em toda a
árvore por chat principal**, incluindo filhos e netos. Cada conclusão libera vaga;
não é um limite de seis tarefas durante toda a conversa. Cada chat principal tem
seu próprio grupo. Uma instância por conversa continua necessária: o grupo em
memória não coordena dois processos editando simultaneamente o mesmo chat.

`AgentGroup` controla reserva atômica, comunicação e relatórios. O chat usa delegação
em segundo plano; a API Python conserva modo síncrono para compatibilidade.
`agent_status` expõe somente comentários/ações públicos, fase, estado, modelo,
effort, velocidade e tempo sem saída. `send_agent_message` entrega orientação entre
etapas; `wait_agents` espera até 30s sem consultar o modelo. Dados/relatórios de
outros agentes não ampliam permissões. Descendentes enviam relatório ao pai e à raiz;
um executor aguarda seus filhos antes de consolidar a própria resposta.

Enter durante execução salva orientação na fila privada `.centaur/inbox/<chat>.json`.
Somente o worker modifica a conversa: termina a etapa atual, registra resultados de
não execução para chamadas restantes do lote antigo e incorpora mensagens novas.
IDs consumidos evitam duplicar mensagens após interrupção entre salvar e confirmar
entrega. Falhas preservam rascunho/anexos; mensagens enfileiradas são recuperadas na
próxima execução. Não interrompe instantaneamente a inferência do provedor.

Concluir resposta do principal não cancela os filhos. Relatório posterior retoma
somente a sessão de origem, mesmo que outro chat esteja aberto. Ctrl+C cancela toda
a árvore deste principal; perguntas/aprovações usam um lock por sessão para não
sobrescrever uma resposta pendente. Execução ainda compartilha arquivos: posse e
dependências precisam ser definidas no contrato, sem isolamento automático por
worktree. Histórico/limpeza verificam descendentes e protegem todos os ancestrais
ativos ou com mensagens pendentes.

## Pesquisa de computer use

Fontes primárias consultadas em 2026-10-07:

- [OpenAI — Computer use](https://developers.openai.com/api/docs/guides/tools-computer-use):
  manter ambiente entre chamadas, combinar grupos curtos de ações, retornar captura
  para conferir resultado e mapear coordenadas quando a imagem é redimensionada.
  A documentação aceita ferramentas próprias; o Centaur continua nesse caminho.
- [Anthropic — Computer use tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool):
  respeitar dimensões da imagem recebida, controlar quantidade de capturas no contexto
  e parar o restante de um lote quando uma ação falha.
- [Anthropic — Tool combinations](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-combinations):
  ferramentas específicas são preferíveis quando resolvem a tarefa; o desktop geral
  exige mais observações. Não foi acrescentado um navegador ou acesso a sessões nesta mudança.

Aplicação no Centaur:

1. Enviar somente o quadro atual por decisão. Captura local/buffer seguem 2fps/três
   quadros em memória, sem imagens no histórico. O teste com três telas diferentes
   confirma um único quadro enviado, em vez de três; não mede latência de rede/modelo.
2. `computer_batch` permite até quatro passos de edição no mesmo alvo: foco único,
   seleção, texto e Enter/Tab apenas ao final. Navegação entre alvos continua exigindo
   nova observação. Todo lote é validado antes de qualquer input; referências são
   consumidas antes da execução, e falha parcial não permite repetir o lote.
3. PNG com compressão level=1 reduz trabalho local de codificação, podendo aumentar
   bytes da imagem. Intervalo ASCII passa de 10ms para 1ms por caractere; cancelamento
   continua entre blocos de até 50 caracteres. Não há benchmark end-to-end autenticado.
4. Schema estrito trata campos opcionais nulos também dentro de objetos/listas,
   permitindo que Codex/Claude retornem passos de lote tipados sem falha de integração.
5. Consentimento persistente do chat, pausa por foco/menu, revogação, alvo/idade/
   resolução, fail-safe e exclusividade do desktop continuam nos mesmos componentes.
   Subagentes não herdam acesso ao computador.

`$attach`/`$screenshot` saem do autocomplete e deixam de ser comandos de preparação.
Colagem/arrasto continuam no compositor. Ctrl+S solicita captura única após 3s,
com cancelamento antes da captura; anexar não concede controle do computador.

## Verificação local

- `python3 -m unittest discover -s tests -v`: 513 casos; 507 aprovados e seis opt-in
  desktop/macOS clipboard ignorados neste ambiente.
- 12 testes novos de coordenação: limite concorrente, recursão/router, orientação
  entre ferramentas, continuidade de executor, comunicação/progresso sem reasoning,
  recuperação da fila, duas permissões serializadas, comandos removidos, proteção
  de ancestral, espera por neto e retomada em chat diferente e resumo de status limitado com consulta por ID.
- Cinco testes novos de computer use: foco único/ordem, validação antes de input,
  referência única, falha parcial sem replay e schema tipado com opcionais nulos.
- PTY real: orientação multilinha durante inferência, fila visível e resize 40×12,
  em cores, NO_COLOR e movimento reduzido. Os testes anteriores de paste/compactação/
  retomada e árvore continuam presentes.
- Compileall, git diff --check, Premium audit strict e DESIGN.md lint.
- Wheel/sdist locais, twine strict e check_dist verificam 71 recursos e instalação limpa.

Os testes de inferência usam respostas controladas e threads/subprocessos reais, sem
conta de modelo, chamadas pagas ou desktop do usuário. Xvfb e extras de computer use
não estão instalados neste executor; o desktop real e clipboard macOS permanecem
opt-in. CI remoto não foi executado porque push está suspenso por instrução do proprietário.

## Consistência visual

| Contrato | Evidência | Decisão |
| --- | --- | --- |
| Navy e cores por papel | Palette e geometria compartilhadas preservadas | Sem novos tokens |
| Compositor durante trabalho | Enter orienta; fila aparece com rótulo textual | Extensão solicitada do compositor |
| Perguntas e permissões | Mesmos seletores, serializados por sessão | Preservar foco/resposta pendente |
| Anexos | Colagem/arrasto/Ctrl+S na mesma superfície | Remover comandos auxiliares solicitados |
