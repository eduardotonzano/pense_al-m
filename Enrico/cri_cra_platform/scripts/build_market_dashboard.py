"""Painel HTML local do mercado de CRA/CRI a partir dos relatórios de mercado já gerados (só leitura).

Lê reports/market_summary.json, market_ranking.csv, market_events.csv, market_debtors.csv e
market_securitizadoras.csv e gera reports/painel_mercado.html: um arquivo só, sem dependência externa,
com tabelas ordenáveis e filtro de texto. Rodar depois de run_market_checks, run_market_events,
run_debtor_exposure e run_securitizadora_scorecard.
"""
from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

STYLE = """
:root { --bg:#fff; --fg:#1d1d1f; --muted:#666; --line:#ddd; --card:#f5f6f8; --accent:#0b57d0; --warn:#b3261e; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#16171a; --fg:#e8e8ea; --muted:#a0a0a6; --line:#34353a; --card:#1f2024; --accent:#8ab4f8; --warn:#f2b8b5; }
}
* { box-sizing:border-box; }
body { background:var(--bg); color:var(--fg); font:14px/1.45 system-ui, sans-serif; margin:0 auto; max-width:1280px; padding:16px; }
h1 { font-size:22px; margin:4px 0; } h2 { font-size:17px; margin-top:28px; }
.muted { color:var(--muted); }
.kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:10px; margin:14px 0; }
.kpi { background:var(--card); border-radius:10px; padding:10px 12px; }
.kpi b { display:block; font-size:20px; }
.wrap { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:13px; }
th, td { border-bottom:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; white-space:nowrap; }
th { background:var(--card); position:sticky; top:0; cursor:pointer; user-select:none; }
td.num, th.num { text-align:right; }
input.filter { width:100%; max-width:360px; padding:6px 8px; margin:6px 0; border:1px solid var(--line); border-radius:6px;
               background:var(--bg); color:var(--fg); }
nav a { color:var(--accent); margin-right:14px; }
.warn { color:var(--warn); font-weight:600; }
"""

SCRIPT = """
document.querySelectorAll('table.sortable').forEach(table => {
  table.querySelectorAll('th').forEach((th, index) => th.addEventListener('click', () => {
    const body = table.tBodies[0];
    const rows = Array.from(body.rows);
    const asc = th.dataset.dir !== 'asc';
    th.dataset.dir = asc ? 'asc' : 'desc';
    const value = cell => {
      const text = cell.innerText.trim().replace(/\\./g, '').replace(',', '.');
      const number = parseFloat(text);
      return isNaN(number) ? cell.innerText.trim().toLowerCase() : number;
    };
    rows.sort((a, b) => {
      const x = value(a.cells[index]), y = value(b.cells[index]);
      return (x > y ? 1 : x < y ? -1 : 0) * (asc ? 1 : -1);
    });
    rows.forEach(row => body.appendChild(row));
  }));
});
document.querySelectorAll('input.filter').forEach(input => input.addEventListener('input', () => {
  const term = input.value.toLowerCase();
  document.getElementById(input.dataset.table).querySelectorAll('tbody tr').forEach(row => {
    row.style.display = row.innerText.toLowerCase().includes(term) ? '' : 'none';
  });
}));
"""


def read_csv(name: str) -> list[dict[str, str]]:
    path = REPORTS / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def brl_mi(value: str | None) -> str:
    try:
        return f"{Decimal(value or 0) / 1_000_000:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return value or ""


def table(table_id: str, headers: list[tuple[str, bool]], rows: list[list[str]], limit: int | None = None) -> str:
    head = "".join(f"<th class='{'num' if numeric else ''}'>{html.escape(label)}</th>" for label, numeric in headers)
    body = []
    for row in rows[:limit] if limit else rows:
        cells = "".join(
            f"<td class='{'num' if headers[i][1] else ''}'>{cell}</td>" for i, cell in enumerate(row)
        )
        body.append(f"<tr>{cells}</tr>")
    return (f"<input class='filter' data-table='{table_id}' placeholder='Filtrar…'>"
            f"<div class='wrap'><table id='{table_id}' class='sortable'><thead><tr>{head}</tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table></div>")


