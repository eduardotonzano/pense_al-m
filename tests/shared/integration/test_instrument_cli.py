"""Testes da entrada operacional de debentures (instrumento)."""

import hashlib
from pathlib import Path

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityIdentifier,
    EntityType,
    IdentifierType,
    RelationshipType,
    SourceType,
)
from pense_alm.shared.integration import (
    DebentureIssuerBatchImportService,
    LegacyDebentureIssuerReader,
)
from pense_alm.shared.integration import instrument_cli
from pense_alm.shared.integration.instrument_cli import (
    build_parser,
    main,
    run_instrument_import,
)
from pense_alm.shared.persistence import (
    SQLiteConnectionManager,
    SQLiteEntityRepository,
    SQLiteRelationshipRepository,
)


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def open_repositories(target_db):
    manager = SQLiteConnectionManager(target_db)

    return (
        SQLiteEntityRepository(manager),
        SQLiteRelationshipRepository(manager),
    )


@pytest.fixture
def seeded_target(tmp_path, legacy_database):
    """Destino sintetico que ja recebeu os emissores."""

    target_db = tmp_path / "destino" / "target.sqlite3"
    entities, _ = open_repositories(target_db)

    report = DebentureIssuerBatchImportService(
        LegacyDebentureIssuerReader(legacy_database),
        entities,
    ).run()

    assert report.created == 3

    return target_db


def instrument_totals(target_db):
    entities, relationships = open_repositories(target_db)

    return (
        entities.count(EntityType.DEBENTURE),
        relationships.count(RelationshipType.ISSUES),
    )


def test_parser_defaults_to_dry_run():
    arguments = build_parser().parse_args(
        [
            "--legacy-db",
            "legacy.sqlite3",
            "--target-db",
            "target.sqlite3",
        ]
    )

    assert arguments.legacy_db == Path("legacy.sqlite3")
    assert arguments.target_db == Path("target.sqlite3")
    assert arguments.batch_size == 100
    assert arguments.dry_run is False
    assert arguments.commit is False
    assert arguments.backup_dir is None
    assert arguments.create is False


@pytest.mark.parametrize(
    "extra",
    [
        ["--batch-size", "0"],
        ["--commit"],
        ["--backup-dir", "backups"],
        ["--create"],
        ["--dry-run", "--commit", "--backup-dir", "b"],
    ],
)
def test_main_rejects_invalid_arguments(
    tmp_path,
    legacy_database,
    extra,
):
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--legacy-db",
                str(legacy_database),
                "--target-db",
                str(tmp_path / "target.sqlite3"),
                *extra,
            ]
        )

    assert error.value.code == 2
    assert not (tmp_path / "target.sqlite3").exists()


def test_main_rejects_missing_legacy_database(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--legacy-db",
                str(tmp_path / "inexistente.sqlite3"),
                "--target-db",
                str(tmp_path / "target.sqlite3"),
            ]
        )

    assert error.value.code == 2


def test_main_rejects_same_source_and_target(legacy_database):
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--legacy-db",
                str(legacy_database),
                "--target-db",
                str(legacy_database),
            ]
        )

    assert error.value.code == 2


def test_main_rejects_commit_without_backup_dir_on_existing_target(
    seeded_target,
    legacy_database,
):
    target_before = sha256_of(seeded_target)

    with pytest.raises(SystemExit) as error:
        main(
            [
                "--legacy-db",
                str(legacy_database),
                "--target-db",
                str(seeded_target),
                "--commit",
            ]
        )

    assert error.value.code == 2
    assert sha256_of(seeded_target) == target_before


def test_commit_requires_create_for_missing_target(
    tmp_path,
    legacy_database,
):
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--legacy-db",
                str(legacy_database),
                "--target-db",
                str(tmp_path / "target.sqlite3"),
                "--commit",
                "--backup-dir",
                str(tmp_path / "backups"),
            ]
        )

    assert error.value.code == 2
    assert not (tmp_path / "target.sqlite3").exists()
    assert not (tmp_path / "backups").exists()


