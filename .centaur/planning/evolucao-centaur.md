# Evolução do Centaur

**Status:** implementação autorizada pelo usuário nesta conversa em 29/09/2026, incluindo instalação local, commit e push. Este documento preserva o escopo aprovado; resultados e limites ficam no [registro da entrega](../implements/evolucao-2026-09-29.md).

## 1. Experiência no editor

Manter o desenvolvedor no controle, com código e produto em execução no centro do trabalho:

- Volante como apoio contextual atualizado: funcionalidade → regras → código → testes e evidências.
- Navegação por fluxos e, quando houver instrumentação, inspeção de valores e erros de execução.
- Autocomplete com IA usando o contexto do projeto, conforme a integração disponível.
- Delegação de mudanças delimitadas, com revisão do diff e retomada da edição manual a qualquer momento.

**Primeiro recorte:** selecionar uma funcionalidade, localizar código e testes, alterar e conferir o resultado. Autocomplete e inspeção de execução ficam para etapas seguintes.

Remover o HTML de acompanhamento e sua geração — chamado de `acompanhamento.html` na conversa e identificado como `andamento.html` no repositório — e a skill `centaur-driven-commitAndPush`, incluindo suas referências.

## 2. Organização e contexto

Centralizar os artefatos gerados pelo Centaur em `.centaur/`: documentação, memória local, índices, caches, relatórios, estados, evidências, logs, backups e temporários.

| Conteúdo | Destino |
| --- | --- |
| Graphify, hoje em `graphify-out/` | `.centaur/graphify/` |
| Arquivos locais de memória e sincronização do ai-memory | `.centaur/ai-memory/` |
| Demais artefatos, incluindo documentação gerada em `docs/system/` | Subdiretórios de `.centaur/`, a definir |

Versionar definições duráveis no Git; caches e temporários não precisam ser versionados. Código do produto e documentos independentes, preexistentes ou mantidos manualmente permanecem em seus locais.

Priorizar busca e símbolos do editor. Graphify será usado sob demanda em investigações amplas, sem indexação obrigatória nas tarefas comuns. Medir ganho de tempo ou qualidade antes de automatizar sua atualização; esse ganho ainda não foi demonstrado no projeto.

## 3. Base conceitual

Integrar a especificação aos contratos existentes, mantendo uma fonte de verdade e vínculos com código, testes e evidências.

| Elemento | Definição |
| --- | --- |
| Conceito e escopo | Problema, público, objetivos e exclusões. |
| Requisitos funcionais | Comportamentos oferecidos. |
| Requisitos não funcionais | Critérios mensuráveis de qualidade, conforme o projeto. |
| Casos de uso | Atores, pré-condições, fluxo principal, alternativas e falhas. |
| Modelo de dados | Entidades, relacionamentos, cardinalidades e integridade. |

Uma versão aprovada estabiliza o conceito; mudanças exigem revisão explícita da definição. Começar por uma funcionalidade de ponta a ponta, sem exigir a especificação completa do sistema.

## 4. Skill `update`

Reconstruir a estrutura gerada com segurança, preservando requisitos, contratos, decisões, evidências, memória e configurações.

1. Inventariar e preservar o conteúdo durável.
2. Testar o funcionamento das dependências e o acesso aos serviços configurados: Graphify sem indexação completa; ai-memory com conexão e acesso quando configurado.
3. Preparar a estrutura atualizada em área temporária dentro de `.centaur/`, migrando conteúdo e regenerando apenas o necessário.
4. Validar caminhos, referências, comandos e integrações.
5. Substituir a estrutura anterior somente após aprovação das verificações, mantendo backup recuperável em `.centaur/`.

**Migração obrigatória:** localizar os artefatos do Centaur fora de `.centaur/` e movê-los para os destinos definidos, atualizando referências em scripts, skills e configurações. Reaproveitar índices quando possível, tratar conflitos sem sobrescrever conteúdo silenciosamente e remover origens somente após validar a transferência.

**Critérios de aceite:** falhas obrigatórias preservam a instalação anterior; repetir o update não duplica nem perde arquivos; código e arquivos independentes do usuário permanecem intactos.

## 5. Skill `deploy`

Preparar o workflow do GitHub Actions, configurar os acessos possíveis e orientar os próximos passos. A skill não publica diretamente nem dispara o workflow.

### Preparação

- Perguntar se o gatilho será push na `main` ou execução manual (`workflow_dispatch`).
- Reutilizar chave SSH adequada; gerar somente se faltar, sem sobrescrever chaves existentes. Fornecer o comando para autorizar a chave pública na VPS quando necessário, sem expor a chave privada.
- Configurar Environment, variables e secrets quando houver autenticação e permissões no GitHub. Caso contrário, fornecer as instruções de configuração; acesso ao Git local não basta.
- Informar arquivos gerados, configurações realizadas, pendências e como executar e acompanhar o workflow.

### Execução do workflow

1. **Integridade:** executar testes apropriados ao projeto e validar os artefatos. Falha bloqueia a publicação.
2. **Publicação:** enviar uma versão limpa para ambiente isolado, com retry limitado e intervalo para falhas transitórias de transferência. Esgotar tentativas deve resultar em falha; a reexecução deve ser segura.

**Sem downtime:** manter a versão atual atendendo durante a preparação, validar a nova com health checks e então trocar o tráfego. A estratégia depende do runtime: troca atômica para estáticos ou, por exemplo, blue-green com proxy e drenagem de conexões para serviços.

Preservar dados, uploads e configuração separadamente. Verificar a saúde após a troca, acionar rollback em caso de falha e limpar versões antigas somente após validação, mantendo uma versão recuperável. Migrações de banco devem permitir coexistência das versões e considerar limites de rollback. Infraestrutura incompatível com ausência de downtime deve ser apontada como pendência.

## 6. Pontos a definir

- Estrutura definitiva dos documentos, identificadores, schemas e vínculos com os contratos atuais.
- Integrações de autocomplete, atualização do contexto e instrumentação de execução.
- Estratégia de deploy por runtime, testes de integridade, política de retry e retenção de versões.
- Compatibilizar a centralização em `.centaur/` com arquivos de integração que exigem localização própria, como o workflow em `.github/workflows/`.
