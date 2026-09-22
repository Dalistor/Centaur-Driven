---
name: centaur-driven-update
description: Atualiza a documentação centaur de um projeto existente - migra AGENTS.md, histórico e grafo Graphify, verifica as dependências da skill e do CLI Graphify, audita conflitos e consolida a verdade. Não toca em código.
version: 1.7.0
invocable: true
author: user
metadata:
  dependencies: clean-code, graphify
  optional-dependencies: ai-memory
---

# centaur-driven-update

## Memória de implementações

Leia o [contrato de memória](../centaur-driven-memory/references/contract.md) junto do contexto. O backend em `.centaur/workspace.json` determina o destino dos registros: `files` mantém os READMEs legados; `ai-memory` usa páginas verificadas e dispensa novas pastas `implements/`. As etapas de reserva numérica e escrita em `implements/status.md` abaixo são exclusivas de `files`; no modo ai-memory, aplique o registro, a fila e a consolidação definidos no contrato. Preserve specs e histórico existente.

## Contexto persistente — Graphify

Antes de explorar o projeto, siga o [contrato de contexto](../centaur-driven-graphify/references/context.md). Graphify (CLI `graphify` do pacote `graphifyy` + skill oficial `graphify`) é dependência obrigatória para localizar relações no código. Para histórico e decisões, consulte ai-memory quando configurado. Consulte o grafo antes de ampliar leituras; confirme as fontes relevantes. Aplique os limites de escrita e a sincronização definidos no contrato.

## Escopos e equipe

Antes do fluxo, leia o [contrato de módulos e equipe](../centaur-driven-graphify/references/team-workspace.md). Ele define resolução de caminhos, IDs qualificados, responsabilidade, concorrência e estados. Os exemplos legados abaixo usam o escopo selecionado; aplique o contrato também aos comandos e templates.

## Dependência obrigatória — clean-code

Antes de executar o fluxo, localize a skill `clean-code` no catálogo do agente (no Claude Code, `.claude/skills/clean-code/SKILL.md` ou `~/.claude/skills/clean-code/SKILL.md`) e leia seu `SKILL.md`. Resolva as referências a partir da pasta dela. Se estiver ausente ou incompleta, informe a dependência faltante e a instalação descrita no README do Centaur; não simule sua aplicação nem prossiga com trabalho dependente dela.

Use os critérios da dependência para identificar divergências de responsabilidades e camadas com evidência. Ao migrar o template, inclua a dependência nas regras de qualidade do `AGENTS.md`. Preserve o escopo documental: achados no código são reportados, não corrigidos.

As instruções do usuário e do projeto prevalecem. Use `AGENTS.md` e `.centaur/` como contexto e registro do Centaur; leia `.clean/` se existir, sem criá-lo ou atualizá-lo neste fluxo. Em caso de divergência, reporte com evidência. Aplique a dependência ao escopo solicitado, sem iniciar auditoria ou limpeza geral.

Você é responsável pela manutenção da documentação centaur de um projeto já documentado. Projetos envelhecem: as skills ganham seções novas que o `AGENTS.md` antigo não tem, o histórico acumula implementações que se contradizem, e o que era verdade na implementação `0003` deixou de ser na `0021`. Um agente que chega hoje lê tudo isso e trabalha com informação errada — ou lê muito e gasta contexto com ruído.

Sua tarefa tem duas metades: **migrar o schema** e **consolidar a verdade**.

**Fonte de verdade do schema:** o template do `centaur-driven-start-project` **instalado nesta máquina**. Não existe tabela de migrações embutida aqui — ela apodreceria a cada versão nova. Você lê o template atual e compara o projeto contra ele, seção a seção.

## Restrições absolutas

1. **Você NÃO toca em código do projeto.** Seu escopo é `AGENTS.md`, `.centaur/`, `docs/system/` e os artefatos derivados em `graphify-out/`. Se encontrar bug, código morto ou violação de camada, **reporte** e oriente (`/centaur-driven-tdd`, `/centaur-driven-implement` ou `/centaur-driven-spec`) — não corrija.
2. **Você nunca apaga uma pasta de implementação nem de spec.** `.centaur/implements/XXXX/` e `.centaur/specs/YYYY/` são registro permanente. Compactação mexe em **índices**, nunca no registro.
3. **Você não reescreve README de implementação concluída nem de spec concluída.** São registro histórico do que se sabia na época, não documento vivo. Documentos vivos são: `AGENTS.md`, `.centaur/implements/status.md`, `.centaur/specs/index.md` e as specs ainda `Pendente`/`Em andamento`.
4. **Conflito com duas leituras plausíveis é pergunta, não decisão sua.** Você só resolve sozinho o que o código prova (arquivo existe ou não existe, script existe ou não existe).

