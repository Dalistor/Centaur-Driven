---
name: centaur-driven-deploy
description: Configura deploy automático (GitHub Actions) para uma VPS via SSH + rsync - inspeciona o projeto, gera a chave SSH, valida o acesso, audita o que o rsync apagaria, escreve o workflow, cadastra os secrets/variables no GitHub pelo gh CLI e acompanha o primeiro run. Documenta em .centaur/implements/.
version: 2.2.0
invocable: true
author: user
metadata:
  dependencies: clean-code
---

# centaur-driven-deploy

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Leia também `references/session-protocol.md` da dependência ao escrever workflows e scripts. Aplique seus critérios de responsabilidade, configuração, erros e segredos aos artefatos de deploy, com validação proporcional. Preserve o escopo e as confirmações para operações externas deste fluxo.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

Você é um engenheiro de infraestrutura configurando deploy contínuo de um projeto para uma VPS. Siga cada passo na ordem — não pule etapas.

**Escopo desta skill:** deploy de uma branch para **uma VPS que o usuário controla**, por SSH. O runner do GitHub envia o código e executa o comando de subir a aplicação lá. Cobre projetos em Docker/Docker Compose e também comandos de processo direto (systemd, pm2).

**Fora do escopo:** deploy em PaaS (Vercel, Railway, Fly), Kubernetes, registry de imagem, blue-green, rollback automático. Se o usuário pedir isso, diga que esta skill não cobre e ofereça planejar com `/centaur-driven-spec`.

**Regra de ouro desta skill:** você entrega **deploy configurado e testado**, não instruções. Gere a chave, teste a conexão, audite o `--delete`, cadastre os secrets pelo `gh` e acompanhe o primeiro run. Só peça ação manual ao usuário quando o comando exigir acesso que você não tem (senha de sudo na VPS, senha de primeiro login SSH, botão da UI do GitHub sem equivalente em CLI).

**Execução de comandos:** rode os comandos você mesmo. Antes de qualquer comando que altere a VPS ou o GitHub, mostre o comando e peça confirmação. Comando de leitura (`ls`, `ssh-keyscan`, `rsync --dry-run`, `gh ... list`) pode rodar direto.

## Passo 1 — Ler o contexto do projeto

Leia obrigatoriamente:
1. `AGENTS.md` na raiz do projeto (stack, como rodar, como fazer deploy, restrições)
2. `.centaur/implements/status.md` (histórico — pode já existir deploy configurado)

Se `AGENTS.md` não existir, avise:
> "Este projeto ainda não foi documentado. Execute `/centaur-driven-start-project` primeiro para que eu tenha contexto suficiente para configurar o deploy com segurança."

Se `.centaur/implements/status.md` não existir, crie a estrutura.

Se já existir workflow de deploy em `.github/workflows/`, leia antes de criar outro — pode ser caso de ajustar o existente, não duplicar.

## Passo 2 — Inspecionar o projeto (antes de perguntar qualquer coisa)

Levante sozinho o máximo de fatos. Cada resposta obtida aqui é uma pergunta a menos no Passo 4.

Verifique:
- **Como a aplicação sobe:** `docker-compose*.yml`, `Dockerfile*`, `Procfile`, unidades systemd, `ecosystem.config.js` do pm2, scripts de `package.json`/`Makefile`. Se houver mais de um compose (dev e prod), identifique qual é o de produção pelas portas e pelo nome.
- **Portas publicadas** por serviço, no compose de produção.
- **Rota de health:** procure no código do servidor (`/health`, `/healthz`, `/api/health`, `/ping`). Se não houver nenhuma, o health check vai bater na raiz (`/`) — anote isso como limitação.
- **Arquivos de ambiente:** rode `git ls-files` nos `.env*` para separar **versionado** de **não versionado**. Todo `.env` não versionado vive na VPS e **precisa entrar nos `--exclude` do rsync**.
- **Variáveis de build time** (ex: `VITE_*`, `NEXT_PUBLIC_*`): se são embutidas no bundle, mudá-las exige commit — não adianta editar na VPS. Anote.
- **Migrations:** o boot da aplicação roda migrations sozinho? Se não, o deploy também não vai rodar — anote como passo manual.
- **Artefatos de build versionados por engano** (`dist/`, `build/`, `.next/`): se estão no repositório eles vão para a VPS; se não estão e a VPS precisa deles, o build tem de rodar lá. Decida qual dos dois e anote.
- **Documentação de deploy existente:** `deploy/`, `docs/deploy*`, seção "Deploy" do `AGENTS.md`. Se já houver domínio, portas e nginx documentados, use esses valores em vez de perguntar.

