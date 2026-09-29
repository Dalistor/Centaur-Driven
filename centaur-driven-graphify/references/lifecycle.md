# Ciclo por contratos e evidências

Contrato é o molde humano do sistema. A IA propõe e implementa dentro dele; evidências permitem distinguir intenção, implementação e entrega. Este é o contrato normativo de ciclo de vida de todas as skills Centaur. As demais referências descrevem memória, contexto e concorrência, sem redefinir estados.

## Pré-requisito

Usar Python 3.10+ e a raiz de um projeto com `.centaur/workspace.json` contendo `scopes` não vazio. Cada escopo define `specs` (diretório relativo), `code` (raiz relativa, opcional) e `owner` (opcional); `master` é o escopo inicial. Inicializar com start-project ou preservar o workspace existente. O gerador não cria configuração implicitamente.

## Fontes e precedência

| Fonte | Responsabilidade |
|---|---|
| `.centaur/contracts/<id>/vNNN.json` | Comportamento desejado, aceite, limites, autonomia e autorização; versões preservadas |
| `.centaur/state/<id>.json` | Realização atual de cada regra, fontes, IDs das evidências selecionadas e entrega registrada |
| `.centaur/evidence/<id>.json` | Verificação imutável, resultado, método, revisão e hashes das fontes |
| README da spec | Plano de uma entrega, tasks, dependências e status da execução |
| Registros `files` / ai-memory | Histórico e justificativas, conforme backend; não substituir o estado atual |
| `.centaur/volante.html` | Projeção local dessas fontes e dos trechos explicitamente vinculados |
| `.centaur/use-cases/<id>.json` | Fluxo de uso editável, proposto pela IA ou criado pelo usuário; não altera contrato nem evidência |

Contrato desejado e estado observado são separados. Código que contradiz um contrato aprovado é desvio a investigar; não reescrever o contrato para justificar o código. Instruções explícitas do usuário podem autorizar nova versão; registrar o pedido como referência. Aprovação significa uma decisão de produto registrada, não assinatura criptográfica. Nenhum JSON impede alguém com escrita de falsificá-lo: revisões, permissões do repositório e CI continuam necessários.

Esses registros locais existem com ambos os backends. Não copiar a wiki ou todo o histórico para eles. Fontes canônicas de estado não são `graph.json`, índices ou HTML. Para contratos ligados a specs, o README registra a execução; o estado registra comportamento verificado. Checklist marcado não promove verificação ou publicação.

## Base conceitual

A [especificação](specification.md) integra conceito, requisitos funcionais/não funcionais, casos de uso e dados ao contrato. O campo opcional `specification` e `rules[].kind` são validados e entram no hash de evidências.

## Definir e versionar o molde

- Usar IDs estáveis de capacidades (ex.: `agendamento`) e regras (`RES-01`). Uma regra removida não tem seu ID reutilizado com outro significado.
- Registrar intenção, regras observáveis e aceites; incluir falhas esperadas, permissões e compatibilidade quando relevantes. Dimensionar pelo risco e pelo comportamento, nunca por quota de arquivos/testes.
- Registrar `boundaries` (limites), `autonomy` (decisões delegadas) e `decisions` (lacunas materiais ainda abertas). A autonomia não concede publicação, acesso a serviços ou gastos implicitamente.
- `draft` representa proposta. `approved` exige `approval.by`, `approval.at` e `approval.reference` verificáveis no pedido/documento de decisão. Reutilizar autorização inequívoca da sessão; não pedir confirmação ritual. Inferência sobre código não é aprovação humana.
- Versão aprovada é imutável. Evolução cria `v002.json`, etc.; manter versões anteriores e a razão da alteração na spec/registro. Preservar IDs estáveis de regras. Preparar estado novo explicitamente; não reaproveitar um “aprovado” da versão anterior sem revalidar a cobertura.
- O visor escolhe a maior versão aprovada; mostra versões em rascunho separadamente. Sem aprovada, apresenta o último rascunho e não libera execução. `retired` serve para propostas retiradas; retirar contrato aprovado exige nova versão aprovada que documente a desativação, preservando o original.
- Herança usa `extends: ["sistema@1"]`, com versões fixas e sem ciclos. Contratos herdados precisam estar aprovados. Regras gerais são limites cumulativos; não sobrescrever silenciosamente. Nova versão do pai exige avaliar consumidores e publicar novas versões dos contratos afetados. Regras próprias não repetem as gerais.

Exemplo mínimo de `.centaur/contracts/agendamento/v001.json` (adaptar, nunca registrar a autorização ilustrativa como real):

```json
{
  "schema": 1,
  "id": "agendamento",
  "version": 1,
  "title": "Reservar um horário",
  "scope": "master",
  "status": "draft",
  "intent": "Paciente reserva um horário disponível sem duplicidade.",
  "extends": [],
  "boundaries": ["Preservar autenticação e política de cobrança"],
  "autonomy": ["Organizar funções internas dentro dos limites existentes"],
  "decisions": ["Definir o prazo de cancelamento"],
  "rules": [{
    "id": "RES-01",
    "description": "Impedir duas reservas ativas para o mesmo horário",
    "acceptance": ["Em duas tentativas concorrentes, apenas uma reserva é confirmada"],
    "depends_on": []
  }]
}
```

