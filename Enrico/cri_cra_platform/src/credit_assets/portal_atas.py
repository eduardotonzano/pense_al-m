"""Atas, editais, fatos relevantes e comunicados publicados nos portais das securitizadoras (Opea, Riza, Eco, Vert).

Seleção pelo título do documento e pela categoria que o portal dá a ele (aba da página da Eco, tipo do documento na
Riza, tipo do evento no diário de bordo da Opea, categoria no VERT Data): ata, AGT/AGE, assembleia, termo de não
instalação, edital, convocação, proposta para a assembleia, fato relevante, comunicado. Ficam de fora relatórios
mensais, informes, demonstrações financeiras, termos de securitização, documentos de oferta, rating e protocolos.
O título manda; a categoria só decide quando o título não diz nada (e nunca resgata um título excluído).

Os eventos graves (vencimento antecipado, recuperação judicial, liquidação do patrimônio separado, waiver,
repactuação) vêm do que a ata decidiu (credit_assets.assembly_outcomes) e, sem decisão, do que o texto discute
(credit_assets.assembly_topics). Triagem: cada evento guarda o trecho; vale depois de lido no documento.
Site da securitizadora é a fonte de menor prioridade (regra 3 do projeto): complementa a CVM, nunca a corrige.
"""
from __future__ import annotations

import html
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

ECO_STORAGE = "https://ecoagro.agr.br/public/storage/Arquivo/"
BRASILIA = timezone(timedelta(hours=-3))  # sem horário de verão desde 2019


def plain(text: str) -> str:
    """Minúsculas, sem acentos, com ``_``/``-``/``.`` como espaço (nomes de arquivo da Eco e da Opea)."""

    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[_\-.()\[\]/]+", " ", text)).strip()


PROTOCOL = re.compile(r"\bprotocolo\b")
ATA = re.compile(r"\batas?\b|termo de nao instalacao|nao instalacao|\bsumario de ata")
EDITAL = re.compile(r"\bedital\b|\bconvocacao\b|\bconvocatoria\b")
FATO = re.compile(r"fatos? relevantes?")
PROPOSTA = re.compile(r"\bproposta\b(?! vinculante)")
ASSEMBLEIA = re.compile(r"\bassembleias?\b|\bag[teo]s?\b|\bage ?ago\b")
COMUNICADO = re.compile(r"\bcomunicados?\b|\bnotificacao\b|\baviso aos? (?:titulares|investidores)\b")
EXCLUDED = re.compile(
    r"relatorio|\binforme\b|demonstra[cç]|\bdfs?\b|termo de securitiza|\bprospecto\b|\blamina\b|"
    r"anuncio de (?:inicio|encerramento)|\baviso ao mercado\b|\brating\b|\bescritura\b|aditamento|"
    r"material de apoio|(?:inicio|encerramento|modificacao|revogacao|suspensao) da oferta|\bmonitoramento\b")


def document_kind(title: str, category: str = "") -> str:
    """"ata" | "edital" | "proposta" | "fato_relevante" | "assembleia" | "comunicado" | "" (fora da seleção)."""

    t, c = plain(title), plain(category)
    if PROTOCOL.search(f"{t} {c}"):
        return ""  # recibo de protocolo na CVM: o documento em si vem à parte

    def strong(text: str) -> str:
        if ATA.search(text):
            return "ata"
        if EDITAL.search(text):
            return "edital"
        if FATO.search(text):
            return "fato_relevante"
        if PROPOSTA.search(text):
            return "proposta"
        return ""

    def weak(text: str) -> str:
        if ASSEMBLEIA.search(text):
            return "assembleia"
        if COMUNICADO.search(text):
            return "comunicado"
        return ""

    found = strong(t)
    if found:
        return found
    if EXCLUDED.search(t) or EXCLUDED.search(c):
        return ""
    return weak(t) or strong(c) or weak(c)


def in_window(published: str, since: str) -> bool:
    return bool(published) and published[:10] >= since


# ---- Eco: abas da página pública da emissão ----

TAB = re.compile(r'class="documents__link"\s+data-tab="(\d+)"[^>]*>([^<]+)<')
GROUP = re.compile(r'class="documents__current"\s+data-group="(\d+)"')
ITEM = re.compile(r'<p class="documents__text">\s*(.*?)\s*</p>\s*<a href="([^"]+)"', re.S)


@dataclass(frozen=True)
class EcoDocument:
    category: str     # aba da página ("Atas de Assembléias", "Convocação Assembléia"...)
    title: str        # texto do item na página
    url: str
    uploaded: int     # carimbo Unix no nome do arquivo = data de publicação

    @property
    def published(self) -> str:
        """Data de publicação no horário de Brasília (o carimbo das 22h de 22/05 é 23/05 em UTC)."""
        return datetime.fromtimestamp(self.uploaded, BRASILIA).date().isoformat()

    @property
    def file_name(self) -> str:
        return urllib.parse.unquote(self.url.split("/Arquivo/", 1)[1])[10:]


def eco_documents(page_html: str) -> list[EcoDocument]:
    """Documentos da página da emissão com a aba em que aparecem. Corrige o link duplicado que a página às vezes
    traz (``.../public/storage/http://ecoagro.agr.br/public/storage/Arquivo/...``)."""

    tabs = {number: html.unescape(name).strip() for number, name in TAB.findall(page_html)}
    groups = list(GROUP.finditer(page_html))
    found = []
    for index, group in enumerate(groups):
        end = groups[index + 1].start() if index + 1 < len(groups) else len(page_html)
        for title, href in ITEM.findall(page_html[group.end():end]):
            href = html.unescape(href)
            tail = href.rsplit("/public/storage/Arquivo/", 1)
            stamp = re.match(r"\d{10}", tail[1]) if len(tail) == 2 else None
            if not stamp:
                continue
            found.append(EcoDocument(tabs.get(group.group(1), ""), html.unescape(re.sub(r"\s+", " ", title)).strip(),
                                     ECO_STORAGE + tail[1], int(stamp.group(0))))
    return list({d.url: d for d in found}.values())


