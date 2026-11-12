import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_guarantees_covenants.py"
spec = importlib.util.spec_from_file_location("build_guarantees_covenants", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_other_emissions_annex_is_skipped_until_next_annex():
    pages = [
        (2, "ANEXO VIII – INFORMAÇÕES ......................... 115\nANEXO IX – MODELO ............ 259", False),
        (78, "9.3. Nos termos do artigo 6º, parágrafo 2º, da Resolução CVM 17, o Agente Fiduciário já atuou "
             "em outras emissões, conforme ANEXO VIII.", False),
        (115, "ANEXO VIII – INFORMAÇÕES PARA OS FINS DO ARTIGO 6º, PARÁGRAFO 2º, DA RESOLUÇÃO CVM 17 ACERCA DA "
              "EXISTÊNCIA DE OUTRAS EMISSÕES", False),
        (155, "Garantias: (i) Fiança - prestada pelos Fiadores - UFV TNT AGRESTINA I LTDA.", False),
        (259, "ANEXO IX – MODELO DE RESPOSTA À OFERTA DE RESGATE DOS CRA", False),
    ]
    kept = [number for number, _, _ in module.pages_outside_other_emissions_annex(pages)]
    assert kept == [2, 78, 259]


def test_table_of_other_emissions_by_codes_or_status_column():
    assert module.other_emissions_page("CRA02300PRU 24C2146614 24C2149145 Aval", "24D3676679")
    assert module.other_emissions_page("CRA0 294.5 Adimplent Aval Adimplente Inadimplente", "23A1407158")
    assert not module.other_emissions_page("Os CRI contam com Alienação Fiduciária. 24D3676679", "24D3676679")
