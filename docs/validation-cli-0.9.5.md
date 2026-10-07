# Validação Centaur CLI 0.9.5

Data: 2026-10-07. A nova captura mostra `codex: tempo limite de 1800 segundos`,
com aproximadamente 28% do contexto restante. Isso confirma o deadline de uma
chamada nativa; não confirma travamento, falta de contexto, rede ou esforço excessivo.

## Investigação

- O Centaur envia contexto e ferramentas em JSON a cada execução efêmera do CLI.
  O processo precisa terminar e entregar uma resposta estruturada válida antes
  de qualquer ferramenta ser executada. Não é a sessão interativa do Codex.
- A 0.9.4 perdia os diagnósticos acumulados em stdout/stderr quando atingia o prazo.
  A mesma mensagem genérica encobria situações distintas.
- `codex_output` também rejeitava qualquer evento `error`, inclusive um aviso de
  reconexão seguido de resposta válida e `turn.completed`. Regressão reproduzida
  com subprocesso Python real antes da correção e aprovada depois.
- O processador oficial JSONL distingue `error` (continua Running) de
  `turn.failed` (InitiateShutdown). O adaptador agora preserva essa distinção.
- A referência oficial documenta idle de stream de 300000ms e stream_max_retries
  padrão 5. Interrupções repetidas podem ocupar grande parte do deadline do harness;
  isso é uma hipótese compatível com a captura, não causa confirmada na máquina.

Fontes: [exec não interativo](https://developers.openai.com/codex/noninteractive/),
[configuração](https://developers.openai.com/codex/config-reference/) e
[processador oficial](https://github.com/openai/codex/blob/main/codex-rs/exec/src/event_processor_with_jsonl_output.rs).

## Correção e verificação

- Timeout mantém fase pública, contagens de bytes e categoria fixa de aviso quando
  disponível. Nunca exibe logs brutos, mensagens do provedor, credenciais, chamadas
  parciais ou análise privada. Sem evidência, a causa é explicitamente desconhecida.
- Eventos definitivos de falha encerram cedo mesmo com processo ainda aberto.
  Avisos recuperáveis permitem conclusão válida. Arquivo final não supera turn.failed.
- Prazo absoluto, cancelamento, idle opt-in, validação integral e checkpoints seguem
  ativos. Não há aumento do timeout, redução de effort ou retry automático de ações.
- 12 regressões novas: 1800s por relógio simulado; timeout de processo real com
  reconexão; silêncio sem causa comprovada; Claude/Codex com falha terminal e processo
  aberto; recuperação seguida de resposta final; arquivo final mais falha terminal;
  JSON/UTF-8 fragmentado; dados privados e eventos desconhecidos; parcial sem sucesso.
- Suíte completa: 477 casos, 471 aprovados e seis opt-in desktop/clipboard ignorados
  localmente. Compileall e git diff --check passaram. Wheel/sdist passam twine strict
  e check_dist, incluindo 68 recursos e instalação limpa.

Não há Codex CLI instalado nem sessão autenticada neste executor. Os testes usam
subprocessos reais e envelopes do protocolo, sem chamadas pagas. A causa específica
do timeout recorrente do proprietário exige o diagnóstico da execução local; não
é possível reproduzir sua conexão/conta/histórico a partir da captura. CI verifica
Linux 3.10/3.13, macOS 3.13 e desktop descartável antes da release GitHub; PyPI separado.
