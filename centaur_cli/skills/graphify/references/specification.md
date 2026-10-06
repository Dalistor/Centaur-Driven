# Base conceitual do sistema

A definição aprovada vive no próprio contrato versionado; não mantenha um catálogo de requisitos contraditório em outro arquivo. Documentos em `.centaur/system/` explicam e vinculam a definição, sem duplicá-la.

- `intent`, `title`, `boundaries` e `specification.exclusions`: conceito, objetivos, escopo e exclusões.
- `rules[].kind`: `functional` (padrão compatível com contratos antigos) ou `non_functional`. IDs estáveis, como RF-01/RNF-01; aceite verificável e mensurável. Para desempenho, explicitar carga, ambiente, janela e limite, sem inventar metas.
- `specification.actors` e `use_cases`: atores, pré-condições, passos, alternativas/falhas, pós-condições e IDs das regras locais atendidas.
- `specification.data_model`: entidades, atributos, relacionamentos, cardinalidades e invariantes.
- Estado e evidências existentes ligam as regras a fontes de produção, testes e verificações. Alterar uma definição aprovada exige nova versão; o hash do contrato invalida evidências antigas.

`specification` é opcional para manter contratos antigos válidos. Na criação/evolução, documente somente os elementos pertinentes à funcionalidade; campos vazios são aceitáveis quando não se aplicam, nunca como aprovação de lacunas. Referências inválidas são recusadas pelo validador.

Exemplo de campos a adicionar ao contrato (ilustrativo, não representa aprovação):

```json
{
  "specification": {
    "actors": ["Paciente"],
    "exclusions": ["Processamento de pagamentos"],
    "use_cases": [{
      "id": "UC-01",
      "title": "Reservar consulta",
      "actor": "Paciente",
      "preconditions": ["Paciente autenticado"],
      "main_flow": ["Consultar horários", "Selecionar horário", "Confirmar reserva"],
      "alternatives": ["Horário ocupado: informar indisponibilidade e permitir nova seleção"],
      "postconditions": ["Reserva vinculada ao paciente e ao horário"],
      "rules": ["RF-01"]
    }],
    "data_model": {
      "entities": [
        {"name": "Paciente", "attributes": ["id"], "invariants": ["id único"]},
        {"name": "Reserva", "attributes": ["id", "paciente_id", "horário"], "invariants": ["Horário não admite reservas ativas sobrepostas"]}
      ],
      "relationships": [{"from": "Paciente", "to": "Reserva", "cardinality": "1:N", "invariants": ["Toda reserva pertence a um paciente existente"]}]
    }
  }
}
```

O editor de fluxos em `.centaur/use-cases/` continua sendo rascunho visual. A proposta só passa a definição normativa quando integrada a uma versão do contrato conforme autorização; salvar um fluxograma não aprova requisitos.

Comece por uma funcionalidade demonstrável. A skill `spec` escreve essa definição e a entrega correspondente; `start-project` identifica o conceito inicial; `update` preserva definições e registra lacunas sem inferir aprovação.
