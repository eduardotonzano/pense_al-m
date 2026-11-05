"""Covenants e alertas por ativo: junta, por código CETIP, os sinais de cada fonte já gerados em reports/.

    python scripts/build_alertas_por_ativo.py

Fontes (só leitura, nada é gravado no banco):
  - CVM / triagem do mercado: config/ativos_mercado.csv (saldo, score, sinais) e reports/acompanhamento_credito.csv;
  - Opea, Vert, Leverage, Bari e Canal: reports/<securitizadora>_monitoramentos.csv (itens "não atendido" do
    relatório mensal da securitizadora; arquivo ausente é ignorado);
  - Eco: reports/eco_relatorios_mensais.csv (recebíveis vencidos, cobertura, itens não aderentes);
  - Riza: reports/riza_status_vs_cvm.csv (operação em "Default" no portal);
  - Termo/documentos do Fundos.NET: reports/garantias_covenants.csv (covenants com limite extraído).
Cada sinal leva a fonte. Site da securitizadora complementa a CVM (regra 3): divergência é alerta para leitura, não
correção. Saída: reports/alertas_por_ativo.{csv,md}.
"""
from __future__ import annotations

import csv
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
MONITORS = {"Opea": "opea", "Vert": "vert", "Leverage": "leverage", "Bari": "bari", "Canal": "canal"}
FINANCIAL = re.compile(r"[íi]ndice|cobertura|raz[ãa]o de garantia|ltv|d[íi]vida|ebitda|liquidez|alavanc|endivid", re.IGNORECASE)


def read(path: Path, delimiter: str = ";") -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def money(value: str) -> float:
    found = re.search(r"-?[\d.]+,\d+", value or "")
    return float(found.group(0).replace(".", "").replace(",", ".")) if found else 0.0


def brl(value: float) -> str:
    return f"R$ {value / 1e6:,.1f} mi".replace(",", "X").replace(".", ",").replace("X", ".") if value else ""