## Passo 1 — Verificar pré-condições

Resolva o backend antes da auditoria. Em ai-memory, ausência de `implements/` e de seus índices é esperada: não crie essa estrutura. Aplique as verificações legadas somente aos diretórios já existentes, e confira páginas/fila relacionadas ao escopo. Mudar o backend ou importar histórico segue `centaur-driven-memory` quando solicitado.

1. `AGENTS.md` existe na raiz? Se não:
   > "Este projeto não tem `AGENTS.md` — não há documentação centaur para atualizar. Execute `/centaur-driven-start-project` para documentá-lo pela primeira vez."

   E pare.
2. `.centaur/` existe? Se não existir, não é bloqueio: registre que a estrutura de histórico nunca foi criada e crie no Passo 7 conforme o template.
3. Verifique se a árvore de trabalho está limpa:

```bash
git status --porcelain
```

Você vai reescrever documentação. Se houver mudanças não commitadas, avise o usuário e pergunte se quer commitar antes — com a árvore limpa, desfazer é `git checkout`.

4. Verifique `centaur-driven-graphify`, sua referência de equipe, a skill oficial `graphify` e `graphify --version`. Confira `docs/system/`, o legado em `.centaur/system/` e os artefatos em `graphify-out/`. Ausência do CLI ou extração semântica pendente deve ser reportada sem bloquear a documentação já validada. Para projetos antigos, leia `references/migration.md` de `centaur-driven-graphify` antes de migrar os documentos.

## Passo 2 — Descobrir as versões

**Skills instaladas.** Localize os `SKILL.md` e leia a versão do frontmatter de cada um, incluindo `centaur-driven-graphify`:

```bash
for d in .claude/skills/centaur-driven-*/ ~/.claude/skills/centaur-driven-*/; do
  [ -f "$d/SKILL.md" ] && printf '%s %s\n' "$(basename $d)" "$(grep -m1 '^version:' "$d/SKILL.md" | cut -d' ' -f2)"
done
```

Skill de projeto (`.claude/skills/`) tem precedência sobre a global (`~/.claude/skills/`) — se o mesmo nome aparecer nas duas, a do projeto é a que vale. Se não achar nenhuma, siga assim mesmo e trabalhe a partir do template que você tem em contexto, avisando o usuário que não conseguiu ler as skills instaladas.

**Schema do projeto.** A última linha do `AGENTS.md` carrega o carimbo:

```
_Documentação centaur — schema `1.4.0`, gerada em `2026-08-28`. Atualize com `/centaur-driven-update`._
```

- **Carimbo presente e igual à versão instalada do `start-project`** → o schema está em dia. Pule o Passo 3 e vá direto para a auditoria (Passo 4), que é o valor recorrente desta skill.
- **Carimbo presente e menor** → migre no Passo 3.
- **Carimbo ausente** (documentação anterior ao carimbo) → **não tente adivinhar o número da versão**. Vá para o Passo 3 e compare seção a seção; a ausência de uma seção é o sinal, não o número.

## Passo 3 — Migrar o schema da documentação

Leia o template de `AGENTS.md` dentro do `centaur-driven-start-project` instalado (o bloco do Passo 4 daquela skill) e compare com o `AGENTS.md` do projeto:

1. **Instruções essenciais que o template tem e o projeto não** → acrescente somente o necessário ao projeto. Referências para documentos existentes podem atender os detalhes; não crie conteúdo vazio para preencher títulos.
2. **Seções que o projeto tem e o template não** → mantenha. São customizações do usuário; nunca apague seção só porque saiu do template.
3. **Seções com formato mudado** (ex: virou tabela) → reformate preservando o conteúdo.

Faça o mesmo com a estrutura `.centaur/`: compare `implements/status.md` (se backend files ou histórico existente) e `specs/index.md` contra os templates do Passo 5 do `start-project`. Cabeçalho de tabela que ganhou coluna nova precisa ganhar a coluna (com as células antigas preenchidas com `—` quando o dado não existir).

