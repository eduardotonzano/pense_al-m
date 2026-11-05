import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_cnpj_devedor_cvm.py"


def load():
    spec = importlib.util.spec_from_file_location("build_cnpj_devedor_cvm", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cpf_nunca_sai_no_relatorio():
    module = load()
    assert module.classify_identifier("03.941.052/0001-50") == ("cnpj", "03941052000150")
    kind, digits = module.classify_identifier("529.982.247-25")  # CPF válido de exemplo
    assert kind == "cpf" and digits is None
    assert "cpf" not in module.FIELDS and "identificador" in module.FIELDS


def test_consultas_so_usam_arquivos_vigentes_e_o_devedor():
    module = load()
    assert "f.is_current = 1" in module.CERTIFICATES and "f.is_current = 1" in module.DEBTORS
    assert "t.Tipo = 'Devedor'" in module.DEBTORS
