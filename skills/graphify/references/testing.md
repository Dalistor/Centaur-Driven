# Testes nos pontos vitais

Esta é a política de testes do ciclo Centaur, aplicada no planejamento, implementação,
TDD, delegação e revisão. Instruções explícitas do usuário, critérios aprovados e gates
obrigatórios do projeto prevalecem. Não reduza um gate existente para obter verde.

## Decidir antes de criar

O padrão é **reaproveitar proteção existente e não adicionar teste automaticamente**.
Ser testável, ter um bug ou aparecer em um critério de aceite não basta para exigir
um teste novo. Toda entrega precisa de verificação adequada; nem toda verificação
precisa virar um arquivo permanente na suíte.

Crie ou amplie um teste somente quando as três condições forem atendidas:

1. Há uma falha concreta identificada, não uma possibilidade genérica do checklist.
2. Ela afeta um ponto vital da entrega ou do sistema.
3. Nenhum teste existente protege suficientemente esse risco; atualizar um caso
   existente é preferível a criar uma cópia.

Pontos vitais são comportamentos cujo defeito compromete um fluxo principal,
uma regra essencial ou produz dano relevante. Exemplos:

- Autenticação, autorização, isolamento, privacidade e permissões de execução.
- Integridade/persistência dos dados, migrações, valores financeiros e operações
  irreversíveis ou que não podem ser repetidas.
- Invariantes essenciais do domínio e resultados centrais para o usuário.
- Contratos críticos entre serviços/provedores, concorrência, idempotência,
  recuperação, cancelamento e deadlines quando uma falha pode duplicar ações,
  perder trabalho ou deixar o fluxo principal preso.

O nome do componente não torna todos os seus métodos vitais. Teste a consequência
importante pela interface observável. Uma integração crítica pode ter um teste de
contrato bem escolhido; não exige uma matriz de todos os campos e combinações.

Ajustes de texto, cor, espaçamento, renomeações, getters/setters, mapeamento direto,
configuração trivial e helpers sem decisão relevante normalmente dispensam testes
novos. Se o contexto lhes der consequência vital, explique essa consequência e
aplique o mesmo filtro. Regressão de alto impacto merece proteção; correção cosmética
não ganha teste automaticamente só por ser chamada de bug.

## Escolher a menor proteção suficiente

- Consulte primeiro os testes pertinentes. Preserve, atualize ou consolide os que
  já protegem o comportamento; não duplique por task, arquivo, camada ou subagente.
- Escolha um nível que detecte a falha real: unidade para uma regra isolável;
  integração/contrato para uma fronteira; ponta a ponta para um fluxo principal
  que não possa ser protegido suficientemente nos níveis anteriores.
- Não repita a mesma proteção em unidade, integração e E2E sem riscos distintos.
  Parametrize poucos casos que distingam resultados relevantes; não enumere todas
  as combinações ou divida cada asserção em um teste.
- Não teste detalhes privados, constantes isoladas, texto-fonte ou mocks que só
  confirmam chamadas da própria implementação. Não crie infraestrutura ou fixtures
  extensas para um comportamento de baixo impacto.
- Use TDD quando houver uma lacuna vital a proteger e infraestrutura disponível,
  ou quando explicitamente solicitado. Sem essa lacuna, use implementação direta
  e validação proporcional. A dependência clean-code não amplia essa obrigação.
- Pare quando os riscos vitais da mudança estiverem protegidos e o aceite verificado.
  Não persiga contagem, cobertura total, testes por função ou uma bateria por entrega.

Na spec/registro existente, indique brevemente o risco vital e a proteção reutilizada
ou necessária; fora dos pontos vitais, indique a verificação escolhida. Não crie um
novo documento, formulário ou aprovação só para justificar não adicionar testes.
O coordenador inclui essa decisão na task e confere duplicações entre executores.

## Verificar sem inflar a suíte

Durante a edição, rode a seleção existente relacionada. Amplie para consumidores
afetados, lint/type-check, build, inspeção ou demonstração conforme a mudança.
Execute a suíte completa quando exigida pelo projeto/CI ou justificada pelo impacto
transversal; não a repita após cada ajuste sem nova evidência de risco.

Inspeção/demonstração manual registra método, resultado e limites no formato de
evidências já definido pelo ciclo. Build/lint sozinhos não comprovam uma regra
crítica. Nunca registre sucesso sem observar o resultado.

Uma suíte com 700 testes não é, por si só, um defeito nem uma meta. Não imponha teto
numérico, não apague regressões úteis para reduzir a contagem e não faça limpeza
massiva fora do escopo. Ao tocar uma área, consolide redundâncias comprovadas e
remova testes obsoletos somente quando o requisito removido ou a proteção equivalente
estiverem claros. Preserve a proteção dos comportamentos ainda exigidos.
