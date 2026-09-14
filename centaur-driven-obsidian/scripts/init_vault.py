#!/usr/bin/env python3
"""Create Centaur's local Obsidian vault without overwriting existing notes."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


NOTES = {
    "Sistema/Visão geral.md": """---
tipo: sistema
estado: rascunho
---

# Visão geral do sistema

## Propósito

_A definir durante o refinamento com o Centaur._

## Capacidades

_A definir. Use conceitos em linguagem humana, não arquivos ou classes._

## Fluxos

_Os fluxos confirmados ficarão em [[Sistema/Fluxos]]._

## Decisões

_Decisões confirmadas ficarão em [[Sistema/Decisões]]._
""",
    "Sistema/Drafts/README.md": "# Drafts do sistema\n\nCada draft combina um Canvas e uma nota irmã com objetivo, hipóteses e perguntas abertas.\n",
    "Sistema/Drafts/_modelo.md": """---
estado: hipótese
---

# [Nome do draft]

## Objetivo

_O que deve existir para quem usa o sistema?_

## Hipótese de fluxo

_Descreva etapas, entradas e resultado em linguagem humana._

## Perguntas abertas

-
""",
    "Sistema/Fluxos/README.md": "# Fluxos do sistema\n\nRegistre fluxos confirmados em linguagem humana; use Mermaid quando ajudar a explicar a sequência.\n",
    "Sistema/Perspectivas/README.md": "# Perspectivas do sistema\n\nCada Canvas responde uma pergunta específica, como jornada, dados, segurança ou publicação.\n",
    "Sistema/Decisões/README.md": "# Decisões do sistema\n\nRegistre decisões confirmadas, seus motivos e consequências.\n",
    "Sistema/Specs/README.md": "# Referências de specs\n\nCada nota aponta para a spec executável em `../../specs/YYYY/README.md` e para os drafts, fluxos e decisões de origem.\n",
}


def write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--skill-source", type=Path, required=True)
    args = parser.parse_args()

    vault = args.project_root.resolve() / ".centaur" / "obsidian"
    vault.mkdir(parents=True, exist_ok=True)
    write_if_missing(vault / ".obsidian" / "app.json", json.dumps({"showLineNumber": False}, indent=2) + "\n")
    for relative_path, content in NOTES.items():
        write_if_missing(vault / relative_path, content)

    destination = vault / ".agents" / "skills" / "centaur-driven-obsidian"
    shutil.copytree(args.skill_source, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    print(vault)


if __name__ == "__main__":
    main()
