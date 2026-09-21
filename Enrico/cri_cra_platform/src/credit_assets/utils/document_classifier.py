from __future__ import annotations

from credit_assets.models.document import DOCUMENT_CATEGORIES


def classify_document(item: dict) -> str:
    text = " ".join(
        str(item.get(key) or "")
        for key in ("tipo", "categoria", "titulo", "nome", "descricao")
    ).casefold()
    rules = (
        (("termo",), "Termo de Securitização"),
        (("aditamento",), "Aditamento"),
        (("informe", "mensal"), "Informe Mensal"),
        (("ata", "edital"), "Ata/Edital"),
        (("fato relevante",), "Fato Relevante"),
        (("agente fiduciário", "agente fiduciario"), "Relatório Agente Fiduciário"),
        (("rating",), "Relatório de Rating"),
        (("encerramento",), "Anúncio de Encerramento"),
    )
    for terms, category in rules:
        if any(term in text for term in terms):
            return category
    return "Outro"


def is_valid_category(category: str) -> bool:
    return category in DOCUMENT_CATEGORIES
