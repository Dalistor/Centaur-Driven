#!/usr/bin/env python3
"""Generate .centaur/volante.html, an offline, read-only code and contract viewer."""
import argparse
import html
import json
import os
import re
from pathlib import Path
import tempfile
from volante import load_project, project_path


def render(project):
    data = load_project(project)
    payload = json.dumps(data, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    template = Path(__file__).with_name('volante-template.html').read_text(encoding='utf-8')
    values = {'PROJECT': html.escape(data['project']), 'DATA': payload}
    return re.sub(r'\{\{(PROJECT|DATA)\}\}', lambda m: values[m.group(1)], template)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    output = project_path(project, '.centaur/volante.html')
    page = render(project)
    fd, tmp = tempfile.mkstemp(dir=output.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(page)
        os.replace(tmp, output)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print(output)


if __name__ == '__main__':
    main()