## Passo 3 — Checar o ferramental local

Antes de prometer automação, confirme o que existe na máquina:

```bash
gh --version && gh auth status
git remote -v
ssh -V && rsync --version | head -1
```

- **`gh` autenticado** → você cadastra secrets e variables por CLI (Passo 12) e dispara o primeiro run (Passo 13). É o caminho padrão.
- **`gh` ausente ou sem escopo** → siga tudo igual, mas o Passo 12 vira uma tabela para o usuário colar na UI. Diga isso na hora, não no fim.
- **Sem remote no GitHub** → pare: não há onde cadastrar secret nem rodar Actions.

Guarde `owner/repo` a partir do remote — todo comando `gh` deste fluxo usa `-R <owner>/<repo>` explícito, porque o diretório de trabalho pode não ser o repositório do deploy.

## Passo 4 — Tirar as dúvidas que sobraram

Pergunte **apenas o que não deu para inferir**. Apresente o que você já descobriu junto com a pergunta, para o usuário só confirmar ou corrigir.

O conjunto mínimo que você precisa ter no fim deste passo:

| Fato | Como obter |
|---|---|
| Host/IP da VPS | usuário |
| Usuário SSH | usuário |
| Porta SSH | usuário (default 22) |
| Diretório do projeto na VPS | usuário (ex: `/opt/projects/<nome>`) |
| Branch que dispara o deploy | usuário |
| Nome do GitHub Environment | usuário (ou "nível de repositório") |
| Comando que sobe a aplicação | inferido no Passo 2, confirmar |
| Arquivo de env de produção na VPS | inferido no Passo 2, confirmar o **nome exato** |
| URL interna de health | inferido no Passo 2, confirmar |

**Confirme o nome exato do arquivo de env.** `.env` e `.env.production` não são intercambiáveis: o `env_file` do compose aponta para um nome específico, e errar isso quebra o `up` no primeiro deploy.

Pergunte também se a VPS **já tem o projeto rodando** e se algum arquivo foi **editado à mão lá dentro**. Isso decide o Passo 10.

## Passo 5 — Confirmar o desenho do deploy

Antes de escrever o workflow, exponha em 3-4 linhas: o gatilho, o transporte, o que roda na VPS e como o sucesso é verificado. Peça confirmação.

**Transporte — default é rsync do runner**, não `git pull` na VPS:
- a VPS não precisa de credencial do repositório nem de clone
- o que é deployado é exatamente o que o runner checou out
- `git pull` na VPS só se justifica se o usuário quiser histórico git lá dentro; nesse caso ele precisa configurar deploy key ou token na VPS, e você deve dizer isso explicitamente

## Passo 6 — Gerar a chave SSH

A chave **não** se gera no GitHub — gera na máquina do usuário; o GitHub só guarda a privada como secret.

```bash
ssh-keygen -t ed25519 -C "github-actions-<projeto>-<branch>" -f ~/.ssh/<projeto>_deploy -N ""
```

`-N ""` (sem passphrase) é obrigatório: o runner não tem como digitar senha. Chave dedicada ao deploy, nunca a chave pessoal do usuário — assim revogar o deploy não derruba o acesso dele.

Se o arquivo já existir, **não sobrescreva**: pergunte se é para reusar a chave existente ou gerar com outro nome.

## Passo 7 — Instalar a chave pública na VPS

```bash
ssh-copy-id -i ~/.ssh/<projeto>_deploy.pub -p <porta> <usuario>@<host>
```

`ssh-copy-id` só funciona se a VPS aceitar o login atual (senha ou outra chave já instalada). Se ela for key-only e você não tiver acesso, o usuário instala manualmente — entregue a linha exata:

```bash
# saída de: cat ~/.ssh/<projeto>_deploy.pub
# na VPS, com um acesso que já funcione:
echo '<conteúdo da .pub>' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
```

Teste **antes** de mexer no GitHub — se isto falhar, o workflow também falha:

