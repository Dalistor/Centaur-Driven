---
name: centaur-driven-deploy
description: Prepara GitHub Actions para deploy limpo em VPS, com integridade, transferência com retry, ativação sem interrupção e rollback; configura acessos disponíveis e orienta os próximos passos, sem publicar.
metadata:
  version: 5.0.0
  dependencies: clean-code
---

# Preparar deploy via GitHub Actions

Entregue o workflow, os scripts necessários e instruções específicas para o projeto. **Não conecte à VPS, não faça deploy direto, não dispare Actions e não faça commit/push como parte desta skill.** Uma solicitação separada e explícita pode autorizar essas ações. Configurar Environment, variables e secrets no GitHub faz parte da preparação quando houver autenticação e permissões suficientes.

## 1. Entender o projeto e escolher o gatilho

Carregue a skill `clean-code` e suas referências pertinentes ao escrever workflows/scripts. Leia `AGENTS.md`, configuração de build, testes, runtime e infraestrutura. Use busca local; Graphify é opcional, sob demanda, sem indexação obrigatória. Respeite o contrato de memória vigente e registre a preparação em `.centaur/`.

Pergunte se o usuário quer **push na `main` ou execução manual (`workflow_dispatch`)**, exceto se já tiver respondido nesta sessão. Não escolha automaticamente por ele. Manual contém somente `workflow_dispatch`; automático adiciona `push: branches: [main]` e pode manter execução manual.

Obtenha somente os dados ainda desconhecidos: repositório GitHub, Environment, host, usuário/porta SSH, raiz de releases, runtime, testes/build, URL de health e estratégia atual de tráfego. Determine onde ficam banco, uploads e configuração persistente. Não invente valores nem chame simples lint de teste de integridade quando houver testes de comportamento.

## 2. Definir uma estratégia compatível com ausência de downtime

**Estáticos:** use `templates/deploy-vps.yml` e os scripts desta skill. O servidor existente serve `<VPS_PATH>/current`, um link simbólico trocado por rename atômico no mesmo filesystem. Cada release contém somente o build limpo e recebe diretório próprio. O script verifica checksums, inicia um servidor HTTP candidato em loopback, verifica seu conteúdo, troca o link e verifica um marcador exclusivo pela URL servida. Falha restaura o link anterior e verifica a recuperação; releases antigos são preservados.

Pré-requisitos a entregar ao usuário, sem executá-los na VPS:

- Linux com Bash, GNU coreutils (`mv -T`), `flock`, Python 3, curl e rsync; usuário com escrita apenas na raiz de releases.
- Servidor já configurado para `<VPS_PATH>/current`, com uma versão anterior funcional e `centaur-release.txt` identificando-a. Primeira instalação sem serviço existente é bootstrap e deve ser tratada explicitamente como pendência, não chamada de troca sem downtime.
- `HEALTH_URL` aponta para `https://dominio/centaur-release.txt`, sem cache e acessível da VPS. O marcador verifica qual release está atendendo; acrescente smoke tests específicos do produto antes e depois da ativação.
- Assets imutáveis devem usar URLs versionadas e permanecer acessíveis às páginas abertas da versão anterior (por exemplo, rota de assets por release). Só manter pastas antigas não garante isso: configure/teste a rota no servidor/CDN antes de afirmar continuidade. Considere cache e service workers.
- Configuração, uploads e dados ficam em `shared/` ou serviços externos, fora de `releases/`. O template não copia segredos nem limpa essas áreas.

**Serviços dinâmicos:** não use `activate-static.sh`. Gere e valide scripts específicos do runtime: iniciar candidato em outra porta/slot, health/readiness interno, troca de upstream atômica com reload gracioso, health após troca, restauração do upstream se falhar e drenagem de conexões antigas antes de desligar o slot anterior. Preserve sessões, WebSockets, workers e jobs conforme a aplicação. Em Nginx, valide configuração antes do reload e confirme o tráfego após ele; processo iniciado não é evidência de saúde. Nunca use `compose down`, reinício do serviço ativo ou `rsync --delete` no diretório em produção como estratégia sem downtime.

Se infraestrutura não permitir duas versões simultâneas, deixe a publicação bloqueada e explique a preparação necessária. Migrações de banco devem permitir coexistência (expand/contract); não executar migração destrutiva automaticamente nem prometer que rollback do código reverte dados.

## 3. Reutilizar acesso SSH ou gerar somente o que faltar

Inspecione nomes de secrets e configuração local, sem imprimir valores sensíveis. Reutilize uma chave dedicada adequada; não substitua credenciais remotas que já funcionam. Se já existir chave privada local, obtenha sua pública com `ssh-keygen -y` quando necessário. Se faltar completamente, gere em `.centaur/deploy/private/` (ignorado pelo Git), com diretório 700 e arquivos privados 600:

```bash
ssh-keygen -t ed25519 -C 'github-actions-PROJETO' -f .centaur/deploy/private/id_ed25519 -N ''
```

Substitua `PROJETO` pelo identificador real. Verifique existência antes: não sobrescrever arquivo, não usar chave pessoal como default. Não exponha a privada no chat, logs ou documentação. Se a chave existe apenas no secret GitHub, ela não pode ser recuperada; preserve-a e informe que a identidade precisa ser validada pelo operador.

Quando autorização na VPS ainda faltar, forneça ao usuário o comando com valores reais:

```bash
ssh-copy-id -i .centaur/deploy/private/id_ed25519.pub -p PORTA USUARIO@HOST
```

