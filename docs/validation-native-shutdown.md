# Espera no encerramento dos backends nativos

Data: 2026-10-08 UTC. Correção preparada para a release 0.10.1, sobre a 0.10.0.

## O que a captura permite concluir

A captura informa que o principal aguarda Codex há aproximadamente 22 minutos sem
nova saída. O último comando já tem resultado salvo. Ela não exibe o último evento
nativo nem stdout/stderr, portanto não confirma se a chamada aguarda a rede, a
resposta do modelo ou o encerramento do processo. Não há CLI Codex autenticado neste
ambiente para reproduzir a requisição exata do usuário.

## Bloqueios reproduzidos

Um processo Python real, usado como CLI controlado, entrega a resposta e cria um
descendente em outra sessão que herda stdout/stderr. O processo principal termina,
mas `communicate()` continua aguardando EOF do descendente. Antes da correção,
Codex e Claude descartavam respostas completas por timeout neste cenário.

Outro cenário entrega resposta estruturada completa e evento de conclusão, mas
mantém o processo principal aberto. Antes, o adaptador também aguardava o timeout
inteiro, mesmo com o resultado pronto. Um evento de conclusão sem resposta válida
continua insuficiente para executar ferramentas.

## Correção

- Consultar o estado real do processo durante a leitura dos canais. Quando o CLI
  termina, drenar/fechar os canais com prazo limitado, conferir código de saída e
  validar a resposta final. EOF de descendentes não determina o fim da inferência.
- Para processo ainda aberto, aceitar somente evento terminal de sucesso e resposta
  integral validada após dois segundos para o encerramento natural. A limpeza atua
  no grupo de processos dessa chamada. Não há replay de comandos, nova chamada ao
  modelo, alteração do evento de cancelamento compartilhado ou encerramento dos
  outros agentes do Centaur.
- Continuar rejeitando JSON parcial, turno iniciado sem conclusão, lote inválido,
  falha terminal e código de saída não zero observado antes da limpeza.
- Exibir o último tipo de evento público também após 30 segundos de silêncio.
  Nenhum texto de reasoning, log bruto ou credencial é exibido.

## Validação e limites

Uma regressão parametrizada cobre Codex e Claude: principal encerrado com canais
herdados; principal aberto após resultado completo; principal encerrado com resultado
incompleto. Os descendentes descartáveis são encerrados pelo próprio teste. A suíte completa passou: 535 testes, com 6 ignorados. A suíte
existente mantém cobertura de cancelamento, timeout absoluto, compactação, mensagens
durante execução, árvore de agentes e rejeição de chamadas inválidas.

O timeout total de inferência continua 30 minutos. Silêncio legítimo não é tratado
como prova de travamento. Nenhuma configuração de rede ou limite de retry do Codex
foi alterado. Se a máquina do usuário estiver sem evento terminal, estes ajustes
não afirmam corrigir a causa da espera; o último evento e o diagnóstico persistido
do timeout ainda são necessários para localizar o problema.

Referências oficiais: [eventos do modo não interativo](https://developers.openai.com/codex/noninteractive/)
e [configuração de conexão/retries](https://developers.openai.com/codex/config-reference/).
