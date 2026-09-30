# Centaur

Harness de skills para guiar Codex e Claude Code pelos projetos, com uso principal no terminal. A IA coordena o trabalho; o humano define comportamentos e limites. Specs organizam entregas, contratos definem o aceite e evidências permitem conferir o resultado.

## Uso no terminal

Peça o trabalho em linguagem natural ou invoque a skill. O Centaur apresenta um resumo do resultado, validação, bloqueios e próximo passo; detalhes ficam nos arquivos vinculados em `.centaur/`.

```text
/centaur-driven-spec Planeje a busca e a exportação como entregas independentes
/centaur-driven-run master/0001
/centaur-driven-check Qual o estado das specs e o próximo passo?
```

Essas são instruções para as skills dentro da sessão de IA, não comandos executáveis do shell. Também é possível pedir: “Retome a spec 0001 e use agentes nas tasks independentes”. A disponibilidade de agentes depende do cliente; um único agente pode executar as tasks sequencialmente. O run executa uma spec por chamada.

Várias specs podem coexistir no mesmo projeto e no mesmo escopo. Cada uma mantém objetivo, aceite, responsável, arquivos previstos, dependências e estado próprios. Use spec mestre/filhas somente quando houver uma entrega conjunta a integrar. O coordenador reserva cada spec antes de executar, compara interferências entre tasks e consolida alterações compartilhadas serialmente. Em terminais separados, uma spec reservada por outra sessão aguarda; tarefas independentes continuam. Veja [concorrência e retomada](centaur-driven-graphify/references/team-workspace.md).

Uma consulta de andamento pode ser tão curta quanto:

```text
Spec         Estado          Próximo passo
master/0001  Em andamento    Validar busca
master/0002  Bloqueada       Aguarda master/0001 — Task 02 integrada
```

Os estados refletem os registros reais. Teste aprovado não equivale a integração, e checklist não comprova comportamento. O fluxo pelo terminal usa diretamente specs, fontes e evidências.

## Instalação e atualização neste PC

