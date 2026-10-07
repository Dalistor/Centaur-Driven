"""Shared, cycle-safe ancestry and ordering for agent navigation."""


class AgentTree:
    def __init__(self, records=()):
        self.records = {record['id']: record for record in records}
        self.children = {}
        for record in self.records.values():
            self.children.setdefault(record.get('parent_id'), []).append(record)
        for children in self.children.values():
            children.sort(key=lambda r: (r.get('created', r.get('updated', '')), r['id']))

    def lineage(self, record):
        path, seen = [record], {record['id']}
        parent = record.get('parent_id')
        while parent and parent not in seen:
            seen.add(parent)
            ancestor = self.records.get(parent)
            if ancestor is None:
                path.append({'id': parent, 'title': 'Agente indisponível'})
                break
            path.append(ancestor)
            parent = ancestor.get('parent_id')
        return list(reversed(path))

    def principal(self, record):
        return self.lineage(record)[0]

    def label(self, record):
        return f'{record["title"]} [{record["id"][:8]}]'

    def prefix(self, record):
        path = self.lineage(record)
        if len(path) == 1:
            return '◆ '
        parts = []
        for ancestor in path[1:]:
            siblings = self.children.get(ancestor.get('parent_id'), [])
            last = not siblings or siblings[-1]['id'] == ancestor['id']
            parts.append(('└─↳ ' if last else '├─↳ ') if ancestor['id'] == record['id']
                         else ('   ' if last else '│  '))
        return ('… ' if len(parts) > 4 else '') + ''.join(parts[-4:])

    def ordered(self):
        roots = [r for r in self.records.values() if r.get('parent_id') not in self.records]
        roots.sort(key=lambda r: (r.get('updated', ''), r['id']), reverse=True)
        result, visited = [], set()
        # Iterative traversal also tolerates imported deeply nested histories.
        for root in [*roots, *self.records.values()]:
            pending = [root]
            while pending:
                record = pending.pop()
                if record['id'] in visited:
                    continue
                visited.add(record['id'])
                result.append(record)
                pending.extend(reversed(self.children.get(record['id'], [])))
        return result
