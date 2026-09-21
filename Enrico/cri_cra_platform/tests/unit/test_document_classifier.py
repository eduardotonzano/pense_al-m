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