Ao aprovar, incluir `"approval": {"by": "autor da decisão", "at": "data ISO-8601", "reference": "referência real ao pedido/decisão"}` e remover de `decisions` apenas lacunas resolvidas. Um contrato com decisão material aberta não libera suas regras; separar capacidades independentes em contratos menores para não bloquear o sistema inteiro.

## Executar uma entrega por comportamento

1. Ler a versão vigente, os limites herdados, estado, evidências e código pertinente.
2. Escolher a menor lacuna demonstrável com dependências satisfeitas. Uma entrega pode atravessar camadas; tasks técnicas internas preservam responsabilidade e arquitetura.
3. Registrar contrato/versão, regras, critérios de aceite, impacto previsto, arquivos sob responsabilidade, dependências, modo TDD/direto e destino de integração na spec. Mudança pequena pode usar contrato existente e registro direto, sem spec extensa.
4. Selecionar executor/modelo pelas ferramentas disponíveis, risco, incerteza e orçamento autorizado. Não fixar nomes comerciais, APIs `Agent`, quantidade de agentes ou nível de raciocínio. Registrar executor/modelo quando conhecido, sem inventar. Um único executor é válido.
5. Replanejar detalhes dentro da autonomia, registrando motivo e diferença entre impacto previsto/real. Mudança de comportamento, permissões, limites, compatibilidade ou custo autorizado pede decisão. Não alterar cláusula para fazer teste passar.
6. Implementar e verificar. Em falha, corrigir dentro do escopo ou registrar bloqueio; dependências independentes podem continuar. Subagentes reportam evidências e deltas de estado; somente o coordenador consolida fontes compartilhadas.
7. Demonstrar antes/depois, decisões tomadas, desvios e limites da prova. Rodar o gate das regras da entrega antes de integrar. Só registrar publicação após observar resultado no destino autorizado.

## Estado observado e evidências

`.centaur/state/agendamento.json`:

```json
{
  "schema": 1,
  "contract": "agendamento@1",
  "rules": {
    "RES-01": {
      "implementation": "parcial",
      "sources": [{"path": "src/reservas.py", "start": 10, "end": 40, "role": "Controle de concorrência"}],
      "evidence": [],
      "delivery": {"stage": "local"},
      "specs": ["master/0001"],
      "notes": "Falta verificar duas tentativas simultâneas."
    }
  }
}
```

- Implementação: `ausente`, `parcial`, `implementada`. Declarar implementada exige inspeção e fontes existentes; a ferramenta rebaixa declaração sem fontes para parcial.
- Verificação é **derivada**, nunca editada: `não verificada`, `aprovada`, `falhou`, `desatualizada`. Exige vínculo à regra e versão, hash do contrato e herança, resultado e hashes dos arquivos. Evidência ausente/malformada não aprova. Falha corrente bloqueia; hash divergente invalida. `evidence` seleciona os registros correntes que cobrem o aceite; histórico antigo permanece em disco, sem bloquear por uma falha já substituída.
- Entrega é independente: `local`, `integrated`, `published`. As duas últimas exigem `reference`, `revision` e `at`; indicar alvo/ambiente na referência. A ferramenta verifica o formato, não consulta deploy remoto. Conferir integração, CI e ambiente pelas ferramentas reais antes de registrar. Evidência envelhecida não apaga uma publicação histórica; o visor mostra as duas dimensões.
- Ausência de testes não autoriza “aprovada” sem prova. Inspeção ou demonstração manual são possíveis, com método e limitação explícitos. Uma execução bem-sucedida só prova o que foi observado; build ou lint isolados não comprovam regra de negócio.
- Registrar fontes de produção **e** testes, configurações, contratos de integração e dependências afetadas que sustentam a evidência. Hash de um arquivo não captura automaticamente toda a árvore de dependências. Mudanças indiretas detectadas exigem ampliar fontes e verificar novamente. Não prometer precisão absoluta sobre comportamento a partir de hashes.

Evidência imutável (`.centaur/evidence/ev-<uuid>.json`) exige `schema: 1`, `id`, `contract: "agendamento@1"`, `rule`, `contract_hash`, `method` (`test`, `manual`, `inspection`, `integration`), `result` (`passed`, `failed`), `at`, `summary`, `reference` e `files` (mapa caminho → SHA-256). Registrar `revision` e `command` quando disponíveis. `contract_hash` é calculado pela projeção `load_project` em `scripts/volante.py`, incluindo herança fixada; não calcular com serialização diferente.

Para checks executáveis, usar o capturador (não colocar credenciais em argumentos):

```bash
python3 /skill/centaur-driven-graphify/scripts/record-evidence.py /projeto agendamento/RES-01 --summary "Duas tentativas geram só uma reserva" --file tests/test_reservas.py -- python3 -m pytest tests/test_reservas.py
```

