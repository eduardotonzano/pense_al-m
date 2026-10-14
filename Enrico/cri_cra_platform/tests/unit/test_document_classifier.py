from credit_assets.models.document import DOCUMENT_CATEGORIES
from credit_assets.utils.document_classifier import classify_document


def test_classifier_covers_expected_fixtures():
    assert classify_document({"tipo": "Termo de Securitização"}) == "Termo de Securitização"
    assert classify_document({"tipo": "Aditamento"}) == "Aditamento"
    assert classify_document({"tipo": "Informe Mensal de CRI"}) == "Informe Mensal"
    assert classify_document({"tipo": "Relatório de Rating"}) == "Relatório de Rating"
    assert classify_document({"tipo": "Documento desconhecido"}) == "Outro"


def test_classifier_always_returns_schema_category():
    assert classify_document({"categoria": "qualquer coisa"}) in DOCUMENT_CATEGORIES


def test_classifier_uses_official_fundosnet_document_fields():
    assert classify_document(
        {"tipoDocumento": "Informe Mensal de CRA"}
    ) == "Informe Mensal"
    assert classify_document(
        {"live_type": "Informe Mensal de CRI"}
    ) == "Informe Mensal"
    assert classify_document(
        {"live_type": "AGO/E", "live_species": "Ata da Assembleia"}
    ) == "Ata/Edital"
    assert classify_document(
        {"categoriaDocumento": "Edital de Convocação"}
    ) == "Ata/Edital"
    assert classify_document(
        {"especieDocumento": "Ata de Assembleia"}
    ) == "Ata/Edital"


def test_financial_statements_are_always_other_before_secondary_signals():
    for field in (
        "document_name",
        "tipoDocumento",
        "especieDocumento",
        "live_type",
        "descricao",
    ):
        for label in (
            "Demonstrações Financeiras",
            "Demonstracoes Financeiras",
            "Demonstração Financeira",
            "Demonstracao Financeira",
        ):
            item = {
                "tipoDocumento": "Informe Mensal de CRA",
                "categoriaDocumento": "CRI",
            }
            item[field] = label
            assert classify_document(item) == "Outro"


def test_document_name_financial_statements_overrides_monthly_report_metadata():
    assert classify_document({
        "document_name": "Demonstrações Financeiras",
        "tipoDocumento": "Informe Mensal",
        "especieDocumento": "CRA - CRI",
        "live_type": "Informe Mensal",
        "descricao": "Informe Mensal de CRA",
    }) == "Outro"


def test_monthly_reports_for_cra_and_cri_remain_monthly_reports():
    assert classify_document(
        {"tipoDocumento": "Informe Mensal de CRA"}
    ) == "Informe Mensal"
    assert classify_document(
        {"live_type": "Informe Mensal de CRI"}
    ) == "Informe Mensal"


def test_existing_specific_category_is_preserved_without_other_evidence():
    assert classify_document({
        "categoriaDocumento": "Relatório de Rating",
        "tipoDocumento": "Documento cadastral",
    }) == "Relatório de Rating"
