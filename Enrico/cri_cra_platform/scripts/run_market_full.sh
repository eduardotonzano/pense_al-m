#!/usr/bin/env bash
# Terceira etapa do mercado inteiro, depois de run_market_followup.sh (fila dos prioritários):
#   1. texto e OCR dos ativos prioritários (score > 0; mantêm o PDF);
#   2. para cada parte de data/lotes_mercado/, os ativos sem sinal (score 0): enfileira (Termo, aditamento e fato
#      relevante completos; atas, comunicados e relatórios do AF desde 2025), baixa, extrai texto e OCR e remove o
#      PDF cujo texto de todas as páginas está no banco (prune_document_files.py);
#   3. rotina mensal.
# Log em logs/mercado_full.log. Uso: scripts/run_market_full.sh [primeira parte] [última parte]
set -u
cd "$(dirname "$0")/.."
first=${1:-1}
last=${2:-30}
log=logs/mercado_full.log
say() { echo "$(date -u +%FT%TZ) $*" >> "$log"; }
cats=(--category "Termo de Securitização" --category Aditamento --category "Fato Relevante" --category "Ata/Edital" --category Outro --category "Relatório Agente Fiduciário")

say "aguardando o fim da fila dos prioritários"
until grep -q "fila: fim" logs/mercado_followup.log 2>/dev/null; do sleep 60; done

say "prioritários: texto e OCR"
python scripts/process_document_text.py --list config/ativos_mercado.csv --score positive >> "$log" 2>&1

for n in $(seq -f "%02g" "$first" "$last"); do
  part="data/lotes_mercado/parte_${n}.csv"
  [ -f "$part" ] || continue
  only=$(python -c "import csv,sys; print(','.join(r['codigo_cetip'] for r in csv.DictReader(open(sys.argv[1], encoding='utf-8')) if int(r['score'] or 0) == 0))" "$part")
  [ -n "$only" ] || { say "parte ${n}: sem ativos sem sinal"; continue; }
  say "parte ${n}: enfileirar"
  python scripts/run_download_queue.py --enqueue --commit --since 2025-01-01 --only "$only" "${cats[@]}" >> "$log" 2>&1
  say "parte ${n}: download"
  python scripts/run_download_queue.py --run --commit --chunk-size 10 >> logs/mercado_download.log 2>&1
  status=$?
  say "parte ${n}: download fim (saída ${status})"
  say "parte ${n}: texto e OCR"
  python scripts/process_document_text.py --list "$part" --score zero >> "$log" 2>&1
  say "parte ${n}: remoção dos PDFs com texto completo"
  python scripts/prune_document_files.py --commit >> "$log" 2>&1
  if grep -q "bloqueio detectado" logs/mercado_download.log; then
    say "parte ${n}: bloqueio do Fundos.NET (HTTP 403); parando"
    exit 3
  fi
done

say "rotina mensal"
python scripts/run_monthly_market.py --commit >> "$log" 2>&1
say "fim"
