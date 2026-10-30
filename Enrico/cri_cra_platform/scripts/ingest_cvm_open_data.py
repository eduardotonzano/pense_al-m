"""Ingestão em massa do Informe Mensal de CRA/CRI dos dados abertos da CVM.

  --dry-run   lista os arquivos e tamanhos que seriam baixados; não grava nada
  --commit    baixa os ZIPs (guardados em data/cvm_open/) e carrega em data/cvm_open.db

Banco separado do catálogo; recarga idempotente por SHA-256. Fonte pública (licença ODbL).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.cvm_open_data import KINDS, connect, create_views, load_zip, plan, zip_url

DEFAULT_DB = ROOT / "data" / "cvm_open.db"
USER_AGENT = "pense-al-m-cri-cra/0.1 (dados abertos CVM; contato: equipe de dados)"


def _request(url: str, method: str = "GET"):
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=180)


def head_size(url: str) -> int | None:
    try:
        with _request(url, "HEAD") as response:
            value = response.headers.get("Content-Length")
            return int(value) if value else None
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kinds", nargs="+", choices=KINDS, default=list(KINDS))
    parser.add_argument("--years", nargs="+", type=int, default=list(range(2019, 2027)))
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    files = plan(args.kinds, args.years, head_size)
    if args.dry_run:
        total = sum(f.size_bytes or 0 for f in files)
        print(json.dumps({
            "dry_run": True, "database": str(args.database),
            "files": [{"kind": f.kind, "year": f.year, "bytes": f.size_bytes, "url": f.url} for f in files],
            "total_megabytes": round(total / 1e6, 1),
            "unreachable": [f.url for f in files if f.size_bytes is None],
        }, ensure_ascii=False, indent=2))
        return 0

    cache = ROOT / "data" / "cvm_open"
    cache.mkdir(parents=True, exist_ok=True)
    connection = connect(args.database)
    summary = []
    try:
        for item in files:
            if item.size_bytes is None:
                summary.append({"kind": item.kind, "year": item.year, "status": "indisponível"})
                continue
            with _request(item.url) as response:
                payload = response.read()
            (cache / f"inf_mensal_{item.kind.lower()}_{item.year}.zip").write_bytes(payload)
            result = load_zip(connection, item.kind, item.year, item.url, payload)
            summary.append({"kind": item.kind, "year": item.year, **{k: v for k, v in result.items() if k != "sha256"}})
        views = create_views(connection)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign = connection.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        connection.close()
    print(json.dumps({"summary": summary, "views": views, "integrity_check": integrity,
                      "foreign_key_check": len(foreign)}, ensure_ascii=False, indent=2))
    return 0 if integrity == "ok" and not foreign else 1


if __name__ == "__main__":
    raise SystemExit(main())