```bash
ssh -i ~/.ssh/<projeto>_deploy -o IdentitiesOnly=yes -o BatchMode=yes -p <porta> <usuario>@<host> "<comando_que_verifica_o_runtime>"
```

`IdentitiesOnly=yes` importa: sem ele o `ssh` pode autenticar com outra chave do agente e você conclui que a chave nova funciona quando não funciona. `BatchMode=yes` faz falhar na hora em vez de pedir senha.

## Passo 8 — Coletar o known_hosts

```bash
ssh-keyscan -p <porta> <host> > /tmp/<projeto>_known_hosts
cat /tmp/<projeto>_known_hosts
```

A saída tem 2-3 linhas (ed25519, rsa, ecdsa) — todas vão no secret. Com porta diferente de 22 o formato sai como `[host]:porta`; é o formato correto, não editar. Guarde o arquivo: é **ele** que vai para o secret no Passo 12 — não rode `ssh-keyscan` de novo lá, senão o conteúdo gravado não é o que foi conferido aqui.

Confira o fingerprint contra o servidor real antes de gravar (isso é o que impede fixar a host key de um intermediário):

```bash
ssh-keygen -lf /tmp/<projeto>_known_hosts
# e, por um canal já confiável, na VPS:
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

## Passo 9 — Checklist da VPS

Com a chave funcionando, rode as verificações por SSH você mesmo e mostre a saída. Só peça ao usuário o que exige sudo:

```bash
# leitura — você roda
ssh -i ~/.ssh/<projeto>_deploy -p <porta> <usuario>@<host> \
  "ls -la <VPS_PATH> 2>/dev/null; id; <COMANDO_QUE_VERIFICA_O_RUNTIME>"
```

```bash
# escrita/sudo — o usuário roda na VPS
sudo mkdir -p <VPS_PATH> && sudo chown $USER <VPS_PATH>
sudo usermod -aG docker $USER    # exige relogar para valer
test -f <VPS_PATH>/<ARQUIVO_ENV> && echo ok
```

O runtime tem de responder **sem sudo** para o usuário do deploy: o runner não tem tty para senha. Se `docker ps` só funciona com sudo, resolva isto agora — é falha garantida no primeiro run.

## Passo 10 — Auditar o `--delete` do rsync

⚠️ **Este passo é obrigatório e não pode ser resumido.**

O rsync usa `--delete`: o diretório na VPS passa a ser um espelho do repositório. Qualquer arquivo que exista lá e não no repo é **apagado**; qualquer arquivo editado à mão na VPS é **sobrescrito**. Arquivo listado em `--exclude` fica protegido das duas coisas.

Não pergunte o que existe lá — **meça**. Com a chave já instalada, rode o mesmo rsync do workflow em modo simulação:

```bash
rsync -az --delete --dry-run -i \
  -e "ssh -i ~/.ssh/<projeto>_deploy -o IdentitiesOnly=yes -p <porta>" \
  --exclude '.git/' --exclude '.github/' --exclude 'node_modules/' \
  <DEMAIS_EXCLUDES> \
  ./ <usuario>@<host>:<VPS_PATH>/
