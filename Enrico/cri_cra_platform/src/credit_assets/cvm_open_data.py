"""Ingestão em massa do Informe Mensal de CRA/CRI publicado nos dados abertos da CVM.

Fonte: https://dados.cvm.gov.br/dados/SECURIT/DOC/INF_MENSAL_<CRA|CRI>/DADOS/ (um ZIP por ano,
vários CSV por ZIP). Vai para um banco SQLite próprio (``data/cvm_open.db``), sem tocar no banco
do catálogo. Regras do projeto:
  - o valor original de cada célula é preservado como texto (nada é convertido na carga);
  - cada linha aponta para o arquivo de origem (URL, SHA-256, data de obtenção);
  - recarga idempotente: o mesmo SHA-256 não é carregado duas vezes; um arquivo novo do mesmo
    ano marca o anterior como não vigente, sem apagar linhas (histórico preservado);
  - todas as versões de um informe ficam gravadas; a view ``*_vigente`` escolhe a maior versão.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

BASE_URL = "https://dados.cvm.gov.br/dados/SECURIT/DOC/INF_MENSAL_{kind}/DADOS/inf_mensal_{kind_lower}_{year}.zip"
KINDS = ("CRA", "CRI")
CSV_NAME = re.compile(r"^inf_mensal_(cra|cri)_([a-z_]+?)_(\d{4})\.csv$")
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (kind IN ('CRA', 'CRI')),
    year INTEGER NOT NULL,
    url TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE CHECK (length(sha256) = 64),
    size_bytes INTEGER NOT NULL,
    downloaded_at TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    tables_loaded TEXT NOT NULL,
    rows_loaded INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_source_files_current ON source_files(kind, year, is_current);
"""


@dataclass(frozen=True)
class RemoteFile:
    kind: str
    year: int
    url: str
    size_bytes: int | None


Fetcher = Callable[[str], bytes]


def zip_url(kind: str, year: int) -> str:
    return BASE_URL.format(kind=kind.upper(), kind_lower=kind.lower(), year=year)


def _identifier(name: str) -> str:
    if not IDENTIFIER.match(name):
        raise ValueError(f"nome de coluna ou tabela inválido: {name!r}")
    return name


def _read_csv(data: bytes) -> tuple[list[str], list[list[str]]]:
    text = io.StringIO(data.decode("latin-1"), newline="")
    reader = csv.reader(text, delimiter=";")
    header = next(reader)
    return [_identifier(column.strip()) for column in header], [row for row in reader if row]


def ensure_table(connection: sqlite3.Connection, table: str, columns: list[str]) -> None:
    _identifier(table)
    existing = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
    if not existing:
        body = ", ".join(f"{column} TEXT" for column in columns)
        connection.execute(
            f"CREATE TABLE {table} (_file_id INTEGER NOT NULL, _row INTEGER NOT NULL, {body}, "
            f"PRIMARY KEY (_file_id, _row), FOREIGN KEY(_file_id) REFERENCES source_files(file_id))"
        )
        return
    for column in columns:  # deriva de esquema entre anos: só colunas novas, nunca remove
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")


def load_zip(
    connection: sqlite3.Connection, kind: str, year: int, url: str, payload: bytes,
    now: datetime | None = None,
) -> dict[str, int | str]:
    """Carrega um ZIP. Devolve o resumo; ``skipped`` se o mesmo SHA-256 já foi carregado."""

    sha = hashlib.sha256(payload).hexdigest()
    if connection.execute("SELECT 1 FROM source_files WHERE sha256 = ?", (sha,)).fetchone():
        return {"status": "skipped", "sha256": sha}
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [name for name in archive.namelist() if CSV_NAME.match(name.rsplit("/", 1)[-1])]
        if not members:
            raise ValueError("ZIP sem CSV no padrão inf_mensal_<tipo>_<tabela>_<ano>.csv")
        connection.execute("BEGIN")
        try:
            connection.execute(
                "UPDATE source_files SET is_current = 0 WHERE kind = ? AND year = ?", (kind, year)
            )
            cursor = connection.execute(
                """INSERT INTO source_files (kind, year, url, sha256, size_bytes, downloaded_at,
                       tables_loaded, rows_loaded) VALUES (?, ?, ?, ?, ?, ?, '', 0)""",
                (kind, year, url, sha, len(payload), stamp),
            )
            file_id = cursor.lastrowid
            tables, total = [], 0
            for name in sorted(members):
                match = CSV_NAME.match(name.rsplit("/", 1)[-1])
                table = f"{match.group(1)}_{match.group(2)}"
                columns, rows = _read_csv(archive.read(name))
                ensure_table(connection, table, columns)
                placeholders = ",".join("?" * (len(columns) + 2))
                connection.executemany(
                    f"INSERT INTO {table} (_file_id, _row, {','.join(columns)}) VALUES ({placeholders})",
                    [(file_id, number, *(row + [""] * (len(columns) - len(row)))[: len(columns)])
                     for number, row in enumerate(rows, start=1)],
                )
                tables.append(table)
                total += len(rows)
            connection.execute(
                "UPDATE source_files SET tables_loaded = ?, rows_loaded = ? WHERE file_id = ?",
                (",".join(tables), total, file_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return {"status": "loaded", "file_id": file_id, "tables": len(tables), "rows": total, "sha256": sha}


def create_views(connection: sqlite3.Connection) -> list[str]:
    """Views da versão vigente por informe e do universo de emissões (só leitura)."""

    created = []
    for kind in ("cra", "cri"):
        geral, classe = f"{kind}_geral", f"{kind}_classe"
        have = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if geral not in have or classe not in have:
            continue
        for table in (geral, classe):
            partition = "CNPJ_Emissora, Codigo_Identificacao_Certificado, Data_Referencia"
            if table == classe:
                partition += ", Numero_Serie, Codigo_ISIN"
            connection.execute(f"DROP VIEW IF EXISTS {table}_vigente")
            connection.execute(
                f"""CREATE VIEW {table}_vigente AS
                    SELECT * FROM (
                        SELECT t.*, ROW_NUMBER() OVER (
                            PARTITION BY {partition}
                            ORDER BY CAST(t.Versao AS INTEGER) DESC, t._file_id DESC) AS _rank
                        FROM {table} t JOIN source_files f ON f.file_id = t._file_id
                        WHERE f.is_current = 1)
                    WHERE _rank = 1"""
            )
            created.append(f"{table}_vigente")
    return created


def plan(kinds: Iterable[str], years: Iterable[int], head: Callable[[str], int | None]) -> list[RemoteFile]:
    return [
        RemoteFile(kind, year, zip_url(kind, year), head(zip_url(kind, year)))
        for kind in kinds for year in years
    ]


def connect(path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)  # transações explícitas (BEGIN/COMMIT)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection
