#!/usr/bin/env python3
"""Render a local progress snapshot from a project's canonical Centaur specs."""

import argparse
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path


STATUS = ("Pendente", "Em andamento", "Bloqueada", "Em revisão", "Concluída")
CHECKBOX = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.+)$", re.MULTILINE)


def escape(value):
    return html.escape(str(value), quote=True)


def field(markdown, name):
    match = re.search(r"^\*\*" + re.escape(name) + r":\*\*\s*(.+)$", markdown, re.MULTILINE)
    return match.group(1).strip() if match else ""


def project_path(project, configured):
    path = (project / configured).resolve()
    if not path.is_relative_to(project.resolve()):
        raise ValueError(f"Caminho fora do projeto: {configured}")
    return path


def spec_records(project, scope, config):
    directory = project_path(project, config["specs"])
    if not directory.is_dir():
        return []
    records = []
    for readme in sorted(directory.glob("*/README.md")):
        source = readme.read_text(encoding="utf-8")
        title = re.search(r"^#\s+(?:\d{4}(?:-[\w-]+)?\s+)?(.+)$", source, re.MULTILINE)
        checklist = re.search(r"^## Checklist de conclusão\s*$(.*?)(?=^## |\Z)", source, re.MULTILINE | re.DOTALL)
        task_source = checklist.group(1) if checklist else source
        tasks = [(item.strip(), mark.lower() == "x") for mark, item in CHECKBOX.findall(task_source)]
        status = field(source, "Status") or "Sem status"
        records.append({
            "id": f"{scope}/{readme.parent.name}",
            "title": title.group(1) if title else readme.parent.name,
            "status": status,
            "tasks": tasks,
            "href": os.path.relpath(readme, project / ".centaur"),
        })
    return records


def render_spec(spec):
    pending = [task for task, done in spec["tasks"] if not done]
    total = len(spec["tasks"])
    done = total - len(pending)
    status_class = "done" if spec["status"] == "Concluída" else "blocked" if spec["status"] == "Bloqueada" else "active"
    items = "".join(f"<li>{escape(task)}</li>" for task in pending)
    remaining = f"<ul>{items}</ul>" if pending else ("<p>Sem tarefas pendentes.</p>" if total else "<p>Sem checklist registrado.</p>")
    return (
        f'<article class="spec"><div class="spec-head"><a href="{escape(spec["href"])}">'
        f'{escape(spec["id"])} · {escape(spec["title"])}</a>'
        f'<span class="badge {status_class}">{escape(spec["status"])}</span></div>'
        f'<p class="muted">{done} de {total} tarefas concluídas</p>{remaining}</article>'
    )


def render(project):
    workspace = json.loads((project / ".centaur/workspace.json").read_text(encoding="utf-8"))
    scopes = workspace.get("scopes", {})
    if not scopes:
        raise ValueError("workspace.json não contém escopos")

    sections = []
    attention = []
    total_specs = total_pending = 0
    for scope, config in scopes.items():
        specs = spec_records(project, scope, config)
        total_specs += len(specs)
        pending = sum(1 for spec in specs if spec["status"] != "Concluída")
        total_pending += pending
        blocked = [spec for spec in specs if spec["status"] == "Bloqueada"]
        attention.extend(blocked)
        body = "".join(render_spec(spec) for spec in specs) or '<p class="empty">Nenhuma spec registrada neste módulo.</p>'
        sections.append(
            f'<section class="module"><div class="module-head"><div><p class="eyebrow">MÓDULO</p>'
            f'<h2>{escape(scope)}</h2><p class="muted">Responsável: {escape(config.get("owner", "não definido"))}</p></div>'
            f'<strong>{pending} pendente{"s" if pending != 1 else ""}</strong></div>{body}</section>'
        )

    attention_body = "".join(
        f'<li><a href="{escape(spec["href"])}">{escape(spec["id"])} · {escape(spec["title"])}</a></li>'
        for spec in attention
    ) or '<li>Nenhuma spec bloqueada.</li>'
    updated = datetime.now().astimezone().strftime("%d/%m/%Y às %H:%M")
    template = Path(__file__).with_name("dashboard-template.html").read_text(encoding="utf-8")
    values = {
        "UPDATED": escape(updated),
        "MODULE_COUNT": str(len(scopes)),
        "SPEC_COUNT": str(total_specs),
        "PENDING_COUNT": str(total_pending),
        "MODULES": "\n".join(sections),
        "ATTENTION": attention_body,
    }
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: values[match.group(1)], template)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Raiz do projeto com .centaur/workspace.json")
    args = parser.parse_args()
    project = args.project.resolve()
    output = project / ".centaur/andamento.html"
    page = render(project)
    output.write_text(page, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