# ---- Opea: diário de bordo ----

def opea_selected(events: list[dict], since: str) -> list[tuple[str, dict]]:
    """(tipo, evento) dos eventos selecionados com anexo e incluídos no portal desde ``since``."""

    found = []
    for event in events:
        if not event.get("diarioBordoAnexoList"):
            continue
        published = opea_published(event)
        kind = document_kind(f"{event.get('titulo') or event.get('tituloPortal') or ''}",
                             str(event.get("tipoEventoDiarioBordo") or ""))
        if kind and in_window(published, since):
            found.append((kind, event))
    return found


def opea_published(event: dict) -> str:
    """Data em que o evento entrou no portal (``dataInclusao``); sem ela, a data de ocorrência."""

    return str(event.get("dataInclusao") or event.get("dataOcorrencia") or "")[:10]


def opea_family(codigo_opea: str) -> str:
    """Emissão sem a série: "CRI.301.CIA.1" → "CRI.301.CIA" (séries da mesma emissão repetem as atas)."""

    parts = str(codigo_opea).split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 and parts[-1].isdigit() else str(codigo_opea)


# ---- eventos graves ----

GRAVE_DECISIONS = (
    ("vencimento_antecipado_declarado", "vencimento antecipado declarado"),
    ("vencimento_antecipado_nao_declarado", "vencimento antecipado não declarado"),
    ("vencimento_antecipado_efeitos_sustados", "vencimento antecipado ocorrido, efeitos sustados"),
    ("sustacao_dos_efeitos_do_vencimento_antecipado_rejeitada", "sustação dos efeitos do vencimento antecipado rejeitada"),
    ("nao_declaracao_do_vencimento_antecipado_rejeitada", "não declaração do vencimento antecipado rejeitada"),
    ("recuperacao_judicial", "recuperação judicial"),
    ("liquidacao_patrimonio", "liquidação do patrimônio separado"),
    ("waiver", "waiver"),
    ("prorrogacao_repactuacao", "repactuação/prorrogação"),
)
GRAVE_TOPICS = {"vencimento_antecipado": "vencimento antecipado", "liquidacao_patrimonio": "liquidação do patrimônio separado",
                "waiver": "waiver", "prorrogacao_repactuacao": "repactuação/prorrogação"}
RECOVERY = re.compile(r"recupera[cç][aã]o (?:judicial|extrajudicial)|fal[eê]ncia", re.IGNORECASE)
# decisões sem assunto identificado: com elas, o que o texto discute ainda conta
GENERIC_DECISIONS = {"outras_materias_aprovadas", "ordem_do_dia_aprovada_em_bloco", "assembleia_suspensa", "nao_instalada",
                     "sem_quorum_para_deliberar", "titulares_se_abstiveram"}
def is_future_meeting(kind: str, meeting_date: str, published: str, today: str) -> bool:
    """Ata ou assembleia de reunião que ainda não aconteceu (data da reunião ou de publicação depois de ``today``,
    AAAA-MM-DD): é minuta ("aprovou(aram)", ordem do dia) e não registra decisão nenhuma."""
    return kind in ("ata", "assembleia") and max(meeting_date or "", published or "") > today


GRAVE_ORDER = ("vencimento antecipado", "recuperação judicial", "liquidação do patrimônio separado", "waiver",
               "repactuação/prorrogação")


def grave_events(decisions: list[str], topics: list[tuple[str, str]]) -> tuple[list[str], str]:
    """Eventos graves e de onde vieram: "decisão" (o que a ata decidiu) ou "texto" (o que o documento discute).

    ``decisions``: eventos de assembly_outcomes.decide (ex.: "waiver_aprovado_em_bloco");
    ``topics``: (assunto relevante, trecho) de assembly_topics.classify. Ata que decidiu assunto específico e não
    grave (ex.: aprovação das DFs) não herda eventos do texto: menção a vencimento antecipado ali é cláusula padrão."""

    def ordered(labels: list[str]) -> list[str]:
        return sorted(labels, key=lambda label: next((i for i, g in enumerate(GRAVE_ORDER) if label.startswith(g)), 99))

    found = []
    for event in decisions:
        for prefix, label in GRAVE_DECISIONS:
            if event.startswith(prefix):
                suffix = event[len(prefix):].strip("_")
                verdict = "" if prefix.startswith(("vencimento", "nao_declaracao")) else \
                    " (aprovado)" if suffix.startswith("aprovado") else " (rejeitado)" if suffix.startswith("rejeitado") else ""
                if label + verdict not in found:
                    found.append(label + verdict)
                break
    if found:
        return ordered(found), "decisão"
    if any(event not in GENERIC_DECISIONS for event in decisions):
        return [], ""
    for topic, excerpt in topics:
        if topic in GRAVE_TOPICS and GRAVE_TOPICS[topic] not in found:
            found.append(GRAVE_TOPICS[topic])
        elif topic == "inadimplencia_devedor" and RECOVERY.search(excerpt) and "recuperação judicial" not in found:
            found.append("recuperação judicial")
    return ordered(found), "texto" if found else ""
