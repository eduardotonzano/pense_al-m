"""Remove o PDF baixado quando o texto de todas as páginas já está no banco (economia de disco no mercado inteiro).

Só para ativos de config/ativos_mercado.csv sem sinal de triagem (score 0): os ativos já trabalhados (pilotos,
lotes 1 e 2) e os prioritários (score > 0) mantêm o PDF. Um arquivo só sai se:
  - o SHA-256 do arquivo bate com document_versions.file_hash;
  - o número de páginas do PDF é o número de páginas gravadas em document_text_pages;
  - toda página tem texto (nativo do pdftotext ou OCR).
O registro em document_versions (hash, caminho, link do Fundos.NET em documents) continua: o documento pode ser
baixado de novo e conferido pelo hash. Cada remoção vai para data/arquivos_removidos.csv.

    python scripts/prune_document_files.py --dry-run
    python scripts/prune_document_files.py --commit
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect

LOG_FIELDS = ["removed_at", "codigo_cetip", "source_document_id", "version_id", "local_file_path", "file_hash",
              "size_bytes", "pages"]


def prunable_cetips(market_list: Path) -> set[str]:
    with market_list.open(encoding="utf-8-sig") as handle:
        return {row["codigo_cetip"] for row in csv.DictReader(handle) if int(row["score"] or 0) == 0}


def check(connection, version, path: Path) -> tuple[bool, str, int]:
    import pymupdf

    if not path.is_file():
        return False, "arquivo ausente", 0
    if hashlib.sha256(path.read_bytes()).hexdigest() != version["file_hash"]:
        return False, "hash diverge", 0
    try:
        with pymupdf.open(path) as document:
            page_count = document.page_count
    except Exception:
        return False, "PDF não abre", 0
    pages = {}
    for row in connection.execute(
            "SELECT page_number, text FROM document_text_pages WHERE document_version_id = ?", (version["version_id"],)):
        pages[row["page_number"]] = pages.get(row["page_number"], False) or bool((row["text"] or "").strip())
    if set(pages) != set(range(1, page_count + 1)):
        return False, "páginas sem texto gravado", page_count
    if not all(pages.values()):
        return False, "página vazia sem OCR", page_count
    return True, "ok", page_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "cri_cra.db")
    parser.add_argument("--market-list", type=Path, default=ROOT / "config" / "ativos_mercado.csv")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    cetips = prunable_cetips(args.market_list)
    connection = connect(args.database)
    log_path = ROOT / "data" / "arquivos_removidos.csv"
    reasons, freed, removed = Counter(), 0, []
    try:
        rows = connection.execute(
            """SELECT v.version_id, v.local_file_path, v.file_hash, a.codigo_cetip, d.source_document_id
               FROM document_versions v JOIN documents d ON d.document_pk = v.document_id
               JOIN assets a ON a.asset_id = d.asset_id
               WHERE v.is_current = 1 AND v.validation_status = 'valid' AND lower(v.file_format) = 'pdf'
                 AND v.local_file_path IS NOT NULL"""
        ).fetchall()
        for version in rows:
            if version["codigo_cetip"] not in cetips:
                continue
            path = ROOT / version["local_file_path"]
            ok, reason, page_count = check(connection, version, path)
            reasons[reason] += 1
            if not ok:
                continue
            size = path.stat().st_size
            freed += size
            removed.append({
                "removed_at": datetime.now(timezone.utc).isoformat(), "codigo_cetip": version["codigo_cetip"],
                "source_document_id": version["source_document_id"], "version_id": version["version_id"],
                "local_file_path": version["local_file_path"], "file_hash": version["file_hash"],
                "size_bytes": size, "pages": page_count,
            })
            if args.commit:
                path.unlink()
    finally:
        connection.close()
    if args.commit and removed:
        new_file = not log_path.exists()
        with log_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
            if new_file:
                writer.writeheader()
            writer.writerows(removed)
    print(json.dumps({"dry_run": args.dry_run, "ativos_sem_sinal": len(cetips), "verificados": sum(reasons.values()),
                      "situacao": dict(reasons), "removidos": len(removed) if args.commit else 0,
                      "removiveis": len(removed), "megabytes": round(freed / 1e6, 1)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
