"""Atas, editais, fatos relevantes e comunicados publicados nos portais da Opea, Riza, Eco e Vert desde --since.

    python scripts/collect_portal_atas.py --dry-run [--only 24G2100031]       # escopo; com --only, lista sem baixar
    python scripts/collect_portal_atas.py --commit [--since 2026-08-01] [--only 24G2100031] [--source opea]
                                          [--max-minutes 45]
    python scripts/collect_portal_atas.py --parse-only                        # relê o que já foi baixado

Escopo, nesta ordem: 1) CETIPs de reports/alertas_por_ativo.csv e ativos do banco; 2) resto do universo
(config/ativos_mercado.csv). Opea: diário de bordo de cada série; Riza: documentos de cada operação; Eco: abas da
página pública (config/eco_emissoes_site.csv); Vert: categorias "Assembléias" e "Comunicados" do VERT Data (do universo
e, se der tempo, os demais CRI/CRA vivos). Seleção e eventos graves em credit_assets.portal_atas; assuntos e decisões
por credit_assets.assembly_topics e credit_assets.assembly_outcomes. Texto por pymupdf; página sem texto vai para OCR
(rapidocr-onnxruntime), marcado no relatório: o trecho pode ter erro de leitura.

Não grava no banco (aberto só com mode=ro). Documentos em data/documents/atas_portais/<securitizadora>/<id>/,
proveniência (URL, SHA-256, publicação, obtenção) em data/atas_portais/manifest.csv, texto em cache em
data/atas_portais/texto/, saída em reports/atas_portais.{csv,md}. Site da securitizadora é a fonte de menor
prioridade (regra 3): complementa a CVM, nunca a corrige. Arquivos baixados são dados: só são lidos pelo pymupdf.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.assembly_outcomes import decide
from credit_assets.assembly_topics import classify, relevant
from credit_assets.opea_portal import OpeaPortal
from credit_assets.portal_atas import (document_kind, eco_documents, grave_events, in_window, opea_family, opea_published,
                                       opea_selected)
from credit_assets.riza_portal import RizaPortal

USER_AGENT = "pense-al-m-cri-cra/0.1 (uso interno de research)"
DOCS = ROOT / "data" / "documents" / "atas_portais"
MANIFEST = ROOT / "data" / "atas_portais" / "manifest.csv"
TEXTS = ROOT / "data" / "atas_portais" / "texto"
MANIFEST_FIELDS = ["securitizadora", "emissao_id", "emissao", "cetips", "prioridade", "documento_id", "tipo", "titulo",
                   "categoria", "publicado_em", "data_evento", "nome_arquivo", "arquivo", "formato", "sha256", "url",
                   "obtido_em"]
OUT_FIELDS = ["securitizadora", "emissao_id", "emissao", "cetips", "prioridade", "publicado_em", "data_evento", "tipo",
              "titulo", "assuntos_relevantes", "rotina", "resultado", "decisoes", "eventos_graves", "origem_eventos",
              "nao_instalada", "segunda_convocacao", "trecho", "trecho_decisao", "ocr", "paginas", "paginas_ocr",
              "formato", "arquivo", "sha256", "url"]
SOURCES = ("opea", "riza", "eco", "vert")
LIVE_OPEA = ("Ativa", "Execução", None)
OCR_MAX_PAGES = 20
LOCK = threading.Lock()


def ua_opener(timeout: int):
    """Abre a requisição com o User-Agent do projeto (substitui o dos clientes)."""

    def open_(request: urllib.request.Request) -> bytes:
        request.add_header("User-Agent", USER_AGENT)
        return urllib.request.urlopen(request, timeout=timeout).read()
    return open_


class Throttled:
    """GET simples com ~1 req/s (páginas e arquivos da Eco)."""

    def __init__(self, min_interval: float = 1.0):
        self.min_interval, self._last = min_interval, 0.0

    def get(self, url: str) -> bytes:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        try:
            request = urllib.request.Request(urllib.parse.quote(url, safe=":/?=&%"), headers={"User-Agent": USER_AGENT})
            return urllib.request.urlopen(request, timeout=120).read()
        finally:
            self._last = time.monotonic()


def refused(error: Exception) -> bool:
    """403/429: o portal recusou o acesso; a fonte para e o restante vai para "faltou" (não insistir)."""

    return getattr(error, "code", None) in (403, 429)


def scope() -> tuple[set[str], set[str]]:
    """(prioridade 1: CETIPs dos alertas e CETIPs/ISINs dos ativos do banco; universo: config/ativos_mercado.csv)."""

    first = set()
    with (ROOT / "reports" / "alertas_por_ativo.csv").open(encoding="utf-8-sig") as handle:
        first |= {row["codigo_cetip"].upper() for row in csv.DictReader(handle, delimiter=";")}
    connection = sqlite3.connect(f"file:{ROOT / 'data' / 'cri_cra.db'}?mode=ro", uri=True)
    for cetip, isin in connection.execute("SELECT codigo_cetip, isin FROM assets"):
        first |= {str(cetip or "").upper(), str(isin or "").upper()}
    connection.close()
    universe = set(first)
    with (ROOT / "config" / "ativos_mercado.csv").open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            universe |= {row["codigo_cetip"].upper(), row["isin"].upper()}
    return first - {""}, universe - {""}


def priority(codes: set[str], first: set[str], universe: set[str]) -> int:
    codes = {c.upper() for c in codes if c}
    return 1 if codes & first else 2 if codes & universe else 3


def safe_name(name: str) -> str:
    return re.sub(r"[^\w.-]+", "_", name, flags=re.ASCII)[:80].strip("_") or "documento"


def file_format(content: bytes, name: str) -> str:
    if content[:5] == b"%PDF-":
        return "pdf"
    suffix = Path(name).suffix.lower().lstrip(".")
    return suffix if re.fullmatch(r"[a-z0-9]{1,5}", suffix) else "desconhecido"


def load_manifest() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(encoding="utf-8") as handle:
        return {row["arquivo"]: row for row in csv.DictReader(handle)}


def save_manifest(manifest: dict[str, dict]) -> None:
    with LOCK:
        rows = sorted(manifest.values(), key=lambda r: (r["securitizadora"], r["emissao_id"], r["publicado_em"], r["arquivo"]))
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


class Store:
    """Grava o arquivo baixado e a linha do manifesto (já baixado não baixa de novo; CETIPs se acumulam)."""

    def __init__(self, manifest: dict[str, dict], commit: bool):
        self.manifest, self.commit = manifest, commit
        self.by_doc = defaultdict(list)
        for row in manifest.values():
            self.by_doc[(row["securitizadora"], row["documento_id"])].append(row)
        self.listed: list[dict] = []  # dry-run: o que seria baixado

    def known(self, source: str, doc_id: str, cetips: list[str]) -> bool:
        rows = [r for r in self.by_doc.get((source, str(doc_id)), []) if (ROOT / r["arquivo"]).exists()]
        with LOCK:
            for row in rows:
                row["cetips"] = " ".join(sorted(set(row["cetips"].split()) | set(cetips)))
        return bool(rows)

    def save(self, base: dict, index: int, name: str, content: bytes, url: str, fetched_at: str) -> None:
        kind = file_format(content, name)
        target = DOCS / base["securitizadora"] / safe_name(str(base["emissao_id"])) / \
            f"{safe_name(str(base['documento_id']))}_{index}.{kind if kind != 'desconhecido' else 'bin'}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        relative = str(target.relative_to(ROOT)).replace("\\", "/")
        row = {**base, "nome_arquivo": name, "arquivo": relative, "formato": kind,
               "sha256": hashlib.sha256(content).hexdigest(), "url": url, "obtido_em": fetched_at}
        with LOCK:
            self.manifest[relative] = row
            self.by_doc[(row["securitizadora"], str(row["documento_id"]))].append(row)


def scope_only(args) -> bool:
    """--dry-run sem --only só mede o escopo (não abre emissão por emissão)."""
    return args.dry_run and not args.only


def wanted(only: list[str] | None, *codes: str) -> bool:
    return not only or bool({c.upper() for c in codes if c} & {o.upper() for o in only})


# ---- coletores por securitizadora (cada um numa thread, com o próprio ritmo de ~1 req/s) ----

def collect_opea(args, first, universe, store: Store, deadline: float) -> dict:
    portal = OpeaPortal(opener=ua_opener(120))
    stats, missing = Counter(), []
    emissions = []
    for e in portal.emissions():
        codes = {str(e.get("codigoIf") or ""), str(e.get("isin") or "")}
        level = priority(codes, first, universe)
        status = (e.get("statusPassivoOperacao") or {}).get("value")
        if level == 3 or (level == 2 and status not in LIVE_OPEA):
            continue
        if wanted(args.only, *codes, e["codigoOpea"], opea_family(e["codigoOpea"])):
            emissions.append((level, e))
    emissions.sort(key=lambda item: (item[0], item[1]["codigoOpea"]))
    stats["emissoes_no_escopo"] = len(emissions)
    if scope_only(args):
        return {"stats": dict(stats), "faltou": []}
    seen: dict[tuple, str] = {}  # (emissão, título, data, arquivo) → id do evento já guardado
    for number, (level, emission) in enumerate(emissions, start=1):
        if time.monotonic() > deadline:
            missing.append(emission["codigoOpea"])
            continue
        code, family, cetip = emission["codigoOpea"], opea_family(emission["codigoOpea"]), str(emission.get("codigoIf") or "")
        try:
            selected = opea_selected(portal.events(code), args.since)
        except Exception as error:
            stats["erro_eventos"] += 1
            print(f"opea {code}: erro nos eventos ({type(error).__name__})", file=sys.stderr)
            if refused(error):
                deadline = 0.0
            continue
        stats["emissoes_lidas"] += 1
        for kind, event in selected:
            names = tuple(sorted(str(a.get("nomeArquivo") or "") for a in event.get("diarioBordoAnexoList") or []))
            key = (family, str(event.get("titulo") or ""), str(event.get("dataOcorrencia") or ""), names)
            doc_id = seen.setdefault(key, str(event["id"]))
            if store.known("opea", doc_id, [cetip]):
                stats["ja_baixado"] += 1
                continue
            base = {"securitizadora": "opea", "emissao_id": family, "emissao": f"{family} ({emission.get('nomeDevedor') or ''})",
                    "cetips": cetip, "prioridade": level, "documento_id": doc_id, "tipo": kind,
                    "titulo": str(event.get("titulo") or ""), "categoria": str(event.get("tipoEventoDiarioBordo") or ""),
                    "publicado_em": opea_published(event),
                    "data_evento": str(event.get("dataAssembleia") or event.get("dataOcorrencia") or "")[:10]}
            if not args.commit:
                store.listed.append(base)
                continue
            try:
                for index, attachment in enumerate(portal.attachments(event)):
                    store.save(base, index, attachment.file_name, attachment.content, attachment.url, attachment.fetched_at)
                    stats["baixado"] += 1
            except Exception as error:
                stats["erro_anexo"] += 1
                print(f"opea {code} evento {event['id']}: erro no anexo ({type(error).__name__})", file=sys.stderr)
        if number % 100 == 0:
            print(f"opea {number}/{len(emissions)} {dict(stats)}", file=sys.stderr)
            if args.commit:
                save_manifest(store.manifest)
    stats["emissoes_nao_visitadas"] = len(missing)
    return {"stats": dict(stats), "faltou": missing}


def collect_riza(args, first, universe, store: Store, deadline: float) -> dict:
    portal = RizaPortal(opener=ua_opener(180))
    stats, missing = Counter(), []
    operations = []
    for op in portal.operations():
        codes = [str(s.get("instrumentCode") or "") for s in op.get("series") or []]
        level = priority(set(codes), first, universe)
        if level < 3 and wanted(args.only, *codes, op["id"]):
            operations.append((level, op, [c for c in codes if c]))
    operations.sort(key=lambda item: (item[0], item[1]["id"]))
    stats["operacoes_no_escopo"] = len(operations)
    if scope_only(args):
        return {"stats": dict(stats), "faltou": []}
    for level, op, codes in operations:
        if time.monotonic() > deadline:
            missing.append(op["id"])
            continue
        try:
            documents = portal.documents(op["id"])
        except Exception as error:
            stats["erro_documentos"] += 1
            print(f"riza {op['id']}: erro nos documentos ({type(error).__name__})", file=sys.stderr)
            if refused(error):
                deadline = 0.0
            continue
        stats["operacoes_lidas"] += 1
        for doc in documents:
            kind = document_kind(str(doc.get("description") or ""), str(doc.get("type") or ""))
            published = str(doc.get("emissionDate") or "")[:10]
            if not kind or not in_window(published, args.since):
                continue
            if store.known("riza", str(doc["id"]), codes):
                stats["ja_baixado"] += 1
                continue
            base = {"securitizadora": "riza", "emissao_id": op["id"],
                    "emissao": f"{op.get('type') or ''} {op.get('issuanceNumber') or ''}ª {op.get('alias') or ''} ({op.get('status') or ''})",
                    "cetips": " ".join(codes), "prioridade": level, "documento_id": str(doc["id"]), "tipo": kind,
                    "titulo": str(doc.get("description") or "").strip(), "categoria": str(doc.get("type") or "").strip(),
                    "publicado_em": published, "data_evento": ""}
            if not args.commit:
                store.listed.append(base)
                continue
            try:
                download = portal.download(doc)
                store.save(base, 0, download.description, download.content, download.url, download.fetched_at)
                stats["baixado"] += 1
            except Exception as error:
                stats["erro_download"] += 1
                print(f"riza {op['id']} documento {doc['id']}: erro no download ({type(error).__name__})", file=sys.stderr)
    stats["operacoes_nao_visitadas"] = len(missing)
    return {"stats": dict(stats), "faltou": missing}


def collect_eco(args, first, universe, store: Store, deadline: float) -> dict:
    http = Throttled()
    stats, missing = Counter(), []
    pages: dict[str, dict] = {}
    with (ROOT / "config" / "eco_emissoes_site.csv").open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            page = pages.setdefault(row["id_eco"], {**row, "cetips": []})
            page["cetips"].append(row["codigo_cetip"])
    chosen = []
    for ident, page in pages.items():
        level = priority(set(page["cetips"]), first, universe)
        if level < 3 and wanted(args.only, *page["cetips"], ident):
            chosen.append((level, ident, page))
    chosen.sort(key=lambda item: (item[0], -int(item[1])))
    stats["paginas_no_escopo"] = len(chosen)
    if scope_only(args):
        return {"stats": dict(stats), "faltou": []}
    for level, ident, page in chosen:
        if time.monotonic() > deadline:
            missing.append(ident)
            continue
        try:
            documents = eco_documents(http.get(page["url"]).decode("utf-8", errors="replace"))
        except Exception as error:
            stats["erro_pagina"] += 1
            print(f"eco {ident}: erro na página ({type(error).__name__})", file=sys.stderr)
            if refused(error):
                deadline = 0.0
            continue
        stats["paginas_lidas"] += 1
        for doc in documents:
            kind = document_kind(f"{doc.title} | {doc.file_name}", doc.category)
            if not kind or not in_window(doc.published, args.since):
                continue
            doc_id = f"{doc.uploaded}_{hashlib.sha256(doc.url.encode('utf-8')).hexdigest()[:8]}"
            if store.known("eco", doc_id, page["cetips"]):
                stats["ja_baixado"] += 1
                continue
            base = {"securitizadora": "eco", "emissao_id": ident,
                    "emissao": f"{page['emissao']}ª emissão {page['operacao']}", "cetips": " ".join(page["cetips"]),
                    "prioridade": level, "documento_id": doc_id, "tipo": kind, "titulo": doc.title, "categoria": doc.category,
                    "publicado_em": doc.published, "data_evento": ""}
            if not args.commit:
                store.listed.append(base)
                continue
            try:
                content = http.get(doc.url)
                store.save(base, 0, doc.file_name, content, doc.url, datetime.now(timezone.utc).isoformat())
                stats["baixado"] += 1
            except Exception as error:
                stats["erro_download"] += 1
                print(f"eco {ident}: {doc.file_name[:60]} indisponível ({type(error).__name__})", file=sys.stderr)
    stats["paginas_nao_visitadas"] = len(missing)
    return {"stats": dict(stats), "faltou": missing}


def collect_vert(args, first, universe, store: Store, deadline: float) -> dict:
    from credit_assets.vert_portal import VertPortal, is_live

    portal = VertPortal(opener=ua_opener(120))
    stats, missing = Counter(), []
    chosen = []
    for e in portal.emissions():
        if str(e.get("financialTitle") or "").upper() not in ("CRI", "CRA"):
            continue
        codes = [str(s.get("codeCetip") or "") for s in e.get("series") or []] + \
                [str(s.get("codeIsin") or "") for s in e.get("series") or []]
        level = priority(set(codes), first, universe)
        if (level < 3 or is_live(e)) and wanted(args.only, *codes, str(e["id"])):
            chosen.append((level, e, [str(s.get("codeCetip") or "") for s in e.get("series") or [] if s.get("codeCetip")]))
    chosen.sort(key=lambda item: (item[0], -int(item[1]["id"])))
    stats["emissoes_no_escopo"] = len(chosen)
    stats["do_universo"] = sum(1 for level, _, _ in chosen if level < 3)
    if scope_only(args):
        return {"stats": dict(stats), "faltou": []}
    for level, emission, cetips in chosen:
        if time.monotonic() > deadline:
            missing.append(str(emission["id"]))
            continue
        stats["emissoes_lidas"] += 1
        for category in ("Assembléias", "Comunicados"):
            try:
                documents = portal.documents(emission["id"], category, page_size=10)
                if len(documents) == 10 and all(in_window(str(d.get("createdAt") or d.get("referenceDate") or ""), args.since)
                                                for d in documents):
                    documents = portal.documents(emission["id"], category, page_size=50)
            except Exception as error:
                stats["erro_documentos"] += 1
                print(f"vert {emission['id']} {category}: erro nos documentos ({type(error).__name__})", file=sys.stderr)
                if refused(error):
                    deadline = 0.0
                continue
            for doc in documents:
                kind = document_kind(str(doc.get("name") or ""), category)
                published = str(doc.get("createdAt") or doc.get("referenceDate") or "")[:10]
                if not kind or not in_window(published, args.since) or doc.get("isNeedInfoDownload"):
                    continue
                if store.known("vert", str(doc["id"]), cetips):
                    stats["ja_baixado"] += 1
                    continue
                base = {"securitizadora": "vert", "emissao_id": str(emission["id"]),
                        "emissao": str(emission.get("name") or ""), "cetips": " ".join(cetips), "prioridade": level,
                        "documento_id": str(doc["id"]), "tipo": kind, "titulo": str(doc.get("name") or ""),
                        "categoria": category, "publicado_em": published,
                        "data_evento": str(doc.get("referenceDate") or "")[:10]}
                if not args.commit:
                    store.listed.append(base)
                    continue
                try:
                    download = portal.download(doc)  # URL assinada expira em minutos: baixa logo depois de listar
                    store.save(base, 0, download.url.rsplit("/", 1)[-1], download.content, download.url, download.fetched_at)
                    stats["baixado"] += 1
                except Exception as error:
                    stats["erro_download"] += 1
                    print(f"vert {emission['id']} documento {doc['id']}: erro no download ({type(error).__name__})", file=sys.stderr)
    stats["emissoes_nao_visitadas"] = len(missing)
    return {"stats": dict(stats), "faltou": missing}


COLLECTORS = {"opea": collect_opea, "riza": collect_riza, "eco": collect_eco, "vert": collect_vert}


# ---- leitura e classificação ----

class Reader:
    """Texto por página (pymupdf); página sem texto vai para OCR. Cache por SHA-256 em data/atas_portais/texto/."""

    def __init__(self):
        self._engine = None

    def _ocr(self, page) -> str:
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR
            sys.path.insert(0, str(ROOT / "scripts"))
            from ocr_document_pages import lines_from_boxes
            self._engine, self._lines = RapidOCR(), lines_from_boxes
        result, _ = self._engine(page.get_pixmap(dpi=150).tobytes("png"))
        return self._lines(result)[0]

    def pages(self, row: dict) -> tuple[list[str], list[int]]:
        cache = TEXTS / f"{row['sha256']}.json"
        if cache.exists():
            data = json.loads(cache.read_text(encoding="utf-8"))
            return data["paginas"], data["paginas_ocr"]
        import pymupdf

        texts, ocr = [], []
        with pymupdf.open(ROOT / row["arquivo"], filetype="pdf") as document:
            for number, page in enumerate(document, start=1):
                text = page.get_text()
                if not text.strip() and len(ocr) < OCR_MAX_PAGES:
                    try:
                        text = self._ocr(page)
                        ocr.append(number)
                    except Exception as error:
                        print(f"OCR falhou em {row['arquivo']} p.{number} ({type(error).__name__})", file=sys.stderr)
                texts.append(text)
        TEXTS.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"arquivo": row["arquivo"], "paginas": texts, "paginas_ocr": ocr}, ensure_ascii=False),
                         encoding="utf-8")
        return texts, ocr


def analyse(row: dict, reader: Reader) -> dict:
    out = {k: row.get(k, "") for k in OUT_FIELDS}
    if row["formato"] != "pdf":
        return {**out, "resultado": f"nao_lido ({row['formato']})"}
    try:
        pages, ocr_pages = reader.pages(row)
    except Exception as error:
        return {**out, "resultado": f"erro_leitura ({type(error).__name__})"}
    text = "\n".join(pages)
    out.update({"paginas": len(pages), "paginas_ocr": len(ocr_pages), "ocr": "sim" if ocr_pages else "nao"})
    if not text.strip():
        return {**out, "resultado": "sem_texto"}
    hits, marks = classify(text)
    outcome = decide(text) if row["tipo"] in ("ata", "assembleia") else None
    decisions = [d.event for d in outcome.decisions] if outcome else []
    graves, origin = grave_events(decisions, [(h.topic, h.excerpt) for h in hits if h.level == "relevante"])
    out.update({
        "assuntos_relevantes": "; ".join(relevant(hits)), "rotina": "; ".join(h.topic for h in hits if h.level == "rotina"),
        "resultado": (outcome.status if outcome.kind == "ata" else "edital_ou_outro") if outcome else "",
        "decisoes": "; ".join(decisions), "eventos_graves": "; ".join(graves), "origem_eventos": origin,
        "nao_instalada": int(marks["nao_instalada"]), "segunda_convocacao": int(marks["segunda_convocacao"]),
        "trecho": next((h.excerpt for h in hits if h.level == "relevante"), "")[:300],
        "trecho_decisao": outcome.decisions[0].excerpt[:400] if outcome and outcome.decisions else ""})
    return out


def write_reports(rows: list[dict], since: str, runs: dict[str, dict]) -> None:
    rows.sort(key=lambda r: (r["publicado_em"], r["securitizadora"], r["emissao_id"]), reverse=True)
    with (ROOT / "reports" / "atas_portais.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUT_FIELDS, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    def cell(text, size=200) -> str:
        return str(text or "").replace("|", "/").replace("\n", " ")[:size]

    def when(r) -> str:
        return r["data_evento"] or r["publicado_em"]

    by_source = Counter((r["securitizadora"], r["tipo"]) for r in rows)
    kinds = sorted({k for _, k in by_source})
    graves = [r for r in rows if r["eventos_graves"]]
    decided = sorted((r for r in graves if r["origem_eventos"] == "decisão"), key=when, reverse=True)
    discussed = sorted((r for r in graves if r["origem_eventos"] == "texto"), key=when, reverse=True)
    atas = [r for r in rows if r["tipo"] in ("ata", "assembleia") and r["resultado"] not in ("", "edital_ou_outro")]
    lines = [
        "# Atas e comunicados publicados nos portais das securitizadoras", "",
        f"Documentos publicados desde {since} nos portais da Opea (diário de bordo), Riza (portal do investidor), Eco "
        "(página pública da emissão) e Vert (VERT Data). Site da securitizadora é a fonte de menor prioridade: complementa "
        "a CVM, nunca a corrige. Assuntos e decisões por regras de texto (sem IA): candidatos para leitura, não conclusões. "
        "Documento lido por OCR vem marcado: o trecho pode ter erro de leitura.", "",
        f"Documentos: **{len(rows)}**; com evento grave decidido em ata: **{len(decided)}**; com evento grave só no texto "
        f"(edital, fato relevante, comunicado ou ata sem decisão identificada): **{len(discussed)}**; lidos por OCR: "
        f"**{sum(1 for r in rows if r['ocr'] == 'sim')}**.", "",
        "| Securitizadora | " + " | ".join(kinds) + " | Total |", "|---|" + "---|" * (len(kinds) + 1)]
    for source in SOURCES:
        counts = [by_source.get((source, k), 0) for k in kinds]
        if sum(counts):
            lines.append(f"| {source} | " + " | ".join(str(c) for c in counts) + f" | {sum(counts)} |")
    lines += ["", "## Eventos graves decididos em ata (mais recentes primeiro)", "",
              "Vencimento antecipado, recuperação judicial, liquidação do patrimônio separado, waiver e repactuação, pelo "
              "que a ata decidiu. Data = data da assembleia quando o portal informa; senão, a de publicação.", "",
              "| Data | Securitizadora | Emissão | CETIPs | Título | Resultado | Eventos | OCR | Trecho da decisão |",
              "|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {when(r)} | {r['securitizadora']} | {cell(r['emissao'], 70)} | {cell(r['cetips'], 60)} | {cell(r['titulo'], 70)} | "
              f"{r['resultado'].replace('_', ' ')} | {r['eventos_graves']} | {r['ocr']} | {cell(r['trecho_decisao'], 220)} |"
              for r in decided]
    lines += ["", "## Eventos graves só no texto (mais recentes primeiro)", "",
              "Edital ou proposta (o assunto está na ordem do dia), fato relevante, comunicado ou ata em que as regras não "
              "acharam a decisão.", "",
              "| Data | Securitizadora | Emissão | CETIPs | Tipo | Título | Eventos | Resultado da ata | OCR | Trecho |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {when(r)} | {r['securitizadora']} | {cell(r['emissao'], 70)} | {cell(r['cetips'], 60)} | {r['tipo']} | "
              f"{cell(r['titulo'], 70)} | {r['eventos_graves']} | {r['resultado'].replace('_', ' ')} | {r['ocr']} | "
              f"{cell(r['trecho'], 200)} |" for r in discussed]
    lines += ["", "## O que as atas decidiram", "", f"{len(atas)} atas e termos de não instalação.", "",
              "| Resultado | Atas |", "|---|---|"]
    lines += [f"| {k.replace('_', ' ')} | {n} |" for k, n in Counter(r["resultado"] for r in atas).most_common()]
    events = Counter(e for r in atas for e in r["decisoes"].split("; ") if e)
    lines += ["", "| Decisão | Atas |", "|---|---|"] + [f"| {k.replace('_', ' ')} | {n} |" for k, n in events.most_common()]
    unread = [r for r in rows if r["resultado"].startswith(("nao_lido", "erro_leitura", "sem_texto"))]
    lines += ["", f"## Documentos não lidos ({len(unread)})", "", "| Securitizadora | Emissão | Título | Motivo | Arquivo |", "|---|---|---|---|---|"]
    lines += [f"| {r['securitizadora']} | {cell(r['emissao'], 60)} | {cell(r['titulo'], 60)} | {r['resultado']} | {r['arquivo']} |"
              for r in unread]
    if runs:
        lines += ["", "## Cobertura da coleta", "", "| Securitizadora | Contagens | Não visitadas (limite de tempo) |", "|---|---|---|"]
        for source, run in runs.items():
            missing = run.get("faltou") or []
            lines.append(f"| {source} | {', '.join(f'{k}: {v}' for k, v in sorted(run.get('stats', {}).items()))} | "
                         f"{len(missing)}{': ' + ', '.join(missing[:15]) + (' ...' if len(missing) > 15 else '') if missing else ''} |")
    (ROOT / "reports" / "atas_portais.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    mode.add_argument("--parse-only", action="store_true")
    parser.add_argument("--only", action="append", help="código CETIP, ISIN ou id no portal (código Opea, operação Riza, id Eco/Vert)")
    parser.add_argument("--since", default="2026-08-01", help="publicados a partir desta data (AAAA-MM-DD)")
    parser.add_argument("--source", action="append", choices=SOURCES)
    parser.add_argument("--max-minutes", type=float, default=45.0, help="limite da coleta; o que faltar sai no relatório")
    args = parser.parse_args()
    sources = args.source or list(SOURCES)
    if "vert" in sources and not (ROOT / "src" / "credit_assets" / "vert_portal.py").exists():
        print("vert_portal.py não existe: Vert fica de fora", file=sys.stderr)
        sources.remove("vert")

    manifest = load_manifest()
    runs: dict[str, dict] = {}
    if not args.parse_only:
        first, universe = scope()
        store = Store(manifest, args.commit)
        deadline = time.monotonic() + args.max_minutes * 60
        with ThreadPoolExecutor(max_workers=len(sources)) as pool:
            futures = {source: pool.submit(COLLECTORS[source], args, first, universe, store, deadline) for source in sources}
            for source, future in futures.items():
                try:
                    runs[source] = future.result()
                except Exception as error:  # uma securitizadora fora do ar não derruba as outras
                    runs[source] = {"stats": {"erro": f"{type(error).__name__}: {error}"[:200]}, "faltou": []}
                print(f"{source}: {json.dumps(runs[source]['stats'], ensure_ascii=False)}", file=sys.stderr)
        if args.dry_run:
            print(json.dumps({"dry_run": True, "since": args.since,
                              "por_securitizadora": {s: r["stats"] for s, r in runs.items()},
                              "documentos_a_baixar": Counter(f"{d['securitizadora']}/{d['tipo']}" for d in store.listed)},
                             ensure_ascii=False, indent=2))
            for doc in store.listed[:200] if args.only else []:
                print(f"  {doc['securitizadora']} {doc['emissao_id']} {doc['publicado_em']} {doc['tipo']}: {doc['titulo']}")
            return 0
        save_manifest(manifest)

    reader = Reader()
    rows = []
    for row in manifest.values():
        if not in_window(row["publicado_em"], args.since) or row["securitizadora"] not in sources:
            continue
        if args.only and not wanted(args.only, *row["cetips"].split(), row["emissao_id"]):
            continue
        rows.append(analyse(row, reader))
    write_reports(rows, args.since, runs)
    print(json.dumps({"documentos": len(rows), "por_tipo": Counter(r["tipo"] for r in rows),
                      "com_evento_grave": sum(1 for r in rows if r["eventos_graves"]),
                      "ocr": sum(1 for r in rows if r["ocr"] == "sim"),
                      "coleta": {s: r["stats"] for s, r in runs.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
