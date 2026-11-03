"""Base única de covenants por ativo, no formato do módulo "Covenants" da plataforma (um item monitorado por linha).

    python scripts/build_covenants_mensais.py

Junta, por código CETIP, o que já foi gerado em reports/ (só leitura; nada é gravado no banco):
  - apuração mensal das securitizadoras: reports/<securitizadora>_monitoramentos.csv (Opea, Vert, Leverage, Bari,
    Canal): exigido × apurado × situação informada pela securitizadora, com data de verificação;
  - acompanhamento mensal da Eco: reports/eco_relatorios_mensais.csv (cobertura de garantias, carteira vencida,
    aderência aos critérios do Termo);
  - o que o Termo exige, lido nos documentos do Fundos.NET: reports/garantias_covenants.csv (covenant com limite).
Cada linha leva a fonte, o documento (caminho e SHA-256) e o leitor. Valores copiados como estão; a situação é a que a
fonte informa (sem dedução). Site da securitizadora complementa a CVM (regra 3).
Saída: reports/covenants_mensais.{csv,md}.
"""
from __future__ import annotations

import csv
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
MONITORS = {"Opea": "opea", "Vert": "vert", "Leverage": "leverage", "Bari": "bari", "Canal": "canal"}
FIELDS = ["codigo_cetip", "isin", "tipo", "securitizadora", "emissao", "devedor", "fonte", "competencia", "grupo",
          "item", "exigido", "apurado", "situacao", "data_verificacao", "proxima_verificacao", "documento", "sha256",
          "leitor"]


def read(path: Path, delimiter: str = ";") -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def codes(value: str) -> list[str]:
    return [code for code in re.split(r"[\s,;]+", value or "") if code]


def group_of(kind: str, text: str) -> str:
    text = f"{kind} {text}".lower()
    if re.search(r"fundo", text):
        return "fundo"
    if re.search(r"covenant|[íi]ndice|ltv|d[íi]vida|ebitda|liquidez|cobertura|raz[ãa]o|alavanc|subordina", text):
        return "covenant"
    if re.search(r"garantia|aliena|cess[ãa]o|fian|aval", text):
        return "garantia"
    return "obrigacao"


