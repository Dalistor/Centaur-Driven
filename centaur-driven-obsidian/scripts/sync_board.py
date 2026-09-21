#!/usr/bin/env python3
"""Project canonical Centaur spec records into an Obsidian status board."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


STATUSES = ("Pendente", "Em andamento", "Bloqueada", "Em revisão", "Concluída", "A verificar")


def field(content: str, name: str, default: str = "—") -> str:
    match = re.search(rf"^\*\*{re.escape(name)}:\*\*\s*([^\n]*)", content, re.MULTILINE)
    return match.group(1).strip() if match else default


def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Caminho fora do projeto: {relative}")
    return path


def read_specs(root: Path) -> list[dict]:
    config = root / ".centaur/workspace.json"
    scopes = json.loads(config.read_text(encoding="utf-8"))["scopes"] if config.exists() else {
        "master": {"specs": ".centaur/specs"}
    }
    if "master" not in scopes:
        raise ValueError("workspace.json precisa do escopo master")
    records = []
    seen_paths = set()
    for scope, settings in scopes.items():
        folder = inside(root, settings["specs"])
        if folder in seen_paths:
            raise ValueError(f"Pasta de specs repetida: {folder}")
        seen_paths.add(folder)
        for record in sorted(folder.glob("*/README.md")):
            inside(root, str(record))
            content = record.read_text(encoding="utf-8")
            heading = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            tasks = re.findall(r"^\s*- \[([ xX])\]\s+Task\b", content, re.MULTILINE)
            status = field(content, "Status", "A verificar")
            records.append({
                "id": f"{scope}/{record.parent.name}",
                "title": heading.group(1) if heading else record.parent.name,
                "status": status if status in STATUSES else "A verificar",
                "declared_status": status,
                "owner": field(content, "Responsável", settings.get("owner", "a definir")),
                "master": field(content, "Spec mestre"),
                "children": field(content, "Specs filhas"),
                "dependencies": field(content, "Dependências"),
                "progress": f"{sum(task.lower() == 'x' for task in tasks)}/{len(tasks)}" if tasks else "sem checklist",
                "source": record.as_uri(),
            })
    return records


def card_text(spec: dict) -> str:
    return (
        f"### {spec['title']}\n\n**{spec['id']}** · {spec['declared_status']}\n\n"
        f"Responsável: {spec['owner']}\n\nTasks: {spec['progress']}\n\n"
        f"Mestre: {spec['master']}\n\nFilhas: {spec['children']}\n\n"
        f"Dependências: {spec['dependencies']}\n\n[Ver spec]({spec['source']})"
    )


def render_board(specs: list[dict]) -> tuple[dict, str]:
    nodes = []
    summary = ["# Quadro de specs", "", "> Gerado dos registros canônicos. Atualize o status na spec e sincronize novamente.", ""]
    for column, status in enumerate(STATUSES):
        entries = [spec for spec in specs if spec["status"] == status]
        nodes.append({"id": f"status-{column}", "type": "group", "label": f"{status} ({len(entries)})",
                      "x": column * 460, "y": 0, "width": 440, "height": max(460, len(entries) * 420 + 60)})
        summary.extend([f"## {status}", ""])
        for row, spec in enumerate(entries):
            identifier = hashlib.sha256(spec["id"].encode()).hexdigest()[:16]
            nodes.append({"id": identifier, "type": "text", "text": card_text(spec),
                          "x": column * 460 + 20, "y": row * 420 + 40, "width": 400, "height": 400})
            summary.extend([card_text(spec), ""])
        if not entries:
            summary.extend(["Nenhuma spec neste status.", ""])
    return {"nodes": nodes, "edges": []}, "\n".join(summary)


def connect_map(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"nodes": [], "edges": []}
    target = "Sistema/Quadro de specs.canvas"
    if not any(node.get("file") == target for node in data["nodes"]):
        ids = {node["id"] for node in data["nodes"]}
        identifier = "centaur-spec-board"
        while identifier in ids:
            identifier += "-new"
        right = max((node["x"] + node["width"] for node in data["nodes"]), default=0)
        data["nodes"].append({"id": identifier, "type": "file", "file": target,
                              "x": right + 120, "y": 0, "width": 400, "height": 300, "color": "3"})
        if "overview" in ids:
            edge_id = identifier + "-link"
            edge_ids = {edge["id"] for edge in data["edges"]}
            while edge_id in edge_ids:
                edge_id += "-new"
            data["edges"].append({"id": edge_id, "fromNode": "overview", "toNode": identifier,
                                  "label": "planejado e entregue"})
    return data


def sync(root: Path) -> int:
    root = root.resolve()
    specs = read_specs(root)
    board, summary = render_board(specs)
    system = inside(root, ".centaur/obsidian/Sistema")
    map_path = system / "Mapa do sistema.canvas"
    updated_map = connect_map(map_path)
    system.mkdir(parents=True, exist_ok=True)
    outputs = {system / "Quadro de specs.canvas": json.dumps(board, ensure_ascii=False, indent=2) + "\n",
               system / "Quadro de specs.md": summary,
               map_path: json.dumps(updated_map, ensure_ascii=False, indent=2) + "\n"}
    for path, content in outputs.items():
        inside(root, str(path))
        path.write_text(content, encoding="utf-8")
    return len(specs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    args = parser.parse_args()
    print(f"Quadro sincronizado: {sync(args.project_root)} specs")


if __name__ == "__main__":
    main()
