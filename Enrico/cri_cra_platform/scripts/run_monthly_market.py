"""Rotina mensal do mercado de CRA/CRI num comando só.

  --dry-run   mostra o que a ingestão baixaria e roda as análises sobre a base atual (não grava no banco)
  --commit    atualiza data/cvm_open.db com os dados abertos da CVM e roda as análises
  --portais   também coleta os relatórios mensais e as atas nos portais das securitizadoras (Opea, Eco, Vert,
              Leverage, Bari, Canal; com --commit grava só em data/ e reports/). A Opea leva horas (~10 s por emissão).
              Falha de um portal não interrompe a rotina: fica registrada e as análises seguem com o último relatório.

Etapas: ingestão (só com --commit), triagem e ranking, eventos do mês, universo por ISIN e candidatos a lote,
exposição por devedor, placar por securitizadora, sinais das DFs, e sobre os ativos do catálogo (só leitura de
data/cri_cra.db): Termo × CVM, assuntos de assembleias, fichas contratuais, garantias e covenants, alertas por ativo e
base de covenants (junta os relatórios das securitizadoras), fichas por ativo; por último o painel HTML
(reports/painel_mercado.html). Para a primeira etapa que falhar e devolve o código dela.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSES = [
    "run_market_checks.py",
    "run_market_events.py",
    "build_market_universe.py",
    "run_debtor_exposure.py",
    "run_securitizadora_scorecard.py",
    "run_dfin_checks.py",
    "run_termo_vs_cvm.py",
    "run_assembly_topics.py",
    "build_contract_sheets.py",
    "build_guarantees_covenants.py",
    "build_alertas_por_ativo.py",
    "build_covenants_mensais.py",
    "build_asset_dossiers.py",
    "build_credit_watchlist.py",
    "build_market_dashboard.py",
]
PORTALS = [
    "collect_opea_reports.py",
    "collect_eco_reports.py",
    "collect_vert_reports.py",
    "collect_leverage_reports.py",
    "collect_bari_reports.py",
    "collect_canal_reports.py",
    "collect_portal_atas.py",
]


def run(script: str, *extra: str) -> int:
    started = time.perf_counter()
    result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / script), *extra],
                            capture_output=True, text=True, encoding="utf-8")
    print(f"[{'ok' if result.returncode == 0 else 'FALHOU'}] {script} ({time.perf_counter() - started:.0f} s)")
    if result.returncode != 0:
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    parser.add_argument("--portais", action="store_true")
    args = parser.parse_args()
    code = run("ingest_cvm_open_data.py", "--commit" if args.commit else "--dry-run")
    if code:
        return code
    code = run("ingest_cvm_dfin.py", "--commit" if args.commit else "--dry-run")
    if code:
        return code
    for script in PORTALS if args.portais else []:
        if not (ROOT / "scripts" / script).is_file():
            print(f"[pulado] {script} (não existe)")
            continue
        if run(script, "--commit" if args.commit else "--dry-run"):
            print(f"[segue] {script} falhou; as análises usam o último relatório gerado")
    for script in ANALYSES:
        if script == "run_dfin_checks.py" and not (ROOT / "data" / "cvm_dfin.db").is_file():
            print("[pulado] run_dfin_checks.py (data/cvm_dfin.db ainda não carregado)")
            continue
        code = run(script)
        if code:
            return code
    print("Painel: reports/painel_mercado.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