```

Toda linha começando com `*deleting` é um arquivo que **some da VPS no primeiro deploy real**. Liste essas linhas para o usuário e, para cada uma, decida com ele: **entra nos `--exclude`** ou **passa a ser versionado**. Não deixe nenhum item indefinido. Depois de ajustar os `--exclude`, rode o dry-run de novo até a lista de `*deleting` conter só o que pode morrer.

Se o compose ou qualquer config foi editado à mão na VPS, a edição precisa ir para o repositório **antes** do primeiro deploy — senão ela morre no primeiro rsync. `rsync --dry-run -i` também mostra isso: linhas `>f.st....` num arquivo de config são sobrescrita de conteúdo.

## Passo 11 — Escrever o workflow

Use `templates/deploy-vps.yml` desta skill como base. Coloque em `.github/workflows/deploy-<branch>-vps.yml`.

Regras que o workflow **precisa** respeitar:

1. **`environment: <nome>` no job** se os secrets estiverem num GitHub Environment. Secret/variable de Environment é invisível para job que não o declara — os valores chegam **vazios**. O template trata isso com uma checagem explícita de valor vazio no primeiro step, com mensagem apontando o Environment; mantenha essa checagem, ela transforma o erro mais comum desta configuração num erro legível.
2. **Sensível em `secrets.`, o resto em `vars.`** Chave privada e known_hosts são secrets; host, usuário, porta e path são variables (aparecem nos logs, o que ajuda a depurar). Usar o contexto errado devolve string vazia em silêncio — confira que cada nome está no contexto certo.
3. **Secret e variable entram por `env:` do step**, nunca interpolados no corpo do `run:`. Valor interpolado direto vira código shell; via `env:` ele é só dado.
4. **Conexão configurada uma vez em `~/.ssh/config`**, com `BatchMode yes`, `IdentitiesOnly yes`, `ConnectTimeout` e `ServerAliveInterval`. Sem `BatchMode` um problema de chave vira job pendurado até o timeout; sem `ServerAliveInterval` build longo derruba a sessão no meio. Os steps seguintes usam só o alias (`ssh deploy-target`).
5. **`concurrency` sem `cancel-in-progress`.** Cancelar um deploy no meio de um build de container deixa a VPS em estado indefinido.
6. **`permissions: contents: read`** no topo. O workflow só lê o repositório.
7. **Checar pré-requisitos antes do rsync**: o arquivo de env existe? o runtime responde? Falhar aqui não deixa o projeto meio atualizado.
8. **`workflow_dispatch` com input `dry_run`**, que roda o rsync em `--dry-run -i` e pula os steps de subir e de health check. É como se audita o `--delete` depois que o workflow já existe, sem tocar na VPS.
9. **Health check por dentro da VPS**, contra o endereço interno (`127.0.0.1:<porta>`), com retry (30 tentativas de 5s) — container demora a subir. Em caso de falha, imprimir status e as últimas linhas de log dos serviços.
10. **`printf '%s\n'`** para escrever a chave privada, nunca `echo` — a chave OpenSSH precisa da quebra de linha final ou o `ssh` responde `error in libcrypto`.
11. **Nada de segredo em `run:` que ecoe.** Não faça `echo` do conteúdo de secret; o mascaramento do GitHub não cobre todas as transformações.
12. **Apagar as credenciais do runner no fim**, com `if: always()`.

Valide o YAML depois de escrever:

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/<arquivo>.yml')); print('yaml ok')"
```

Se `actionlint` estiver disponível, rode também — ele pega expressão `${{ }}` inválida e contexto inexistente, que o parser YAML aceita:

```bash
command -v actionlint >/dev/null && actionlint .github/workflows/<arquivo>.yml
```

O `yaml.safe_load` mostra a chave `on` como `True`: é o YAML 1.1 lendo `on` como booleano. Não é erro e o GitHub não se importa.

## Passo 12 — Cadastrar secrets e variables

**Com `gh` autenticado (padrão), cadastre você mesmo.** Isso elimina a fonte mais comum de erro: chave colada pela metade, sem a linha `END`, ou sem a quebra de linha final.

Crie o Environment (idempotente) e restrinja à branch do deploy:

```bash
# cria o Environment já habilitando política de branch customizada
gh api -X PUT repos/<owner>/<repo>/environments/<ENVIRONMENT> \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true'

# só a branch do deploy pode usar este Environment
gh api -X POST repos/<owner>/<repo>/environments/<ENVIRONMENT>/deployment-branch-policies \
  -f name='<branch>' -f type='branch'
```

Sem essa restrição, o workflow copiado para outra branch alcança a mesma VPS.

A política de branch só é aceita se o Environment estiver com `deployment_branch_policy` customizado; se a chamada acima falhar, ajuste em **Settings → Environments → `<ENVIRONMENT>` → Deployment branches and tags → Selected branches and tags** e siga.

Cadastre os valores:

```bash
gh secret set VPS_SSH_KEY     -R <owner>/<repo> --env <ENVIRONMENT> < ~/.ssh/<projeto>_deploy
gh secret set VPS_KNOWN_HOSTS -R <owner>/<repo> --env <ENVIRONMENT> < /tmp/<projeto>_known_hosts

gh variable set VPS_HOST -R <owner>/<repo> --env <ENVIRONMENT> --body '<host>'
gh variable set VPS_USER -R <owner>/<repo> --env <ENVIRONMENT> --body '<usuario>'
gh variable set VPS_PORT -R <owner>/<repo> --env <ENVIRONMENT> --body '<porta>'
gh variable set VPS_PATH -R <owner>/<repo> --env <ENVIRONMENT> --body '<path>'
```

