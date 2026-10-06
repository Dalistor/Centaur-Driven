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
| Dependências, CI e configuração | Inputs de PR podem alcançar execução privilegiada ou segredos? Permissões, scripts de instalação, defaults e modos de erro abrem acesso indevido? A versão afetada está de fato resolvida/usada? |
| Memória, parsing e recursos | Dados controláveis causam acesso inválido, overflow relevante ou consumo desproporcional de CPU/memória/disco? Limites e condições reais de disparo sustentam o impacto alegado? |

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
