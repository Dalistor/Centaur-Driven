# Execução, configuração e segredos

Como o sistema roda em produção: o que o mantém de pé, de onde vem a configuração e quem tem acesso a quê. Descubra o que já está em uso antes de propor; o que só existe no servidor é pergunta ao usuário.

## Processo supervisionado

- Um supervisor reinicia o processo quando ele cai e o sobe no boot: systemd, o orquestrador de contêineres ou o próprio PaaS. `nohup`, `screen` e terminal aberto não são supervisão.
- O serviço roda com **usuário próprio sem privilégio**, não como root; escreve só onde precisa.
- **Encerramento gracioso**: ao receber SIGTERM, para de aceitar trabalho novo, conclui o que está em curso e sai dentro do prazo do supervisor. Sem isso, todo deploy derruba requisições.
- Limites explícitos de memória/CPU e política de reinício com espera, para uma falha não virar laço de reinícios.
- Tarefas agendadas e workers têm o mesmo cuidado que o serviço web: supervisão, log e alerta quando param.

Em **systemd**: unidade com `User=`, `Restart=on-failure`, `RestartSec=`, `EnvironmentFile=` fora do repositório e as proteções que o serviço tolerar (`NoNewPrivileges=yes`, `ProtectSystem=`, `PrivateTmp=yes`). Em **contêineres**: imagem-base fixada por digest ou versão exata, build em estágios, usuário não root, `.dockerignore` cobrindo `.git`, `.env` e chaves, `HEALTHCHECK` ou probe equivalente, e nada de segredo em `ARG`/`ENV` da imagem. Em **compose**, `restart: unless-stopped`, volumes nomeados para dados e nenhuma porta de banco publicada no host sem necessidade.

## Configuração por ambiente

- O mesmo artefato roda em todos os ambientes; o que muda entra por variável de ambiente ou arquivo de configuração **fora** do artefato.
- Versione um `.env.example` (ou equivalente) com todos os nomes e valores fictícios; o arquivo real nunca entra no Git.
- O serviço **valida a configuração ao iniciar** e falha com mensagem clara se faltar algo, em vez de quebrar na primeira requisição.
- Defaults seguros: depuração desligada, CORS restrito, cookies seguros, nada escutando em `0.0.0.0` que deveria estar só em loopback.

## Borda: proxy, TLS e rede

- Um proxy reverso (Nginx, Caddy, o balanceador do provedor) termina TLS e repassa ao serviço em loopback ou rede privada. Certificados com renovação automática e alerta antes do vencimento.
- Só as portas necessárias ficam abertas ao mundo (em geral 80/443 e o SSH); banco, cache e painéis administrativos ficam em rede privada ou loopback.
- SSH só por chave, sem login de root por senha. Atualizações de segurança do sistema operacional têm dono e rotina.
- Timeouts, limite de tamanho de corpo e, onde couber, limite de taxa são definidos no proxy; o padrão ilimitado raramente é o desejado.

## Health check

- **Liveness**: o processo responde. **Readiness**: está pronto para receber tráfego (dependências essenciais acessíveis, migrações aplicadas). São perguntas diferentes; o deploy e o balanceador usam a segunda.
- O endpoint é barato, não exige autenticação sensível e não expõe detalhes internos. Identificar a versão em execução (como o `centaur-release.txt` do deploy estático) permite verificar o que de fato está servindo.

## Segredos e acessos

- **Inventário por nome**: para cada segredo, onde fica guardado, quem o usa, que escopo tem e como é revogado. Nunca registre valores.
- Guardados no cofre do provedor, em secrets do GitHub atrás de Environment ou em arquivo do servidor com dono e modo restritos (600). Não em repositório, imagem, log, artefato ou histórico de conversa.
- **Um segredo por uso e por ambiente.** A chave de deploy não é a chave pessoal; a senha do banco de produção não é a de homologação; a aplicação usa um usuário de banco com o mínimo de privilégio, não o administrador.
- Prefira credencial de **curta duração** (OIDC, tokens com expiração). Para as de longa duração, defina a rotação e quem a faz.
- **Vazou, rotaciona.** Um segredo que apareceu em commit, log ou conversa está comprometido: revogue e substitua; apagar o commit não desfaz a exposição. Encontrou um durante o levantamento? Informe localização e tipo, sem reproduzir o valor.
- Quem sai do time ou do projeto perde acesso: liste onde isso precisa ser feito (repositório, servidor, provedor, painéis).

## Entregar

Arquivos de configuração do runtime versionados (unidade systemd, `Dockerfile`, compose, bloco do proxy) como **propostas para o operador aplicar**, com o comando de validação de cada um (`systemd-analyze verify`, `docker build`, `nginx -t`), mais o `.env.example` e o inventário de segredos no runbook. Nada disso é aplicado no servidor por esta skill.
