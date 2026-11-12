"""Fila de revisão humana priorizada (só leitura).

Ordena o que aguarda aprovação para que o revisor comece pelo que mais importa e possa aprovar
em bloco o que já foi conferido. Não aprova nada e não grava no banco.

Níveis (1 = decidir primeiro):
  1 divergência entre documentos, conferência visual divergente/inconclusiva ou nota de contradição
  2 alimenta alerta contratual, vem de OCR ou é campo core do catálogo
  3 conferido visualmente, mas com observação da proposta (vale ler a observação)
  4 conferido visualmente, sem observação: candidato a aprovação em bloco
  5 sem conferência visual
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TIER_LABELS = {
    1: "Decidir primeiro",
    2: "Importante",
    3: "Conferido visualmente, com observação",
    4: "Conferido, sem observação (aprovação em bloco)",
    5: "Sem conferência visual",
}
FLAG_WORDS = re.compile(r"contradiz|revis[aã]o humana|inferid|interpreta[cç][aã]o|ambígu|ambigu|diverge", re.IGNORECASE)


def fact_names_in_rules(config_dir: Path) -> set[str]:
    """Nomes de fatos citados nas regras de alerta (qualquer arquivo em config/alert_rules)."""

    names: set[str] = set()

    def walk(node: Any, key: str | None = None) -> None:
        if isinstance(node, dict):
            for child_key, child in node.items():
                walk(child, child_key)
        elif isinstance(node, list):
            for child in node:
                walk(child, key)
        elif isinstance(node, str) and key in {"fact", "facts"}:
            names.add(node)

    for path in sorted(config_dir.glob("*.json")):
        walk(json.loads(path.read_text(encoding="utf-8")))
    return names


def classify_fact(
    fact: dict[str, Any], note: str | None, visual: dict[str, Any] | None,
    in_divergence: bool, feeds_alert: bool,
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    verdict = (visual or {}).get("verdict")
    if in_divergence:
        reasons.append("diverge de outro documento")
    if verdict in {"diverge", "inconclusivo"}:
        reasons.append(f"conferência visual {verdict}")
    if note and FLAG_WORDS.search(note):
        reasons.append("nota com contradição/interpretação")
    if reasons:
        return 1, reasons
    if feeds_alert:
        reasons.append("alimenta alerta contratual")
    if "ocr" in (fact.get("extraction_method") or ""):
        reasons.append("leitura por OCR")
    if reasons:
        return 2, reasons
    if verdict != "confere":
        return 5, ["sem conferência visual" + ("; tem observação na proposta" if note else "")]
    if note:
        return 3, ["conferido visualmente; ler a observação da proposta"]
    return 4, ["conferido visualmente, sem observação"]


def classify_parameter(
    parameter: dict[str, Any], core_names: set[str], in_divergence: bool,
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    note = parameter.get("justification") or ""
    if in_divergence:
        reasons.append("diverge de outro documento")
    if FLAG_WORDS.search(note):
        reasons.append("nota com contradição/interpretação")
    if reasons:
        return 1, reasons
    if parameter["parameter_name"] in core_names:
        return 2, ["campo core do catálogo"]
    return 5, ["parâmetro sem conferência visual"]
