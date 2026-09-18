import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "snd_import_one.py"


def load_module():
    specification = importlib.util.spec_from_file_location(
        "snd_import_one",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class FakeProvider:
    def __init__(self):
        self.fetch_calls = []
        self.collect_calls = []

    def normalize_asset_code(self, value):
        normalized = "".join(str(value).strip().upper().split())
        if not normalized:
            raise ValueError("O codigo do ativo e obrigatorio.")
        return normalized

    def fetch_html(self, code):
        self.fetch_calls.append(code)
        text = (
            "Codigo do Ativo\tEmpresa\tISIN\n"
            "PETR27\tPETROBRAS\tBRPETRDBS0C2\n"
        )
        return SimpleNamespace(
            url="https://example.test?Ativo=PETR27",
            status=200,
            content_type="application/vnd.ms-excel",
            text=text,
            size_bytes=len(text.encode("utf-8")),
        )

    def collect(self, code):
        self.collect_calls.append(code)
        return SimpleNamespace(
            status="success",
            issuer_id=1,
            debenture_id=2,
            raw_record_id=3,
            observations_created=4,
            observations_reused=0,
            conflicts_created=0,
        )


class FakeBackupService:
    def __init__(self):
        self.calls = 0

    def create_backup(self):
        self.calls += 1
        return SimpleNamespace(path=Path("backup.sqlite3"))


def test_default_mode_is_preview():
    module = load_module()
    arguments = module.build_argument_parser().parse_args([])

    assert arguments.asset_code == "PETR27"
    assert arguments.commit is False


def test_commit_flag_is_explicit():
    module = load_module()
    arguments = module.build_argument_parser().parse_args(
        ["PETR27", "--commit"]
    )

    assert arguments.commit is True


def test_preview_does_not_collect_or_backup():
    module = load_module()
    provider = FakeProvider()
    backup = FakeBackupService()

    result = module.run(
        "petr27",
        commit=False,
        provider=provider,
        backup_service=backup,
    )

    assert result.parsed_asset_code == "PETR27"
    assert provider.fetch_calls == ["PETR27"]
    assert provider.collect_calls == []
    assert backup.calls == 0


def test_preview_prints_no_write(capsys):
    module = load_module()
    result = module.run(
        "PETR27",
        commit=False,
        provider=FakeProvider(),
    )

    module.print_preview(result)
    output = capsys.readouterr().out

    assert "Gravacao no banco: NAO EXECUTADA" in output


def test_commit_creates_backup_before_collect(monkeypatch):
    module = load_module()
    events = []

    class Backup:
        def create_backup(self):
            events.append("backup")
            return SimpleNamespace(path=Path("backup.sqlite3"))

    class Provider(FakeProvider):
        def collect(self, code):
            events.append("collect")
            return super().collect(code)

    monkeypatch.setattr(
        module.database,
        "integrity_check",
        lambda: "ok",
    )
    monkeypatch.setattr(
        module.database,
        "foreign_key_check",
        lambda: [],
    )

    result, path = module.run(
        "PETR27",
        commit=True,
        provider=Provider(),
        backup_service=Backup(),
    )

    assert events == ["backup", "collect"]
    assert result.status == "success"
    assert path == Path("backup.sqlite3")


def test_rejects_empty_asset_code():
    module = load_module()

    with pytest.raises(ValueError, match="obrigatorio"):
        module.run(" ", provider=FakeProvider())