def main() -> int:
    market = {r["codigo_cetip"]: r for r in read(ROOT / "config" / "ativos_mercado.csv", ",")}
    # ativos do catálogo não estão na lista do mercado: cadastro do banco (só leitura)
    connection = sqlite3.connect(f"file:{ROOT / 'data' / 'cri_cra.db'}?mode=ro", uri=True)
    for cetip, kind, issuer, emission, debtor in connection.execute(
            "SELECT codigo_cetip, tipo_ativo, securitizadora, emissao, devedor FROM assets WHERE codigo_cetip IS NOT NULL"):
        market.setdefault(cetip, {"tipo_ativo": kind or "", "securitizadora": issuer or "", "emissao": emission or "",
                                  "devedor": debtor or ""})
    connection.close()
    signals: dict[str, list[tuple[str, str]]] = defaultdict(list)  # cetip -> [(fonte, texto)]
    debtor_hint: dict[str, str] = {}

    for r in read(REPORTS / "acompanhamento_credito.csv"):
        signals[r["ativo"]].append(("CVM/atas", f"nível {r['nivel']}: {r['situacao']}"))
        market.setdefault(r["ativo"], {})
        market[r["ativo"]].setdefault("saldo_brl", r["saldo_brl"])
        if not market[r["ativo"]].get("saldo_brl"):
            market[r["ativo"]]["saldo_brl"] = r["saldo_brl"]

    # relatórios mensais das securitizadoras com tabela de monitoramento (mesmo formato de colunas)
    for source, slug in MONITORS.items():
        failing = defaultdict(list)
        for r in read(REPORTS / f"{slug}_monitoramentos.csv"):
            for cetip in re.split(r"[\s,;]+", r.get("codigo_cetip") or ""):  # várias séries no mesmo campo
                if cetip and r.get("devedor"):
                    debtor_hint.setdefault(cetip, f"{r['devedor']} ({source})")
                if cetip and r.get("situacao") == "nao_atendido":
                    failing[cetip].append(r)
        for cetip, items in failing.items():
            financial = [i for i in items if FINANCIAL.search(f"{i['grupo']} {i['item']}")]
            shown = (financial or items)[:3]
            detail = "; ".join(f"{i['item'] or i['grupo']} (exigido {i['valor_referencia']} {i['condicao_referencia']}, "
                               f"apurado {i['valor_apurado']})" for i in shown)
            label = "covenant/garantia financeira" if financial else "obrigação"
            signals[cetip].append((source, f"{len(items)} não atendido(s), {label}, {items[0]['competencia']}: {detail}"))

    for r in read(REPORTS / "eco_relatorios_mensais.csv"):
        parts = []
        overdue, linked = money(r.get("acompanhamento_recebiveis_vencidos", "")), money(r.get("acompanhamento_recebiveis_vinculados", ""))
        if overdue:
            parts.append(f"recebíveis vencidos {brl(overdue)}" + (f" ({overdue / linked:.0%} da carteira)" if linked else ""))
        if int(r.get("acompanhamento_aderencia_nao_aderentes") or 0):
            parts.append(f"{r['acompanhamento_aderencia_nao_aderentes']} critério(s) não aderente(s) ao Termo")
        if r.get("cobertura_garantias") and int(r["cobertura_garantias"].rstrip("%")) < 100:
            parts.append(f"cobertura de garantias {r['cobertura_garantias']}")
        if parts:
            note = f" [saldo igual ao da emissão {r['saldo_igual_ao_da_emissao']}: conferir]" if r.get("saldo_igual_ao_da_emissao") else ""
            for cetip in r["cetips"].split():
                signals[cetip].append(("Eco", f"{r.get('acompanhamento_publicado_em', '')}: " + "; ".join(parts) + note))

    for r in read(REPORTS / "riza_status_vs_cvm.csv"):
        if r["codigo_cetip"]:
            debtor_hint.setdefault(r["codigo_cetip"], f"{r['apelido']} (Riza)")
        if r["status_riza"].strip().lower() == "default" and r["codigo_cetip"]:
            signals[r["codigo_cetip"]].append(("Riza", f"Default no portal; CVM {r['competencia_cvm']}: {r['situacao_cvm']}"))

    limits = defaultdict(list)
    for r in read(REPORTS / "garantias_covenants.csv"):
        if r["grupo"] == "covenant" and r["limite"]:
            limits[r["codigo_cetip"]].append(f"{r['rotulo']} {r['operador']} {r['limite']}{r['unidade']}")

    rows = []
    for cetip, found in signals.items():
        base = market.get(cetip, {})
        sources = sorted({source for source, _ in found})
        rows.append({
            "codigo_cetip": cetip, "tipo": base.get("tipo_ativo", ""), "securitizadora": base.get("securitizadora", ""),
            "emissao": base.get("emissao", ""), "devedor": base.get("devedor") or debtor_hint.get(cetip, ""),
            "saldo_brl": base.get("saldo_brl", ""), "score_triagem": base.get("score", ""),
            "fontes": " + ".join(sources), "n_fontes": len(sources),
            "covenants_do_termo": "; ".join(dict.fromkeys(limits.get(cetip, []))),
            "sinais": " | ".join(f"[{source}] {text}" for source, text in found),
        })
    rows.sort(key=lambda r: (-r["n_fontes"], -float(r["saldo_brl"] or 0)))
    with (REPORTS / "alertas_por_ativo.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    by_source = defaultdict(int)
    for r in rows:
        for source in r["fontes"].split(" + "):
            by_source[source] += 1
    multi = [r for r in rows if r["n_fontes"] >= 2]
    lines = ["# Covenants e alertas por ativo", "",
             "Junta, por código CETIP, os sinais de cada fonte: Informe CVM e atas (acompanhamento de crédito), relatório "
             "mensal das securitizadoras com tabela de monitoramento (Opea, Vert, Leverage, Bari, Canal: itens não atendidos), acompanhamento mensal da Eco (recebíveis vencidos, aderência), portal "
             "da Riza (Default) e os covenants com limite lidos no Termo. Sites de securitizadora complementam a CVM: "
             "divergência é para leitura, não correção.", "",
             f"Ativos com algum sinal: **{len(rows)}**; em duas ou mais fontes: **{len(multi)}**.", "",
             "| Fonte | Ativos com sinal |", "|---|---|", *[f"| {k} | {v} |" for k, v in sorted(by_source.items())], "",
             f"## Sinal em duas ou mais fontes ({len(multi)})", ""]
    for r in multi:
        lines += [f"### {r['codigo_cetip']} · {r['tipo']} · {r['securitizadora']} · emissão {r['emissao']}",
                  f"Devedor: {r['devedor'] or '-'} · saldo CVM {brl(float(r['saldo_brl'] or 0)) or '-'} · fontes: {r['fontes']}", ""]
        lines += [f"- {signal}" for signal in r["sinais"].split(" | ")]
        if r["covenants_do_termo"]:
            lines.append(f"- [Termo] covenants com limite: {r['covenants_do_termo']}")
        lines.append("")
    financial = [r for r in rows if "covenant/garantia financeira" in r["sinais"] or "% da carteira" in r["sinais"]]
    financial.sort(key=lambda r: -float(r["saldo_brl"] or 0))
    lines += [f"## Covenant ou garantia financeira não atendida, ou carteira vencida (por saldo; {len(financial)} ativos)", "",
              "| CETIP | Tipo | Securitizadora | Devedor | Saldo CVM | Fontes | Sinal |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['codigo_cetip']} | {r['tipo']} | {r['securitizadora']} | {r['devedor']} | {brl(float(r['saldo_brl'] or 0))} | "
              f"{r['fontes']} | {r['sinais'].replace('|', '/')[:300]} |" for r in financial[:60]]
    lines += ["", f"Lista completa ({len(rows)} ativos) em reports/alertas_por_ativo.csv."]
    (REPORTS / "alertas_por_ativo.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print({"ativos": len(rows), "duas_ou_mais_fontes": len(multi), **by_source})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