Requer Python 3.10+, Git e a skill completa [clean-code](https://github.com/btseee/clean-code-skills), incluindo suas referências. Skills são instaladas no Codex em `~/.agents/skills/` e no Claude Code em `~/.claude/skills/`.

```bash
git clone https://github.com/Dalistor/Centaur-Driven.git
cd Centaur-Driven
mkdir -p ~/.agents/skills ~/.claude/skills
# Inspecionar a substituição antes de aplicar:
python3 scripts/install.py --root . --target ~/.agents/skills --target ~/.claude/skills
python3 scripts/install.py --root . --target ~/.agents/skills --target ~/.claude/skills --apply
```

O instalador substitui as skills Centaur nos destinos escolhidos, remove a antiga `centaur-driven-commitAndPush` e preserva outras skills. Backups ficam em `.centaur/backups/`. Reinicie as sessões dos agentes para carregar as instruções novas.

Neste repositório de distribuição, `.centaur/` guarda somente o contexto local e fica fora do versionamento. Nos projetos que usam as skills, siga a política de versionamento das definições, specs e evidências descrita abaixo.

Instale `clean-code` completo no mesmo diretório de skills, caso ausente; não copie apenas `SKILL.md`. Referência da integração: 3.2.0. Não é necessário instalar Graphify nem ai-memory para usar busca direta e registros em arquivos.

## Skills

| Skill | Finalidade |
| --- | --- |
| `centaur-driven-start-project` | Inicializar instruções, escopos e conceito do projeto. |
| `centaur-driven-spec` | Definir contratos e planejar entregas verificáveis. |
| `centaur-driven-run` | Executar entregas, consolidar evidências e integrar conforme autorização. |
| `centaur-driven-implement` | Mudanças diretas de estrutura, configuração e UI, com validação proporcional. |
| `centaur-driven-tdd` | Regras de negócio e correções relevantes guiadas por testes. |
| `centaur-driven-check` | Responder com base nas fontes atuais, sem alterar arquivos. |
| `centaur-driven-security` | Auditar segurança e relatar evidências, sem corrigir automaticamente. |
| `centaur-driven-mcp` | Consultar APIs externas e encaminhar o trabalho à skill apropriada. |
| `centaur-driven-graphify` | Investigar relações e manter índices/mapas sob demanda. |
| `centaur-driven-memory` | Configurar e consultar ai-memory ou registrar histórico verificado. |
| `centaur-driven-update` | Migrar/reconstruir estrutura gerada e verificar dependências, preservando definições. |
| `centaur-driven-deploy` | Preparar GitHub Actions e acessos, com instruções para publicação. |

## Conceito, requisitos e realização

A [base conceitual](centaur-driven-graphify/references/specification.md) integra ao contrato:

- Conceito, objetivos, escopo e exclusões.
- Requisitos funcionais e não funcionais, com critérios verificáveis.
- Casos de uso com atores, pré-condições, fluxos, alternativas e falhas.
- Entidades, atributos, relacionamentos, cardinalidades e regras de integridade.

Os requisitos usam `rules`, com `kind: functional | non_functional`; atores, casos de uso e dados usam o campo opcional `specification`. Contratos antigos continuam válidos. Casos de uso referenciam regras existentes e relacionamentos referenciam entidades declaradas; o validador recusa referências inválidas.

Contratos aprovados são versionados, sem reescrita silenciosa. O estado liga regras a arquivos e testes; evidências registram método, resultado e hashes. Alterações em fontes ou definições tornam evidências anteriores desatualizadas. Implementação, verificação e publicação são estados distintos. Veja [ciclo e formatos](centaur-driven-graphify/references/lifecycle.md).

Comece por uma funcionalidade de ponta a ponta. O planejamento da entrega fica nas specs; definições não precisam ser repetidas em vários documentos. Fluxogramas editáveis são rascunhos até serem incorporados ao contrato aprovado.

## Arquivos do projeto

```text
projeto/
├── AGENTS.md                     # Entrada mínima de instruções para agentes
├── .github/workflows/            # Workflows no caminho exigido pelo GitHub
└── .centaur/
    ├── workspace.json           # Escopos, responsáveis e backend de memória
    ├── contracts/<id>/vNNN.json  # Conceito e requisitos versionados
    ├── state/                   # Realização atual por regra
    ├── evidence/                # Verificações imutáveis
    ├── specs/                   # Planos de entrega
    ├── system/                  # Documentação gerada, fluxos e decisões
    ├── use-cases/               # Rascunhos visuais
    ├── graphify/                # Índice e caches opcionais
    ├── ai-memory/               # Configuração e arquivos locais de memória
    ├── implements/              # Registros no backend files ou histórico legado
    ├── deploy/                  # Scripts e artefatos auxiliares de deploy
    ├── worktrees/               # Execuções isoladas de agentes
    ├── backups/                 # Recuperação de migrações/instalações
    └── tmp/                     # Preparação temporária
```

Todos os artefatos gerados do Centaur ficam sob `.centaur/`. Exceções de integração mantêm o caminho exigido pelo consumidor: `AGENTS.md`, `.github/workflows/` e configuração do editor. Código do produto, instalação global de ferramentas e documentos independentes do usuário não são movidos para essa pasta.

Versione definições, estado e evidências. Ignore caches, temporários, backups, worktrees, artefatos de build e segredos. Um store ai-memory compartilhado continua sob administração do serviço; apenas os arquivos locais do projeto são centralizados.

## Contexto e memória

Busca textual e símbolos do editor são a primeira opção. Graphify é opcional para relações amplas; não há indexação automática após cada edição, commit ou entrega. Confirme resultados no código atual.

Para usar Graphify, instale `graphifyy` (`uv tool install graphifyy`) e registre a skill oficial com `graphify install --platform agents` ou `--platform claude`. Referência verificada: 0.9.65. O adaptador define `GRAPHIFY_OUT` para `.centaur/graphify/`:

```bash
python3 /caminho/centaur-driven-graphify/scripts/graphify-local.py /projeto query "dependências do módulo" --budget 1500
# Extração apenas de código, explicitamente solicitada:
python3 /caminho/centaur-driven-graphify/scripts/graphify-local.py /projeto extract --code-only
```

Extração AST não cobre documentação; para corpus misto, siga a skill Graphify com caminhos adaptados. Consulte [contexto e limites](centaur-driven-graphify/references/context.md).

Ai-memory é opcional. A [skill de memória](centaur-driven-memory/SKILL.md) verifica serviço e cliente antes de ativar `memory.backend: ai-memory`. A identidade reside em `.centaur/ai-memory/config.toml`, com `workspace` e `project` explícitos em cada chamada. Não dependa da descoberta automática do marcador antigo na raiz. Falhas preservam registros em `.centaur/ai-memory/pending/`. Sem backend configurado, use `files`; nenhum projeto muda silenciosamente de backend. Consulte [contrato de memória](centaur-driven-memory/references/contract.md).

## Update seguro

`/centaur-driven-update` inventaria, verifica dependências, prepara a nova estrutura, valida e substitui somente após os checks. Preserva contratos, requisitos, evidências, decisões e configurações; falhas obrigatórias mantêm a instalação anterior.

O [migrador](centaur-driven-update/scripts/migrate.py) move `graphify-out/`, configuração e fila antigas do ai-memory. Documentos gerados em `docs/system/` devem ser identificados com `--owned-doc`; arquivos vivos cujas referências precisam mudar usam `--reference`. Não sobrescreve conflitos nem move documentos manuais por suposição. Reexecução não duplica dados. Veja o [fluxo completo](centaur-driven-update/SKILL.md).

```bash
python3 /caminho/centaur-driven-update/scripts/migrate.py --root /projeto
# Após revisar o inventário, aplicar no escopo autorizado:
python3 /caminho/centaur-driven-update/scripts/migrate.py --root /projeto --apply
```

As páginas de acompanhamento geradas antigas são removidas quando reconhecidas; HTML personalizado é preservado.

## Deploy

`/centaur-driven-deploy` prepara o workflow e orienta os próximos passos, sem publicar nem executar o workflow. Pergunta entre push na `main` e execução manual; reutiliza SSH ou gera chave se faltar; fornece o comando de autorização da chave pública na VPS. Configura Environment, variables e secrets se houver acesso suficiente ao GitHub.

O workflow testa a integridade antes da publicação, transfere uma release isolada com retry limitado e só troca tráfego após health checks. Preserva dados e versão anterior para rollback. O template estático usa troca atômica; serviços dinâmicos precisam de estratégia específica, como blue-green. Infraestrutura e migrações incompatíveis com zero downtime são pendências explícitas. Veja [deploy e pré-requisitos](centaur-driven-deploy/SKILL.md).

## Verificação do conjunto

```bash
python3 -m unittest discover -s tests -v
```

VPS real depende do ambiente de uso. O conjunto não alega deploy remoto apenas por passar nos testes locais.