Entregue também o comando de verificação com `IdentitiesOnly=yes`, `BatchMode=yes`, `StrictHostKeyChecking=yes` e known_hosts validado. O usuário o executa. Para coletar a host key, entregue `ssh-keyscan -p PORTA HOST` e a comparação de fingerprint com `/etc/ssh/ssh_host_ed25519_key.pub` por console confiável. Não trate `ssh-keyscan` sozinho como validação. Reutilize known_hosts já verificado; nunca desabilite a checagem de host.

## 4. Gerar e validar os arquivos

- Workflow: `.github/workflows/deploy-vps.yml` (exceção necessária ao layout `.centaur/`, exigida pelo GitHub).
- Scripts versionados: `.centaur/deploy/seal-static.sh`, `.centaur/deploy/activate-static.sh` e `.centaur/deploy/retry-transfer.sh`, ou equivalentes específicos do runtime.
- Instruções: `.centaur/deploy/README.md` com gatilho escolhido, pré-requisitos, acessos configurados, pendências, execução, health, rollback, retenção e revogação.
- Builds, chaves, logs e temporários: `.centaur/deploy/build/`, `artifact/`, `private/`, `logs/`, `tmp/`, ignorados pelo Git.

O template é uma base deliberadamente bloqueada até substituir a etapa de integridade por instalação com lockfile, testes pertinentes e build limpo **reais do projeto**. Adapte a saída para `.centaur/deploy/build/site/`, evitando resíduos de builds anteriores. Não entregue esse `exit 1` como configuração concluída; quando faltarem decisões, mantenha-o e reporte a pendência.

Empacote somente a saída pública através de `seal-static.sh`: arquivos extras da pasta de build não entram no artefato; links e nomes comuns de credenciais são recusados. Isso não detecta segredos embutidos em JavaScript ou arquivos com nomes arbitrários: confira as variáveis de build e rode a inspeção pertinente ao projeto.

Dois jobs: `integrity` produz um único artefato testado; `publish` declara `needs: integrity` e usa esse artefato, sem recompilar outro conteúdo. Variáveis entram por `env`, nunca interpoladas como comandos. Segredos ficam somente no job com Environment e são limpos do runner ao final. Use `contents: read`, concorrência por ambiente e `cancel-in-progress: false`.

Retry aplica-se **somente à transferência idempotente para a release isolada**: três tentativas, esperas de 5 e 10 segundos e falha explícita ao esgotar. Nunca repetir ativação ou migrações indiscriminadamente. Cada tentativa de execução do Actions usa um ID novo, incluindo `run_attempt`, preservando releases anteriores. `--delete` fica restrito à nova release. Limpeza de versões é posterior à validação, exclui ativa/anterior e respeita janela de cache e drenagem; o template preserva todas por padrão até definir a política.

Valide YAML com parser disponível, `bash -n` nos scripts e `actionlint` quando disponível. Rode os testes do projeto e testes locais das transições/falhas dos scripts. Não confunda essas verificações com um deploy remoto validado.

## 5. Configurar o GitHub quando houver permissão

Descubra `owner/repo` pelo remote e use `-R OWNER/REPO` em todos os comandos `gh`. `git` local ou push funcionando não comprovam permissão de administrar Environment/secrets. Consulte `gh auth status`, o Environment e suas políticas existentes. Crie o Environment se ausente, sem apagar revisores, tempos de espera ou proteções de um existente. Configure restrição à branch autorizada consultando políticas atuais antes de adicionar; não duplique nem amplie permissões. O modo manual também deve restringir referências que podem publicar.

Cadastre valores disponíveis e confirmados. Se faltar acesso/permissão ou valor, forneça a instrução correspondente e mantenha a pendência explícita:

```bash
gh secret set VPS_SSH_KEY -R OWNER/REPO --env production < .centaur/deploy/private/id_ed25519
gh secret set VPS_KNOWN_HOSTS -R OWNER/REPO --env production < .centaur/deploy/private/known_hosts
gh variable set VPS_HOST -R OWNER/REPO --env production --body 'HOST'
gh variable set VPS_USER -R OWNER/REPO --env production --body 'USUARIO'
gh variable set VPS_PORT -R OWNER/REPO --env production --body 'PORTA'
gh variable set VPS_PATH -R OWNER/REPO --env production --body '/opt/PROJETO'
gh variable set HEALTH_URL -R OWNER/REPO --env production --body 'https://DOMINIO/centaur-release.txt'
```

Esses comandos são modelos: substitua valores e Environment pelo que foi descoberto; preserve secrets existentes quando estiver reutilizando-os. Liste somente nomes para confirmar cadastro (`gh secret list`, `gh variable list`). Nunca grave placeholders no GitHub.

## 6. Entregar próximos passos, sem publicar

Informe exatamente o que foi gerado, validado localmente, configurado no GitHub e o que ainda depende do operador. Forneça os comandos para autorizar a chave, preparar a infraestrutura, publicar o workflow e executá-lo/acompanhá-lo (`gh workflow run`, `gh run list`, `gh run watch`), **sem executá-los**. Avise que push na main dispara publicação quando esse for o gatilho escolhido. Não declare ausência de downtime comprovada sem ensaio no ambiente alvo.

Documente recuperação manual pelo link/upstream anterior, nomes de releases preservadas, limites do rollback e revogação (remover somente a chave pública dedicada do `authorized_keys` e apagar o secret correspondente). Registre o resultado como **preparação concluída** ou **preparação com pendências**, nunca deploy realizado. Nenhuma atualização Graphify obrigatória.

## Referências oficiais

- [Artefatos e dependências entre jobs](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-what-your-workflow-does/storing-and-sharing-data-from-a-workflow)
- [GitHub Environments](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments)
- [Reload gracioso do Nginx](https://nginx.org/en/docs/control.html)
