"""Rotina mensal do mercado de CRA/CRI num comando só.

  --dry-run   mostra o que a ingestão baixaria e roda as análises sobre a base atual (não grava no banco)
  --commit    atualiza data/cvm_open.db com os dados abertos da CVM e roda as análises

Etapas: ingestão (só com --commit), triagem e ranking, eventos do mês, universo por ISIN e candidatos a lote,
exposição por devedor, placar por securitizadora e painel HTML (reports/painel_mercado.html).
Para a primeira etapa que falhar e devolve o código dela.
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
    "build_market_dashboard.py",
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
    args = parser.parse_args()
    code = run("ingest_cvm_open_data.py", "--commit" if args.commit else "--dry-run")
    if code:
        return code
    code = run("ingest_cvm_dfin.py", "--commit" if args.commit else "--dry-run")
    if code:
        return code
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
