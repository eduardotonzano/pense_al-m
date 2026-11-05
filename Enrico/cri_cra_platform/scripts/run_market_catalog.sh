#!/usr/bin/env bash
# Catálogo do Fundos.NET para o mercado inteiro, em partes de 100 ativos (data/lotes_mercado/parte_NN.csv,
# geradas de config/ativos_mercado.csv). Cada parte grava no banco (idempotente: rodar de novo não duplica)
# e deixa o log em logs/catalogo_mercado_parte_NN.log. Uso: scripts/run_market_catalog.sh [primeira] [última]
set -u
cd "$(dirname "$0")/.."
first=${1:-1}
last=${2:-30}
for n in $(seq -f "%02g" "$first" "$last"); do
  part="data/lotes_mercado/parte_${n}.csv"
  [ -f "$part" ] || continue
  log="logs/catalogo_mercado_parte_${n}.log"
  echo "$(date -u +%FT%TZ) parte ${n} início" >> logs/catalogo_mercado.log
  python scripts/run_document_catalog.py --config-path "$part" > "$log" 2>&1
  echo "$(date -u +%FT%TZ) parte ${n} fim (saída $?)" >> logs/catalogo_mercado.log
done
