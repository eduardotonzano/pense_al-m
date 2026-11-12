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
    """Um registro por linha física, como a CVM publica.

    Aspa de abertura sem fechamento (ex.: ``"AAAsf(bra)`` no CRI de 2019 a 2022, ``"Setembro/2026`` no de 2026)
    fazia o leitor engolir as linhas seguintes num campo só, perdendo registros; nessa linha a aspa é lida como
    texto, e o valor original fica preservado.
    """

    lines = data.decode("latin-1").split("\n")
    header = next(csv.reader([lines[0].rstrip("\r")], delimiter=";"))
    rows = []
    for line in lines[1:]:
        line = line.rstrip("\r")
        if not line:
            continue
        try:
            rows.append(next(csv.reader([line], delimiter=";", strict=True)))
        except csv.Error:
            rows.append(next(csv.reader([line], delimiter=";", quoting=csv.QUOTE_NONE)))
    return [_identifier(column.strip()) for column in header], rows


def _insert_rows(
    connection: sqlite3.Connection, table: str, columns: list[str], rows: list[list[str]], file_id: int
) -> None:
    ensure_table(connection, table, columns)
    placeholders = ",".join("?" * (len(columns) + 2))
    connection.executemany(
        f"INSERT INTO {table} (_file_id, _row, {','.join(columns)}) VALUES ({placeholders})",
        [(file_id, number, *(row + [""] * (len(columns) - len(row)))[: len(columns)])
         for number, row in enumerate(rows, start=1)],
    )


def _read_zip(payload: bytes) -> list[tuple[str, list[str], list[list[str]]]]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [name for name in archive.namelist() if CSV_NAME.match(name.rsplit("/", 1)[-1])]
        if not members:
            raise ValueError("ZIP sem CSV no padrão inf_mensal_<tipo>_<tabela>_<ano>.csv")
        tables = []
        for name in sorted(members):
            match = CSV_NAME.match(name.rsplit("/", 1)[-1])
            columns, rows = _read_csv(archive.read(name))
            tables.append((f"{match.group(1)}_{match.group(2)}", columns, rows))
    return tables


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
        for table, columns, rows in _read_zip(payload):
            _insert_rows(connection, table, columns, rows, file_id)
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


def reparse_zip(connection: sqlite3.Connection, payload: bytes) -> dict[str, int | str]:
    """Relê um ZIP já carregado (mesmo SHA-256) com o leitor atual e regrava só as linhas desse arquivo.

    Para corrigir carga feita com leitor antigo (aspa sem fechamento engolia linhas). Só regrava se o número de
    linhas de alguma tabela mudar; o registro em ``source_files`` (proveniência, vigência) continua o mesmo.
    """

    sha = hashlib.sha256(payload).hexdigest()
    found = connection.execute(
        "SELECT file_id, tables_loaded, rows_loaded FROM source_files WHERE sha256 = ?", (sha,)
    ).fetchone()
    if not found:
        return {"status": "not_loaded", "sha256": sha}
    file_id, loaded, before = found[0], [t for t in found[1].split(",") if t], found[2]
    tables = _read_zip(payload)
    stored = {
        table: connection.execute(f"SELECT COUNT(*) FROM {_identifier(table)} WHERE _file_id = ?", (file_id,)).fetchone()[0]
        for table in loaded
    }
    if sorted(loaded) == sorted(t for t, _, _ in tables) and all(stored[t] == len(r) for t, _, r in tables):
        return {"status": "unchanged", "file_id": file_id, "rows": before, "sha256": sha}
    total = sum(len(rows) for _, _, rows in tables)
    connection.execute("BEGIN")
    try:
        for table in loaded:
            connection.execute(f"DELETE FROM {_identifier(table)} WHERE _file_id = ?", (file_id,))
        for table, columns, rows in tables:
            _insert_rows(connection, table, columns, rows, file_id)
        connection.execute(
            "UPDATE source_files SET tables_loaded = ?, rows_loaded = ? WHERE file_id = ?",
            (",".join(t for t, _, _ in tables), total, file_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"status": "reparsed", "file_id": file_id, "rows_before": before, "rows": total, "sha256": sha}


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


DFIN_URL = "https://dados.cvm.gov.br/dados/SECURIT/DOC/DFIN_{kind}/DADOS/dfin_{kind_lower}_{year}.csv"


def dfin_url(kind: str, year: int) -> str:
    return DFIN_URL.format(kind=kind.upper(), kind_lower=kind.lower(), year=year)


def load_csv(
    connection: sqlite3.Connection, kind: str, year: int, url: str, payload: bytes, table: str,
    now: datetime | None = None,
) -> dict[str, int | str]:
    """Carrega um CSV avulso (ex.: índice de DFs dos patrimônios separados) com a mesma proveniência e idempotência
    de ``load_zip``. Usar num banco próprio por conjunto: ``source_files`` marca o vigente por tipo e ano."""

    sha = hashlib.sha256(payload).hexdigest()
    if connection.execute("SELECT 1 FROM source_files WHERE sha256 = ?", (sha,)).fetchone():
        return {"status": "skipped", "sha256": sha}
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    columns, rows = _read_csv(payload)
    connection.execute("BEGIN")
    try:
        connection.execute("UPDATE source_files SET is_current = 0 WHERE kind = ? AND year = ?", (kind, year))
        file_id = connection.execute(
            """INSERT INTO source_files (kind, year, url, sha256, size_bytes, downloaded_at, tables_loaded, rows_loaded)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (kind, year, url, sha, len(payload), stamp, table, len(rows)),
        ).lastrowid
        _insert_rows(connection, table, columns, rows, file_id)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"status": "loaded", "file_id": file_id, "rows": len(rows), "sha256": sha}
