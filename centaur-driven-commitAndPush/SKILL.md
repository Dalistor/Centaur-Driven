---
name: centaur-driven-commitAndPush
description: Cria commit do trabalho solicitado e publica na main após buscar a main remota, simular a integração e validar o resultado; interrompe se houver conflitos e sugere como resolvê-los.
---

# centaur-driven-commitAndPush

Use quando o usuário pedir commit e push na `main`. Criar ou editar esta skill não autoriza publicar o repositório. Uma invocação explícita para publicar já autoriza commit, integração limpa e push normal no escopo pedido; não peça confirmação repetida. Respeite permissões do ambiente e proteção de branch.

## Preparar o candidato

1. Leia `AGENTS.md`, convenções de commit e verificações exigidas. Inspecione `git status --short`, branch atual, remotes, upstream e diffs staged/unstaged. Identifique o remoto de destino pelo upstream/configuração, sem presumir `origin` se houver ambiguidade. Não exponha credenciais das URLs.
2. Se houver merge/rebase/cherry-pick em andamento, arquivos unmerged, HEAD destacado sem origem clara ou remoto ambíguo, pare com a causa e a ação necessária. Não limpe, faça stash ou descarte trabalho automaticamente.
3. Revise os arquivos e commits que serão publicados. Inclua somente mudanças do pedido; preserve trabalho alheio e staging preexistente fora do escopo. Não use `git add .` indiscriminadamente. Se a branch tiver commits não relacionados que também entrariam na main, esclareça o escopo antes de publicá-los. Rode as verificações do projeto pertinentes à mudança e crie o commit com caminhos explícitos e mensagem nas convenções locais. Se não houver mudanças, use os commits pendentes; se não houver nada a publicar, informe isso.

## Buscar e simular a main

4. Busque explicitamente a branch: `git fetch <remoto> refs/heads/main:refs/remotes/<remoto>/main`. Em falha de rede/autenticação ou ausência de main, pare; refs antigas não servem como prova. Registre os SHAs do candidato (`HEAD`) e da main remota recém-buscada. Examine também a main local, caso exista, e informe commits locais ainda não publicados; não sobrescreva sua referência.
5. Verifique ancestralidade com `git merge-base --is-ancestor`. Se o candidato já é ancestral da main remota, não há conteúdo novo desse candidato a publicar. Se a main remota é ancestral do candidato, a integração é fast-forward. Se divergiram, simule com `git merge-tree --write-tree <sha-main-remota> <sha-candidato>`. Código 0 indica integração textual limpa; código 1 indica conflitos e deve ser reportado com os caminhos; outros erros significam checagem inconclusiva. Sem ancestral comum, pare e explique; não use `--allow-unrelated-histories`.
6. Se o Git instalado não suportar a simulação, use um worktree temporário com HEAD destacado na main remota e execute nele `git merge --no-commit --no-ff <sha-candidato>`. Inspecione os unmerged e aborte o merge simulado no worktree temporário. Nunca faça essa tentativa no checkout do usuário. Remova apenas o worktree temporário criado pela skill, após encerrar a operação, preservando artefatos necessários para explicar falhas.

## Integrar, validar e publicar

7. Havendo conflito ou resultado inconclusivo, **não faça push** nem tente resolver automaticamente. Informe SHAs comparados, arquivos conflitantes e se o commit local já foi criado. Sugira integrar a main em uma branch de trabalho, resolver arquivos, rodar os testes e invocar novamente; para branch protegida, sugira PR. Não apresente comandos destrutivos como solução padrão.
8. Sem conflitos, prepare o resultado em worktree temporário destacado a partir da main remota: fast-forward para o candidato quando possível; caso divergente, crie merge normal do candidato preservando ambos os históricos. Rode ali as verificações exigidas para o resultado integrado. Falha em teste, hook ou build impede push e deve ser reportada. Ausência de conflito textual não comprova correção do sistema. Não ignore hooks nem gates obrigatórios.
9. Antes de publicar, faça novo fetch de main e compare com o SHA usado na simulação. Se mudou, refaça a simulação/integração e a validação para os novos SHAs. Limite a duas tentativas de atualização; se continuar mudando, pare e sugira combinar uma janela de integração. Não entre em loop indefinido.
10. Publique somente o SHA integrado e validado, usando `git push <remoto> <sha-integrado>:refs/heads/main`. **Nunca use force, force-with-lease ou refspec com `+`.** Uma corrida após o último fetch deve resultar em rejeição normal de non-fast-forward; pare e explique como repetir a checagem. Proteções de branch ou falta de permissão também devem ser reportadas, com sugestão de PR, sem contorná-las.
11. Confirme a main remota com novo fetch e verifique que contém o SHA publicado (pode ter avançado depois). Se a consulta falhar após push aceito, diga que o push foi aceito mas a confirmação não foi possível. Preserve o checkout e a branch original; não mova a main local que tenha trabalho divergente. Remova o worktree temporário limpo criado pela skill e reporte branch de origem, commit, SHA integrado, destino, validações e estado do push.

Ao haver bloqueio, explique a causa concreta e proponha o próximo passo. Nunca afirme que não haverá conflitos futuros: a checagem vale para os SHAs buscados, e o push normal protege contra atualizações concorrentes.