def test_dry_run_does_not_change_existing_target(
    seeded_target,
    legacy_database,
    capsys,
):
    target_before = sha256_of(seeded_target)
    legacy_before = sha256_of(legacy_database)

    exit_code = main(
        [
            "--legacy-db",
            str(legacy_database),
            "--target-db",
            str(seeded_target),
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 4
    assert "Modo: dry-run" in output
    assert "Total lido: 4" in output
    assert "Criados: 2" in output
    assert "Revisao: 2" in output
    assert "Dry run: True" in output
    assert sha256_of(seeded_target) == target_before
    assert sha256_of(legacy_database) == legacy_before
    assert instrument_totals(seeded_target) == (0, 0)


def test_explicit_dry_run_flag_behaves_like_default(
    seeded_target,
    legacy_database,
):
    target_before = sha256_of(seeded_target)

    exit_code = main(
        [
            "--legacy-db",
            str(legacy_database),
            "--target-db",
            str(seeded_target),
            "--dry-run",
        ]
    )

    assert exit_code == 4
    assert sha256_of(seeded_target) == target_before


def test_dry_run_with_missing_target_creates_nothing(
    tmp_path,
    legacy_database,
    capsys,
):
    target_db = tmp_path / "novo" / "target.sqlite3"

    exit_code = main(
        [
            "--legacy-db",
            str(legacy_database),
            "--target-db",
            str(target_db),
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 4
    assert "banco de destino inexistente" in output
    assert "Criados: 0" in output
    assert "Revisao: 4" in output
    assert not target_db.exists()
    assert not target_db.parent.exists()


def test_dry_run_lists_pending_records_with_reason(
    seeded_target,
    legacy_database,
    capsys,
):
    main(
        [
            "--legacy-db",
            str(legacy_database),
            "--target-db",
            str(seeded_target),
        ]
    )

    output = capsys.readouterr().out

    assert (
        "Pendente: legacy_id=3; codigo=SEMC13; isin=-; "
        "acao=review; motivo=issuer_without_cnpj"
    ) in output
    assert (
        "Pendente: legacy_id=4; codigo=-; "
        "isin=BRSEMEDBS003; acao=review; "
        "motivo=issuer_missing"
    ) in output


def test_commit_makes_backup_before_writing(
    seeded_target,
    legacy_database,
    tmp_path,
    capsys,
):
    backup_dir = tmp_path / "backups"

    exit_code = main(
        [
            "--legacy-db",
            str(legacy_database),
            "--target-db",
            str(seeded_target),
            "--commit",
            "--backup-dir",
            str(backup_dir),
        ]
    )

    output = capsys.readouterr().out
    backups = list(backup_dir.iterdir())

    assert exit_code == 4
    assert "Modo: commit" in output
    assert "Criados: 2" in output
    assert "Dry run: False" in output
    assert len(backups) == 1
    assert f"Backup: {backups[0]}" in output
    assert f"sha256: {sha256_of(backups[0])}" in output
    assert instrument_totals(seeded_target) == (2, 2)

    # O backup guarda o estado anterior a gravacao.
    assert instrument_totals(backups[0]) == (0, 0)


def test_commit_is_idempotent(
    seeded_target,
    legacy_database,
    tmp_path,
    capsys,
):
    arguments = [
        "--legacy-db",
        str(legacy_database),
        "--target-db",
        str(seeded_target),
        "--commit",
        "--backup-dir",
        str(tmp_path / "backups"),
    ]

    main(arguments)
    capsys.readouterr()

    exit_code = main(arguments)

    output = capsys.readouterr().out

    assert exit_code == 4
    assert "Criados: 0" in output
    assert "Correspondentes: 2" in output
    assert instrument_totals(seeded_target) == (2, 2)
    assert len(list((tmp_path / "backups").iterdir())) == 2


def test_commit_does_not_write_when_backup_fails(
    seeded_target,
    legacy_database,
    tmp_path,
    monkeypatch,
    capsys,
):
    def failing_backup(database_path, backup_dir):
        raise OSError("disco cheio")

    monkeypatch.setattr(
        instrument_cli,
        "create_sqlite_backup",
        failing_backup,
    )

    target_before = sha256_of(seeded_target)

    exit_code = main(
        [
            "--legacy-db",
            str(legacy_database),
            "--target-db",
            str(seeded_target),
            "--commit",
            "--backup-dir",
            str(tmp_path / "backups"),
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 2
    assert "nada foi gravado" in output
    assert "disco cheio" in output
    assert sha256_of(seeded_target) == target_before
    assert instrument_totals(seeded_target) == (0, 0)


def test_commit_with_create_builds_new_target_without_backup(
    tmp_path,
    legacy_database,
    capsys,
):
    target_db = tmp_path / "novo" / "target.sqlite3"
    backup_dir = tmp_path / "backups"

    exit_code = main(
        [
            "--legacy-db",
            str(legacy_database),
            "--target-db",
            str(target_db),
            "--commit",
            "--backup-dir",
            str(backup_dir),
            "--create",
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 4
    assert "nao ha o que copiar" in output
    assert target_db.is_file()
    assert not backup_dir.exists()
    assert instrument_totals(target_db) == (0, 0)


def test_commit_does_not_change_legacy_database(
    seeded_target,
    legacy_database,
    tmp_path,
):
    before = sha256_of(legacy_database)

    main(
        [
            "--legacy-db",
            str(legacy_database),
            "--target-db",
            str(seeded_target),
            "--commit",
            "--backup-dir",
            str(tmp_path / "backups"),
        ]
    )

    assert sha256_of(legacy_database) == before


def test_run_requires_backup_dir_for_commit(
    seeded_target,
    legacy_database,
):
    with pytest.raises(ValueError):
        run_instrument_import(
            legacy_db=legacy_database,
            target_db=seeded_target,
            batch_size=10,
            commit=True,
        )


def test_run_rejects_backup_dir_without_commit(
    seeded_target,
    legacy_database,
    tmp_path,
):
    with pytest.raises(ValueError):
        run_instrument_import(
            legacy_db=legacy_database,
            target_db=seeded_target,
            batch_size=10,
            backup_dir=tmp_path / "backups",
        )


def clean_legacy(legacy_database_factory):
    return legacy_database_factory(
        issuers=(
            (
                1,
                "12345678000199",
                "Empresa Alfa S.A.",
                None,
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
        ),
        debentures=(
            (
                1,
                1,
                "ALFA11",
                "BRALFADBS001",
                "active",
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
        ),
    )


def seed_issuers(target_db, legacy_db):
    entities, _ = open_repositories(target_db)

    DebentureIssuerBatchImportService(
        LegacyDebentureIssuerReader(legacy_db),
        entities,
    ).run()

    return entities


def test_exit_code_is_zero_without_pending(
    tmp_path,
    legacy_database_factory,
    capsys,
):
    legacy_db = clean_legacy(legacy_database_factory)
    target_db = tmp_path / "target.sqlite3"
    seed_issuers(target_db, legacy_db)

    exit_code = main(
        [
            "--legacy-db",
            str(legacy_db),
            "--target-db",
            str(target_db),
            "--commit",
            "--backup-dir",
            str(tmp_path / "backups"),
        ]
    )

    assert exit_code == 0
    assert "Pendente:" not in capsys.readouterr().out
    assert instrument_totals(target_db) == (1, 1)


def test_exit_code_is_three_when_blocked(
    tmp_path,
    legacy_database_factory,
    capsys,
):
    legacy_db = clean_legacy(legacy_database_factory)
    target_db = tmp_path / "target.sqlite3"
    entities = seed_issuers(target_db, legacy_db)

    provenance = DataProvenance(
        source_type=SourceType.MANUAL,
        source_name="Teste",
    )
    entities.save(
        Entity(
            legal_name="Empresa Qualquer S.A.",
            entity_type=EntityType.COMPANY,
            provenance=provenance,
            identifiers=(
                EntityIdentifier(
                    identifier_type=IdentifierType.ASSET_CODE,
                    value="ALFA11",
                    provenance=provenance,
                ),
            ),
        )
    )

    exit_code = main(
        [
            "--legacy-db",
            str(legacy_db),
            "--target-db",
            str(target_db),
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 3
    assert "Bloqueados: 1" in output
    assert "motivo=not_an_instrument" in output


def test_exit_code_is_two_for_invalid_legacy_row(
    tmp_path,
    legacy_database_factory,
    capsys,
):
    legacy_db = legacy_database_factory(
        issuers=(
            (
                1,
                "12345678000199",
                "Empresa Alfa S.A.",
                None,
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
        ),
        debentures=(
            (
                1,
                1,
                "ALFA11",
                "BR-ALFA-0001",
                "active",
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
        ),
    )
    target_db = tmp_path / "target.sqlite3"
    seed_issuers(target_db, legacy_db)

    exit_code = main(
        [
            "--legacy-db",
            str(legacy_db),
            "--target-db",
            str(target_db),
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Erros: 1" in output
    assert "legacy_id=1" in output
    assert "tipo=ValueError" in output

