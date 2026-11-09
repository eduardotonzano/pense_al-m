import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_covenants_mensais.py"
specification = importlib.util.spec_from_file_location("build_covenants_mensais", SCRIPT)
module = importlib.util.module_from_spec(specification)
specification.loader.exec_module(module)


def test_codes_split_series_listed_in_one_field():
    assert module.codes("24G1966807,24G1967273") == ["24G1966807", "24G1967273"]
    assert module.codes("CRA022008SP CRA022008SQ") == ["CRA022008SP", "CRA022008SQ"]
    assert module.codes("") == []


def test_group_of_monitored_item():
    assert module.group_of("Garantia", "Fundo de Despesas") == "fundo"
    assert module.group_of("Covenant", "Dívida Líquida / EBITDA") == "covenant"
    assert module.group_of("Garantia", "Razão de garantia mínima") == "covenant"
    assert module.group_of("Garantia", "Alienação fiduciária de imóvel") == "garantia"
    assert module.group_of("Obrigaçao", "Envio de documentos") == "obrigacao"
