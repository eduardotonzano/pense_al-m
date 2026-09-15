import argparse
import subprocess
import sys
from pathlib import Path


def find_project_root(start_path=None):
    """Localiza a raiz do projeto a partir deste script."""

    if start_path is None:
        current = Path(__file__).resolve().parent
    else:
        current = Path(start_path).resolve()

        if current.is_file():
            current = current.parent

    for candidate in (current, *current.parents):
        source_directory = (
            candidate
            / "src"
            / "debenture_search"
        )

        collection_script = (
            candidate
            / "scripts"
            / "run_collection.py"
        )

        if (
            source_directory.is_dir()
            and collection_script.is_file()
        ):
            return candidate

    raise FileNotFoundError(
        "Nao foi possivel localizar a raiz "
        "do projeto."
    )


def build_argument_parser():
    """Configura os argumentos da execução agendada."""

    parser = argparse.ArgumentParser(
        description=(
            "Executa a coleta de debentures "
            "em modo agendado."
        )
    )

    parser.add_argument(
        "--project-root",
        default=None,
        help=(
            "Raiz do projeto. Quando omitida, "
            "sera localizada automaticamente."
        ),
    )

    parser.add_argument(
        "--config",
        default=(
            "config/collection.production.json"
        ),
        help=(
            "Arquivo de configuracao relativo "
            "a raiz do projeto."
        ),
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa sem gravar no banco.",
    )

    mode.add_argument(
        "--commit",
        action="store_true",
        help="Executa com gravacao autorizada.",
    )

    return parser


def build_command(
    project_root,
    config_path,
    committed,
    python_executable=None,
):
    """Monta o comando do processo de coleta."""

    root = Path(project_root).resolve()

    collection_script = (
        root
        / "scripts"
        / "run_collection.py"
    )

    configuration = Path(config_path)

    if not configuration.is_absolute():
        configuration = (
            root
            / configuration
        )

    configuration = configuration.resolve()

    if not collection_script.is_file():
        raise FileNotFoundError(
            "Script principal nao encontrado: "
            + str(collection_script)
        )

    if not configuration.is_file():
        raise FileNotFoundError(
            "Configuracao nao encontrada: "
            + str(configuration)
        )

    python_path = (
        python_executable
        or sys.executable
    )

    mode = (
        "--commit"
        if committed
        else "--dry-run"
    )

    return [
        str(python_path),
        str(collection_script),
        str(configuration),
        mode,
    ]


def execute_scheduled_collection(
    project_root,
    config_path,
    committed,
    python_executable=None,
    runner=None,
):
    """Executa a coleta e preserva o código de saída."""

    root = Path(project_root).resolve()

    command = build_command(
        root,
        config_path,
        committed,
        python_executable=python_executable,
    )

    process_runner = (
        runner
        or subprocess.run
    )

    completed = process_runner(
        command,
        cwd=str(root),
        check=False,
    )

    return int(completed.returncode)


def main(argv=None):
    """Ponto de entrada da execução agendada."""

    arguments = (
        build_argument_parser()
        .parse_args(argv)
    )

    try:
        if arguments.project_root:
            project_root = Path(
                arguments.project_root
            ).resolve()
        else:
            project_root = find_project_root()

        return execute_scheduled_collection(
            project_root=project_root,
            config_path=arguments.config,
            committed=arguments.commit,
        )

    except FileNotFoundError as error:
        print(
            "Falha:",
            error,
            file=sys.stderr,
        )

        return 1

    except KeyboardInterrupt:
        print(
            "Falha: execucao interrompida "
            "pelo usuario.",
            file=sys.stderr,
        )

        return 130

    except Exception as error:
        print(
            "Falha inesperada:",
            type(error).__name__,
            "-",
            error,
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())