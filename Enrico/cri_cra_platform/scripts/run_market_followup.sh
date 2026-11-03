#!/usr/bin/env bash
# Depois do catálogo do mercado (run_market_catalog.sh): repescagem das falhas e download dos documentos
# importantes dos ativos com sinal de triagem. Catálogo e fila não rodam juntos: o catálogo segura o banco
# durante a sessão do navegador de cada ativo. Log em logs/mercado_followup.log.
# Uso: scripts/run_market_followup.sh [parte final esperada do catálogo, padrão 30]
set -u
cd "$(dirname "$0")/.."
last=${1:-30}
log=logs/mercado_followup.log
say() { echo "$(date -u +%FT%TZ) $*" >> "$log"; }

say "aguardando o fim da parte ${last} do catálogo"
until grep -q "parte ${last} fim" logs/catalogo_mercado.log 2>/dev/null; do sleep 60; done

say "repescagem: montando a lista"
python scripts/build_catalog_retry.py >> "$log" 2>&1
if [ -f data/lotes_mercado/repescagem.csv ]; then
  say "repescagem: catálogo"
  python scripts/run_document_catalog.py --config-path data/lotes_mercado/repescagem.csv > logs/catalogo_mercado_repescagem.log 2>&1
  say "repescagem: fim (saída $?)"
fi

only=$(python -c "import csv; print(','.join(r['codigo_cetip'] for r in csv.DictReader(open('config/ativos_mercado.csv', encoding='utf-8-sig')) if int(r['score']) > 0))")
cats=(--category "Termo de Securitização" --category Aditamento --category "Fato Relevante" --category "Ata/Edital" --category Outro --category "Relatório Agente Fiduciário")
say "fila: prévia"
python scripts/run_download_queue.py --enqueue --dry-run --since 2025-01-01 --only "$only" "${cats[@]}" >> "$log" 2>&1
say "fila: enfileirar"
python scripts/run_download_queue.py --enqueue --commit --since 2025-01-01 --only "$only" "${cats[@]}" >> "$log" 2>&1
say "fila: download"
python scripts/run_download_queue.py --run --commit --chunk-size 10 --max-duration-minutes 900 >> logs/mercado_download.log 2>&1
say "fila: fim (saída $?)"
