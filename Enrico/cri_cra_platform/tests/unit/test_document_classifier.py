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
