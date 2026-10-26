"""Fixtures sinteticas do banco legado de debentures.

Os bancos nascem em tmp_path, fora do repositorio. O DDL repete as
restricoes do schema real (Eduardo/debenture-replica/migrations/001).
"""

import sqlite3

import pytest


_LEGACY_DDL = (
    """
    CREATE TABLE issuers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cnpj TEXT UNIQUE,
        legal_name TEXT NOT NULL
            CHECK(length(trim(legal_name)) > 0),
        trade_name TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK(
            cnpj IS NULL
            OR (
                length(cnpj) = 14
                AND cnpj NOT GLOB '*[^0-9]*'
            )
        )
    )
    """,
    """
    CREATE TABLE debentures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        issuer_id INTEGER REFERENCES issuers(id),
        asset_code TEXT UNIQUE,
        isin TEXT UNIQUE,
        issue_number TEXT,
        series TEXT,
        status TEXT NOT NULL DEFAULT 'unknown'
            CHECK(
                status IN (
                    'unknown',
                    'active',
                    'inactive',
                    'matured',
                    'cancelled'
                )
            ),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        inactive_at TEXT,
        CHECK(asset_code IS NOT NULL OR isin IS NOT NULL),
        CHECK(
            asset_code IS NULL
            OR (
                length(trim(asset_code)) > 0
                AND asset_code = upper(asset_code)
            )
        ),
        CHECK(
            isin IS NULL
            OR (
                length(isin) = 12
                AND isin = upper(isin)
            )
        )
    )
    """,
)

# id, cnpj, legal_name, trade_name, created_at, updated_at
DEFAULT_ISSUERS = (
    (
        1,
        "12345678000199",
        "Empresa Alfa S.A.",
        "Empresa Alfa",
        "2026-09-20 10:00:00",
        "2026-09-21 12:00:00",
    ),
    (
        2,
        "22345678000198",
        "Empresa Beta S.A.",
        None,
        "2026-09-20 11:00:00",
        "2026-09-21 13:00:00",
    ),
    (
        3,
        None,
        "Empresa Sem Cnpj S.A.",
        None,
        "2026-09-20 12:00:00",
        "2026-09-21 14:00:00",
    ),
)

# id, issuer_id, asset_code, isin, status, created_at, updated_at
DEFAULT_DEBENTURES = (
    (
        1,
        1,
        "ALFA11",
        "BRALFADBS001",
        "active",
        "2026-09-20 10:00:00",
        "2026-09-21 12:00:00",
    ),
    (
        2,
        2,
        "BETA12",
        "BRBETADBS002",
        "inactive",
        "2026-09-20 11:00:00",
        "2026-09-21 13:00:00",
    ),
    (
        3,
        3,
        "SEMC13",
        None,
        "unknown",
        "2026-09-20 12:00:00",
        "2026-09-21 14:00:00",
    ),
    (
        4,
        None,
        None,
        "BRSEMEDBS003",
        "unknown",
        "2026-09-20 13:00:00",
        "2026-09-21 15:00:00",
    ),
)


def build_legacy_database(
    path,
    issuers=DEFAULT_ISSUERS,
    debentures=DEFAULT_DEBENTURES,
):
    """Cria um banco legado sintetico e devolve o caminho."""

    connection = sqlite3.connect(path)

    try:
        for statement in _LEGACY_DDL:
            connection.execute(statement)

        connection.executemany(
            """
            INSERT INTO issuers (
                id,
                cnpj,
                legal_name,
                trade_name,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            issuers,
        )
        connection.executemany(
            """
            INSERT INTO debentures (
                id,
                issuer_id,
                asset_code,
                isin,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            debentures,
        )
        connection.commit()
    finally:
        connection.close()

    return path


@pytest.fixture
def legacy_database(tmp_path):
    return build_legacy_database(
        tmp_path / "legacy_debentures.sqlite3"
    )


@pytest.fixture
def legacy_database_factory(tmp_path):
    counter = {"value": 0}

    def factory(issuers=(), debentures=()):
        counter["value"] += 1

        return build_legacy_database(
            tmp_path
            / f"legacy_custom_{counter['value']}.sqlite3",
            issuers=issuers,
            debentures=debentures,
        )

    return factory
