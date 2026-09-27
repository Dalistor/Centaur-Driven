#!/usr/bin/env python3
"""Check canonical records; optionally enforce a rule's integration readiness."""
import argparse
import json
from pathlib import Path
from volante import load_project


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('project', type=Path)
    p.add_argument('--ready', help='Qualified rule ID: contract/R1; requires approved contract, implementation and current passing evidence')
    args = p.parse_args()
    try:
        data = load_project(args.project)
        errors = list(data['warnings'])
        if args.ready:
            rule = next((r for c in data['contracts'] for r in c['rules'] if r['key'] == args.ready), None)
            if not rule or not rule['eligible'] or rule['waiting'] or rule['implementation'] != 'implementada' or rule['verification'] != 'aprovada':
                errors.append(f'{args.ready}: contrato, dependências, implementação ou evidências não permitem integração')
        print(json.dumps({'ok': not errors, 'errors': errors, 'revision': data['revision']}, ensure_ascii=False, indent=2))
        return 1 if errors else 0
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(json.dumps({'ok': False, 'errors': [str(error)]}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