def main() -> int:
    summary = json.loads((REPORTS / "market_summary.json").read_text(encoding="utf-8"))
    ranking = read_csv("market_ranking.csv")
    events = read_csv("market_events.csv")
    debtors = read_csv("market_debtors.csv")
    issuers = read_csv("market_securitizadoras.csv")
    termo = read_csv("termo_vs_cvm.csv")
    assemblies = [r for r in read_csv("assembleias_topicos.csv") if r.get("assuntos_relevantes")]
    dfin = read_csv("market_dfin.csv")
    e = html.escape

    kpis = []
    for kind, info in summary.items():
        kpis += [
            (f"{kind.upper()}: emissões com informe recente", f"{info['emissoes_com_informe_recente']:,}".replace(",", ".")),
            (f"{kind.upper()}: saldo (R$ bi)", f"{Decimal(info['saldo_total']) / 1_000_000_000:,.1f}".replace(".", ",")),
            (f"{kind.upper()}: emissões com sinal", f"{info['com_sinal']:,}".replace(",", ".")),
            (f"{kind.upper()}: em atraso", str(info["sinais"].get("em_atraso", 0))),
        ]
    new_late = sum(1 for ev in events if ev["evento"] == "entrou_em_atraso")
    contagion = sum(1 for d in debtors if d.get("contagio") == "1")
    kpis += [("Séries que entraram em atraso no mês", str(new_late)), ("Devedores com contágio", str(contagion))]
    reference = " / ".join(f"{k.upper()} {v['referencia'][:7]}" for k, v in summary.items())

    parts = [
        "<h1>Painel do mercado de CRA e CRI</h1>",
        f"<p class='muted'>Fonte: Informe Mensal dos dados abertos da CVM. Competência de referência: {e(reference)}. "
        f"Gerado em {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC. "
        "Sinais para triagem, não conclusões: o dado é o do próprio Informe e erros de preenchimento vêm junto.</p>",
        "<nav><a href='#eventos'>Eventos do mês</a><a href='#ranking'>Ranking</a><a href='#devedores'>Devedores</a>"
        "<a href='#securitizadoras'>Securitizadoras</a><a href='#termo'>Termo × Informe</a><a href='#assembleias'>Assembleias e fatos</a><a href='#dfin'>DFs</a></nav>",
        "<div class='kpis'>" + "".join(f"<div class='kpi'><span class='muted'>{e(label)}</span><b>{e(value)}</b></div>"
                                       for label, value in kpis) + "</div>",
        "<h2 id='eventos'>Eventos de crédito no mês</h2>",
        table("t-eventos", [("Tipo", False), ("Evento", False), ("ISIN", False), ("Certificado", False), ("Antes", False),
                            ("Depois", False), ("Saldo (R$ mi)", True)],
              [[e(ev["tipo"]), e(ev["evento"]), e(ev["isin"]), e(ev["certificado"] or ""), e(ev["antes"][:40]),
                e(ev["depois"][:40]), brl_mi(ev["saldo"])]
               for ev in sorted(events, key=lambda r: -Decimal(r["saldo"] or 0))]),
        "<h2 id='ranking'>Ranking de emissões por sinais</h2>",
        table("t-ranking", [("Tipo", False), ("Certificado", False), ("Séries", True), ("Saldo (R$ mi)", True),
                            ("Última competência", False), ("Pontos", True), ("Sinais", False)],
              [[e(r["tipo"]), e(r["certificado"]), e(r["series"]), brl_mi(r["saldo_brl"]), e(r["ultima_competencia"][:7]),
                e(r["score"]), e(", ".join(f"{k}×{v}" for k, v in r.items()
                                         if k not in ("tipo", "certificado", "emissora_cnpj", "series", "saldo_brl",
                                                      "ultima_competencia", "score") and v not in ("0", "")))]
               for r in ranking], limit=400),
        "<h2 id='devedores'>Exposição por devedor</h2>",
        table("t-devedores", [("CNPJ", False), ("Tipos", False), ("Emissões", True), ("Em atraso", True),
                              ("Exposição (R$ mi)", True), ("Contágio", False)],
              [[e(d["cnpj_devedor"]), e(d["tipos"]), e(d["emissoes"]), e(d["emissoes_em_atraso"]),
                brl_mi(d["exposicao_estimada_brl"]), "<span class='warn'>sim</span>" if d["contagio"] == "1" else ""]
               for d in debtors], limit=400),
        "<h2 id='securitizadoras'>Securitizadoras</h2>",
        table("t-securitizadoras", [("Securitizadora", False), ("Tipos", False), ("Emissões", True), ("Saldo (R$ mi)", True),
                                    ("% saldo em atraso", True), ("Atraso mediano de entrega (dias)", True),
                                    ("% após 30 dias", True), ("Reenvios / 100 informes", True),
                                    ("% séries com erro cadastral", True), ("% devedor não informado", True),
                                    ("% CNPJ de devedor inválido", True)],
              [[e(s["nome"]), e(s["tipos"]), e(s["emissoes"]), e(s["saldo_mi"]), e(s["pct_saldo_em_atraso"]),
                e(s["atraso_mediano_dias"]), e(s["pct_entregue_apos_30d"]), e(s["reenvios_por_100_informes"]),
                e(s["pct_series_com_erro_cadastral"]), e(s.get("pct_devedor_nao_informado")),
                e(s["pct_devedor_cnpj_invalido"])] for s in issuers]),
        "<h2 id='termo'>Termo de Securitização × Informe da CVM (ativos com Termo baixado)</h2>",
        "<p class='muted'>Valores do Termo extraídos por regex (candidatos, não parâmetros aprovados). Divergência pede leitura humana.</p>",
        table("t-termo", [("Ativo", False), ("ISIN", False), ("Campo", False), ("Resultado", False), ("Termo", False), ("CVM", False)],
              [[e(r["ativo"]), e(r["isin"]), e(r["campo"]),
                f"<span class='warn'>{e(r['resultado'])}</span>" if r["resultado"] == "diverge" else e(r["resultado"]),
                e(r["termo"][:60]), e(r["cvm"])]
               for r in sorted(termo, key=lambda r: (r["resultado"] != "diverge", r["ativo"]))]),
        "<h2 id='assembleias'>Assembleias, fatos relevantes e comunicados (ativos com documentos baixados)</h2>",
        "<p class='muted'>Assuntos por palavras-chave: o que foi discutido, não o que foi decidido.</p>",
        table("t-assembleias", [("Data", False), ("Ativo", False), ("Documento", False), ("Assuntos", False),
                                ("Resultado da ata", False), ("Decisões", False), ("Trecho", False)],
              [[e(r["data"]), e(r["ativo"]), e(f"{r['categoria']} {r['documento']}"), e(r["assuntos_relevantes"]),
                e((r.get("resultado") or "").replace("_", " ") if r.get("documento_tipo") == "ata" else ""),
                e((r.get("decisoes") or "").replace("_", " ")),
                e((r.get("trecho_decisao") or r["trecho"])[:160])]
               for r in sorted(assemblies, key=lambda r: r["data"], reverse=True)]),
        "<h2 id='dfin'>Demonstrações financeiras dos patrimônios separados</h2>",
        ("<p class='muted'>Opinião do auditor como informada à CVM; ler o relatório antes de concluir.</p>" if dfin else
         "<p class='muted'>Ainda sem dados: rode scripts/ingest_cvm_dfin.py --commit e scripts/run_dfin_checks.py.</p>"),
        table("t-dfin", [("Tipo", False), ("Certificado", False), ("Emissão", False), ("Data-base", False), ("Parecer", False),
                         ("Sinais", False), ("Em atraso", False), ("Saldo (R$ mi)", True), ("DF", False)],
              [[e(r["tipo"]), e(r["certificado"]), e(r["emissao"][:50]), e(r["data_base"]), e(r["parecer"]), e(r["sinais"]),
                "sim" if r["em_atraso"] == "1" else "", brl_mi(r["saldo_brl"]),
                f"<a href='{e(r['link'])}' target='_blank'>abrir</a>" if r["link"] else ""]
               for r in sorted(dfin, key=lambda r: -Decimal(r["saldo_brl"] or 0))], limit=500) if dfin else "",
    ]
    page = ("<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'><title>Painel do mercado CRA/CRI</title>"
            f"<style>{STYLE}</style></head><body>{''.join(parts)}<script>{SCRIPT}</script></body></html>")
    out = REPORTS / "painel_mercado.html"
    out.write_text(page, encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {len(events)} eventos, {len(ranking)} emissões com sinal, {len(debtors)} devedores, "
          f"{len(issuers)} securitizadoras")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
