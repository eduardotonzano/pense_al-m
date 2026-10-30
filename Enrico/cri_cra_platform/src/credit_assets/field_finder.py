"""Localiza, no texto de um Termo, as páginas onde cada campo padrão é tratado.

Só localiza (nunca lê o valor). A qualidade é medida contra os parâmetros aprovados:
um parâmetro "foi achado" quando alguma página sugerida pelo localizador fica a no máximo
``tolerance`` páginas da página do trecho que sustentou o parâmetro.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_topics(path: Path) -> dict[str, list[re.Pattern]]:
    config = json.loads(path.read_text(encoding="utf-8"))
    return {
        field: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
        for field, patterns in config["topics"].items()
    }


def hit_pages(pages: list[tuple[int, str]], patterns: list[re.Pattern]) -> list[int]:
    """Números das páginas em que algum padrão casa em alguma linha."""

    hits = []
    for number, text in pages:
        if any(pattern.search(line) for line in text.splitlines() for pattern in patterns):
            hits.append(number)
    return hits


def found(parameter_page: int, hits: list[int], tolerance: int = 1) -> bool:
    return any(abs(parameter_page - page) <= tolerance for page in hits)