Para regra nova ou execução delegada sem estado consolidado, informar todos os arquivos de produção/testes/configuração pertinentes com `--file`; o capturador não exige criar estado antes. Se já houver fontes no estado, elas são incluídas junto dos arquivos adicionais. O comando roda de fato, sem shell; só registra `passed` com saída zero e fontes estáveis durante a execução. Não altera estado nem aprova contrato. Conferir se o check cobre os critérios e vincular o ID retornado no estado. Captura manual precisa registrar o procedimento, resultado observado e referência, nunca inventar uma execução.

## Gates e próximos passos

```bash
python3 /skill/centaur-driven-graphify/scripts/validate-lifecycle.py /projeto
python3 /skill/centaur-driven-graphify/scripts/validate-lifecycle.py /projeto --ready agendamento/RES-01
# Exportação HTML opcional:
python3 /skill/centaur-driven-graphify/scripts/render-volante.py /projeto
```

O primeiro valida integridade dos registros; saída zero **não significa** projeto concluído. `--ready` verifica aprovação, ausência de lacunas materiais, dependências implementadas/verificadas/integradas, fontes e evidência corrente da regra. Aplicar para cada regra da entrega e os gates reais do projeto. Conectar a CI quando autorizado; um script que ninguém executa não bloqueia publicação.

| Lacuna | Próximo passo |
|---|---|
| Registro inválido | Corrigir rastreabilidade; não declarar pronto |
| Contrato rascunho/lacuna material | Apresentar decisão humana com alternativas e impactos |
| Dependência sem entrega integrada e verificada | Aguardar ou executar a dependência |
| Implementação ausente/parcial | Implementar comportamento |
| Prova falhou | Corrigir e verificar |
| Prova ausente/desatualizada | Verificar antes de integrar |
| Implementada, verificada, local | Integrar sob autorização existente |
| Integrada | Avaliar publicação conforme pedido; não publicar automaticamente |
| Publicada | Observar sinais e critérios definidos para o ambiente |

Regras `depends_on` usam IDs `contrato/REGRA` da versão vigente daquele contrato; revisar planos quando uma versão mudar. Ciclos e referências ausentes bloqueiam, não produzem fila fictícia. A política conservadora requer dependência integrada antes de liberar a próxima; duas regras que precisam integrar juntas pertencem à mesma entrega, sem dependência circular entre elas.

## Estado das specs e migração

Specs são planos finitos e preservam histórico. Estados únicos: `Pendente`, `Em andamento`, `Bloqueada`, `Em revisão`, `Concluída`, `Cancelada`. `Concluída` exige tasks, critérios de aceite, evidências correntes e integração da entrega e das filhas. Publicação é separada, salvo se fizer parte do aceite. Checkboxes sozinhos nunca concluem a spec. `Cancelada` exige decisão explícita.

Ao migrar: preservar IDs, READMEs, aprovações e registros históricos; adicionar vínculos novos sem reescrever conclusões antigas. Spec legada sem contrato aparece com verificação desconhecida. Criar contratos inferidos como rascunho; reutilizar requisitos já autorizados apenas com referência. Não gerar contratos fictícios para preencher o visor. Evoluir primeiro a área solicitada; não exigir conversão integral antes de trabalhar.

## Atualizar o Volante

O explorador nativo acompanha mudanças salvas nos contratos e fontes vinculadas. O HTML é exportação opcional, gerada ao abrir o painel de fluxos/agentes ou por pedido explícito. Consultas puras não escrevem arquivos; a validade de evidências é conferida nas fontes atuais, independentemente de exportação.

O HTML avulso é autocontido e não executa comandos; a extensão VS Code é um hospedeiro opcional que oferece modelo de linguagem, persistência de casos de uso e executores locais. Contratos e Código priorizam resumos e permitem aprofundar somente quando solicitado; Casos de uso expõe fluxos salvos em `.centaur/use-cases/<id>.json`. Fluxos gerados por IA são rascunhos e exigem revisão antes de salvar. Um fluxo salvo não autoriza a execução de regra bloqueada nem comprova implementação. O painel também preserva specs e documentos. Trechos são explicitamente selecionados (até 120 linhas por fonte), nunca varrer/copiar todo o repositório ou incluir segredos. A IA revisa o conteúdo antes de vincular fontes. Não publicar o HTML automaticamente: contém código do projeto. Data/revisão visíveis e comparação de hashes ocorrem **na geração**, não enquanto a página está aberta.

A extensão só inicia perfil de agente configurado após ação explícita em regra elegível, com um worktree/branch isolado por execução, sem integração ou publicação automática. O executor deve conferir o contrato fixado, limites e fontes; o operador revisa diff, evidências e resultado antes de consolidar. Notas continuam locais ao navegador; a chave antiga de `andamento.html` é reutilizada. Exportar contexto produz um pedido revisável com notas, limites, estado e fontes, sem alterar o projeto ou conceder autorização. `render-dashboard.py` permanece como entrada compatível; não cria páginas de acompanhamento antigas.
