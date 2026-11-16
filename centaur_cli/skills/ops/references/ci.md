# Integração contínua (CI)

O CI existe para que nenhuma mudança chegue à branch principal sem passar pelas mesmas verificações, em ambiente limpo. Ele é a base do resto: deploy automático sem CI só publica defeitos mais rápido.

## O que o pipeline precisa fazer

Use os comandos que o projeto já tem (manifestos, `Makefile`, scripts, `AGENTS.md`); não introduza ferramenta nova para ter um passo a mais.

1. **Instalar pelo lockfile**, no modo que falha se ele estiver desatualizado (`npm ci`, `pip install --require-hashes`/`uv sync --locked`, `composer install --no-dev` conforme o caso, `cargo --locked`). Sem lockfile versionado, registre a pendência: build não reprodutível.
2. **Verificações rápidas primeiro**: formatação, lint e checagem de tipos, quando o projeto os usa.
3. **Testes**: a suíte que o projeto considera gate. Serviços auxiliares (banco, fila) sobem como `services` do job ou contêineres, com dados sintéticos.
4. **Build**: o mesmo comando usado para produção. Se o artefato for publicado depois, é este que segue adiante — não recompile no deploy.

Rode em `pull_request` e em `push` na branch principal. Matriz de versões só para o que o projeto declara suportar. Mantenha o pipeline rápido o bastante para ser esperado (alvo: poucos minutos); se passar disso, pare de acrescentar passos e use cache ou paralelismo.

O gate só existe se a branch estiver protegida: status do CI obrigatório para merge na branch principal. Configurar a proteção exige permissão de administração; sem ela, entregue a instrução e marque a pendência.

## Endurecimento de workflows

Vale para todo workflow do repositório, inclusive os de deploy:

- **Permissões mínimas do token.** `permissions: contents: read` no topo; cada job eleva só o que usa (`id-token: write` para OIDC, `packages: write` para publicar imagem). Nunca `write-all`.
- **Actions fixadas pelo SHA completo do commit**, com a versão em comentário (`uses: actions/checkout@<40 hex> # v4.4.0`). Tag e branch podem ser movidas por quem controla o repositório da action. Confira o SHA no repositório oficial antes de fixar; não copie de exemplos.
- **Atualização dos pins**: `.github/dependabot.yml` com o ecossistema `github-actions` (modelo em `../templates/dependabot.yml`). Sem isso, o pin congela também as correções de segurança.
- **`persist-credentials: false` no checkout**, para o token não ficar gravado no `.git/config` do runner à disposição dos passos seguintes.
- **Código de terceiros não roda com segredos.** `pull_request` de fork não recebe segredos, e deve continuar assim. `pull_request_target` e `workflow_run` rodam com o contexto do repositório base: não faça checkout nem execute código do PR neles.
- **Entradas nunca viram comando.** Título de PR, nome de branch, mensagem de commit e inputs entram por `env:` e são usados como `"$VARIAVEL"`; nunca interpole `${{ ... }}` dentro de `run:`.
- **Segredos só no job que precisa**, de preferência atrás de um Environment com restrição de branch e revisores. Para nuvem, prefira OIDC (credencial de curta duração) a chave estática.
- **`timeout-minutes` em todo job** e `concurrency` por branch/ambiente: cancele execuções superadas em PR (`cancel-in-progress: true`), nunca em deploy.
- **Cache não é artefato confiável**: chave derivada do lockfile, e nada vindo de cache vai direto para produção.

## Dependências

- Atualizações automáticas agrupadas e com frequência que alguém de fato revisa (semanal costuma bastar); o CI é quem valida cada uma.
- Auditoria de vulnerabilidades com a ferramenta do ecossistema (`npm audit`, `pip-audit`, `cargo audit`) é útil como aviso; como gate, só para severidade alta e com caminho claro para exceção, senão o time aprende a ignorar o vermelho.
- Varredura de segredos no repositório (a do GitHub, quando disponível) e `.gitignore` cobrindo `.env`, chaves e builds.

## Entregar

`.github/workflows/ci.yml` a partir do [modelo](../templates/ci.yml), com os comandos reais; `dependabot.yml` quando ausente; instrução da proteção de branch. Valide com `actionlint` quando disponível e rode localmente os mesmos comandos que o workflow executa. O workflow só está comprovado depois de uma execução real no GitHub: sem ela, diga que foi validado apenas localmente.

## Referências oficiais

- [Uso seguro do GitHub Actions](https://docs.github.com/en/actions/reference/security/secure-use)
- [Dependabot para actions](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/keeping-your-actions-up-to-date-with-dependabot)
- [OIDC no GitHub Actions](https://docs.github.com/en/actions/concepts/security/openid-connect)
