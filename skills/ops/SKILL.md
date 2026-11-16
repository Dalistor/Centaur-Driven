---
name: ops
description: Prepara a operação de um sistema - CI, deploy com rollback, execução em produção, segredos, observabilidade, backups e runbook - a partir do que o projeto já tem. Use para configurar ou revisar pipeline, publicação, ambiente de produção ou qualquer rotina operacional; entrega arquivos e instruções, sem publicar nem acessar servidores.
metadata:
  version: 6.0.0
  optional-dependencies: clean-code, graphify, _internal/memory
---

# ops

Deixe o sistema pronto para ser operado: integrar com segurança, publicar sem interrupção, rodar de forma previsível, ser observado e ser recuperado. Entregue arquivos versionáveis, validação local e instruções específicas do projeto.

**Esta skill prepara; não opera.** Não conecte a servidores, não faça deploy, não dispare workflows, não aplique mudanças em infraestrutura e não faça commit/push como parte dela. Um pedido separado e explícito pode autorizar cada uma dessas ações (no Centaur CLI, o usuário libera comandos com `$allow`). Configurar Environment, variables e secrets no GitHub faz parte da preparação quando houver autenticação e permissão suficientes.

## 1. Levantar o que existe

Leia `AGENTS.md`, manifestos, lockfiles, configuração de build e testes, `Dockerfile`/compose, workflows em `.github/workflows/`, scripts de publicação e documentação de ambiente. Use busca local; Graphify é opcional e sob demanda. Para decisões anteriores, consulte a [memória](../_internal/memory/SKILL.md) quando configurada.

Monte o inventário das seis áreas, marcando cada uma como **pronta**, **parcial**, **ausente** ou **não se aplica**, com o arquivo que comprova:

| Área | O que precisa existir | Referência |
|---|---|---|
| Integração (CI) | Testes, lint e build rodam a cada PR e bloqueiam a integração quando falham | [ci.md](references/ci.md) |
| Publicação (deploy) | O artefato testado é o publicado; troca sem interrupção; rollback ensaiável | [deploy.md](references/deploy.md) |
| Execução | Processo supervisionado, configuração por ambiente, proxy/TLS, health check | [runtime.md](references/runtime.md) |
| Segredos e acessos | Nada sensível no repositório; credenciais dedicadas, mínimas e revogáveis | [runtime.md](references/runtime.md) |
| Observação | Logs úteis, métricas dos sinais essenciais e alerta que chega a alguém | [reliability.md](references/reliability.md) |
| Recuperação | Backup com restauração testada, migrações reversíveis, runbook | [reliability.md](references/reliability.md) |

Não invente o que não encontrou: ausência de evidência é **ausente**, não "provavelmente configurado no servidor". O que só existe no servidor ou no painel do provedor é pergunta ao usuário.

## 2. Combinar o recorte

Se o pedido nomeou uma área ("configure o CI", "prepare o deploy"), trabalhe nela e apenas relate as demais no inventário. Se pediu ops de forma ampla, apresente o inventário e proponha a ordem abaixo, do que protege mais para o que refina:

1. CI que bloqueia regressão — sem isso, o resto publica defeitos mais rápido.
2. Segredos fora do repositório e acessos dedicados.
3. Deploy com artefato único, health check e rollback.
4. Backup com restauração testada, quando houver dados.
5. Observação e alerta.
6. Runbook e rotinas (atualização de dependências, retenção, rotação de credenciais).

Pergunte apenas o que muda a entrega e não está nas fontes: onde roda (VPS, PaaS, nuvem, contêiner), como o tráfego chega, onde ficam dados e uploads, quem recebe alertas, gatilho de publicação (push na `main` ou manual). Não escolha o gatilho pelo usuário. Proporcione ao porte: um site estático não precisa de métricas de saturação; um serviço com dados de clientes precisa de backup antes de qualquer refinamento.

## 3. Preparar cada área

Abra **somente** a referência da área em que está trabalhando e siga-a. Reaproveite o que o projeto já tem: estenda o workflow existente em vez de criar outro, mantenha o gerenciador de processos e o provedor em uso. Trocar de ferramenta é decisão do usuário, apresentada com o motivo.

Regras que valem em todas as áreas:

- **Configuração como código.** O que define a operação fica versionado e revisável; passos manuais viram script ou instrução no runbook, com o comando exato.
- **Menor privilégio.** Tokens, chaves e usuários dedicados ao uso, com o escopo mínimo e revogação documentada. Nunca reutilize credencial pessoal como padrão.
- **Nada sensível em arquivo versionado, log ou conversa.** Liste nomes de segredos, nunca valores. Arquivos privados gerados ficam em `.centaur/deploy/private/`, ignorados pelo Git.
- **Construir uma vez.** O artefato que passou nos testes é o que vai para produção; não recompile entre o teste e a publicação.
- **Toda mudança tem volta.** Diga como desfazer antes de dizer como aplicar; o que não tem volta (migração destrutiva, exclusão de dados) é pendência explícita, nunca passo automático.
- **Falhar fechado.** Passo que não conseguiu verificar interrompe; não segue adiante supondo sucesso.

Se a skill `clean-code` estiver instalada (no Centaur CLI, `read_skill` com `clean-code/SKILL.md`), aplique seus critérios aos scripts e workflows que escrever. Ausente, informe e prossiga.

## 4. Onde ficam os arquivos

- Workflows e automações do GitHub: `.github/workflows/` e `.github/dependabot.yml` (exigência do GitHub; única exceção ao layout `.centaur/`).
- Scripts de publicação: `.centaur/deploy/` (`seal-static.sh`, `activate-static.sh`, `retry-transfer.sh` ou equivalentes do runtime).
- Visão operacional: `.centaur/ops/README.md` com o inventário, decisões, pendências e o runbook (como publicar, verificar, reverter, restaurar e quem acionar).
- Builds, chaves, logs e temporários: `.centaur/deploy/build/`, `artifact/`, `private/`, `logs/`, `tmp/`, ignorados pelo Git.

Os modelos em `templates/` são bases a adaptar, não configuração pronta: `ci.yml`, `deploy-vps.yml` e `dependabot.yml`. Cada um traz um passo que falha de propósito até receber os comandos reais do projeto; não entregue esse bloqueio como configuração concluída.

## 5. Validar localmente

Valide YAML com o parser disponível, scripts com `bash -n`, workflows com `actionlint` quando disponível e os testes do projeto. Scripts de transição (ativação, rollback, restauração) merecem ensaio local dos caminhos de falha. Nada disso é operação validada: diga o que foi verificado localmente e o que só o ambiente real comprova.

## 6. Entregar

Registre o resultado conforme o [ciclo por contratos e evidências](../graphify/references/lifecycle.md) quando o projeto usar specs, sempre como **preparação concluída** ou **preparação com pendências** — nunca como deploy realizado nem como sistema monitorado. Entrega `published` exige observação externa.

Informe, de forma curta:

- Inventário das áreas, antes e depois.
- Arquivos gerados ou alterados e o que foi validado localmente.
- O que foi configurado no GitHub e o que depende do operador, com os comandos exatos para ele executar (autorizar chave, preparar servidor, publicar o workflow, acompanhar com `gh run watch`).
- Como reverter cada mudança e os limites desse retorno.
- Próximo passo recomendado na ordem do passo 2.

Avise quando um push na `main` passar a disparar publicação. Não declare ausência de downtime, restauração funcional ou alerta operante sem ensaio no ambiente alvo.
