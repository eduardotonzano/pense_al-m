#!/usr/bin/env bash
# Atualização agendada dos dados da plataforma (Agendador de Tarefas do Windows chama este arquivo pelo Git Bash).
# Só leitura do banco: gera data/plataforma/ com scripts/build_plataforma.py. Log em logs/plataforma.log.
cd "$(dirname "$0")/.."
log=logs/plataforma.log
echo "$(date -u +%FT%TZ) início" >> "$log"
python -X utf8 scripts/build_plataforma.py >> "$log" 2>&1
echo "$(date -u +%FT%TZ) fim (saída $?)" >> "$log"
