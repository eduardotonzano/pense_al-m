import pathlib
import sqlite3

import pytest

from apoio import make_test_cnpj
from fundos import backup
from fundos.backup import BackupError
from fundos.backup import check_local_path
from fundos.backup import check_path_length
from fundos.backup import create_backup
from fundos.backup import file_sha256
from fundos.backup import network_reason


# Caminhos de rede ficticios: o servidor nao existe, e nenhum teste toca a
# rede, porque a recusa vem antes de qualquer acesso ao caminho.
NETWORK_PATHS = (
    "\\\\servidor\\pasta\\fundos.db",
    "//servidor/pasta/fundos.db",
    "\\\\?\\UNC\\servidor\\pasta\\fundos.db",
    "\\\\?\\C:\\pense\\fundos\\fundos.db",
)


def only_l_is_remote(drive):
    return backup.REMOTE_DRIVE if drive.upper() == "L:" else 3


def test_backup_is_a_valid_copy_with_short_name(db, tmp_path):
    result = create_backup(db.database_path, tmp_path / "bk")

    assert result.path.parent == tmp_path / "bk"
    assert result.path.name.startswith("fundos_")
    assert result.path.suffix == ".sqlite3"
    assert result.sha256 == file_sha256(result.path)
    assert result.size_bytes == result.path.stat().st_size

    copy = sqlite3.connect(result.path)
    try:
        versions = copy.execute("SELECT version FROM schema_migrations").fetchall()
    finally:
        copy.close()

    assert versions == [(1,)]


def test_missing_or_invalid_database_is_refused(tmp_path):
    garbage = tmp_path / "lixo.db"
    garbage.write_bytes(b"isto nao e um banco sqlite" * 10)

    with pytest.raises(BackupError, match="nao encontrado"):
        create_backup(tmp_path / "inexistente.db", tmp_path / "bk")

    with pytest.raises(BackupError, match="nao e valido"):
        create_backup(garbage, tmp_path / "bk")

    assert not (tmp_path / "bk").exists()


def test_database_with_foreign_key_errors_is_refused(db, tmp_path):
    raw = sqlite3.connect(db.database_path)
    try:
        raw.execute(
            "INSERT INTO fund_classes (fund_id, cnpj) VALUES (999, ?)",
            (make_test_cnpj(1),),
        )
        raw.commit()
    finally:
        raw.close()

    with pytest.raises(BackupError, match="chave estrangeira"):
        create_backup(db.database_path, tmp_path / "bk")


def test_long_backup_path_is_refused_before_creating_anything(db, tmp_path):
    long_dir = tmp_path / ("b" * 255)

    with pytest.raises(BackupError, match="caminho longo") as error:
        create_backup(db.database_path, long_dir)

    assert "--backup-dir" in str(error.value)
    assert not long_dir.exists()

    check_path_length("C:\\bk\\fundos\\fundos_20261027T130000_000000Z.sqlite3")

    with pytest.raises(BackupError, match="caminho longo"):
        check_path_length("C:\\" + "x" * 251)


@pytest.mark.parametrize("path", NETWORK_PATHS)
def test_network_path_is_refused(path):
    # O prefixo de caminho estendido com unidade local tambem e recusado:
    # falso positivo seguro, como na fundos_cli.
    assert network_reason(path) == "UNC"

    with pytest.raises(BackupError, match=r"--database em caminho de rede \(UNC\)"):
        check_local_path(path, "--database")


def test_relative_path_inside_a_network_folder_is_refused(monkeypatch):
    # Como rodar o script de dentro do clone, que fica no compartilhamento.
    monkeypatch.setattr(backup, "_absolute", lambda text: "\\\\servidor\\pasta\\" + text)

    assert network_reason("fundos.db") == "UNC"


def test_remote_drive_is_refused(monkeypatch):
    monkeypatch.setattr(backup, "_drive_type", only_l_is_remote)

    assert network_reason("L:\\pasta\\fundos.db") == "unidade remota"
    assert network_reason("l:\\pasta\\fundos.db") == "unidade remota"

    with pytest.raises(BackupError, match=r"--backup-dir em caminho de rede \(unidade remota\)"):
        check_local_path("L:\\bk", "--backup-dir")

    # Relativo com a pasta atual numa unidade remota.
    monkeypatch.setattr(backup, "_absolute", lambda text: "L:\\pasta\\" + text)

    assert network_reason("fundos.db") == "unidade remota"


def test_local_paths_are_accepted(monkeypatch, tmp_path):
    assert network_reason(tmp_path / "fundos.db") is None
    check_local_path(tmp_path / "fundos.db", "--database")

    monkeypatch.setattr(backup, "_drive_type", only_l_is_remote)

    assert network_reason("C:\\pense\\fundos\\fundos.db") is None

    # Fora do Windows o tipo da unidade nao e conhecido: nao recusa.
    monkeypatch.setattr(backup, "_drive_type", lambda drive: None)

    assert network_reason("L:\\pasta\\fundos.db") is None


def test_check_does_not_touch_the_path(monkeypatch):
    def touched(*args, **kwargs):
        raise AssertionError("o caminho foi tocado")

    for name in ("resolve", "exists", "is_file", "stat"):
        monkeypatch.setattr(pathlib.Path, name, touched)

    monkeypatch.setattr(backup, "_drive_type", only_l_is_remote)

    for path in NETWORK_PATHS + ("L:\\pasta\\fundos.db",):
        with pytest.raises(BackupError):
            check_local_path(path, "--database")

    check_local_path("C:\\pense\\fundos\\fundos.db", "--database")


def test_refusal_message_has_only_the_label_and_the_reason(monkeypatch):
    monkeypatch.setattr(backup, "_drive_type", only_l_is_remote)

    for path, reason in (("\\\\servidor\\pasta\\fundos.db", "UNC"), ("L:\\pasta\\fundos.db", "unidade remota")):
        with pytest.raises(BackupError) as error:
            check_local_path(path, "--backup-dir")

        message = str(error.value)

        assert message.startswith("--backup-dir em caminho de rede (" + reason + "): ")

        for part in ("servidor", "\\", "/", "fundos.db", "L:"):
            assert part not in message