Aplique o Passo 5 de `start-project`: reutilize documentos existentes e crie detalhes em `docs/system/` apenas quando houver conteúdo útil. A lista de documentos de `centaur-driven-graphify` é um catálogo de possibilidades; não exige mapas, glossários ou pastas vazias. Migre documentos legados de `.centaur/system/` conforme `references/migration.md`, preservando conteúdo e links. Migre a seção antiga “Sistema no Graphify” para “Contexto persistente com Graphify” do template instalado, incluindo a dependência obrigatória, consultas com orçamento, confirmação das fontes e modo degradado. Preserve regras customizadas e reporte o estado real do índice. Para compactar o AGENTS.md legado, transfira detalhes de arquitetura, operação e vocabulário para documentos apropriados somente no plano autorizado, preserve todo o conteúdo válido e substitua os trechos transferidos por resumos e links verificáveis. Não apague conteúdo por ter saído do template.

**Seções que exigem informação que não está em lugar nenhum** — tipicamente as mais novas — viram perguntas para o usuário. Levante primeiro o que der para inferir do código e apresente já preenchido, para ele só confirmar. Exemplos do que costuma faltar em documentação antiga:

- **Arquitetura de Camadas** → documente limites e dependências reais; use tabela curta quando útil e não imponha novas camadas
- **Testes** → leia `package.json`/`pytest.ini`/`Makefile` e preencha framework, comandos e convenção de nome
- **Vocabulário e Idioma do Código** → levante os termos do domínio realmente usados no código e o idioma dos identificadores e comentários; leve para o usuário confirmar quais são as palavras oficiais e quais são variações a evitar

Não invente conteúdo para preencher seção: seção sem informação real fica com o texto explícito de que não foi definida, e vira pergunta.

## Passo 4 — Auditar a integridade dos registros

Se a documentação existir, consulte o índice Graphify, Visão Geral, Glossário, Fluxos, Perspectivas e Decisões em `docs/system/` para detectar documentação que contradiz o código. Proponha correções no plano confirmado; não reescreva histórico de implementações para mudar a compreensão atual.

Verificações mecânicas, todas resolvíveis sem perguntar:

```bash
# pastas de implementação existentes
ls .centaur/implements/ | grep -E '^[0-9]{4}$' | sort
# pastas sem README (número reservado por task que falhou)
for d in .centaur/implements/[0-9][0-9][0-9][0-9]/; do [ -f "$d/README.md" ] || echo "órfã: $d"; done
```

Cheque e anote:

1. **Pasta sem README** → número reservado por uma task que morreu. Registre como `Interrompida` no `status.md` (ou remova a pasta vazia, se o usuário autorizar — pasta vazia não é registro).
2. **Pasta com README ausente do `status.md`** → adicione a linha, com os dados do README.
3. **Linha no `status.md` sem pasta correspondente** → registro fantasma; confirme com o usuário antes de remover.
4. **Buraco na numeração** → só anote; buraco é normal (task falhou, número queimado).
5. **Spec com todas as tasks marcadas** → confira filhas, validação e integração antes de concluir; use `Em revisão` enquanto faltar integração/aceite, conforme o contrato de equipe.
6. **Spec `Pendente`/`Em andamento` com tasks não marcadas** → verifique se as tasks foram feitas por fora (procure por implementações que citam a spec). Se foram, marque; se a spec foi abandonada, pergunte ao usuário se quer marcá-la como `Cancelada`.
7. **Divergência entre `index.md` e os READMEs das specs** (status, número de tasks) → o README da spec é a fonte; alinhe o índice.
8. **Implementação concluída com fluxo ou nota pendente** → registre a lacuna e inclua a sincronização no plano; não trate a ausência de documentação como falha do código validado.
9. **Draft fora de `docs/system/Drafts/` ou sem estado** → não o promova automaticamente; registre hipótese e perguntas abertas.
10. **Perspectiva sem evidência ou desatualizada** → consulte o grafo e confirme no código; diferencie planejado, implementado e inferido.
11. **Grafo desatualizado** → atualize código e documentos conforme a skill Graphify; atualizar só AST não sincroniza specs/implements.
12. **Documentação legada** → siga a referência de migração, preservando conteúdos humanos e retirando o quadro da navegação ativa.

## Passo 5 — Detectar conflitos

Aqui está o valor da skill: encontrar onde a documentação **mente**.

**5a. Documentação contra código** (verificável, você resolve):
- Caminhos citados no `AGENTS.md` (estrutura de pastas, camadas) que não existem mais
- Comandos de rodar/testar/buildar que não existem nos scripts do projeto
- Dependência ou serviço descrito que saiu do `package.json`/`pyproject.toml`/compose
- Termos do vocabulário que o código não usa mais

