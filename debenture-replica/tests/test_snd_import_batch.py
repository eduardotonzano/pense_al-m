import importlib.util
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "snd_import_batch.py"
FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "snd_asset_codes_exemplo.txt"
)


def load_module():
    specification = importlib.util.spec_from_file_location(
        "snd_import_batch",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_reads_codes_and_ignores_comments():
    module = load_module()
    assert module.read_codes(FIXTURE_PATH) == [
        "PETR27",
        "CEPEA1",
        "SBSPC9",
        "PETR27",
    ]


def test_default_arguments_are_safe():
    module = load_module()
    arguments = module.build_argument_parser().parse_args(
        [str(FIXTURE_PATH)]
    )

    assert arguments.commit is False
    assert arguments.max_items == 20


def test_commit_flag_is_explicit():
    module = load_module()
    arguments = module.build_argument_parser().parse_args(
        [str(FIXTURE_PATH), "--commit", "--max-items", "3"]
    )

    assert arguments.commit is True
    assert arguments.max_items == 3
