"""Repescagem do catálogo do mercado: ativos que falharam nas partes (logs/catalogo_mercado_parte_NN.log).

Lê as partes de data/lotes_mercado/, aplica config/securitizadoras_fundosnet.csv (nome que o Fundos.NET encontra)
e grava data/lotes_mercado/repescagem.csv. Imprime as falhas por tipo de erro. Não grava em banco.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def failures(log_path: Path) -> dict[str, str]:
    text = log_path.read_text(encoding="utf-8", errors="replace")
    try:
        payload = json.loads(text[text.index("{"):])
    except ValueError:
        return {}
    return {
        item["codigo_cetip"]: str(item["erros"][0])
        for item in payload.get("assets", [])
        if item.get("erros")
    }


def main() -> int:
    names_path = ROOT / "config" / "securitizadoras_fundosnet.csv"
    with names_path.open(encoding="utf-8") as handle:
        names = {(r["cnpj"], r["nome_cvm"]): r["nome_busca"] for r in csv.DictReader(handle)}
    retry, kinds = [], Counter()
    for log_path in sorted((ROOT / "logs").glob("catalogo_mercado_parte_*.log")):
        number = re.search(r"parte_(\d+)", log_path.name).group(1)
        failed = failures(log_path)
        part = ROOT / "data" / "lotes_mercado" / f"parte_{number}.csv"
        with part.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["codigo_cetip"] in failed:
                    row["securitizadora"] = names.get((row["cnpj_securitizadora"], row["securitizadora"]), row["securitizadora"])
                    retry.append(row)
                    kinds[failed[row["codigo_cetip"]][:70]] += 1
    out = ROOT / "data" / "lotes_mercado" / "repescagem.csv"
    if retry:
        with out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(retry[0].keys()))
            writer.writeheader()
            writer.writerows(retry)
    print(json.dumps({"repescagem": len(retry), "arquivo": str(out), "erros": kinds.most_common()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
