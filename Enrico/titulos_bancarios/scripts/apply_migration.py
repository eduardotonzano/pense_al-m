"""Aplica as migrations pendentes do banco de titulos bancarios.

Uso (a partir de Enrico/titulos_bancarios):

    python scripts/apply_migration.py --database <banco> --dry-run
    python scripts/apply_migration.py --database <banco> --commit

--database e obrigatorio e uma das duas flags tambem. Banco novo: --create
(primeiro com --dry-run). O detalhe esta em titulos_bancarios/migrate.py.
"""

import pathlib
import sys


SOURCE_DIR = pathlib.Path(__file__).resolve().parent.parent / "src"

# O codigo que altera o banco vem sempre deste checkout, nunca de uma copia
# instalada num ambiente virtual.
sys.path.insert(0, str(SOURCE_DIR))

from titulos_bancarios.migrate import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
