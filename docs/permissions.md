# Política de permissões

## Computer use e interrupção

Computer use tem autorização própria em todos os modos, inclusive `never`:
`computer_start` pede captura do monitor principal inteiro por até 120s e explica
o envio de quadros ao modelo. Cada `computer_action` pede confirmação de ação,
coordenadas, texto/teclas e clique para focar o alvo. Essa autorização não fica
no histórico, não é herdada por subagentes e não permite executar código arbitrário.
Texto/páginas da tela são contexto não confiável. Ctrl+C bloqueia novas ações e para
a captura; fail-safe permanece ativo. Reiniciar exige outra autorização. Quadros ficam
fora dos registros; Codex usa anexos temporários com modo 0600 removidos ao fim da chamada.

Todos os turnos aceitam Ctrl+C. Comandos locais e CLIs nativos são encerrados; chamadas
OpenRouter podem aguardar o timeout da rede, sem aplicar a resposta após cancelamento.
Perguntas `ask_user` são decisões de conversa, independentes da aprovação de ações.

## Arquivos e comandos

Fonte: solicitação do proprietário em 2026-10-06, com escolha explícita de “Edições e consultas”
para o modo intermediário, refinada a pedido do usuário após confirmação desnecessária do
validador incluído. Implementação canônica: `centaur_cli/permissions.py` e `ProjectTools`.

- `ask`: leituras livres; toda gravação e comando precisam de aprovação.
- `auto`: edições comuns em arquivos do projeto e consultas da lista permitida executam sem
  confirmação. Opções/sintaxe desconhecidas, testes, builds, exclusões, rede, instalações e Git
  com alteração de estado exigem aprovação. Edições em caminhos ocultos, links, arquivos com
  bit executável, hardlinks e pastas de credenciais exigem revisão. Exceção documental:
  `.md`, `.json` e `.html` em `.centaur/specs`, `implements`, `contracts`, `modules` e `system`.
  Configuração, workspace, chats e skills continuam exigindo aprovação. Caminhos absolutos
  dentro do projeto seguem a mesma classificação dos relativos.
- `never`: ferramentas de gravação e comando executam sem pedir aprovação. Comandos continuam
  com as permissões do usuário; não há promessa de sandbox. Ferramentas de arquivo mantêm
  limites de caminho e credenciais, redaction e timeouts.

A escolha explícita do usuário vale para coordenador e subagentes. Modelos e classificações
fornecidas pelo modelo não ampliam esse modo. `--approval-mode` prevalece sobre
`CENTAUR_APPROVAL_MODE`, que prevalece sobre `approval_mode` em `.centaur/config.json`.
Arquivos antigos usam ask. Retomar chats não restaura o modo gravado no histórico.

Trocar somente permissões mantém a conversa. Alterações são aplicadas depois de salvar;
falha/cancelamento preservam o modo atual. O seletor mostra descrição e revisão antes do
commit, e o cabeçalho apresenta o modo ativo. Durante um turno, as ferramentas usam o modo
com que foram criadas; configuração fica indisponível enquanto o turno estiver ativo.

Consultas automáticas usam argumentos diretos e executáveis do sistema, sem shell ou PATH
customizado. Git desativa pager, fsmonitor, assinatura, ext-diff e textconv; rg ignora configs.
Diretórios de instalação do sistema incluem `/usr/local/bin` e `/opt/homebrew/bin`;
aliases do diretório raiz do projeto são normalizados sem ignorar links internos.
A lista é conservadora e não equivale a análise universal da segurança de um comando.

O modo auto aceita leitura por intervalos com `sed -n`, `head -n` e `tail -n`, globs de `rg`
e consultas em `.centaur`. A execução do `validate-lifecycle.py` incluído no catálogo é
automática apenas para a pasta aberta, com opções `--ready`/`--complete` verificadas.
Python ignora PYTHONPATH e hooks de site; PATH usa executáveis do sistema e Git recebe
configuração que desativa fsmonitor. Scripts de mesmo nome no projeto não são confiáveis;
outros scripts Python, testes e builds continuam exigindo aprovação.
