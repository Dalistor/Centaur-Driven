# Revisão dos fluxos de agentes por backend

Data: 2026-10-07. Alterações locais sobre a revisão de coordenação concorrente.
Nenhum push, tag, release, deploy ou publicação PyPI foi realizado.

## Escopo e evidências

Revisados `agent.py`, `agent_runtime.py`, `subagents.py`, `terminal.py`,
`backends.py`, `native_client.py`, `openrouter.py`, `context.py`, `attachments.py`,
`vision.py`, `tools.py`, `history.py` e `sessions.py`, além dos testes correspondentes.

A matriz nova passa pelos adaptadores reais do Centaur. Codex e Claude recebem
stdin e devolvem eventos/arquivos por executáveis Python controlados, com processos,
threads e encerramento reais. OpenRouter usa transporte HTTP simulado, conservando
montagem da requisição, parser e validação do adaptador. Não substitui testes com
CLIs oficiais autenticados, modelos reais, cotas, rede externa ou desktop real.

| Caminho | OpenRouter | Codex | Claude |
| --- | --- | --- | --- |
| Principal delega filho, filho delega neto | Testado | Testado | Testado |
| Modelo próprio por executor e backend preservado | Testado | Testado | Testado |
| Escrita pelo neto e relatório ao pai/principal | Testado | Testado | Testado |
| Orientação entre ações; ação atual preservada | Testado | Testado | Testado |
| Cancelamento antes da requisição | Testado | Testado | Testado |
| Cancelamento de filho em inferência; vaga liberada | Testado | Testado | Testado |
| Compactação sem ferramentas e histórico preservado | Testado | Testado | Testado |
| Falha ao salvar relatório; reserva liberada | Testado | Testado | Testado |

Os testes existentes cobrem as demais fronteiras: recusa de escrita, perguntas e
permissões serializadas, roteamento sem trocar backend, limite de seis executores,
cancelamento de comando, mensagens após troca de chat, recuperação de histórico
sem repetir ações, compaction checkpoints, esquemas aninhados, anexos e resize PTY.

## Falhas corrigidas

1. **OpenRouter executava o início de um lote inválido.** Agora valida nomes,
   tipos, objetos aninhados, campos obrigatórios e IDs únicos antes de retornar
   qualquer chamada. JSON inválido ou ferramenta não declarada impede todo o lote.
   A validação tipada é compartilhada com os backends nativos.
2. **OpenRouter mantinha o executor bloqueado até o timeout de rede ao cancelar.**
   A espera do agente agora observa cancelamento e deadline. O POST não é repetido;
   resposta tardia é descartada. Até oito requisições canceláveis podem permanecer
   encerrando por cliente. O transporte urllib subjacente pode continuar aguardando
   a rede; cancelamento local não comprova cancelamento ou reembolso no provedor.
3. **Respostas OpenRouter truncadas podiam ser tratadas como conclusão.**
   `length`, `content_filter` e `error` são recusados antes de executar ferramentas.
   O corpo aceito é limitado a 8 MB.
4. **Blocos de protocolo de modelos com reasoning eram perdidos após ferramentas.**
   `reasoning_details` mantém a sequência recebida no replay OpenRouter; o campo
   plaintext duplicado `reasoning` não é incorporado. Esses blocos não são exibidos
   no transcript, no progresso dos agentes nem incluídos no resumo de compactação.
   Backends nativos não recebem esses blocos. O harness não gera ou expõe pensamento
   privado como resumo público.
5. **Codex aceitava arquivo de saída de um turno iniciado e não concluído.**
   A conclusão precisa corresponder ao último turno observado. Arquivo isolado sem
   eventos continua aceito por compatibilidade; falha terminal sempre é recusada.
6. **Codex/Claude aceitavam resposta vazia como final.** Sem conteúdo útil e sem
   chamadas não há conclusão. Erros de pipe limpam o processo; saída rápida acima
   do limite também é rejeitada, mesmo sem timeout intermediário. A limpeza não
   envia o mesmo encerramento duas vezes nos caminhos de cancelamento/watchdog.
7. **Effort Codex podia contrariar o catálogo conhecido.** Quando há níveis no
   cache, um nível incompatível é recusado antes de iniciar o processo. Seleção de
   subagentes já conserva somente effort/fast compatíveis com o modelo escolhido.
8. **Falhas de criação de thread/checkpoint/relatório podiam vazar reservas.**
   A reserva é liberada mesmo se a construção ou início da thread falhar, se salvar
   o checkpoint de falha também falhar, ou se o armazenamento rejeitar o relatório.
   Telemetria indisponível não deixa executor ativo indefinidamente.
9. **Pergunta do neto alterava o estado do pai.** Descendentes chamam o callback
   original da sessão, conservando a serialização do terminal, e atualizam seu
   próprio estado em vez de empilhar callbacks de todos os ancestrais.
10. **`wait_agents` esperava o próprio executor.** A espera verifica outros agentes
    ativos. Sem outro executor, retorna imediatamente.

## Fontes primárias consultadas

- [OpenRouter — Tool calling](https://openrouter.ai/docs/guides/features/tool-calling):
  formato do lote, finish reason e responsabilidade do harness pela execução.
- [OpenRouter — Reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens):
  continuidade dos blocos `reasoning_details` e sequência preservada após ferramentas.
- [Codex — Non-interactive mode](https://developers.openai.com/codex/noninteractive):
  eventos JSONL, resultado final, schema e isolamento de configuração.
- [Claude Code — CLI reference](https://code.claude.com/docs/en/cli-reference):
  execução print/stream-json, schema, safe mode e configuração de ferramentas.
- [Claude Code — Model configuration](https://code.claude.com/docs/en/model-config):
  modelos, effort, limites administrativos e diferenças entre provedores.

Não foram trocadas flags de isolamento com base em suposições sobre versões.
O código conserva verificação de disponibilidade do CLI antes de autenticar/usar.
Não há fallback automático entre OpenRouter, Codex e Claude.

## Verificação final local

- `python3 -m unittest discover -s tests -v`: 534 casos, 528 aprovados e seis testes
  opcionais de desktop/clipboard macOS ignorados.
- `tests/test_backend_flows.py`: 21 casos novos, com subcasos nos três backends.
- Compileall e `git diff --check`.
- Build local de wheel/sdist, `twine check --strict` e `scripts/check_dist.py`:
  72 recursos e instalação limpa fora da árvore do projeto.

## Limites que permanecem explícitos

Modelos/cotas/latência reais exigem conta autenticada e não foram medidos. O
catálogo Codex depende do cache do CLI; Claude oferece aliases, que podem resolver
modelos diferentes conforme provedor/política. Janela desconhecida não é inventada:
a compactação automática depende de janela conhecida ou `CENTAUR_CONTEXT_WINDOW`.
Um comando tem seu próprio limite de 60s; inferência e compactação têm deadlines
independentes. Atividade de subagentes não renova o timeout de uma inferência presa.
Mensagens de agentes em memória não sobrevivem ao encerramento do processo; seus
históricos sobrevivem, e a fila de orientação do usuário é persistente. Reiniciar
não repete automaticamente ferramentas nem ressuscita threads de executores.
