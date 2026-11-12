import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import build_plataforma as bp  # noqa: E402
from credit_assets.debtor_exposure import classify_identifier  # noqa: E402


def test_cpf_is_masked_in_free_text():
    text = "inscrito no CPF sob o nº 604.996.673-79, CNPJ 12.345.678/0001-95, CPF/MF 60499667379"
    out = bp.mask_cpf(text)
    assert "604.996.673-79" not in out and "60499667379" not in out
    assert "12.345.678/0001-95" in out


def test_cpf_padded_with_zeros_is_not_a_cnpj():
    assert classify_identifier("00861598016") == ("cpf", None)
    assert bp.looks_like_cpf_padded("00000861598016")
    assert bp.cnpj_or_blank("00.000.000/0001-91") == "00.000.000/0001-91"  # Banco do Brasil
    assert bp.cnpj_or_blank("00.000.861/5980-16") == ""


def test_informe_dates_sort_chronologically():
    dates = ["12/2025", "09/2026", "03/2020", "15/10/2026"]
    assert sorted(dates, key=bp.sort_date, reverse=True) == ["15/10/2026", "09/2026", "12/2025", "03/2020"]


def test_rating_placeholders_are_blank():
    assert bp.clean_rating("N/A") == "" and bp.clean_rating("0") == "" and bp.clean_rating("A.br (sf)") == "A.br (sf)"


def test_coherence_alert():
    assert bp.coherence_alert("5x Mínimo", "4,56x", "atendido")
    assert not bp.coherence_alert("120% Mínimo", "131%", "atendido")
    assert "não comparáveis" in bp.coherence_alert("R$ 65.000.000,00 Mínimo", "98%", "atendido")
