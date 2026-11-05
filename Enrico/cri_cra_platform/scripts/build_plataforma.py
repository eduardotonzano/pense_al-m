"""Dados da plataforma (página do MVP) para Securitizados: busca por ISIN, nome ou CNPJ e ficha por ativo (só leitura).

    python scripts/build_plataforma.py

Lê data/cri_cra.db, data/cvm_open.db e os relatórios de reports/ e grava em data/plataforma/ (fora do git):
  index.html               página do MVP (plataforma/template.html) com a busca e a ficha de CRI/CRA
  dados/indice.json        um item por ativo, com os campos da busca
  dados/fichas/NN.json     fichas divididas em blocos (o bloco do ativo é carregado quando a ficha abre)

Cada valor sai com a fonte: cadastro do Fundos.NET, Informe Mensal da CVM (competência), relatório da securitizadora,
Termo de Securitização (página) ou ata. Nada é estimado: campo sem dado sai vazio. CPF não sai (só CNPJ).
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.cvm_lookup import emission  # noqa: E402
from credit_assets.debtor_exposure import classify_identifier, format_cnpj  # noqa: E402

REPORTS = ROOT / "reports"
OUT = ROOT / "data" / "plataforma"
SHARDS = 64
LAST_INFORMES = 12  # Informe Mensal: só os 12 mais recentes por ativo (a contagem total aparece na ficha)
CATEGORIES = ["Termo de Securitização", "Aditamento", "Informe Mensal", "Ata/Edital", "Fato Relevante",
              "Relatório Agente Fiduciário", "Relatório de Rating", "Anúncio de Encerramento", "Outro"]


def shard_of(cetip: str) -> int:
    return zlib.crc32(cetip.upper().encode("utf-8")) % SHARDS


def digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def cnpj_or_blank(value: str | None) -> str:
    kind, number = classify_identifier(value or "")
    return format_cnpj(number) if kind == "cnpj" and number else ""


def read_csv(name: str) -> list[dict[str, str]]:
    path = REPORTS / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def short_sha(value: str | None) -> str:
    return (value or "")[:12]


def main() -> int:
    catalog = sqlite3.connect(f"file:{ROOT / 'data' / 'cri_cra.db'}?mode=ro", uri=True, timeout=120)
    catalog.row_factory = sqlite3.Row
    assets = [dict(r) for r in catalog.execute(
        "SELECT asset_id, codigo_cetip, isin, tipo_ativo, securitizadora, cnpj_securitizadora, emissao, serie, devedor, "
        "cnpj_devedor, active FROM assets WHERE codigo_cetip IS NOT NULL ORDER BY codigo_cetip")]

    documents: dict[int, list[dict]] = defaultdict(list)
    for r in catalog.execute(
            """SELECT d.asset_id, d.source_document_id, d.category, d.document_name, d.reference_date,
                      d.publication_date, d.download_status, v.file_format, v.file_size_bytes, v.file_hash,
                      v.validation_status
               FROM documents d LEFT JOIN document_versions v ON v.document_id = d.document_pk AND v.is_current = 1"""):
        documents[r["asset_id"]].append(dict(r))
    text_docs = {r[0] for r in catalog.execute(
        """SELECT DISTINCT d.source_document_id FROM document_text_pages t
           JOIN document_versions v ON v.version_id = t.document_version_id JOIN documents d ON d.document_pk = v.document_id
           WHERE length(trim(t.text)) > 0""")}
    catalog.close()

    cvm = sqlite3.connect(f"file:{ROOT / 'data' / 'cvm_open.db'}?mode=ro", uri=True, timeout=120)
    cvm.row_factory = sqlite3.Row
    # as views *_vigente recalculam a tabela inteira a cada consulta (3 s por ativo): uma cópia temporária com índice,
    # só nesta conexão e com o mesmo nome (o esquema temp é lido primeiro), dá o mesmo resultado em ~10 ms
    for kind in ("cra", "cri"):
        for view in ("classe_vigente", "geral_vigente"):
            cvm.execute(f"CREATE TEMP TABLE {kind}_{view} AS SELECT * FROM main.{kind}_{view}")
        cvm.execute(f"CREATE INDEX temp.ix_{kind}_cv_isin ON {kind}_classe_vigente(Codigo_ISIN)")
        cvm.execute(f"CREATE INDEX temp.ix_{kind}_cv_cert ON {kind}_classe_vigente(Codigo_Identificacao_Certificado)")
        cvm.execute(f"CREATE INDEX temp.ix_{kind}_cv_cnpj ON {kind}_classe_vigente(CNPJ_Emissora, Codigo_ISIN)")
        cvm.execute(f"CREATE INDEX temp.ix_{kind}_gv_cert ON {kind}_geral_vigente(Codigo_Identificacao_Certificado)")

    debtor_cvm: dict[str, list[dict]] = defaultdict(list)
    for r in read_csv("cnpj_devedor_cvm.csv"):
        debtor_cvm[r["codigo_cetip"].upper()].append(r)
    covenants: dict[str, list[dict]] = defaultdict(list)
    for r in read_csv("covenants_mensais.csv"):
        covenants[r["codigo_cetip"].upper()].append(r)
    guarantees: dict[str, list[dict]] = defaultdict(list)
    for r in read_csv("garantias_covenants.csv"):
        guarantees[r["codigo_cetip"].upper()].append(r)
    atas: dict[str, list[dict]] = defaultdict(list)
    for r in read_csv("atas_portais.csv"):
        for code in re.split(r"[|,; ]+", r.get("cetips") or ""):
            if code:
                atas[code.upper()].append({**r, "fonte": f"portal da {r['securitizadora']}" if r["securitizadora"] else "portal"})
    # atas e fatos relevantes do Fundos.NET lidos pela rotina mensal (run_assembly_topics.py)
    for r in read_csv("assembleias_topicos.csv"):
        if not r.get("ativo"):
            continue
        atas[r["ativo"].upper()].append({
            "data_evento": r["data"], "publicado_em": r["data"], "tipo": r["categoria"], "titulo": r["nome"] or r["categoria"],
            "resultado": r["resultado"], "decisoes": r["decisoes"], "eventos_graves": "",
            "assuntos": (r["assuntos_relevantes"] or "").replace(";", ", "), "origem_eventos": "",
            "trecho_decisao": r["trecho_decisao"], "trecho": r["trecho"], "ocr": "sim" if r["ocr"] == "1" else "nao",
            "url": f"https://fnet.bmfbovespa.com.br/fnet/publico/downloadDocumento?id={r['documento']}",
            "sha256": "", "securitizadora": "", "fonte": "Fundos.NET"})

    index, fichas = [], defaultdict(dict)
    totals = Counter()
    for a in assets:
        cetip = a["codigo_cetip"].upper()
        kind = (a["tipo_ativo"] or "").upper()
        # devedor: cadastro do catálogo; senão o CNPJ informado no Informe Mensal (um único devedor por ativo)
        debtor_rows = debtor_cvm.get(cetip, [])
        debtor_cnpjs = sorted({r["cnpj_devedor"] for r in debtor_rows if r["cnpj_devedor"]})
        devedor_cnpj, devedor_fonte = cnpj_or_blank(a["cnpj_devedor"]), "cadastro do catálogo (Fundos.NET)"
        if not devedor_cnpj and len(debtor_cnpjs) == 1:
            r = debtor_rows[0]
            devedor_cnpj = debtor_cnpjs[0]
            devedor_fonte = f"Informe Mensal da CVM, competência {r['competencia']} (versão {r['versao']})"
        elif not devedor_cnpj and len(debtor_cnpjs) > 1:
            devedor_fonte = f"Informe Mensal da CVM: {len(debtor_cnpjs)} devedores (carteira pulverizada)"
        # catálogo e Informe divergem: os dois aparecem, com a fonte, sem escolha automática (regra G-04)
        cnpj_cvm, cnpj_cvm_fonte = "", ""
        if devedor_cnpj and len(debtor_cnpjs) == 1 and debtor_cnpjs[0] != devedor_cnpj:
            cnpj_cvm = debtor_cnpjs[0]
            cnpj_cvm_fonte = (f"Informe Mensal da CVM, competência {debtor_rows[0]['competencia']} "
                              f"(versão {debtor_rows[0]['versao']})")
            totals["conflito_cnpj_devedor"] += 1

        em = None
        if a["isin"] and kind in ("CRI", "CRA"):
            try:
                em = emission(cvm, kind.lower(), a["isin"])
            except sqlite3.Error:
                em = None
        informe = None
        if em:
            geral = em["geral"]
            informe = {
                "competencia": (em["last"] or "")[:7], "emissora": geral.get("Companhia_Emissora") or "",
                "nome_emissao": geral.get("Nome_Emissao") or "", "data_emissao": em["data_emissao"],
                "series": [{"serie": str(s.get("Numero_Serie") or ""), "isin": s.get("Codigo_ISIN") or "",
                            "classe": s.get("Classe") or "", "situacao": s.get("Situacao") or "",
                            "saldo": s.get("Valor_Certificados") or "", "vencimento": (s.get("Data_Vencimento") or "")[:10],
                            "taxa": s.get("Taxa_Juros") or "", "rating": s.get("Classificacao_Risco_Atual") or ""}
                           for s in sorted(em["series"], key=lambda s: str(s.get("Numero_Serie")))],
            }

        docs = documents.get(a["asset_id"], [])
        by_cat = Counter(d["category"] or "Outro" for d in docs)
        informes = sorted((d for d in docs if d["category"] == "Informe Mensal"),
                          key=lambda d: d["reference_date"] or "", reverse=True)[:LAST_INFORMES]
        shown = [d for d in docs if d["category"] != "Informe Mensal"] + informes
        doc_rows = []
        for d in sorted(shown, key=lambda d: (d["reference_date"] or d["publication_date"] or ""), reverse=True):
            downloaded = d["validation_status"] == "valid"
            state = "baixado" if downloaded else ("falhou" if d["download_status"] == "failed" else "catalogado")
            doc_rows.append({"id": d["source_document_id"], "cat": d["category"] or "Outro",
                             "nome": d["document_name"] or "", "ref": (d["reference_date"] or "")[:10],
                             "pub": (d["publication_date"] or "")[:10], "fmt": (d["file_format"] or "").upper(),
                             "bytes": d["file_size_bytes"] or 0, "sha": short_sha(d["file_hash"]) if downloaded else "",
                             "estado": state, "texto": d["source_document_id"] in text_docs})

        cov_rows = [{"fonte": r["fonte"], "competencia": r["competencia"], "grupo": r["grupo"], "item": r["item"],
                     "exigido": r["exigido"], "apurado": r["apurado"], "situacao": r["situacao"],
                     "data": r["data_verificacao"], "documento": r["documento"], "sha": short_sha(r["sha256"])}
                    for r in covenants.get(cetip, [])]
        gar_rows = [{"grupo": r["grupo"], "item": r["item"], "rotulo": r["rotulo"], "situacao": r["situacao"],
                     "limite": " ".join(x for x in (r["operador"], r["limite"], r["unidade"]) if x),
                     "periodicidade": r["periodicidade"], "documento": r["documento"], "pagina": r["pagina"],
                     "ocr": r["ocr"], "trecho": (r["trecho"] or "")[:600], "revisao": r["revisao"]}
                    for r in guarantees.get(cetip, [])]
        ata_rows = [{"data": r["data_evento"] or r["publicado_em"], "publicado": r["publicado_em"], "tipo": r["tipo"],
                     "titulo": r["titulo"], "resultado": r["resultado"], "decisoes": r["decisoes"],
                     "eventos": r["eventos_graves"], "origem": r["origem_eventos"], "assuntos": r.get("assuntos", ""),
                     "trecho": (r["trecho_decisao"] or r["trecho"] or "")[:500], "ocr": r["ocr"], "url": r["url"],
                     "sha": short_sha(r["sha256"]), "securitizadora": r["securitizadora"], "fonte": r["fonte"]}
                    for r in sorted(atas.get(cetip, []), key=lambda r: r["publicado_em"] or "", reverse=True)]

        names = " ".join(x for x in (a["devedor"], a["securitizadora"], informe["emissora"] if informe else "",
                                     informe["nome_emissao"] if informe else "",
                                     " ".join(r["devedor_catalogo"] for r in debtor_rows)) if x)
        index.append({
            "c": cetip, "i": a["isin"] or "", "t": kind, "s": a["securitizadora"] or "",
            "e": a["emissao"] or "", "r": a["serie"] or "", "d": a["devedor"] or "",
            "n": names, "k": " ".join(sorted({digits(a["cnpj_securitizadora"]), digits(devedor_cnpj),
                                              *(digits(x) for x in debtor_cnpjs)} - {""})),
            "b": shard_of(cetip), "q": [len(docs), len(cov_rows), len(gar_rows), len(ata_rows),
                                         sum(1 for r in cov_rows if r["situacao"] == "nao_atendido")],
            "a": 1 if a["active"] else 0,
        })
        fichas[shard_of(cetip)][cetip] = {
            "id": {"codigo": cetip, "isin": a["isin"] or "", "tipo": kind, "securitizadora": a["securitizadora"] or "",
                   "cnpj_securitizadora": cnpj_or_blank(a["cnpj_securitizadora"]), "emissao": a["emissao"] or "",
                   "serie": a["serie"] or "", "devedor": a["devedor"] or "", "cnpj_devedor": devedor_cnpj,
                   "cnpj_devedor_fonte": devedor_fonte if (devedor_cnpj or debtor_cnpjs) else "",
                   "cnpj_devedor_cvm": cnpj_cvm, "cnpj_devedor_cvm_fonte": cnpj_cvm_fonte,
                   "devedores_cvm": debtor_cnpjs if len(debtor_cnpjs) > 1 else [], "ativo": bool(a["active"])},
            "informe": informe, "docs_por_categoria": dict(by_cat), "docs": doc_rows,
            "docs_informe_total": by_cat.get("Informe Mensal", 0), "covenants": cov_rows, "garantias": gar_rows,
            "atas": ata_rows,
        }
        totals["ativos"] += 1
        totals["documentos"] += len(docs)
        totals["com_covenants"] += bool(cov_rows)
        totals["com_garantias"] += bool(gar_rows)
        totals["com_atas"] += bool(ata_rows)
        totals["com_cnpj_devedor"] += bool(devedor_cnpj)
    cvm.close()

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "dados" / "fichas").mkdir(parents=True)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta = {"gerado_em": generated, "categorias": CATEGORIES, "totais": dict(totals),
            "por_tipo": dict(Counter(x["t"] for x in index)), "informes_por_ativo": LAST_INFORMES}
    (OUT / "dados" / "indice.json").write_text(
        json.dumps({"meta": meta, "ativos": index}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for number in range(SHARDS):
        (OUT / "dados" / "fichas" / f"{number:02d}.json").write_text(
            json.dumps(fichas.get(number, {}), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    template = (ROOT / "plataforma" / "template.html").read_text(encoding="utf-8")
    (OUT / "index.html").write_text(template, encoding="utf-8")
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(json.dumps({**meta, "arquivos": SHARDS + 2, "megabytes": round(size / 1e6, 1),
                      "sha_indice": hashlib.sha256((OUT / "dados" / "indice.json").read_bytes()).hexdigest()[:12]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
