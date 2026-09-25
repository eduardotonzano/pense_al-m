"""Testes da entrada operacional da integracao."""

from pathlib import Path

from pense_alm.shared.integration.cli import (
    build_parser,
)


def test_parser_accepts_required_paths():
    parser = build_parser()

    arguments = parser.parse_args(
        [
            "--legacy-db",
            "legacy.sqlite3",
            "--target-db",
            "target.sqlite3",
        ]
    )

    assert arguments.legacy_db == Path(
        "legacy.sqlite3"
    )
    assert arguments.target_db == Path(
        "target.sqlite3"
    )
    assert arguments.batch_size == 100
    assert arguments.dry_run is False


def test_parser_accepts_optional_arguments():
    parser = build_parser()

    arguments = parser.parse_args(
        [
            "--legacy-db",
            "legacy.sqlite3",
            "--target-db",
            "target.sqlite3",
            "--batch-size",
            "25",
            "--dry-run",
        ]
    )

    assert arguments.batch_size == 25
    assert arguments.dry_run is True


def test_main_rejects_invalid_batch_size(
    monkeypatch,
    tmp_path,
):
    from pense_alm.shared.integration.cli import main

    legacy_path = tmp_path / "legacy.sqlite3"
    legacy_path.touch()

    monkeypatch.setattr(
        "sys.argv",
        [
            "integration-cli",
            "--legacy-db",
            str(legacy_path),
            "--target-db",
            str(tmp_path / "target.sqlite3"),
            "--batch-size",
            "0",
        ],
    )

    try:
        main()
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError(
            "A CLI deveria rejeitar batch_size zero."
        )


def test_main_rejects_missing_legacy_database(
    monkeypatch,
    tmp_path,
):
    from pense_alm.shared.integration.cli import main

    monkeypatch.setattr(
        "sys.argv",
        [
            "integration-cli",
            "--legacy-db",
            str(tmp_path / "missing.sqlite3"),
            "--target-db",
            str(tmp_path / "target.sqlite3"),
        ],
    )

    try:
        main()
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError(
            "A CLI deveria rejeitar banco inexistente."
        )


def test_main_rejects_same_source_and_target(
    monkeypatch,
    tmp_path,
):
    from pense_alm.shared.integration.cli import main

    database_path = tmp_path / "database.sqlite3"
    database_path.touch()

    monkeypatch.setattr(
        "sys.argv",
        [
            "integration-cli",
            "--legacy-db",
            str(database_path),
            "--target-db",
            str(database_path),
        ],
    )

    try:
        main()
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError(
            "A CLI deveria rejeitar caminhos iguais."
        )


