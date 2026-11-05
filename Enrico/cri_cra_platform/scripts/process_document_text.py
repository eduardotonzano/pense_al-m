"""Texto por página (pdftotext) e OCR dos PDFs em imagem, em lote, para os ativos de uma lista.

Chama extract_document_text.py por ativo e ocr_document_pages.py para cada documento que saiu sem texto em
nenhuma página. Precisa do pdftotext no PATH (no Windows, rodar pelo Git Bash) e de pymupdf + rapidocr-onnxruntime.

    python scripts/process_document_text.py --list config/ativos_mercado.csv --score positive
    python scripts/process_document_text.py --list data/lotes_mercado/parte_10.csv --score all
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(arguments: list[str]) -> tuple[int, dict]:
    done = subprocess.run([sys.executable, *arguments], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    text = done.stdout
    try:
        return done.returncode, json.loads(text[text.index("{"):])
    except ValueError:
        return done.returncode, {"error": (done.stderr or text)[-300:]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", type=Path, required=True)
    parser.add_argument("--score", choices=("positive", "zero", "all"), default="all")
    args = parser.parse_args()
    with args.list.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    keep = {"positive": lambda s: s > 0, "zero": lambda s: s == 0, "all": lambda s: True}[args.score]
    cetips = [r["codigo_cetip"] for r in rows if keep(int(r.get("score") or 0))]
    totals = {"ativos": len(cetips), "textos": 0, "ocr": 0, "falhas": []}
    for cetip in cetips:
        code, result = run(["scripts/extract_document_text.py", "--cetip", cetip])
        if "error" in result:
            totals["falhas"].append({"cetip": cetip, "etapa": "texto", "erro": result["error"]})
            continue
        totals["textos"] += len(result.get("stored", [])) + len(result.get("needs_ocr", []))
        totals["falhas"] += [{"cetip": cetip, "etapa": "texto", **f} for f in result.get("failed", [])]
        for item in result.get("needs_ocr", []):
            code, ocr = run(["scripts/ocr_document_pages.py", "--cetip", cetip, "--source-id", item["source_document_id"]])
            if code == 0:
                totals["ocr"] += 1
            else:
                totals["falhas"].append({"cetip": cetip, "etapa": "ocr", "documento": item["source_document_id"],
                                         "erro": str(ocr.get("error", ocr))[-200:]})
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
