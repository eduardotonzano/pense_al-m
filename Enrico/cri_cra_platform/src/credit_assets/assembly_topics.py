"""Assuntos de atas, editais, fatos relevantes e comunicados de CRA/CRI por palavras-chave (sem IA).

Triagem: aponta o que o documento discute (vencimento antecipado, waiver, prorrogação, troca de garantia...),
não o que foi decidido. Cada assunto guarda o primeiro trecho que o acionou, para conferência.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

TOPICS: dict[str, tuple[str, list[str]]] = {
    "vencimento_antecipado": ("relevante", [r"vencimento antecipado", r"declara[cç][aã]o (?:do|de) vencimento", r"evento de inadimplemento"]),
    "waiver": ("relevante", [r"\bwaiver\b", r"anu[eê]ncia pr[eé]via", r"perd[aã]o (?:tempor[aá]rio|de)", r"renúncia de direitos|renuncia de direitos"]),
    "prorrogacao_repactuacao": ("relevante", [r"prorroga[cç][aã]o", r"repactua[cç][aã]o", r"altera[cç][aã]o (?:da|das) datas? de (?:vencimento|pagamento)",
                                              r"novo cronograma", r"altera[cç][aã]o do cronograma", r"car[eê]ncia"]),
    "remuneracao": ("relevante", [r"altera[cç][aã]o (?:da|na) (?:remunera[cç][aã]o|taxa)", r"(?:redu[cç][aã]o|majora[cç][aã]o) (?:da|na) (?:remunera|taxa|spread)"]),
    "garantias": ("relevante", [r"(?:substitui[cç][aã]o|refor[cç]o|libera[cç][aã]o|complementa[cç][aã]o|recomposi[cç][aã]o) (?:da|das|de) garantias?",
                                r"raz[aã]o (?:m[ií]nima )?de garantia", r"desenquadramento"]),
    "inadimplencia_devedor": ("relevante", [r"recupera[cç][aã]o judicial", r"recupera[cç][aã]o extrajudicial", r"fal[eê]ncia",
                                            r"inadimplemento", r"n[aã]o pagamento", r"atraso no pagamento"]),
    "liquidacao_patrimonio": ("relevante", [r"liquida[cç][aã]o do patrim[oô]nio separado", r"insufici[eê]ncia (?:de|dos) (?:recursos|lastro)",
                                            r"administra[cç][aã]o (?:transit[oó]ria|extraordin[aá]ria) do patrim"]),
    "resgate_amortizacao": ("relevante", [r"resgate antecipado", r"amortiza[cç][aã]o extraordin[aá]ria", r"oferta de resgate"]),
    "troca_prestador": ("relevante", [r"substitui[cç][aã]o (?:do|da) (?:agente fiduci[aá]rio|securitizadora|emissora|custodiante|escriturador|servicer)"]),
    "aprovacao_dfs": ("rotina", [r"demonstra[cç][oõ]es financeiras", r"demonstra[cç][oõ]es cont[aá]beis"]),
    "rating": ("rotina", [r"classifica[cç][aã]o de risco", r"\brating\b"]),
}
NOT_INSTALLED = re.compile(r"n[aã]o (?:houve|foi verificad[ao]|atingiu)[^.]{0,80}qu[oó]rum (?:m[ií]nimo )?(?:de|para) instala[cç][aã]o|"
                           r"n[aã]o (?:foi )?instalada|termo de n[aã]o instala[cç][aã]o")
SECOND_CALL = re.compile(r"segunda convoca[cç][aã]o|2[ªa] convoca[cç][aã]o")


@dataclass(frozen=True)
class TopicHit:
    topic: str
    level: str
    excerpt: str


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def classify(text: str) -> tuple[list[TopicHit], dict[str, bool]]:
    """Assuntos encontrados e marcas (não instalada, segunda convocação)."""

    flat = _flat(text)
    lower = flat.lower()
    hits = []
    for topic, (level, patterns) in TOPICS.items():
        for pattern in patterns:
            match = re.search(pattern, lower)
            if match:
                start = max(0, match.start() - 80)
                hits.append(TopicHit(topic, level, flat[start:match.end() + 120].strip()))
                break
    marks = {"nao_instalada": bool(NOT_INSTALLED.search(lower)), "segunda_convocacao": bool(SECOND_CALL.search(lower))}
    return hits, marks


def relevant(hits: list[TopicHit]) -> list[str]:
    return [h.topic for h in hits if h.level == "relevante"]