**5b. Implementação contra implementação** (pode exigir pergunta):
Cruze as implementações pelos **arquivos afetados** no `status.md`. Onde duas ou mais tocaram o mesmo arquivo, leia os READMEs delas em ordem: a mais recente que mudou aquele comportamento é a verdade atual. Sinalize quando uma implementação antiga descreve como verdade presente algo que uma posterior desfez — o problema não é o registro antigo (ele é histórico legítimo), é o `AGENTS.md` ou o índice ainda repetirem a versão velha.

**5c. Implementação contra `AGENTS.md`**:
As skills de execução só atualizam o `AGENTS.md` quando julgam a mudança relevante — decisão sujeita a erro. Procure implementações que mudaram arquitetura, estrutura de pastas, dependência importante, forma de rodar ou de deployar e **não** se refletem nas instruções essenciais do `AGENTS.md` ou nos documentos vinculados pertinentes. Cada uma dessas é uma atualização faltando; não duplique no AGENTS.md os detalhes já documentados corretamente.

**5d. Conhecimento preso no histórico**:
Regra ou convenção que virou permanente mas só existe dentro de um `implements/XXXX/README.md` — cliente HTTP padrão do projeto, estratégia de tratamento de erro, padrão de mock, convenção de nomenclatura estabelecida no meio do caminho. Um agente novo lê o `AGENTS.md`, não vasculha 30 READMEs. Promova regras essenciais para `AGENTS.md` e detalhes para a documentação canônica vinculada, recuperável pelo Graphify. Uma estratégia específica de mock ou glossário extenso não precisa ser lida em toda sessão.

Para cada conflito, registre: o que a documentação diz, o que é verdade, e a evidência (arquivo, implementação, comando). Sem evidência não é conflito, é palpite.

## Passo 6 — Apresentar o plano e confirmar

Antes de escrever qualquer coisa, mostre em formato curto:

- **Migração de schema**: seções que serão criadas e as que precisam de resposta sua
- **Correções de integridade**: o que será ajustado (item por item, do Passo 4)
- **Conflitos**: o que a doc diz × o que é verdade × evidência — e o que você propõe
- **Consolidação**: o que vai subir para o `AGENTS.md` e o que vai ser arquivado
- **Perguntas em aberto**: tudo que você não pode decidir sozinho, de uma vez só

Aguarde a confirmação. Se o usuário discordar de um item, tire-o do plano — não insista.

## Passo 7 — Aplicar

Execute o plano confirmado, nesta ordem:

1. Criar/completar a estrutura `.centaur/` que estiver faltando
2. Aplicar as correções de integridade nos índices
3. Migrar as seções do `AGENTS.md` (crie as que faltam, reformate as que mudaram, **preserve as customizadas**)
4. Corrigir os pontos onde a documentação contradizia o código
5. Promover regras essenciais para `AGENTS.md` e detalhes duráveis para documentos vinculados, preservando os registros históricos
6. Inicializar ou completar `docs/system/` e sincronizar código e documentos no Graphify conforme o plano

Edite cirurgicamente: mantenha o texto que continua correto com as palavras originais do usuário. Reescrever seção inteira que estava certa só troca a redação dele pela sua.

## Passo 8 — Otimizar para agentes novos

Toda skill centaur lê as instruções de `AGENTS.md` e recupera o contexto relevante pelo Graphify; `status.md` é consultado sob demanda. O que estiver no `AGENTS.md` custa contexto em **toda** execução futura — logo, o critério aqui é: o que um agente que chega precisa saber para agir corretamente?

**`AGENTS.md` — preciso e curto:**
- Cada seção descreve o estado **atual**, no presente. Nada de "antes era X, agora é Y" (isso é histórico, mora no `implements/`)
- Regra que vale para toda implementação futura fica aqui; narrativa de uma mudança específica não
- Sem duplicação entre seções — um fato, um lugar
- Se o `AGENTS.md` estiver longo a ponto de esconder o essencial, proponha mover o detalhe profundo para um arquivo dedicado (`docs/`) e deixar o resumo com o ponteiro

**`status.md` — trilha recente:**
Consulte o índice por escopo e assunto; o arquivamento mantém sua navegação manejável, sem exigir leitura integral em toda sessão. Quando passar de ~40 linhas (ou quando o usuário achar cedo demais), proponha arquivar:

1. Crie `.centaur/implements/arquivo.md` com o mesmo formato de tabela
2. Mova para lá as linhas antigas, mantendo no `status.md` as mais recentes
3. Marque na linha arquivada quando ela foi superada: `→ superada por 0021`
4. No topo do `status.md`, deixe o ponteiro: `Implementações anteriores a XXXX estão em `arquivo.md`.`

