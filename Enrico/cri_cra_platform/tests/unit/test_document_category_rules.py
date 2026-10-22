import os
import subprocess
import sys
from pathlib import Path

from credit_assets.models.document import DOCUMENT_CATEGORIES
from credit_assets.utils.document_category_rules import (
    CLASSIFIER_VERSION,
    OTHER,
    RULES,
    UNVERIFIED,
    VERIFIED,
    VETOES,
    classify_strict,
)


VERIFIED_IDS = {"IM-01", "ATA-ESP-01", "EDT-ESP-01"}
UNVERIFIED_IDS = {"ADT-01", "TS-01", "FR-01", "AF-01", "RT-01", "AE-01"}


def category(fields, include_unverified=False):
    return classify_strict(fields, include_unverified).category


def test_rules_use_schema_categories_and_have_unique_ids():
    ids = [rule.rule_id for rule in (*RULES, *VETOES)]

    assert len(ids) == len(set(ids))
    assert all(rule.category in DOCUMENT_CATEGORIES for rule in (*RULES, *VETOES))
    assert {rule.rule_id for rule in RULES if rule.group == VERIFIED} == VERIFIED_IDS
    assert {rule.rule_id for rule in RULES if rule.group == UNVERIFIED} == UNVERIFIED_IDS
    assert CLASSIFIER_VERSION


def test_informe_mensal_by_type_or_by_name():
    by_type = classify_strict({"tipoDocumento": "Informe Mensal de CRA"})
    by_name = classify_strict({"document_name": "Informe Mensal de CRI"})

    assert by_type.category == "Informe Mensal"
    assert (by_type.rule_id, by_type.group, by_type.matched_field) == (
        "IM-01", VERIFIED, "type",
    )
    assert by_name.category == "Informe Mensal"
    assert by_name.matched_field == "name"
    assert category({"tipo": "INFORME MENSAL DE CRA"}) == "Informe Mensal"


def test_bare_informe_is_not_an_informe_mensal():
    assert category({"categoriaDocumento": "Informes Periódicos"}) == OTHER
    assert category({"tipoDocumento": "Informe Trimestral"}) == OTHER
    assert category({"tipoDocumento": "Informe Anual"}) == OTHER


def test_financial_statements_are_vetoed_even_inside_informes_periodicos():
    result = classify_strict(
        {
            "categoriaDocumento": "Informes Periódicos",
            "tipoDocumento": "Demonstrações Financeiras",
        }
    )

    assert result.category == OTHER
    assert result.vetoed is True
    assert result.rule_id == "DF-VETO-01"
    assert category({"document_name": "Demonstração Financeira"}) == OTHER


def test_veto_beats_an_informe_mensal_match():
    result = classify_strict(
        {"tipoDocumento": "Informe Mensal", "document_name": "Demonstrações Financeiras"}
    )

    assert result.category == OTHER
    assert result.vetoed is True


def test_ata_and_edital_only_by_species():
    assert category({"especieDocumento": "Ata da Assembleia"}) == "Ata/Edital"
    assert category({"live_species": "Ata de Assembleia"}) == "Ata/Edital"
    assert category({"especieDocumento": "Edital de Convocação"}) == "Ata/Edital"
    result = classify_strict({"especieDocumento": "Ata da Assembleia"})
    assert (result.rule_id, result.matched_field) == ("ATA-ESP-01", "species")


def test_assembly_documents_alone_do_not_classify():
    assert category({"tipoDocumento": "AGO/E"}) == OTHER
    assert category({"document_name": "AGO/E"}) == OTHER
    assert category({"tipoDocumento": "AGE"}) == OTHER
    assert category({"categoriaDocumento": "Assembleia"}) == OTHER
    assert category({"especieDocumento": "Sumário das Decisões"}) == OTHER
    assert category({"especieDocumento": "Proposta do Administrador"}) == OTHER
    # "ata" e "edital" fora da especie nao bastam
    assert category({"tipoDocumento": "Ata", "document_name": "Edital"}) == OTHER


