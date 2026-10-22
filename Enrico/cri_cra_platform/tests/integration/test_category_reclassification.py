from __future__ import annotations

import importlib.util
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from credit_assets.database.backup import file_sha256
from credit_assets.database.connection import connect, initialize_database
from credit_assets.services.category_reclassification import (
    ReclassificationError,
    apply_changes,
    build_preview,
    commit_reclassification,
    format_preview,
    load_documents,
    open_read_only,
    select_changes,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_DIR / "scripts" / "reclassify_documents.py"
RUN_ID = "reclassification-test-run"


def doc(source_id, category, name, **grid):
    return {"id": source_id, "category": category, "name": name, **grid}


# Documentos reais conhecidos (categoria e nome como guardados no banco).
EVIDENCE = [
    doc("981509", "Outro", "Informe Mensal de CRA"),
    doc("1300722", "Outro", "Informe Mensal de CRA"),
    doc("1319505", "Outro", "AGO/E"),
    doc("1328844", "Informe Mensal", "Informe Mensal de CRA"),
    doc("1340289", "Ata/Edital", "AGO/E"),
    doc("355426", "Termo de Securitização", "Documento"),
    doc("1300985", "Outro", "Informe Mensal de CRI"),
    doc("1298856", "Outro", "Demonstrações Financeiras"),
    doc("1264371", "Outro", "Informe Mensal de CRI"),
]
# Sintetico: rotulo antigo errado (Demonstracoes Financeiras como Informe Mensal).
MISLABELED = doc("mislabel-1", "Informe Mensal", "Demonstrações Financeiras")


def make_database(tmp_path: Path, documents, migrated: bool = True) -> Path:
    empty = tmp_path / "no_migrations"
    empty.mkdir(exist_ok=True)
    path = tmp_path / "cri_cra.db"
    connection = connect(path)
    initialize_database(connection, None if migrated else empty)
    connection.execute(
        "INSERT INTO executions (run_id, started_at, status) "
        "VALUES (?, '2026-01-01T00:00:00Z', 'success')",
        (RUN_ID,),
    )
    connection.execute(
        """INSERT INTO assets (
            codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora,
            emissao, serie, created_at, updated_at
        ) VALUES ('REC0001', 'CRA', 'S', '1', '1', '1', 'now', 'now')"""
    )

    for item in documents:
        connection.execute(
            """INSERT INTO documents (
                source_document_id, asset_id, category, document_name,
                source, source_url, run_id
            ) VALUES (?, 1, ?, ?, 'Fundos.NET', 'https://example.test/doc', ?)""",
            (item["id"], item["category"], item["name"], RUN_ID),
        )

        if migrated:
            connection.execute(
                "UPDATE documents SET source_category = ?, source_type = ?, "
                "source_species = ? WHERE source_document_id = ?",
                (
                    item.get("grid_category"),
                    item.get("grid_type"),
                    item.get("grid_species"),
                    item["id"],
                ),
            )

    connection.commit()
    connection.close()
    return path


def preview_of(path: Path) -> dict:
    with closing(open_read_only(path)) as reader:
        rows, grid = load_documents(reader)

    return build_preview(rows, grid, str(path))


def categories(path: Path) -> dict:
    with closing(sqlite3.connect(path)) as connection:
        return dict(
            connection.execute(
                "SELECT source_document_id, category FROM documents"
            ).fetchall()
        )


def load_script():
    specification = importlib.util.spec_from_file_location(
        "reclassify_documents_script", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def source_ids(changes) -> list[str]:
    return [item["name"] for item in changes]


def test_preview_with_the_available_evidence(tmp_path):
    path = make_database(tmp_path, [*EVIDENCE, MISLABELED])

    preview = preview_of(path)
    verified = preview["verified"]

    assert preview["documents"] == 10
    assert preview["currently_other"] == 6
    assert verified["by_transition"] == {"Outro -> Informe Mensal": 4}
    assert verified["by_rule"] == {"IM-01": 4}
    assert [item["document_pk"] for item in verified["changes"]] == [1, 2, 7, 9]
    assert verified["vetoed"] == 1
    assert verified["unmatched"] == 1
    assert verified["ambiguous"] == []
    assert [item["name"] for item in verified["disagreements"]] == [
        "Demonstrações Financeiras"
    ]
    assert verified["disagreements"][0]["vetoed"] is True
    assert preview["unverified"]["changes"] == []
    assert len(select_changes(preview)) == 4
    assert len(select_changes(preview, include_unverified=True)) == 4


def test_preview_uses_the_grid_fields_when_they_exist(tmp_path):
    documents = [
        doc("a", "Outro", "AGO/E", grid_species="Ata da Assembleia"),
        doc("b", "Outro", "AGO/E", grid_species="Sumário das Decisões"),
        doc("c", "Outro", "Documento", grid_type="Informe Mensal de CRA"),
        doc("d", "Outro", "Documento", grid_species="Edital de Convocação"),
    ]
    path = make_database(tmp_path, documents)

    preview = preview_of(path)

    assert preview["grid_fields_available"] is True
    assert preview["documents_with_grid_fields"] == 4
    changed = {item["document_pk"]: item["to"] for item in preview["verified"]["changes"]}
    assert changed == {1: "Ata/Edital", 3: "Informe Mensal", 4: "Ata/Edital"}
    assert preview["verified"]["unmatched"] == 1


def test_preview_separates_the_unverified_group(tmp_path):
    documents = [
        doc("termo", "Outro", "Termo de Securitização"),
        doc("adit", "Outro", "Aditamento ao Termo de Securitização"),
        doc("fato", "Outro", "Fato Relevante"),
        doc("ok", "Outro", "Informe Mensal de CRA"),
        doc("conflito", "Outro", "Informe Mensal de CRA", grid_species="Fato Relevante"),
        doc("enc", "Outro", "Termo de Encerramento"),
    ]
    path = make_database(tmp_path, documents)

    preview = preview_of(path)

    verified, unverified = preview["verified"], preview["unverified"]
    assert [item["name"] for item in verified["changes"]] == [
        "Informe Mensal de CRA",
        "Informe Mensal de CRA",
    ]
    assert unverified["by_transition"] == {
        "Outro -> Aditamento": 1,
        "Outro -> Fato Relevante": 1,
        "Outro -> Termo de Securitização": 1,
    }
    assert unverified["by_rule"] == {"ADT-01": 1, "FR-01": 1, "TS-01": 1}
    assert [item["document_pk"] for item in unverified["lost_to_ambiguity"]] == [5]
    assert unverified["lost_to_ambiguity"][0]["candidates"] == [
        "Informe Mensal",
        "Fato Relevante",
    ]
    assert len(select_changes(preview)) == 2
    with_flag = select_changes(preview, include_unverified=True)
    assert sorted(item["document_pk"] for item in with_flag) == [1, 2, 3, 4]


def test_preview_flags_unverified_disagreements_without_writing(tmp_path):
    path = make_database(
        tmp_path, [doc("x", "Informe Mensal", "Fato Relevante")]
    )

    preview = preview_of(path)

    assert preview["verified"]["disagreements"] == []
    assert [item["strict"] for item in preview["unverified"]["disagreements"]] == [
        "Fato Relevante"
    ]
    assert select_changes(preview, include_unverified=True) == []


def test_preview_without_the_catalog_columns_uses_names_only(tmp_path):
    path = make_database(tmp_path, EVIDENCE, migrated=False)

    preview = preview_of(path)
    text = format_preview(preview)

    assert preview["grid_fields_available"] is False
    assert preview["documents_with_grid_fields"] == 0
    assert len(preview["verified"]["changes"]) == 4
    assert "migration 001 pendente" in text


def test_format_preview_shows_both_sections_and_the_totals(tmp_path):
    path = make_database(tmp_path, [*EVIDENCE, MISLABELED])

    text = format_preview(preview_of(path))

    assert "== Regras verificadas (valem por padrao) ==" in text
    assert "== Regras nao verificadas (so valem com --enable-unverified-rules) ==" in text
    assert "Mudariam de categoria: 4" in text
    assert "Outro -> Informe Mensal: 4" in text
    assert "Por regra: IM-01: 4" in text
    assert "Por regra: nenhuma" in text
    assert "Mudariam alem das verificadas: 0" in text
    assert "Sem --enable-unverified-rules: 4 documento(s)" in text
    assert "atual Informe Mensal, DF-VETO-01 (veto)" in text


def test_dry_run_never_writes_and_can_save_a_json_report(tmp_path, capsys):
    script = load_script()
    path = make_database(tmp_path, [*EVIDENCE, MISLABELED])
    before = file_sha256(path)
    report = tmp_path / "preview.json"

    code = script.main(
        ["--database", str(path), "--dry-run", "--report-path", str(report)]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert file_sha256(path) == before
    assert "Dry-run concluido" in output
    assert "== Regras verificadas" in output and "== Regras nao verificadas" in output
    data = json.loads(report.read_text(encoding="utf-8"))
    assert len(data["verified"]["changes"]) == 4
    assert not (tmp_path / "backups").exists()


def test_commit_writes_only_the_verified_group_with_audit_and_backup(tmp_path, capsys):
    script = load_script()
    documents = [*EVIDENCE, MISLABELED, doc("termo", "Outro", "Termo de Securitização")]
    path = make_database(tmp_path, documents)
    saved = tmp_path / "saved"
    before = categories(path)

    code = script.main(
        ["--database", str(path), "--commit", "--backup-dir", str(saved)]
    )
    output = capsys.readouterr().out
    after = categories(path)
    backups = sorted(saved.glob("*.sqlite3"))

    assert code == 0
    assert [k for k in after if after[k] != before[k]] == [
        "981509", "1300722", "1300985", "1264371",
    ]
    assert {after[k] for k in ("981509", "1300722", "1300985", "1264371")} == {
        "Informe Mensal"
    }
    # O que ficou de fora: sem regra, vetado, ja especifico e grupo nao verificado.
    assert after["1319505"] == after["1298856"] == after["termo"] == "Outro"
    assert after["mislabel-1"] == "Informe Mensal"
    assert after["1340289"] == "Ata/Edital"
    assert after["355426"] == "Termo de Securitização"
    assert len(backups) == 1
    assert categories(backups[0]) == before
    assert file_sha256(backups[0]) in output

    with closing(sqlite3.connect(path)) as connection:
        audit = connection.execute(
            "SELECT old_category, new_category, rule_id, rule_group, "
            "classifier_version, run_id FROM document_category_changes"
        ).fetchall()
        execution = connection.execute(
            "SELECT status, documents_found FROM executions WHERE run_id = ?",
            (audit[0][5],),
        ).fetchone()
        assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 11
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    assert len(audit) == 4
    assert {row[:5] for row in audit} == {
        ("Outro", "Informe Mensal", "IM-01", "verified", "1.0.0")
    }
    assert execution == ("success", 4)


def test_commit_with_the_flag_also_writes_the_unverified_group(tmp_path, capsys):
    script = load_script()
    documents = [
        doc("termo", "Outro", "Termo de Securitização"),
        doc("adit", "Outro", "Aditamento ao Termo de Securitização"),
        doc("ok", "Outro", "Informe Mensal de CRA"),
        doc("conflito", "Outro", "Informe Mensal de CRA", grid_species="Fato Relevante"),
    ]
    path = make_database(tmp_path, documents)

    code = script.main(
        [
            "--database", str(path), "--commit", "--enable-unverified-rules",
            "--backup-dir", str(tmp_path / "saved"),
        ]
    )
    capsys.readouterr()
    after = categories(path)

    assert code == 0
    assert after == {
        "termo": "Termo de Securitização",
        "adit": "Aditamento",
        "ok": "Informe Mensal",
        "conflito": "Outro",
    }
    with closing(sqlite3.connect(path)) as connection:
        groups = dict(
            connection.execute(
                "SELECT rule_id, rule_group FROM document_category_changes"
            ).fetchall()
        )
    assert groups == {"TS-01": "unverified", "ADT-01": "unverified", "IM-01": "verified"}


def test_second_commit_has_nothing_to_write_and_makes_no_backup(tmp_path, capsys):
    script = load_script()
    path = make_database(tmp_path, EVIDENCE)
    saved = tmp_path / "saved"
    arguments = ["--database", str(path), "--commit", "--backup-dir", str(saved)]

    first = script.main(arguments)
    capsys.readouterr()
    second = script.main(arguments)
    output = capsys.readouterr().out

    assert (first, second) == (0, 0)
    assert "Nada a gravar" in output
    assert len(list(saved.glob("*.sqlite3"))) == 1


def test_commit_requires_the_audit_table(tmp_path, capsys):
    script = load_script()
    path = make_database(tmp_path, EVIDENCE, migrated=False)
    before = file_sha256(path)

    code = script.main(["--database", str(path), "--commit"])
    error = capsys.readouterr().err

    assert code == 1
    assert "apply_migration.py" in error
    assert file_sha256(path) == before
    assert not (tmp_path / "backups").exists()


def test_apply_changes_rolls_back_when_a_document_changed_meanwhile(tmp_path):
    path = make_database(tmp_path, EVIDENCE)
    preview = preview_of(path)
    changes = select_changes(preview)
    # Um dos documentos deixou de estar em "Outro" depois da previa.
    with closing(sqlite3.connect(path)) as other:
        other.execute(
            "UPDATE documents SET category = 'Fato Relevante' WHERE document_pk = ?",
            (changes[-1]["document_pk"],),
        )
        other.commit()
    before = categories(path)
    connection = connect(path)

    with pytest.raises(ReclassificationError, match="mudou durante a regravacao"):
        apply_changes(connection, changes, "rollback-run")

    connection.close()
    assert categories(path) == before
    with closing(sqlite3.connect(path)) as check:
        assert check.execute("SELECT COUNT(*) FROM document_category_changes").fetchone()[0] == 0
        assert check.execute(
            "SELECT COUNT(*) FROM executions WHERE run_id = 'rollback-run'"
        ).fetchone()[0] == 0


def test_commit_never_changes_an_already_specific_category(tmp_path):
    path = make_database(
        tmp_path,
        [
            doc("a", "Fato Relevante", "Informe Mensal de CRA"),
            doc("b", "Outro", "Informe Mensal de CRA"),
        ],
    )

    result = commit_reclassification(path, backup_dir=tmp_path / "saved")

    assert result["changes"] == 1
    assert categories(path) == {"a": "Fato Relevante", "b": "Informe Mensal"}


def test_missing_database_and_missing_mode_are_refused(tmp_path, capsys):
    script = load_script()

    code = script.main(["--database", str(tmp_path / "missing.db"), "--dry-run"])
    error = capsys.readouterr().err

    assert code == 1
    assert "Banco nao encontrado" in error
    assert not (tmp_path / "missing.db").exists()
    with pytest.raises(SystemExit) as no_mode:
        script.main(["--database", str(tmp_path / "x.db")])
    with pytest.raises(SystemExit) as no_database:
        script.main(["--dry-run"])
    assert (no_mode.value.code, no_database.value.code) == (2, 2)
