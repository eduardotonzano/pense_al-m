from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.asset_migrations import migrate_cafe_brasil_duplicate_asset
from credit_assets.database.connection import connect


def main() -> int:
    connection = connect(ROOT / "data" / "cri_cra.db")
    try:
        result = migrate_cafe_brasil_duplicate_asset(connection)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
