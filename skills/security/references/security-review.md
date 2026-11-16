# Referência da auditoria de segurança

Leia os focos que correspondem às superfícies encontradas. Este guia orienta perguntas; nenhum item abaixo é um achado sem evidência no alvo.

## Focos por superfície

| Superfície | Perguntas que orientam a investigação |
|---|---|
| Identidade, sessão e autorização | Quem identifica o ator? O servidor verifica ação e recurso, inclusive tenant/proprietário? Expiração, revogação, recuperação e operações administrativas preservam esse vínculo? |
| Entradas e interpretadores | Entrada não confiável alcança SQL, shell, template, desserialização ou HTML? A defesa é adequada ao destino e cobre os caminhos alternativos? |
| Arquivos e requisições externas | Caminhos, uploads, arquivos compactados, URLs e redirects conseguem sair do destino permitido? Há acesso a recursos internos ou dados de outro usuário? |
| Estado e regras sensíveis | Repetição, concorrência ou falha parcial pode duplicar uma operação, quebrar saldo/limite ou separar autorização do uso? O estado persistido corresponde à decisão validada? |
| Segredos e criptografia | Material sensível aparece em logs/respostas/artefatos? Chaves, aleatoriedade, assinatura e verificação são usadas conforme o protocolo real? Uma suspeita criptográfica exige análise específica, não apenas reconhecer um algoritmo. |
| Configuração e defaults | Defaults, modos de depuração, CORS, cabeçalhos, portas e permissões de arquivo/bucket abrem acesso indevido? A configuração de produção difere da revisada, e o que foi de fato verificado? |
| Cadeia de suprimentos e CI | As dependências vêm de lockfile com versões resolvidas e a versão afetada é de fato usada? Scripts de instalação, registries, imagens-base e actions de terceiros são fixados (SHA/digest) e de origem conferida? Inputs de PR ou de fork alcançam execução privilegiada, segredos ou o token do CI? O artefato publicado é o mesmo que foi testado? |
| Falhas e condições excepcionais | Em erro, timeout, exceção ou entrada inesperada, o fluxo nega ou libera (fail-open)? Um erro parcial deixa estado inconsistente, pula uma verificação ou vaza detalhe interno na resposta? |
| Registro e alerta | Eventos relevantes para segurança (login, falha de autorização, mudança de permissão, operação administrativa) ficam registrados com ator e recurso, sem segredos nem dados pessoais desnecessários? Alguém é avisado, ou o log só existe? Entrada controlável consegue forjar ou apagar registros? |
| IA, agentes e ferramentas | Texto não confiável (arquivos, páginas, saídas de ferramentas, mensagens de outros agentes) chega ao modelo como instrução? O agente pode executar comandos, gravar arquivos ou gastar recursos além do que a tarefa exige, e quem aprova as ações arriscadas? Segredos entram em prompts, histórico ou logs? A saída do modelo alcança shell, SQL ou HTML sem validação? |
| Memória, parsing e recursos | Dados controláveis causam acesso inválido, overflow relevante ou consumo desproporcional de CPU/memória/disco? Limites e condições reais de disparo sustentam o impacto alegado? |

Para conferir se alguma superfície ficou de fora, use como índice o [OWASP Top 10:2025](https://owasp.org/Top10/2025/) e, em sistemas com modelos de linguagem, o [OWASP Top 10 para aplicações LLM](https://genai.owasp.org/llm-top-10/). São listas de categorias de risco, não roteiros: a ordem da auditoria continua sendo impacto e exposição no alvo.

Não trate uma lista parcial como auditoria completa. Uma aplicação web, biblioteca nativa e smart contract exigem análises distintas. Quando faltar conhecimento ou tooling de uma superfície especializada, delimite a conclusão.

## Formato do relatório

Adapte o tamanho ao resultado; não crie seções vazias nem findings fictícios. Use um ID estável por achado dentro do relatório, como `SEC-001`.

**Escopo e método:** data real, alvo, revisão/base quando aplicável, estado local, superfícies incluídas, exclusões, ferramentas/regras executadas e limitações. Diferencie arquivos lidos, resultados de scanner e caminhos realmente acompanhados.

**Resumo:** quantidade de confirmados por gravidade, pendentes e refutados pertinentes. Separe observações de proteção adicional sem exploração demonstrada.

Para cada confirmado:

- **ID e título:** descrevem a falha concreta e o recurso afetado.
- **Gravidade e confiança:** Crítica/Alta/Média/Baixa com justificativa contextual; confiança na evidência separada. Use CVSS somente se solicitado ou exigido e com vetor fundamentado.
- **Localização:** arquivo, linha e revisão/lado do diff corretos; caminhos adicionais quando necessários ao fluxo.
- **Condição e impacto:** ator, capacidades prévias, entrada controlável, precondições e consequência demonstrada.
- **Evidência:** percurso até a operação sensível, defesas verificadas e por que não impedem o cenário. Inclua apenas trechos necessários.
- **Validação:** reprodução local com dados sintéticos e resultado, ou análise estática identificada. Não forneça logs contendo segredos.
- **Correção e regressão:** ação sobre a causa e o comportamento que comprovará a correção, sem implementar nesta auditoria.
- **Variantes:** ocorrências relacionadas verificadas e limites da busca, quando houver.

**Pendentes:** alegação, fato ausente, evidência necessária e impacto condicional. Não misture com confirmados nem atribua certeza por falta de acesso.

**Refutados relevantes:** alegação e defesa/condição verificada que a invalida. Não esconda descartes de achados que o usuário pediu conferir.

**Próximos passos:** correções priorizadas e verificações ainda necessárias, sem prometer que a revisão cobriu todo o sistema.

## Atribuição e licença

Esta skill e esta referência são uma adaptação para o Centaur, baseada nas seguintes skills da **Trail of Bits**, consultadas em 2026-09-22:

- [audit-context-building](https://github.com/trailofbits/skills/blob/master/plugins/audit-context-building/skills/audit-context-building/SKILL.md): contexto e rastreamento de pressupostos antes dos veredictos.
- [differential-review](https://github.com/trailofbits/skills/blob/master/plugins/differential-review/skills/differential-review/SKILL.md): revisão de alterações e evidência ligada ao histórico.
- [fp-check](https://github.com/trailofbits/skills/blob/master/plugins/fp-check/skills/fp-check/SKILL.md): tentativa de refutar alegações antes de confirmá-las.
- [variant-analysis](https://github.com/trailofbits/skills/blob/master/plugins/variant-analysis/skills/variant-analysis/SKILL.md): busca de outras ocorrências de uma causa conhecida.

Alterações da adaptação: fluxo único em português, escopos e contratos Centaur, relatório local, ferramentas opcionais, resultado pendente explícito, sem delegação obrigatória e encaminhamento das correções ao TDD/direto. Não é um produto oficial nem implica endosso da Trail of Bits.

Os arquivos desta pasta são distribuídos sob [Creative Commons Attribution-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-sa/4.0/), acompanhando a [licença declarada pelo projeto original](https://github.com/trailofbits/skills#license). Esta declaração abrange a adaptação desta pasta, sem relicenciar os demais arquivos do Centaur.
