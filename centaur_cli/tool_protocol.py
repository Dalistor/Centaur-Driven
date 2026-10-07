"""Shared typed validation before any backend tool batch can execute."""

def validate_arguments(value, spec):
    """Validate the entire typed batch before returning any executable call."""
    kind = spec.get('type')
    valid = {'string': lambda: isinstance(value, str), 'integer': lambda: type(value) is int,
             'number': lambda: type(value) in (int, float), 'boolean': lambda: type(value) is bool,
             'array': lambda: isinstance(value, list), 'object': lambda: isinstance(value, dict)}
    if kind in valid and not valid[kind]():
        raise ValueError('Argumentos devem respeitar os tipos da ferramenta.')
    if 'enum' in spec and value not in spec['enum']:
        raise ValueError('Opção de ferramenta fora do catálogo permitido.')
    if kind == 'string' and len(value) > spec.get('maxLength', float('inf')):
        raise ValueError('Texto excede o limite da ferramenta.')
    if kind in ('integer', 'number') and not spec.get('minimum', -float('inf')) <= value <= spec.get('maximum', float('inf')):
        raise ValueError('Número fora do limite da ferramenta.')
    if kind == 'array':
        if not spec.get('minItems', 0) <= len(value) <= spec.get('maxItems', float('inf')):
            raise ValueError('Quantidade de itens fora do contrato.')
        for item in value:
            validate_arguments(item, spec['items'])
    if kind == 'object':
        properties = spec['properties']
        if set(value) - set(properties) or not set(spec.get('required', [])) <= set(value):
            raise ValueError('Argumentos fora do contrato da ferramenta; tente novamente com /retry.')
        for name, item in value.items():
            validate_arguments(item, properties[name])

def omit_optional_nulls(value, spec):
    if isinstance(value, dict) and spec.get('type') == 'object':
        return {key: omit_optional_nulls(item, spec['properties'].get(key, {}))
                for key, item in value.items() if key not in spec['properties'] or item is not None or key in spec.get('required', [])}
    if isinstance(value, list) and spec.get('type') == 'array':
        return [omit_optional_nulls(item, spec['items']) for item in value]
    return value


