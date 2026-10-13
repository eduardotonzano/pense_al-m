from __future__ import annotations

import re
import unicodedata

from credit_assets.models.document import DOCUMENT_CATEGORIES


def _normalize_text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in folded
        if not unicodedata.combining(character)
    )


def classify_document(item: dict[str, object]) -> str:
    text = _normalize_text(" ".join(
        str(item.get(key) or "")
        for key in (
            "categoriaDocumento",
            "categoria_documento",
            "categoria",
            "tipoDocumento",
            "tipo_documento",
            "live_type",
            "especieDocumento",
            "especie_documento",
            "live_species",
            "tipo",
            "document_name",
            "nome_documento",
            "titulo",
            "nome",
            "descricao",
        )
    ))
    rules = (
        (("termo",), "Termo de Securitização"),
        (("aditamento",), "Aditamento"),
        (("informe", "mensal"), "Informe Mensal"),
        (("edital",), "Ata/Edital"),
        (("ata",), "Ata/Edital"),
        (("ago/e",), "Ata/Edital"),
        (("fato relevante",), "Fato Relevante"),
        (("agente fiduciário", "agente fiduciario"), "Relatório Agente Fiduciário"),
        (("rating",), "Relatório de Rating"),
        (("encerramento",), "Anúncio de Encerramento"),
    )
    for terms, category in rules:
        if any(
            re.search(rf"\b{re.escape(term)}\b", text)
            if term in {"ata", "ago/e"}
            else term in text
            for term in terms
        ):
            return category
    return "Outro"


def is_valid_category(category: str) -> bool:
    return category in DOCUMENT_CATEGORIES
