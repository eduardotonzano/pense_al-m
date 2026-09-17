from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect, initialize_database
from credit_assets.repositories.document_repository import DocumentRepository


def main() -> None:
    connection = connect(ROOT / "data" / "cri_cra.db")
    initialize_database(connection)
    output = DocumentRepository(connection).export_csv(
        ROOT / "data" / "catalogo_documentos.csv"
    )
    print(output)


if __name__ == "__main__":
    main()
