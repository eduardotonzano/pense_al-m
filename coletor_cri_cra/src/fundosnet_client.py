"""Helpers shared by the Fundos.NET capture workflow."""

from __future__ import annotations

import re
from typing import Mapping


SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "x-api-key",
}

SENSITIVE_BODY_PATTERNS = (
    re.compile(r'(?i)("?(?:token|access_token|authorization)"?\s*[:=]\s*")[^"]+(")'),
)


def sanitizar_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Remove headers that can identify or authenticate the browser session."""
    return {
        key: "[REMOVIDO]" if key.lower() in SENSITIVE_HEADERS else value
        for key, value in headers.items()
    }


def sanitizar_texto(texto: str) -> str:
    """Mask common token fields before persisting captured request data."""
    resultado = texto or ""
    for padrao in SENSITIVE_BODY_PATTERNS:
        resultado = padrao.sub(r"\1[REMOVIDO]\2", resultado)
    return resultado


def url_relevante(url: str) -> bool:
    """Keep only Fundos.NET calls likely related to document searches."""
    palavras = (
        "pesquisar",
        "documento",
        "gerenciador",
        "certificado",
        "securit",
        "informe",
        "comunicado",
        "assembleia",
        "cra",
        "cri",
    )
    url_normalizada = url.lower()
    return "fnet.bmfbovespa.com.br" in url_normalizada and any(
        palavra in url_normalizada for palavra in palavras
    )
