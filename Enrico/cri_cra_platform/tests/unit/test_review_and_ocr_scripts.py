"""Testes dos scripts auxiliares de revisão, OCR e série de DFs (sem rede, banco temporário)."""
from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest

from credit_assets.database.connection import connect, initialize_database

PROJECT = Path(__file__).parents[2]


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "t.db"
    connection = connect(path)
    initialize_database(connection)
    connection.execute(
        """INSERT INTO assets (codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora, emissao, serie,
               created_at, updated_at) VALUES ('CRA0TESTE01', 'CRA', 'S', '1', '1', '1', 'now', 'now')"""
    )
    for number in (1, 2):
        connection.execute(
            "INSERT INTO asset_series (asset_id, numero_serie, evidence_json) VALUES (1, ?, '{}')", (number,)
        )
    connection.commit()
    connection.close()
    return path


def _run(script: str, argv: list[str], monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", [script, *argv])
    with pytest.raises(SystemExit) as finished:
        runpy.run_path(str(PROJECT / "scripts" / script), run_name="__main__")
    assert finished.value.code == 0


def test_review_asset_series_approves_only_selected_pending(tmp_path, monkeypatch, capsys):
    database = _database(tmp_path)
    _run("review_asset_series.py", ["--cetip", "CRA0TESTE01", "--status", "approved", "--by", "Revisor",
                                    "--source", "teste", "--serie", "2", "--database", str(database)], monkeypatch)
    connection = connect(database)
    rows = dict(connection.execute("SELECT numero_serie, review_status FROM asset_series").fetchall())
    reviewer = connection.execute("SELECT reviewed_by FROM asset_series WHERE numero_serie = 2").fetchone()[0]
    assert rows == {1: "pending", 2: "approved"}
    assert reviewer == "Revisor (teste)"
    assert "'reviewed': 1" in capsys.readouterr().out


def test_ocr_lines_are_grouped_by_vertical_position():
    namespace = runpy.run_path(str(PROJECT / "scripts" / "ocr_document_pages.py"), run_name="ocr")
    boxes = [
        ([[300, 10], [400, 10], [400, 30], [300, 30]], "10,02330500", 0.99),
        ([[10, 12], [100, 12], [100, 28], [10, 28]], "30/09/2024", 0.98),
        ([[10, 60], [120, 60], [120, 80], [10, 80]], "29/10/2024", 0.80),
    ]
    text, mean = namespace["lines_from_boxes"](boxes)
    assert text.splitlines() == ["30/09/2024   10,02330500", "29/10/2024"]
    assert round(mean, 3) == round((0.99 + 0.98 + 0.80) / 3, 3)
    assert namespace["lines_from_boxes"]([]) == ("", 0.0)


def test_fact_aliases_do_not_repeat_a_fact_name_between_indicators():
    config = json.loads((PROJECT / "config" / "fact_aliases.json").read_text(encoding="utf-8"))
    names = [name for group in config["indicators"].values() for name in group]
    assert len(names) == len(set(names))