def test_run_import_dry_run_does_not_persist(
    tmp_path,
    capsys,
):
    import sqlite3

    from pense_alm.shared.integration.cli import (
        run_import,
    )
    from pense_alm.shared.persistence import (
        SQLiteConnectionManager,
        SQLiteEntityRepository,
    )

    legacy_path = tmp_path / "legacy.sqlite3"
    target_path = tmp_path / "target.sqlite3"

    connection = sqlite3.connect(legacy_path)

    try:
        connection.execute(
            """
            CREATE TABLE issuers (
                id INTEGER PRIMARY KEY,
                cnpj TEXT,
                legal_name TEXT NOT NULL,
                trade_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
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
            (
                1,
                "12345678000199",
                "Empresa Teste S.A.",
                "Empresa Teste",
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
        )

        connection.commit()
    finally:
        connection.close()

    exit_code = run_import(
        legacy_db=legacy_path,
        target_db=target_path,
        batch_size=1,
        dry_run=True,
    )

    repository = SQLiteEntityRepository(
        SQLiteConnectionManager(target_path)
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Total lido: 1" in output
    assert "Criados: 1" in output
    assert "Dry run: True" in output
    assert repository.count() == 0


def test_run_import_dry_run_does_not_persist(
    tmp_path,
    capsys,
):
    import sqlite3

    from pense_alm.shared.integration.cli import (
        run_import,
    )
    from pense_alm.shared.persistence import (
        SQLiteConnectionManager,
        SQLiteEntityRepository,
    )

    legacy_path = tmp_path / "legacy.sqlite3"
    target_path = tmp_path / "target.sqlite3"

    connection = sqlite3.connect(legacy_path)

    try:
        connection.execute(
            """
            CREATE TABLE issuers (
                id INTEGER PRIMARY KEY,
                cnpj TEXT,
                legal_name TEXT NOT NULL,
                trade_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
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
            (
                1,
                "12345678000199",
                "Empresa Teste S.A.",
                "Empresa Teste",
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
        )

        connection.commit()
    finally:
        connection.close()

    exit_code = run_import(
        legacy_db=legacy_path,
        target_db=target_path,
        batch_size=1,
        dry_run=True,
    )

    repository = SQLiteEntityRepository(
        SQLiteConnectionManager(target_path)
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Total lido: 1" in output
    assert "Criados: 1" in output
    assert "Dry run: True" in output
    assert repository.count() == 0


def test_run_import_persists_and_is_idempotent(
    tmp_path,
    capsys,
):
    import sqlite3

    from pense_alm.shared.integration.cli import (
        run_import,
    )
    from pense_alm.shared.persistence import (
        SQLiteConnectionManager,
        SQLiteEntityRepository,
    )

    legacy_path = tmp_path / "legacy_real.sqlite3"
    target_path = tmp_path / "target_real.sqlite3"

    connection = sqlite3.connect(legacy_path)

    try:
        connection.execute(
            """
            CREATE TABLE issuers (
                id INTEGER PRIMARY KEY,
                cnpj TEXT,
                legal_name TEXT NOT NULL,
                trade_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
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
            (
                1,
                "12345678000199",
                "Empresa Persistida S.A.",
                "Empresa Persistida",
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
        )

        connection.commit()
    finally:
        connection.close()

    first_exit_code = run_import(
        legacy_db=legacy_path,
        target_db=target_path,
        batch_size=1,
        dry_run=False,
    )

    first_output = capsys.readouterr().out

    second_exit_code = run_import(
        legacy_db=legacy_path,
        target_db=target_path,
        batch_size=1,
        dry_run=False,
    )

    second_output = capsys.readouterr().out

    repository = SQLiteEntityRepository(
        SQLiteConnectionManager(target_path)
    )

    assert first_exit_code == 0
    assert "Criados: 1" in first_output
    assert "Correspondentes: 0" in first_output

    assert second_exit_code == 0
    assert "Criados: 0" in second_output
    assert "Correspondentes: 1" in second_output

    assert repository.count() == 1


def test_run_import_returns_two_when_record_fails(
    tmp_path,
    capsys,
):
    import sqlite3

    from pense_alm.shared.integration.cli import (
        run_import,
    )

    legacy_path = tmp_path / "legacy_error.sqlite3"
    target_path = tmp_path / "target_error.sqlite3"

    connection = sqlite3.connect(legacy_path)

    try:
        connection.execute(
            """
            CREATE TABLE issuers (
                id INTEGER PRIMARY KEY,
                cnpj TEXT,
                legal_name TEXT NOT NULL,
                trade_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
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
            (
                1,
                "12345678000199",
                "Empresa com Erro S.A.",
                None,
                "data-invalida",
                "2026-09-21 12:00:00",
            ),
        )

        connection.commit()
    finally:
        connection.close()

    exit_code = run_import(
        legacy_db=legacy_path,
        target_db=target_path,
        batch_size=1,
        dry_run=False,
    )

    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Erros: 1" in output
    assert "legacy_id=1" in output
    assert "tipo=ValueError" in output
    assert "Timestamp legado invalido." in output


def test_run_import_returns_three_when_record_is_blocked(
    tmp_path,
    capsys,
):
    import sqlite3

    from pense_alm.shared.integration import (
        DebentureIssuerAdapter,
        DebentureIssuerRecord,
    )
    from pense_alm.shared.integration.cli import (
        run_import,
    )
    from pense_alm.shared.persistence import (
        SQLiteConnectionManager,
        SQLiteEntityRepository,
    )

    legacy_path = tmp_path / "legacy_blocked.sqlite3"
    target_path = tmp_path / "target_blocked.sqlite3"

    connection = sqlite3.connect(legacy_path)

    try:
        connection.execute(
            """
            CREATE TABLE issuers (
                id INTEGER PRIMARY KEY,
                cnpj TEXT,
                legal_name TEXT NOT NULL,
                trade_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
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
            (
                1,
                "12345678000199",
                "Empresa Conflitante S.A.",
                "Empresa Conflitante",
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
        )

        connection.commit()
    finally:
        connection.close()

    repository = SQLiteEntityRepository(
        SQLiteConnectionManager(target_path)
    )

    existing = DebentureIssuerAdapter().convert(
        DebentureIssuerRecord(
            legacy_id=99,
            legal_name="Empresa Conflitante S.A.",
            trade_name="Empresa Conflitante",
            cnpj="99999999000199",
            created_at="2026-09-19 10:00:00",
            updated_at="2026-09-19 12:00:00",
        )
    )

    repository.save(existing)

    exit_code = run_import(
        legacy_db=legacy_path,
        target_db=target_path,
        batch_size=1,
        dry_run=False,
    )

    output = capsys.readouterr().out

    assert exit_code == 3
    assert "Bloqueados: 1" in output
    assert "Erros: 0" in output
    assert repository.count() == 1


def test_run_import_returns_four_when_record_requires_review(
    tmp_path,
    capsys,
):
    import sqlite3

    from pense_alm.shared.integration import (
        DebentureIssuerAdapter,
        DebentureIssuerRecord,
    )
    from pense_alm.shared.integration.cli import (
        run_import,
    )
    from pense_alm.shared.persistence import (
        SQLiteConnectionManager,
        SQLiteEntityRepository,
    )

    legacy_path = tmp_path / "legacy_review.sqlite3"
    target_path = tmp_path / "target_review.sqlite3"

    connection = sqlite3.connect(legacy_path)

    try:
        connection.execute(
            """
            CREATE TABLE issuers (
                id INTEGER PRIMARY KEY,
                cnpj TEXT,
                legal_name TEXT NOT NULL,
                trade_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
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
            (
                1,
                None,
                "Empresa para Revisao S.A.",
                "Empresa para Revisao",
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
        )

        connection.commit()
    finally:
        connection.close()

    repository = SQLiteEntityRepository(
        SQLiteConnectionManager(target_path)
    )

    existing = DebentureIssuerAdapter().convert(
        DebentureIssuerRecord(
            legacy_id=99,
            legal_name="Empresa para Revisao S.A.",
            trade_name="Empresa para Revisao",
            cnpj=None,
            created_at="2026-09-19 10:00:00",
            updated_at="2026-09-19 12:00:00",
        )
    )

    repository.save(existing)

    exit_code = run_import(
        legacy_db=legacy_path,
        target_db=target_path,
        batch_size=1,
        dry_run=False,
    )

    output = capsys.readouterr().out

    assert exit_code == 4
    assert "Revisao: 1" in output
    assert "Bloqueados: 0" in output
    assert "Erros: 0" in output
    assert repository.count() == 1