def main() -> int:
    registry = {r["codigo_cetip"]: r for r in read(ROOT / "config" / "ativos_mercado.csv", ",")}
    connection = sqlite3.connect(f"file:{ROOT / 'data' / 'cri_cra.db'}?mode=ro", uri=True)
    for cetip, isin, kind, issuer, emission, debtor in connection.execute(
            "SELECT codigo_cetip, isin, tipo_ativo, securitizadora, emissao, devedor FROM assets WHERE codigo_cetip IS NOT NULL"):
        registry.setdefault(cetip, {"isin": isin or "", "tipo_ativo": kind or "", "securitizadora": issuer or "",
                                    "emissao": emission or "", "devedor": debtor or ""})
    connection.close()

    rows = []

    def add(cetip: str, **values) -> None:
        base = registry.get(cetip, {})
        isin, debtor = values.pop("isin", ""), values.pop("devedor_fonte", "")
        rows.append({"codigo_cetip": cetip, "isin": isin or base.get("isin", ""),
                     "tipo": base.get("tipo_ativo", ""), "securitizadora": base.get("securitizadora", ""),
                     "emissao": base.get("emissao", ""), "devedor": base.get("devedor") or debtor, **values})

    for source, slug in MONITORS.items():
        for r in read(REPORTS / f"{slug}_monitoramentos.csv"):
            if not r.get("grupo_tipo") and r.get("item", "").startswith("("):
                continue  # relatório lido sem item monitorado
            isins = codes(r.get("isin", ""))
            for index, cetip in enumerate(codes(r.get("codigo_cetip", ""))):
                add(cetip, isin=isins[index] if index < len(isins) else "", devedor_fonte=r.get("devedor", ""),
                    fonte=f"{source} (relatório mensal)", competencia=r.get("competencia", ""),
                    grupo=group_of(r.get("grupo_tipo", ""), f"{r.get('grupo', '')} {r.get('item', '')}"),
                    item=" · ".join(part for part in (r.get("grupo", ""), r.get("item", "")) if part),
                    exigido=f"{r.get('valor_referencia', '')} {r.get('condicao_referencia', '')}".strip(),
                    apurado=r.get("valor_apurado", ""), situacao=r.get("situacao", ""),
                    data_verificacao=r.get("data_verificacao", ""), proxima_verificacao=r.get("proxima_verificacao", ""),
                    documento=r.get("arquivo", ""), sha256=r.get("sha256", ""), leitor=r.get("parser", ""))

    for r in read(REPORTS / "eco_relatorios_mensais.csv"):
        if not r.get("acompanhamento_publicado_em"):
            continue
        items = []
        if r.get("cobertura_garantias"):
            items.append(("garantia", "Cobertura de garantias (total de garantias / saldo devedor)",
                          f"{r.get('acompanhamento_total_garantias', '')} / {r.get('acompanhamento_saldo_devedor', '')} = {r['cobertura_garantias']}", ""))
        if r.get("acompanhamento_recebiveis_vencidos"):
            share = f" ({r['vencidos_sobre_vinculados']} da carteira)" if r.get("vencidos_sobre_vinculados") else ""
            items.append(("covenant", "Recebíveis vencidos na carteira", r["acompanhamento_recebiveis_vencidos"] + share, ""))
        if int(r.get("acompanhamento_aderencia_itens") or 0):
            bad = int(r.get("acompanhamento_aderencia_nao_aderentes") or 0)
            items.append(("covenant", "Critérios de elegibilidade da carteira (aderência ao Termo)",
                          f"{bad} não aderente(s) de {r['acompanhamento_aderencia_itens']}", "nao_atendido" if bad else "atendido"))
        for cetip in codes(r.get("cetips", "")):
            for group, item, value, status in items:
                add(cetip, fonte="Eco (relatório de acompanhamento)", competencia=r.get("acompanhamento_competencia", ""),
                    grupo=group, item=item, exigido="", apurado=value, situacao=status,
                    data_verificacao=r["acompanhamento_publicado_em"], proxima_verificacao="",
                    documento=r.get("url_emissao", ""), sha256="", leitor="eco_reports")

    for r in read(REPORTS / "garantias_covenants.csv"):
        if r["grupo"] == "covenant" and r["limite"]:
            add(r["codigo_cetip"], fonte="Termo (Fundos.NET)", competencia="", grupo="covenant",
                item=r["rotulo"], exigido=f"{r['operador']} {r['limite']}{r['unidade']}".strip(), apurado="",
                situacao="", data_verificacao="", proxima_verificacao=r.get("periodicidade", ""),
                documento=f"documento {r['documento']} p. {r['pagina']}", sha256="", leitor=r["extrator"])

    seen, unique = set(), []
    for row in rows:  # mesma linha vinda duas vezes (várias séries no mesmo relatório) não duplica
        key = tuple(row[f] for f in FIELDS)
        if key not in seen:
            seen.add(key)
            unique.append(row)
    unique.sort(key=lambda r: (r["codigo_cetip"], r["fonte"], r["grupo"], r["item"]))
    with (REPORTS / "covenants_mensais.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerows(unique)

    measured = defaultdict(set)
    for r in unique:
        if r["apurado"]:
            measured[r["fonte"]].add(r["codigo_cetip"])
    with_measure = {r["codigo_cetip"] for r in unique if r["apurado"]}
    only_term = {r["codigo_cetip"] for r in unique} - with_measure
    saldo = {c: float(registry.get(c, {}).get("saldo_brl") or 0) for c in registry}
    total = sum(saldo.values())
    covered = sum(saldo.get(c, 0) for c in with_measure)
    status = Counter(r["situacao"] or "sem situação informada" for r in unique if r["apurado"])
    lines = ["# Covenants por ativo (base para o módulo Covenants)", "",
             "Um item monitorado por linha: o que o contrato exige, o valor apurado, a situação informada pela fonte e a "
             "data. Fontes: relatório mensal das securitizadoras (Opea, Vert, Leverage, Bari, Canal), acompanhamento "
             "mensal da Eco e o Termo lido no Fundos.NET (só o exigido). Valores copiados como estão; situação sem dedução.", "",
             f"Ativos (CETIP) com apuração mensal: **{len(with_measure)}**; só com o exigido do Termo: **{len(only_term)}**; "
             f"linhas: **{len(unique)}**.", "",
             f"Saldo dos ativos com apuração mensal: **R$ {covered / 1e9:.1f} bi** de R$ {total / 1e9:.1f} bi da lista do "
             f"mercado ({covered / total:.0%}); a lista do mercado não inclui os ativos do catálogo.".replace(".", ",", 2), "",
             "| Fonte | Ativos com valor apurado |", "|---|---|",
             *[f"| {k} | {len(v)} |" for k, v in sorted(measured.items())], "",
             "| Situação informada (itens apurados) | Itens |", "|---|---|", *[f"| {k} | {v} |" for k, v in status.most_common()], ""]
    (REPORTS / "covenants_mensais.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print({"linhas": len(unique), "ativos_com_apuracao": len(with_measure), "so_termo": len(only_term),
           "saldo_coberto": f"{covered / total:.0%}" if total else ""})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