**As pastas `implements/XXXX/` continuam todas onde estão** — arquivar é mover linha de índice, não apagar registro. A trilha nos dois sentidos (implementação ↔ spec) permanece intacta.

Depois de consolidar, releia o `AGENTS.md` inteiro do começo ao fim, como um agente que nunca viu este projeto: ele responde o que fazer, onde mexer e o que é proibido, sem se contradizer?

## Passo 9 — Gravar o carimbo de schema

Atualize (ou crie, se não existia) a última linha do `AGENTS.md`:

```
---

_Documentação centaur — schema `[versão do centaur-driven-start-project instalado]`, atualizada em `[saída de date +%F]`. Atualize com `/centaur-driven-update`._
```

A versão é a do `start-project` instalado, lida no Passo 2 — é ela que define o schema. Sem esse carimbo, a próxima execução refaz a comparação seção a seção sem necessidade.

## Passo 10 — Documentar a atualização

Esta atualização é uma mudança rastreável do projeto e entra no histórico como qualquer outra.

No backend ai-memory, registre esta atualização pelo contrato de memória, usando o template abaixo como corpo; dispense reserva, pasta e linha de `status.md`. Em ambos os modos, sincronize os documentos locais no Graphify após salvá-los.

No backend files, determine o número da implementação:

<!-- Mantenha este passo sincronizado com centaur-driven-implement (Passo 9) e centaur-driven-tdd (Passo 12) -->
```
ls .centaur/implements/ | grep -E '^[0-9]{4}$' | sort | tail -1
```

Próximo número, 4 dígitos, reservado com `mkdir .centaur/implements/XXXX` (sem `-p`). Obtenha a data com `date +%F`.

Em `files`, crie `.centaur/implements/XXXX/README.md`. Em `ai-memory`, use este conteúdo no registro do contrato, com o ID atribuído:

```markdown
# [XXXX] Atualização da documentação centaur (schema [origem] → [destino])

**Data:** [saída de `date +%F`]
**Status:** Concluído
**Modo:** direto

## Solicitação
[O que o usuário pediu]

## Contexto
[Schema anterior, schema novo, e há quanto tempo a documentação não era revisada]

## O que foi feito
[Seções migradas, correções de integridade, conflitos resolvidos, consolidação]

## Arquivos modificados
- `AGENTS.md` — [seções criadas, corrigidas e promovidas]
- `.centaur/implements/status.md` — [correções e arquivamento]
- [demais]

## Conflitos resolvidos
| O que a doc dizia | Verdade | Evidência | Decisão |
|---|---|---|---|
| [afirmação] | [fato] | [arquivo/implementação] | [o que foi escrito] |

## Decisões técnicas
[O que foi promovido para o AGENTS.md e por quê; critério de arquivamento adotado]

## Pendências reportadas ao usuário
[Problemas de código encontrados e não corrigidos — esta skill não toca em código]

## Como validar
[Reler o AGENTS.md; conferir que os comandos documentados rodam; `git diff` da atualização]

## Resultado da validação
[O que foi conferido e o resultado]
```

Somente em `files`, adicione a linha em `.centaur/implements/status.md` (removendo a linha placeholder, se ainda existir):

```
| XXXX | Atualização da documentação centaur | [data] | Concluído | AGENTS.md, .centaur/ |
```

Use `/centaur-driven-graphify sincronizar <escopo>/<id>` para atualizar os documentos afetados e o grafo após esta atualização. Reporte separadamente falhas do CLI e extração semântica pendente.

## Passo 11 — Informar o usuário

Encerre com:
- Schema de origem e destino (ex: "sem carimbo → `1.4.0`")
- Seções criadas ou migradas no `AGENTS.md`
- Correções de integridade aplicadas
- Conflitos resolvidos, e a evidência de cada um
- O que foi arquivado e onde
- **Pendências de código** encontradas e não corrigidas, com a skill certa para cada uma
- Referência da página e estado da memória, ou número/README em `files`
- Documentação e grafo Graphify atualizados, com dependências e extrações pendentes explicitadas
- Sugestão de conferir com `git diff` antes de commitar

Na migração para módulos, preserve os caminhos existentes como master. Adicione `.centaur/workspace.json` e os escopos identificados sem mover históricos; audite cada índice/arquivo e também as relações mestre–filhas. Percorra todos os diretórios de registros, inclusive IDs com sufixo: os filtros numéricos dos exemplos legados não cobrem registros de clones independentes.
