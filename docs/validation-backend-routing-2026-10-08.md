# Revisão de roteamento e sessões — 2026-10-08

Base: `476b7217047f65b97a06315818da302cb5ad917e`, versão publicada 0.10.5.
Correções locais na branch `fix/backend-session-routing`; sem alterar a versão,
enviar commits, criar release ou publicar pacote.

## Resultado da revisão

O roteamento usa o backend explicitamente escolhido. OpenRouter delega por padrão
com `openrouter/auto`, faixa de custo limitada e `session_id` próprio por executor.
Codex e Claude expõem os modelos do backend em `delegate_task`; a IA coordenadora
escolhe um deles por task. O principal conserva seu modelo. Há até seis executores
ativos por árvore, incluindo netos; o cancelamento é compartilhado dentro dessa
árvore, e separado entre chats.

A seleção de modelos, criação de executores, relatórios e cancelamento já tinham
proteção. As falhas reproduzidas nesta revisão estavam nas transições de chats e
configuração, que podiam deixar a seleção exibida e a seleção executada diferentes.

## Falhas reproduzidas e corrigidas

1. **Configuração antiga ao voltar ao chat.** Depois de um turno, `$config` atualizava
   o chat e o cliente da UI, mas o contexto guardado ainda apontava para o worker
   anterior. Sair e voltar restaurava cliente, effort, velocidade e permissões
   antigos. A seleção agora tem um novo snapshot; o worker anterior permanece intacto.
2. **Sessões sem turno não conservavam sua conexão.** A criação de um chat e a troca
   de backend não guardavam a seleção de sessões ociosas. Ao voltar, podia haver
   recusa por backend ou mistura com a seleção atual. A navegação conserva também
   essas sessões; mudar backend continua criando outro chat.
3. **Retomada e créditos inconsistentes.** Um histórico compatível podia enviar
   seu modelo, mas manter o modelo principal, effort e velocidade do chat anterior
   no terminal e nos chats novos. A retomada sincroniza esses campos. Mudar de
   cliente limpa créditos/cotas, e respostas atrasadas do cliente antigo são
   descartadas. Permissões persistidas no histórico não concedem acesso: a seleção
   da abertura permanece autoritativa após reiniciar o CLI.
4. **Contexto lembrado confundido com posse do runtime.** O menu dispensava a
   verificação de execução externa quando havia snapshot local. Agora verifica o
   owner do registro vivo antes de permitir abrir uma sessão em outro processo.
   Isso preserva o bloqueio de navegação existente; não cria um lock transacional
   para todas as gravações entre processos.

## Matriz de validação

| Caminho | OpenRouter | Codex | Claude |
| --- | --- | --- | --- |
| Principal escolhe filho; filho escolhe neto; escrita e relatórios | HTTP controlado | Processos controlados | Processos controlados |
| Modelo solicitado chega ao transporte e não altera o principal | Passou | Passou | Passou |
| Effort/Fast incompatíveis no filho usam default/standard | Passou | Passou | Passou |
| Alterar modelo, sair, voltar e delegar com o cliente escolhido | Passou | Passou | Passou |
| Inferência em primeiro chat enquanto outro executa filhos/netos | Passou | Passou | Passou |
| Cancelar primeiro chat conserva segundo chat e seu cliente | Passou | Passou | Passou |
| Retomar histórico e criar novo chat com modelo/effort/velocidade coerentes | Passou | Passou | Passou |
| Histórico não concede permissões da sessão anterior | Passou | Passou | Passou |

Os testes usam os adaptadores do Centaur sem substituir `run_turn` nos cenários de
integração. OpenRouter conserva montagem, validação e parser com transporte HTTP
controlado. Codex/Claude usam executáveis Python descartáveis com stdin, processos,
threads, arquivos de saída e cancelamento reais. Catálogos/capacidades desses
cenários são controlados, portanto não comprovam disponibilidade de modelos reais.

## Verificações

- Regressões novas falharam antes da correção nos três backends.
- `test_config`, `test_sessions`, `test_native_usage_speed` e
  `test_agent_coordination`: 49 testes passaram após a correção inicial.
- `test_backend_flows`: cadeia recursiva, troca de modelos, conversas simultâneas,
  cancelamento, protocolo, compactação e falhas de armazenamento.
- Codex oficial **0.161.0**, com servidor Responses local isolado e sem autenticação:
  `test_codex_protocol` passou; instruções do harness, resposta tipada e isolamento
  de execução foram conferidos.
- Suíte completa, compileall, `git diff --check`, auditoria estática premium estrita
  e wheel/sdist com instalação limpa: resultados finais registrados abaixo.

Resultado final: `CENTAUR_TEST_CODEX_BINARY=<codex-0.161.0> python3 -m unittest
discover -s tests -v` executou **544 testes em 84,621 s: 538 aprovados e seis
integrações opcionais de desktop/clipboard ignoradas**. Os casos com curses/PTY
reais, resize, foco em segundo plano, menu/preview de agentes e mensagens durante
inferência passaram. O teste com Codex oficial está incluído nessa execução.

`compileall` e `git diff --check` passaram. Auditoria premium estrita: zero
findings. `build --no-isolation`, `twine check --strict` e `scripts/check_dist.py`
validaram wheel/sdist, todos os 74 recursos e instalação limpa fora da árvore do
projeto. Pacotes gerados são somente artefatos locais de validação; não são uma
nova publicação da versão 0.10.5.

## Limites

Não foram feitas inferências pagas ou autenticadas em nenhum backend. Conta,
assinatura, cotas, modelos disponíveis, latência e comportamento real de roteamento
precisam de validação no ambiente do usuário. Claude oficial não está instalado
neste ambiente; seu adaptador foi testado com processos controlados e conferido
contra a documentação. Os testes de desktop/clipboard opcionais continuam separados.

Codex depende do cache de modelos do CLI; Claude usa aliases que podem resolver
modelos diferentes conforme conta, provedor e política. O harness conserva a seleção
solicitada e não inventa o modelo efetivo quando o CLI não o informa. OpenRouter
preserva separadamente o modelo solicitado e o retornado pela API.

Snapshots, rascunhos e threads de execução são locais ao processo. Ao reiniciar,
históricos são recuperáveis, mas executores antigos não são reiniciados nem ações
repetidas automaticamente. Chats compartilham os arquivos da pasta do projeto.

## Referências primárias conferidas

- [OpenRouter Auto Router](https://openrouter.ai/docs/guides/routing/routers/auto-router):
  plugin por slug, `cost_tier`, `session_id` e modelo efetivo da resposta.
- [Codex não interativo](https://developers.openai.com/codex/noninteractive):
  execução efêmera, JSONL e saída estruturada.
- [Claude CLI](https://code.claude.com/docs/en/cli-reference) e
  [modelos/effort](https://code.claude.com/docs/en/model-config): seleção por flags,
  isolamento, resultado estruturado e diferenças de capacidade entre modelos.