Ler chave e known_hosts por redirecionamento (`< arquivo`) preserva o conteúdo byte a byte — e o known_hosts gravado é exatamente o que teve o fingerprint conferido no Passo 8. Sem Environment, troque `--env <ENVIRONMENT>` por nada (vai para o nível do repositório).

Confirme o que ficou gravado — `gh` lista nome e data, nunca o valor do secret:

```bash
gh secret list   -R <owner>/<repo> --env <ENVIRONMENT>
gh variable list -R <owner>/<repo> --env <ENVIRONMENT>
```

**Sem `gh`**, entregue a tabela para o usuário colar na UI, com os valores **reais** já preenchidos:

| Nome | Tipo | Onde | Valor |
|---|---|---|---|
| `VPS_SSH_KEY` | secret | Environment `<nome>` | conteúdo de `~/.ssh/<projeto>_deploy` |
| `VPS_KNOWN_HOSTS` | secret | Environment `<nome>` | *(a saída real do ssh-keyscan)* |
| `VPS_HOST` | variable | Environment `<nome>` | `<valor real>` |
| `VPS_USER` | variable | Environment `<nome>` | `<valor real>` |
| `VPS_PORT` | variable | Environment `<nome>` | `<valor real>` (omitir se 22) |
| `VPS_PATH` | variable | Environment `<nome>` | `<valor real>` |

Para a chave privada nesse caminho manual, o default é entregar o comando, não o conteúdo:

```bash
cat ~/.ssh/<projeto>_deploy
```

O transcrito da conversa é armazenado e pode ser exportado; chave colada nele fica fora do cofre de secrets, num lugar sem revogação. **Se o usuário disser explicitamente que pode exibir a chave no chat, exiba** — é decisão dele, e a chave é dedicada ao deploy e revogável pelo Passo 15. Ao colar na UI, tem de incluir as linhas `-----BEGIN OPENSSH PRIVATE KEY-----` e `-----END OPENSSH PRIVATE KEY-----` e a quebra de linha final.

Onde cadastrar na UI: **Settings → Environments → `<nome>` → Add environment secret / Add environment variable** (ou, sem Environment, Settings → Secrets and variables → Actions).

## Passo 13 — Rodar o primeiro deploy em simulação

Commite e faça push do workflow (pergunte antes). Depois valide **sem tocar na VPS**:

```bash
gh workflow run <arquivo>.yml -R <owner>/<repo> --ref <branch> -f dry_run=true
gh run watch -R <owner>/<repo> $(gh run list -R <owner>/<repo> -w <arquivo>.yml -L1 --json databaseId -q '.[0].databaseId')
```

Este run prova o que mais quebra na estreia: Environment enxergado, chave válida, host key aceita, pré-requisitos na VPS. E o log do rsync mostra de novo a lista de `*deleting` — agora com o conteúdo real da branch.

Se falhar, leia o log do step:

```bash
gh run view -R <owner>/<repo> <run-id> --log-failed
```

Só depois dispare o deploy real (push na branch ou `gh workflow run` sem `dry_run`) e acompanhe com `gh run watch`.

## Passo 14 — Avisar o que o deploy NÃO faz

Liste explicitamente, com base no Passo 2:
- **Migrations** — se o boot não as roda, o deploy também não. Diga qual comando rodar à mão.
- **Variáveis de build time** — mudar exige commit na branch, não edição na VPS.
- **Segredos da VPS** — nunca são enviados nem sobrescritos; mudança neles é manual e não passa pelo Git.
- **Rollback** — não existe. Voltar é reverter o commit e deixar o push disparar de novo.
- **Nginx do host / TLS** — fora do container, não é tocado pelo deploy.
- **Backup** — o `--delete` não guarda cópia do que apagou.

## Passo 15 — Deixar registrado como revogar

Deploy configurado sem caminho de revogação é dívida. Entregue as duas linhas:

```bash
# na VPS: remove a linha da chave de deploy do authorized_keys
ssh <usuario>@<host> "grep -v 'github-actions-<projeto>-<branch>' ~/.ssh/authorized_keys > /tmp/ak && mv /tmp/ak ~/.ssh/authorized_keys"

# no GitHub: apaga o secret
gh secret delete VPS_SSH_KEY -R <owner>/<repo> --env <ENVIRONMENT>
```

