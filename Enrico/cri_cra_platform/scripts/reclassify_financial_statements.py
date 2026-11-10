from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.category_migrations import reclassify_financial_statements
from credit_assets.database.connection import connect


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="grava; sem isso é dry-run")
    args = parser.parse_args()
    db_path = ROOT / "data" / "cri_cra.db"
    if args.apply:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(db_path, db_path.with_name(f"cri_cra_backup_antes_reclassificacao_{stamp}.db"))
    connection = connect(db_path)
    try:
        print(json.dumps(
            reclassify_financial_statements(connection, apply=args.apply),
            ensure_ascii=False, indent=2,
        ))
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
