"""Mapa das series de FIDC: senior, mezanino ou subordinada (decisao 8 de Fundos, FU6.2).

mapping: as regras do quota_class_map (migration 006) e a classificacao de
um rotulo de serie. A regra casa com o rotulo NORMALIZADO (a mesma forma de
quota_series.series_label_key: sem acento, minusculo, sem '|' e com os
espacos colapsados); o rotulo original nunca e alterado e continua nas
observacoes. Entre as regras que casam, vence a mais especifica; rotulo sem
regra fica "ausente (rotulo nao mapeado)", nunca um palpite.

review: o relatorio de revisao (so contagens e rotulos normalizados de
serie) e a revisao de uma regra por uma pessoa, identificada por um papel
(nunca pelo nome), com registro no audit_log.

report: as linhas do relatorio de revisao.
"""
