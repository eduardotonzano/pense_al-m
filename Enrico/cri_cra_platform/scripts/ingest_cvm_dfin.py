"""Ingestão do índice de demonstrações financeiras dos patrimônios separados de CRA/CRI (dados abertos da CVM).

  --dry-run   lista os arquivos e tamanhos; não grava nada
  --commit    baixa os CSV (guardados em data/cvm_open/) e carrega em data/cvm_dfin.db

Conteúdo por DF: securitizadora, certificado, data-base, versão, data de entrega, link do documento no
Fundos.NET e **opinião do auditor**. Banco separado do Informe Mensal (data/cvm_open.db); recarga idempotente.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.cvm_open_data import KINDS, connect, dfin_url, load_csv

USER_AGENT = "pense-al-m-cri-cra/0.1 (dados abertos CVM)"
YEARS = {"CRA": range(2019, 2027), "CRI": range(2018, 2027)}


def _request(url: str, method: str = "GET"):
    return urllib.request.urlopen(urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT}), timeout=180)


def head_size(url: str) -> int | None:
    try:
        with _request(url, "HEAD") as response:
            value = response.headers.get("Content-Length")
            return int(value) if value else None
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "cvm_dfin.db")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    files = [(kind, year, dfin_url(kind, year)) for kind in KINDS for year in YEARS[kind]]
    sizes = {url: head_size(url) for _, _, url in files}
    if args.dry_run:
        print(json.dumps({"dry_run": True, "database": str(args.database),
                          "files": [{"kind": k, "year": y, "bytes": sizes[u]} for k, y, u in files],
                          "total_megabytes": round(sum(v or 0 for v in sizes.values()) / 1e6, 1),
                          "unreachable": [u for u in sizes if sizes[u] is None]}, ensure_ascii=False, indent=2))
        return 0
    cache = ROOT / "data" / "cvm_open"
    cache.mkdir(parents=True, exist_ok=True)
    connection = connect(args.database)
    summary = []
    try:
        for kind, year, url in files:
            if sizes[url] is None:
                summary.append({"kind": kind, "year": year, "status": "indisponível"})
                continue
            with _request(url) as response:
                payload = response.read()
            (cache / f"dfin_{kind.lower()}_{year}.csv").write_bytes(payload)
            result = load_csv(connection, kind, year, url, payload, f"dfin_{kind.lower()}")
            summary.append({"kind": kind, "year": year, **{k: v for k, v in result.items() if k != "sha256"}})
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign = connection.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        connection.close()
    print(json.dumps({"summary": summary, "integrity_check": integrity, "foreign_key_check": len(foreign)},
                     ensure_ascii=False, indent=2))
    return 0 if integrity == "ok" and not foreign else 1


if __name__ == "__main__":
    raise SystemExit(main())
