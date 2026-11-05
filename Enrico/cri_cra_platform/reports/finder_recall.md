# Recall do localizador de campos

Parâmetros aprovados do Termo comparados com as páginas sugeridas por `field_topics.json` (tolerância de 1 página). Só leitura.

**Geral:** 177/199 (89%)

| Ativo | Achados |
|---|---|
| 24G2100031 | 86/94 (91%) |
| CRA022009VM | 14/14 (100%) |
| CRA02500C1D | 77/91 (85%) |

| Campo | Achados | Páginas sugeridas (média) | Páginas do Termo (média) |
|---|---|---|---|
| `identificacao.numero_emissao` | 0/1 (0%) | 14 | 175 |
| `identificacao.lastro` | 1/5 (20%) | 23 | 147 |
| `remuneracao.primeira_data_pagamento` | 2/7 (29%) | 18 | 182 |
| `vencimento_antecipado.pagamento_e_quorum` | 2/5 (40%) | 3 | 180 |
| `identificacao.agente_fiduciario` | 2/4 (50%) | 2 | 177 |
| `vencimento_antecipado.limites_e_prazos` | 9/13 (69%) | 3 | 179 |
| `identificacao.classe_serie` | 6/7 (86%) | 41 | 182 |
| `emissao.valor_total` | 7/8 (88%) | 5 | 176 |
| `emissao.data_vencimento` | 7/8 (88%) | 22 | 180 |
| `garantias.razao_minima` | 8/8 (100%) | 6 | 151 |
| `garantias.descricao` | 9/9 (100%) | 54 | 172 |
| `garantias.fundo_despesas` | 7/7 (100%) | 18 | 168 |
| `garantias.fundo_reserva_retencao` | 2/2 (100%) | 4 | 156 |
| `remuneracao.taxa` | 16/16 (100%) | 22 | 158 |
| `emissao.valor_nominal_unitario` | 3/3 (100%) | 30 | 165 |
| `vencimento_antecipado.hipoteses` | 12/12 (100%) | 14 | 174 |
| `covenants.indices_financeiros` | 8/8 (100%) | 4 | 174 |
| `emissao.quantidade_titulos` | 7/7 (100%) | 8 | 182 |
| `emissao.data_emissao` | 2/2 (100%) | 22 | 179 |
| `remuneracao.atualizacao_monetaria` | 2/2 (100%) | 8 | 179 |
| `remuneracao.periodicidade` | 2/2 (100%) | 20 | 179 |
| `remuneracao.amortizacao` | 6/6 (100%) | 2 | 182 |
| `identificacao.devedor` | 2/2 (100%) | 4 | 179 |
| `governanca.ordem_pagamentos` | 5/5 (100%) | 6 | 181 |
| `resgate.facultativo` | 20/20 (100%) | 27 | 139 |
| `identificacao.isin` | 3/3 (100%) | 1 | 180 |
| `obrigacoes.rating` | 3/3 (100%) | 8 | 178 |
| `obrigacoes.dfs_e_relatorios` | 10/10 (100%) | 21 | 177 |
| `vencimento_antecipado.liquidacao_ps` | 2/2 (100%) | 5 | 179 |
| `identificacao.numero_series` | 1/1 (100%) | 14 | 175 |
| `remuneracao.encargos_moratorios` | 1/1 (100%) | 10 | 175 |
| `garantias.liberacao` | 3/3 (100%) | 5 | 175 |
| `governanca.quorum_assembleia` | 6/6 (100%) | 38 | 175 |
| `obrigacoes.destinacao_recursos` | 1/1 (100%) | 9 | 175 |

## Não achados (22)

| Ativo | Campo | Parâmetro | Página do trecho |
|---|---|---|---|
| CRA02500C1D | `emissao.valor_total` | `valor_total_emissao` | 54 |
| CRA02500C1D | `remuneracao.primeira_data_pagamento` | `juros_devidos_2026_06_17_serie_1` | 153 |
| CRA02500C1D | `remuneracao.primeira_data_pagamento` | `juros_devidos_2026_06_17_serie_2` | 153 |
| CRA02500C1D | `remuneracao.primeira_data_pagamento` | `juros_devidos_2026_06_17_serie_3` | 154 |
| CRA02500C1D | `remuneracao.primeira_data_pagamento` | `juros_devidos_2026_06_17_serie_4` | 154 |
| CRA02500C1D | `remuneracao.primeira_data_pagamento` | `juros_devidos_2026_06_17_serie_5` | 155 |
| CRA02500C1D | `identificacao.lastro` | `garantia_lastro_series_1_2_3` | 69 |
| CRA02500C1D | `identificacao.lastro` | `garantia_lastro_series_4_5` | 69 |
| CRA02500C1D | `vencimento_antecipado.pagamento_e_quorum` | `ordem_imputacao_vencimento_antecipado_parte_1` | 96 |
| CRA02500C1D | `vencimento_antecipado.pagamento_e_quorum` | `ordem_imputacao_vencimento_antecipado_parte_2` | 97 |
| CRA02500C1D | `vencimento_antecipado.pagamento_e_quorum` | `va_quorum_nao_declaracao` | 96 |
| CRA02500C1D | `vencimento_antecipado.limites_e_prazos` | `obrigacao_comunicacao_evento_va` | 97 |
| CRA02500C1D | `identificacao.agente_fiduciario` | `taxa_administracao` | 99 |
| CRA02500C1D | `vencimento_antecipado.limites_e_prazos` | `liquidacao_ps_inadimplemento_pecuniario_emissora_prazo` | 101 |
| 24G2100031 | `identificacao.numero_emissao` | `numero_emissao` | 17 |
| 24G2100031 | `identificacao.lastro` | `lastro_debentures_data_vencimento` | 98 |
| 24G2100031 | `identificacao.classe_serie` | `subordinacao` | 21 |
| 24G2100031 | `identificacao.lastro` | `lastro_debentures_spread` | 13 |
| 24G2100031 | `emissao.data_vencimento` | `ultima_parcela_amortizacao` | 108 |
| 24G2100031 | `vencimento_antecipado.limites_e_prazos` | `va_automatico_inadimplemento_pecuniario_cura` | 44 |
| 24G2100031 | `vencimento_antecipado.limites_e_prazos` | `obrigacao_comunicacao_evento_va` | 52 |
| 24G2100031 | `identificacao.agente_fiduciario` | `remuneracao_agente_fiduciario` | 71 |