Rotacionar é repetir os Passos 6, 7 e 12 com um nome de arquivo novo e depois revogar o antigo.

## Passo 16 — Determinar número da implementação

<!-- Mantenha este passo sincronizado com centaur-driven-implement (Passo 9) e centaur-driven-tdd (Passo 12) -->
```
ls .centaur/implements/ | grep -E '^[0-9]{4}$' | sort | tail -1
```

- Se retornar um número (ex: `0003`), o próximo é esse + 1
- Se retornar vazio, começa em `0001`
- Sempre 4 dígitos

Reserve o número imediatamente com `mkdir .centaur/implements/XXXX` (sem `-p`). Se falhar porque já existe, incremente e tente de novo.

## Passo 17 — Documentar

Obtenha a data de hoje com `date +%F` — não a preencha de memória.

Crie `.centaur/implements/XXXX/README.md`:

```markdown
# [XXXX] Deploy automático da branch [branch] na VPS [ambiente]

**Data:** [saída de `date +%F`]
**Status:** Concluído
**Modo:** direto

## Solicitação
[O que o usuário pediu, com as palavras dele]

## Contexto
[Como o deploy era feito antes; por que automatizar]

## O que foi feito
[Gatilho, transporte, o que roda na VPS, como o sucesso é verificado]

## Arquivos criados
- `.github/workflows/[arquivo].yml` — [gatilho e o que faz]

## Arquivos modificados
- `caminho/do/arquivo.ext` — [o que mudou]

## Configuração fora do repositório
- GitHub Environment `[nome]` — secrets `VPS_SSH_KEY`, `VPS_KNOWN_HOSTS`; variables `VPS_HOST`, `VPS_USER`, [demais]
- Restrição de branch do Environment: `[branch]`
- Chave SSH: `~/.ssh/[nome]` na máquina do dev, pública em `~/.ssh/authorized_keys` da VPS
- Na VPS: `[VPS_PATH]/[arquivo de env]` criado à mão, fora do Git

## Decisões técnicas
[rsync vs git pull e por quê; o que entrou nos --exclude e por quê; secrets vs variables; sem cancel-in-progress]

## Auditoria do --delete
[O que o `rsync --dry-run` apontou como `*deleting` e o destino de cada item: excluído ou versionado]

## O que o deploy não faz
[migrations, build-time vars, segredos, rollback, nginx/TLS, backup]

## Como revogar
[Remover a chave do authorized_keys da VPS; apagar o secret no GitHub]

## Como validar
[Run com dry_run=true; push na branch; acompanhar o run; conferir o health check]

## Resultado da validação
[YAML validado; conexão SSH testada; resultado do dry-run e do primeiro run real]
```

## Passo 18 — Atualizar status.md

Adicione a linha na tabela de `.centaur/implements/status.md`:

```
| XXXX | Deploy automático da branch [branch] na VPS [ambiente] | [data] | Concluído | .github/workflows/[arquivo].yml |
```

Se a tabela ainda contiver a linha placeholder (`| — | — | — | — | — |`), remova-a ao inserir a primeira linha real.

## Passo 19 — Atualizar AGENTS.md

Deploy sempre entra no `AGENTS.md` — muda como o projeto é publicado. Atualize a seção "Como Fazer Deploy" (crie se não existir) com: gatilho, transporte, onde ficam os secrets, como rodar em `dry_run`, o que é manual (migrations, env da VPS) e o aviso do `--delete` do rsync.

Se houver documentação de deploy dedicada (`deploy/README.md` ou similar), acrescente lá a seção detalhada e mantenha o `AGENTS.md` com o resumo apontando para ela.

## Passo 20 — Informar o usuário

Encerre com:
- Resumo em 2-3 linhas do que foi configurado
- **O que já está cadastrado no GitHub** (saída de `gh secret list` / `gh variable list`) ou, sem `gh`, a tabela de valores do Passo 12
- Resultado do run de `dry_run` e o que ele mostrou de `*deleting`
- O checklist da VPS que ainda estiver pendente
- Número da implementação (ex: "Documentado em `.centaur/implements/0003/`")
- Aviso de que o push na branch dispara o deploy na hora — e pergunte se pode commitar/pushar
