import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_scheduled_collection.py"
)

SPEC = importlib.util.spec_from_file_location(
    "run_scheduled_collection",
    SCRIPT_PATH,
)

MODULE = importlib.util.module_from_spec(SPEC)

assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def create_project(tmp_path):
    """Cria uma estrutura mínima de projeto."""

    root = tmp_path / "project"

    source = (
        root
        / "src"
        / "debenture_search"
    )

    scripts = root / "scripts"
    config = root / "config"

    source.mkdir(parents=True)
    scripts.mkdir(parents=True)
    config.mkdir(parents=True)

    collection_script = (
        scripts
        / "run_collection.py"
    )

    collection_script.write_text(
        "print('ok')\n",
        encoding="utf-8",
    )

    configuration = (
        config
        / "collection.production.json"
    )

    configuration.write_text(
        "{}\n",
        encoding="utf-8",
    )

    return root


def test_find_project_root(tmp_path):
    root = create_project(tmp_path)

    nested = (
        root
        / "src"
        / "debenture_search"
    )

    assert MODULE.find_project_root(
        nested
    ) == root.resolve()


def test_find_project_root_from_file(tmp_path):
    root = create_project(tmp_path)

    file_path = (
        root
        / "scripts"
        / "helper.py"
    )

    file_path.write_text(
        "",
        encoding="utf-8",
    )

    assert MODULE.find_project_root(
        file_path
    ) == root.resolve()


def test_find_project_root_rejects_invalid_path(
    tmp_path,
):
    with pytest.raises(
        FileNotFoundError,
        match="raiz",
    ):
        MODULE.find_project_root(tmp_path)


def test_build_command_dry_run(tmp_path):
    root = create_project(tmp_path)

    command = MODULE.build_command(
        project_root=root,
        config_path=(
            "config/"
            "collection.production.json"
        ),
        committed=False,
        python_executable="python-test",
    )

    assert command[0] == "python-test"
    assert command[-1] == "--dry-run"
    assert (
        Path(command[1]).name
        == "run_collection.py"
    )


def test_build_command_commit(tmp_path):
    root = create_project(tmp_path)

    command = MODULE.build_command(
        project_root=root,
        config_path=(
            "config/"
            "collection.production.json"
        ),
        committed=True,
        python_executable="python-test",
    )

    assert command[-1] == "--commit"


def test_build_command_rejects_missing_config(
    tmp_path,
):
    root = create_project(tmp_path)

    with pytest.raises(
        FileNotFoundError,
        match="Configuracao",
    ):
        MODULE.build_command(
            project_root=root,
            config_path="config/missing.json",
            committed=False,
        )


def test_build_command_rejects_missing_script(
    tmp_path,
):
    root = create_project(tmp_path)

    (
        root
        / "scripts"
        / "run_collection.py"
    ).unlink()

    with pytest.raises(
        FileNotFoundError,
        match="Script principal",
    ):
        MODULE.build_command(
            project_root=root,
            config_path=(
                "config/"
                "collection.production.json"
            ),
            committed=False,
        )


@pytest.mark.parametrize(
    "exit_code",
    [0, 1, 2, 3, 4, 130],
)
def test_preserves_exit_code(
    tmp_path,
    exit_code,
):
    root = create_project(tmp_path)
    calls = []

    def runner(command, cwd, check):
        calls.append(
            {
                "command": command,
                "cwd": cwd,
                "check": check,
            }
        )

        return SimpleNamespace(
            returncode=exit_code
        )

    result = (
        MODULE.execute_scheduled_collection(
            project_root=root,
            config_path=(
                "config/"
                "collection.production.json"
            ),
            committed=False,
            python_executable="python-test",
            runner=runner,
        )
    )

    assert result == exit_code
    assert len(calls) == 1
    assert calls[0]["cwd"] == str(
        root.resolve()
    )
    assert calls[0]["check"] is False


def test_main_returns_one_for_missing_project(
    tmp_path,
):
    result = MODULE.main(
        [
            "--project-root",
            str(tmp_path),
            "--dry-run",
        ]
    )

    assert result == 1