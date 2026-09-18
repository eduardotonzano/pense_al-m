from pathlib import Path
from types import SimpleNamespace

import pytest

from debenture_search.services.snd_batch_import_service import (
    SndBatchImportService,
)


class Database:
    def integrity_check(self):
        return "ok"

    def foreign_key_check(self):
        return []


class Provider:
    def __init__(self, failing=None):
        self.failing = set(failing or [])
        self.fetch_calls = []
        self.collect_calls = []

    def normalize_asset_code(self, value):
        code = "".join(str(value).strip().upper().split())
        if not code:
            raise ValueError("codigo obrigatorio")
        return code

    def fetch_html(self, code):
        self.fetch_calls.append(code)
        if code in self.failing:
            raise RuntimeError("falha simulada")
        return SimpleNamespace(text="conteudo")

    def collect(self, code):
        self.collect_calls.append(code)
        if code in self.failing:
            raise RuntimeError("falha simulada")
        return SimpleNamespace(
            observations_created=1,
            observations_reused=2,
            conflicts_created=0,
        )


class Backup:
    def __init__(self):
        self.calls = 0

    def create_backup(self):
        self.calls += 1
        return SimpleNamespace(path=Path("backup.sqlite3"))


def test_normalizes_and_removes_duplicates():
    service = SndBatchImportService(Database(), Provider())
    assert service.normalize_codes([" petr27 ", "PETR27", "cepea1"]) == [
        "PETR27",
        "CEPEA1",
    ]


def test_preview_does_not_backup_or_collect():
    provider = Provider()
    backup = Backup()
    result = SndBatchImportService(
        Database(), provider, backup
    ).run(["PETR27", "CEPEA1"], commit=False)

    assert result.successes == 2
    assert backup.calls == 0
    assert provider.collect_calls == []
    assert provider.fetch_calls == ["PETR27", "CEPEA1"]


def test_commit_creates_one_backup():
    provider = Provider()
    backup = Backup()
    result = SndBatchImportService(
        Database(), provider, backup
    ).run(["PETR27", "CEPEA1"], commit=True)

    assert backup.calls == 1
    assert result.observations_created == 2
    assert result.observations_reused == 4


def test_one_failure_does_not_stop_batch():
    backup = Backup()

    result = SndBatchImportService(
        Database(),
        Provider(failing={"CEPEA1"}),
        backup_service=backup,
    ).run(
        ["PETR27", "CEPEA1", "SBSPC9"],
        commit=True,
    )

    assert backup.calls == 1
    assert result.processed == 3
    assert result.successes == 2
    assert result.failures == 1
    assert result.items[1].status == "failed"


def test_rejects_limit_excess():
    service = SndBatchImportService(
        Database(), Provider(), max_items=2
    )

    with pytest.raises(ValueError, match="excede o limite"):
        service.run(["A1", "A2", "A3"])


def test_rejects_empty_list():
    service = SndBatchImportService(Database(), Provider())

    with pytest.raises(ValueError, match="nao possui codigos"):
        service.run(["", "  "])
