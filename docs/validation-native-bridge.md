# Protocolo do harness e diagnóstico de espera

Data: 2026-10-08 UTC. Release 0.10.5, base 0.10.4.

O usuário confirmou a versão 0.10.4, o backend Codex e a fase `Aguardando modelo`.
A captura disponível mostra operações anteriores concluídas e, depois, cancelamento
manual. Ela não registra o evento nativo da chamada durante a espera. A investigação
não usou sua conta nem inferência paga; a causa remota dessa ocorrência permanece
sem confirmação. O prazo total continua 30 minutos e não há replay automático.

## Instruções base

O bridge anterior inseria suas instruções no stdin, junto com o JSON da conversa e
ferramentas. Isso não substituía as instruções base de executor do Codex. Em uma
inspeção local do pedido HTTP real do CLI, o campo `instructions` ainda continha
cerca de 17 mil caracteres das instruções padrão, embora ferramentas de execução
nativas estivessem desabilitadas. É uma incompatibilidade de papéis: o Centaur
precisa da próxima etapa estruturada para executar as ferramentas em seu harness.
Isso constitui uma hipótese de comportamento indevido, não prova de latência do
modelo ou da causa do travamento relatado.

Agora `model_instructions_file` aponta para um arquivo temporário confiável com as
instruções do bridge. O arquivo não é obtido do projeto nem de saídas de ferramentas.
O pedido continua contendo a conversa ativa, o schema tipado e as ferramentas
permitidas. A resposta ainda precisa passar pela validação antes da execução.

O teste `test_codex_protocol.py` usa o executável oficial **0.161.0**, um diretório
de configuração/autenticação novo e um provedor Responses em **127.0.0.1**, sem
autenticação e com resposta SSE sintética. O HTTP real confirmou que `instructions`
é exatamente o bridge. Houve uma chamada ao provedor, retorno tipado de `read_file`
e captura de uso; nenhuma ferramenta Centaur foi executada pela inferência. Esse
teste agora é um gate de publicação, com versão do executável fixada. Não mede
tempo de geração, qualidade, login ou rede da máquina do usuário.

## Evento terminal sem LF

Uma resposta pode terminar com um envelope JSON completo sem quebra de linha final.
Antes, o observador mantinha esse envelope no buffer e não liberava a espera se o
processo continuasse aberto. Agora somente envelopes terminais totalmente decodificados
qualificam; JSON parcial continua insuficiente. A conclusão ainda exige uma resposta
final válida e não pode sobrepor um evento de falha.

Uma reprodução com subprocesso Python real, resposta pública sintética, `turn.completed`
sem LF, processo permanecendo aberto e prazo reduzido de 3s compara as versões:

| Código | Resultado |
| --- | --- |
| 0.10.4 | 3.004s: prazo total esgotado, apesar da resposta completa |
| Correção | 2.112s: resposta validada após a tolerância de encerramento de 2s |

O teste existente de encerramento foi ampliado com esse caso para Codex e Claude.
Os limites de limpeza continuam limitados, inclusive com descendente escapado
segurando os canais. A asserção de tempo inclui essa limpeza; o retorno bem-sucedido
da resposta é o requisito principal, sem relaxar a rejeição de respostas parciais.

## Diagnóstico preservado

`$diagnose` e `/diagnose` consultam o chat atual durante a execução. Não entram no
inbox do agente, não chamam modelos nem modificam o histórico. Reexecute para atualizar;
`$diagnose clear` fecha. `centaur diagnose [pasta] --json` consulta os mesmos registros
sem abrir a TUI ou configurar autenticação. Os metadados permanecem depois de Ctrl+C;
a próxima fase substitui os dados anteriores.

O relatório usa uma lista de campos permitidos: versão, ID, estado, fase fixa,
último evento público, backend, contagens de bytes, PID, tempo/prazo e categoria
fixa de aviso. Ignora arquivos com links simbólicos, IDs inválidos, registros maiores
que 4096 caracteres e conteúdo desconhecido. Não lê mensagens, prompts, argumentos,
logs ou credenciais. A existência de um PID só é consultada num registro recente e
em execução, e não prova progresso remoto. Eventos mudam o diagnóstico imediatamente;
durante silêncio os contadores de tempo atualizam a cada cinco segundos, sem
renovar o prazo absoluto nem fingir nova saída do CLI.

Regressões existentes verificam comando concluído seguido de inferência silenciosa,
cancelamento sem reexecutar o comando e conservação do último evento. Um teste vital
verifica diagnóstico durante o turno, isolamento da fila/histórico, campos privados
injetados e rejeição de links simbólicos. Os demais gates de prazo, recuperação,
subagentes, compactação e JSON parcial permanecem.

Referências oficiais: [model_instructions_file](https://learn.chatgpt.com/docs/config-file/config-reference),
[modo não interativo](https://developers.openai.com/codex/noninteractive/)
e [CLI oficial](https://developers.openai.com/codex/cli/).

Validação local: **539 testes**, **533 aprovados**, **6 skips** de plataforma, em
84.815s, incluindo o protocolo com CLI real. Compileall, Twine estrito e conferência
do wheel/sdist passaram; os pacotes preservam as 74 resources de skills.
