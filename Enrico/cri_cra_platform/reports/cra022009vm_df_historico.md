# Série histórica das DFs do Patrimônio Separado: CRA022009VM

Gerado por `scripts/export_df_history.py` a partir dos fatos reportados aprovados e pendentes (pendentes marcados com *); valores em milhares de reais, como publicados. Nomes equivalentes agrupados por `config/fact_aliases.json`. Coluna de confronto: Informe Mensal vigente da mesma competência, tolerância de 1 mil.

| Indicador | 2023-03-31 | 2024-03-31 | 2025-03-31 | 2026-03-31 |
|---|---|---|---|---|
| total_ativo | 104657* ? |  | 72994* ≠ |  |
| direitos_creditorios_total | 104393 ? | 103724 ✓ | 72907 ✓ | 48925 ≠ |
| direitos_creditorios_circulante | 4393* | 3724* | 32909* |  |
| direitos_creditorios_nao_circulante | 100000* |  | 39998* |  |
| saldo_certificados_total | 104393 ? | 103724 ✓ | 72907 ✓ |  |
| vencidos_nao_pagos |  |  |  | 7089 ≠ |
| caixa_equivalentes | 264 ? | 345* ≠ | 87 ≠ |  |
| fundo_despesas | 83 | 148 | 87 |  |
| fundo_retencao | 181* | 197 | 0* |  |
| juros_apropriados_direitos_creditorios | 8218 | 18177 | 14994 |  |
| juros_pagos_titulares | 3825 | 18846 | 15811 |  |
| recebimentos_direitos_creditorios | 3825 | 18846 | 45811 |  |
| amortizacao_principal |  |  | 30000* |  |

✓ confere com o Informe; ≠ diverge do Informe; ? não comparado (escala do Informe suspeita). Detalhe no CSV.

## Divergências com o Informe (5)

- 2024-03-31 caixa_equivalentes: DF 345 mil (doc 698040 p.16) × Informe 0 reais (diferença -345.000 mil) — fato pendente
- 2025-03-31 total_ativo: DF 72994 mil (doc 935390 p.7) × Informe 72907376.5 reais (diferença -86.624 mil) — fato pendente
- 2025-03-31 caixa_equivalentes: DF 87 mil (doc 935390 p.16) × Informe 0 reais (diferença -87.000 mil)
- 2026-03-31 direitos_creditorios_total: DF 48925 mil (doc 1232148 p.17) × Informe 49148052.72 reais (diferença 223.053 mil)
- 2026-03-31 vencidos_nao_pagos: DF 7089 mil (doc 1232148 p.17) × Informe 0 reais (diferença -7089.000 mil)
