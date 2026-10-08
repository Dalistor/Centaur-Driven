# Recuperação de conexão e esperas do Codex

Data: 2026-10-08 UTC. Release 0.10.4, base 0.10.3.

## Sintoma e alcance da investigação

O usuário confirmou Codex e a fase `Aguardando modelo`. Não forneceu o último
evento nativo nem um diagnóstico de erro nesta ocorrência. O ambiente de validação
não tem Codex autenticado; não é possível afirmar a causa exata da chamada em sua
máquina. A investigação revisou a passagem do prompt por stdin, leitura dos dois
canais, eventos terminais, encerramento, cancelamento, checkpoints e entrega ao chat.
As proteções de encerramento/EOF da 0.10.1 e de foco do terminal da 0.10.2 permanecem.

Um caminho ainda permitia longa espera com evidência de falha: erros recuperáveis
de conexão não tinham prazo próprio. `error` não deve encerrar imediatamente uma
chamada que pode recuperar, mas uma sequência de reconexões podia consumir o prazo
inteiro de 30 minutos. A documentação oficial descreve cinco retries de stream e
timeout de inatividade de 300000ms. Isso torna uma espera longa plausível; não prova
que a ocorrência específica do usuário tinha essa origem.

## Reprodução e correção

Um subprocesso Python real recebe o prompt completo, escreve erros JSONL de conexão
repetidamente e permanece aberto. Comparando o código de HEAD 0.10.3 com a correção,
sob prazo total de 2s e recuperação de 0.3s:

| Código | Tempo observado | Resultado |
| --- | ---: | --- |
| 0.10.3 | 2.00s | Timeout total, apesar dos erros de conexão |
| Correção | 0.41s | Erro específico de recuperação de conexão |

Os tempos foram reduzidos para uma reprodução local rápida, sem inferência paga.
Em produção, o prazo total continua 1800s e a recuperação é 180s. O limite começa
somente após um diagnóstico conhecido de rede em evento de erro ou linha de stderr.
Avisos seguintes, bytes adicionais, eventos de início e heartbeat não o renovam.
Saída de reasoning/mensagem do Codex ou mensagem do Claude prova retomada do stream
e encerra a recuperação, sem publicar o conteúdo privado. Uma nova falha após essa
retomada abre outro episódio, limitado pelo prazo absoluto original da chamada.

O chat e cartões mostram `Reconectando` e duração do episódio, em vez de sugerir que
o modelo está apenas trabalhando. Metadados persistidos incluem apenas fase,
contagem de bytes, categoria fixa e contadores; não incluem logs brutos, texto de
reasoning, prompts, credenciais ou argumentos de ferramentas.

Timeout de recuperação encerra apenas o grupo de processos daquela inferência.
Mantém checkpoints, não aplica a resposta pendente e não repete nenhuma operação.
Compactação recebe `RequestTimeout`, preservando seu tratamento existente. Para
configuração explícita, `CENTAUR_NATIVE_RECOVERY_TIMEOUT` aceita 30–3600s ou zero;
zero desativa apenas a recuperação, mantendo cancelamento e prazo total.

## Verificação e limites

A suíte também revelou uma corrida no reinício de computer use da mesma sessão:
`claim()` adquiria a posse antes da instalação atômica do novo backend/token. Nesse
intervalo, o `finally` do capturador antigo ainda podia liberar a posse pelo mesmo
objeto de sessão. A captura nova então falhava como parada/expirada. A aquisição da
posse agora ocorre sob o lock que instala backend e token. O teste existente de
troca de owner foi ampliado para forçar o encerramento do worker antigo dentro da
fábrica do backend, tornando a corrida determinística. Essa falha não comprova a
causa da espera no modelo relatada pelo usuário.

Uma regressão vital foi adicionada à suíte existente de diagnóstico. Processos reais
cobrem reconexões contínuas em stdout e stderr, chamadas comuns e de resumo, mensagem
pública e ausência de dados privados no erro. Testes existentes foram ampliados para
recuperação seguida de resposta válida, saída real seguida de silêncio legítimo,
episódios distintos, transporte fragmentado e validação/desativação da configuração.
A suíte de watchdog mantém cobertura de prazo absoluto, silêncio legítimo superior
a cinco minutos, subagentes, cancelamento e descendentes com canais herdados.

Validação local: 537 testes, 531 aprovados e 6 skips de integrações opt-in/plataforma,
em 72.756s. Wheel e sdist passaram no Twine estrito e na conferência das 73 resources
e instalação limpa. Foram reutilizados testes existentes e adicionada somente uma
regressão vital para o limite de recuperação, sem nova bateria por método.

Esta correção limita uma recuperação de rede prolongada; não repara rede/proxy do
usuário nem determina o estado remoto do modelo. Um processo sem erro de rede e sem
evento terminal pode continuar esperando até seu prazo total. Nesse caso, o último
evento e diagnóstico do chat continuam necessários para localizar a causa. Não foi
trocado o transporte do Codex nem alterada sua configuração interna de retries.

Referências: [eventos do modo não interativo](https://developers.openai.com/codex/noninteractive/)
e [configuração de retries/stream](https://developers.openai.com/codex/config-reference/).
