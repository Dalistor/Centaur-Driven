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

> [!info] Como navegar
> Comece pelo [[Mapa do sistema.canvas|Mapa do sistema]] e abra a perspectiva que responde à sua pergunta.

## Propósito

_A definir durante o refinamento com o Centaur._

## Estado atual

_A definir. Diferencie o que já existe, o que está planejado e o que ainda depende de decisão._

## Para quem

_A definir: pessoas, papéis ou grupos que usam ou são afetados pelo sistema._

## Capacidades

_A definir. Descreva resultados percebidos pelo usuário, não arquivos ou classes._

## Limites

_A definir: o que o sistema não faz ou onde termina sua responsabilidade._

## Fluxos

_Os fluxos confirmados ficarão em [[Sistema/Fluxos]]._

## Perspectivas

_Leituras visuais específicas ficarão em [[Sistema/Perspectivas]]._

## Decisões

_Decisões confirmadas ficarão em [[Sistema/Decisões]]._

## Vocabulário

_Os termos usados pelo sistema ficam em [[Glossário]]._
""",
    "Sistema/Glossário.md": """---
tipo: glossário
estado: rascunho
---

# Glossário

| Termo | Significado para o usuário | Relacionado a |
|---|---|---|
| _A definir_ | _Explique sem jargão técnico._ | _Fluxo, decisão ou perspectiva_ |
""",
    "Sistema/Drafts/README.md": "# Drafts do sistema\n\nCada draft começa como uma nota com objetivo, hipóteses e perguntas abertas. Adicione um Canvas irmão quando a leitura visual ajudar.\n",
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
    "Sistema/Fluxos/README.md": "# Fluxos do sistema\n\nRegistre fluxos confirmados em linguagem humana; use Mermaid quando ajudar a explicar a sequência. Marque conteúdo planejado explicitamente.\n",
    "Sistema/Perspectivas/README.md": "# Perspectivas do sistema\n\nCada Canvas responde uma pergunta específica, como jornada, ciclo de um dado, segurança ou publicação. Abra [[../Mapa do sistema.canvas|Mapa do sistema]] para navegar.\n",
    "Sistema/Decisões/README.md": "# Decisões do sistema\n\nRegistre decisões confirmadas, seus motivos e consequências.\n",
}


SYSTEM_MAP = {
    "nodes": [
        {"id": "overview", "type": "file", "file": "Sistema/Visão geral.md", "x": 0, "y": 0, "width": 360, "height": 220, "color": "5"},
        {"id": "flows", "type": "file", "file": "Sistema/Fluxos/README.md", "x": 520, "y": -300, "width": 320, "height": 180},
        {"id": "perspectives", "type": "file", "file": "Sistema/Perspectivas/README.md", "x": 520, "y": -80, "width": 320, "height": 180},
        {"id": "decisions", "type": "file", "file": "Sistema/Decisões/README.md", "x": 520, "y": 140, "width": 320, "height": 180},
        {"id": "drafts", "type": "file", "file": "Sistema/Drafts/README.md", "x": 520, "y": 360, "width": 320, "height": 180, "color": "3"},
        {"id": "glossary", "type": "file", "file": "Sistema/Glossário.md", "x": 0, "y": 300, "width": 360, "height": 180},
    ],
    "edges": [
        {"id": "overview-flows", "fromNode": "overview", "toNode": "flows", "label": "como acontece"},
        {"id": "overview-perspectives", "fromNode": "overview", "toNode": "perspectives", "label": "outras leituras"},
        {"id": "overview-decisions", "fromNode": "overview", "toNode": "decisions", "label": "por que é assim"},
        {"id": "overview-drafts", "fromNode": "overview", "toNode": "drafts", "label": "o que está em estudo"},
        {"id": "overview-glossary", "fromNode": "overview", "toNode": "glossary", "label": "termos usados"},
    ],
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
    write_if_missing(vault / "Sistema" / "Mapa do sistema.canvas", json.dumps(SYSTEM_MAP, ensure_ascii=False, indent=2) + "\n")

    destination = vault / ".agents" / "skills" / "centaur-driven-obsidian"
    shutil.copytree(args.skill_source, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    print(vault)


if __name__ == "__main__":
    main()