def test_word_boundaries_prevent_false_matches():
    assert category({"especieDocumento": "Data de entrega"}) == OTHER
    assert category({"especieDocumento": "Metadata"}) == OTHER


def test_two_categories_are_ambiguous_and_stay_other():
    result = classify_strict(
        {"tipoDocumento": "Informe Mensal de CRA", "especieDocumento": "Edital de Convocação"}
    )

    assert result.category == OTHER
    assert result.ambiguous is True
    assert result.candidates == ("Informe Mensal", "Ata/Edital")
    assert result.rule_id is None


def test_two_rules_of_the_same_category_are_not_ambiguous():
    result = classify_strict({"especieDocumento": "Ata e Edital da Assembleia"})

    assert result.category == "Ata/Edital"
    assert result.ambiguous is False
    assert result.rule_id == "ATA-ESP-01"


def test_unverified_rules_are_off_by_default():
    samples = {
        "Termo de Securitização": "Termo de Securitização",
        "Aditamento": "Aditamento ao Termo de Securitização",
        "Fato Relevante": "Fato Relevante",
        "Relatório Agente Fiduciário": "Relatório Anual do Agente Fiduciário",
        "Relatório de Rating": "Relatório de Classificação de Risco",
        "Anúncio de Encerramento": "Anúncio de Encerramento",
    }

    for expected, name in samples.items():
        assert category({"tipoDocumento": name}) == OTHER
        assert category({"tipoDocumento": name}, include_unverified=True) == expected

    result = classify_strict({"tipoDocumento": "Fato Relevante"}, include_unverified=True)
    assert (result.rule_id, result.group) == ("FR-01", UNVERIFIED)


def test_aditamento_wins_over_termo_in_the_same_text():
    with_flag = classify_strict(
        {"tipoDocumento": "Aditamento ao Termo de Securitização"},
        include_unverified=True,
    )

    assert with_flag.category == "Aditamento"
    assert with_flag.ambiguous is False
    assert with_flag.rule_id == "ADT-01"


def test_aditamento_and_termo_in_different_fields_are_ambiguous():
    result = classify_strict(
        {"tipoDocumento": "Termo de Securitização", "especieDocumento": "Aditamento"},
        include_unverified=True,
    )

    assert result.category == OTHER
    assert result.ambiguous is True


def test_termo_de_encerramento_matches_nothing():
    assert category({"tipoDocumento": "Termo de Encerramento"}, True) == OTHER
    assert category({"tipoDocumento": "Termo de Quitação"}, True) == OTHER


def test_unverified_rule_can_make_a_verified_match_ambiguous():
    fields = {"tipoDocumento": "Informe Mensal de CRA", "especieDocumento": "Fato Relevante"}

    assert category(fields) == "Informe Mensal"
    assert classify_strict(fields, include_unverified=True).ambiguous is True


def test_accepts_database_columns_and_legacy_aliases_but_not_the_stored_category():
    assert category({"source_type": "Informe Mensal de CRA"}) == "Informe Mensal"
    assert category({"source_species": "Ata da Assembleia"}) == "Ata/Edital"
    assert category({"live_type": "Informe Mensal de CRI"}) == "Informe Mensal"
    assert category({"nome": "Informe Mensal"}) == "Informe Mensal"
    # a categoria ja gravada (coluna category) nunca alimenta a regra
    assert category({"category": "Informe Mensal"}) == OTHER


def test_empty_input_stays_other():
    assert classify_strict({}) .category == OTHER
    assert category({"tipoDocumento": "  ", "especieDocumento": None}) == OTHER


def test_module_does_not_import_playwright():
    source = Path(__file__).parents[2] / "src"
    code = (
        "import sys\n"
        "import credit_assets.utils.document_category_rules\n"
        "print('playwright' in sys.modules)\n"
    )
    environment = {**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"}

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=environment,
        check=True,
    )

    assert result.stdout.strip() == "False"
