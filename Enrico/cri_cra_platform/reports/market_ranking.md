# Triagem do mercado de CRI e CRA

Fonte: Informe Mensal dos dados abertos da CVM (`data/cvm_open.db`). Só leitura. **Candidatos a revisão, não conclusões**:
o dado é o do próprio Informe e erro de preenchimento vem junto.

## CRA (competência de referência 2026-08-01)

- 1263 emissões desde 2019; 635 com informe recente; 378 com algum sinal.
- Saldo das séries com informe recente: R$ 508,113,793,629.

| Sinal | Emissões com o sinal |
|---|---|
| `em_atraso` | 44 |
| `vencido_com_saldo_adimplente` | 34 |
| `informe_defasado` | 116 |
| `vencimento_fora_mes_base` | 116 |
| `isin_repetido` | 28 |
| `serie_sem_isin` | 2 |
| `identificador_duplicado` | 107 |

Top 30 por pontuação e saldo:

| Certificado | Séries | Saldo (R$ mi) | Última competência | Pontos | Sinais |
|---|---|---|---|---|---|
| BRAPCSCRA0M6 | 4 | 2,779.2 | 2026-08 | 8 | identificador_duplicado×4, em_atraso×2, vencimento_fora_mes_base×2 |
| BRAPCSCRA1Y9 | 6 | 2,539.0 | 2026-08 | 7 | vencimento_fora_mes_base×5, em_atraso×2 |
| BRAPCSCRA0U9 | 2 | 1,552.7 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRAPCSCRA0T1 | 2 | 1,550.4 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRECOACRABX0 | 1 | 45.0 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRRBRACRA5K9 | 2 | 0.0 | 2026-09 | 7 | vencido_com_saldo_adimplente×1, isin_repetido×1 |
| CRA02200ENV | 4 | 0.0 | 2026-09 | 7 | vencido_com_saldo_adimplente×1, isin_repetido×3 |
| BRIMWLCRA3B1 | 2 | 0.0 | 2026-08 | 7 | em_atraso×2, vencimento_fora_mes_base×2 |
| CRA023000B5 | 2 | 0.0 | 2025-08 | 7 | isin_repetido×1, identificador_duplicado×1, informe_defasado×1 |
| CRA0230040I | 3 | 0.0 | 2025-08 | 7 | isin_repetido×1, identificador_duplicado×2, informe_defasado×1 |
| CRA02300IZD | 3 | 0.0 | 2025-07 | 7 | isin_repetido×1, identificador_duplicado×2, informe_defasado×1 |
| X | 3 | 0.0 | 2021-09 | 7 | identificador_duplicado×2, informe_defasado×3, isin_repetido×1 |
| BRIMWLCRA1R1 | 3 | 164.9 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×2 |
| BRIMWLCRA1C3 | 2 | 114.9 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×2 |
| BRCASCCRA0A6 | 1 | 96.0 | 2026-08 | 6 | em_atraso×1, identificador_duplicado×1 |
| BRIMWLCRA0U7 | 2 | 95.4 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×1 |
| BRIMWLCRA093 | 2 | 64.6 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×1 |
| BRCASCCRA0K5 | 1 | 52.6 | 2026-08 | 6 | em_atraso×1, identificador_duplicado×1 |
| BRIMWLCRA7Y4 | 2 | 40.3 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×2 |
| CRA0220020E | 2 | 0.0 | 2026-08 | 6 | serie_sem_isin×1, em_atraso×1 |
| CRA0220020D | 2 | 0.0 | 2026-08 | 6 | serie_sem_isin×1, em_atraso×1 |
| BRGAFLCRA0D0 | 1 | 0.0 | 2024-06 | 6 | isin_repetido×1, informe_defasado×1 |
| BROCTSCRA2W1 | 2 | 0.0 | 2025-12 | 6 | isin_repetido×1, informe_defasado×1 |
| CRA022006BV | 7 | 0.0 | 2025-08 | 6 | informe_defasado×3, isin_repetido×1 |
| CRA0220073L | 5 | 0.0 | 2024-12 | 6 | informe_defasado×2, isin_repetido×1 |
| CRA0220073M | 2 | 0.0 | 2023-11 | 6 | informe_defasado×1, isin_repetido×1 |
| CRA0220073N | 4 | 0.0 | 2023-11 | 6 | informe_defasado×3, isin_repetido×1 |
| BRAPCSCRA1B7 | 2 | 2,414.6 | 2026-08 | 5 | em_atraso×2 |
| BRVERTCRA344 | 1 | 506.5 | 2026-08 | 5 | em_atraso×1 |
| BRECOACRAF93 | 2 | 421.1 | 2026-08 | 5 | em_atraso×2 |

## CRI (competência de referência 2026-08-01)

- 4039 emissões desde 2019; 2402 com informe recente; 1164 com algum sinal.
- Saldo das séries com informe recente: R$ 187,864,550,303.

| Sinal | Emissões com o sinal |
|---|---|
| `em_atraso` | 203 |
| `vencido_com_saldo_adimplente` | 96 |
| `informe_defasado` | 364 |
| `vencimento_fora_mes_base` | 104 |
| `isin_repetido` | 161 |
| `serie_sem_isin` | 74 |
| `identificador_duplicado` | 464 |

Top 30 por pontuação e saldo:

| Certificado | Séries | Saldo (R$ mi) | Última competência | Pontos | Sinais |
|---|---|---|---|---|---|
| BRAPCSCRIJL8 | 5 | 67.9 | 2026-08 | 10 | em_atraso×2, serie_sem_isin×2, vencido_com_saldo_adimplente×1 |
| 22J1379218 | 2 | 24.6 | 2026-08 | 10 | vencido_com_saldo_adimplente×2, vencimento_fora_mes_base×1, identificador_duplicado×1, isin_repetido×1 |
| 22J1381567 | 2 | 21.6 | 2026-08 | 10 | vencido_com_saldo_adimplente×2, vencimento_fora_mes_base×1, identificador_duplicado×1, isin_repetido×1 |
| 22J1381764 | 2 | 17.2 | 2026-08 | 10 | vencido_com_saldo_adimplente×2, vencimento_fora_mes_base×1, identificador_duplicado×1, isin_repetido×1 |
| BRRBRACRI8T6 | 3 | 0.0 | 2026-09 | 10 | vencido_com_saldo_adimplente×1, identificador_duplicado×3, em_atraso×2 |
| BRRBCSCRI2P4 | 4 | 0.0 | 2026-09 | 10 | vencido_com_saldo_adimplente×1, identificador_duplicado×4, em_atraso×2 |
| 22E1273339 | 6 | 182.9 | 2026-08 | 9 | serie_sem_isin×2, isin_repetido×1, vencido_com_saldo_adimplente×1, identificador_duplicado×2 |
| 23A1772203 | 2 | 32.5 | 2026-08 | 9 | isin_repetido×1, em_atraso×1, identificador_duplicado×1 |
| 22C1024589 | 3 | 16.0 | 2026-08 | 9 | serie_sem_isin×1, isin_repetido×1, em_atraso×1 |
| BRCBSCCRI2O4 | 2 | 0.1 | 2026-08 | 9 | vencido_com_saldo_adimplente×1, em_atraso×1 |
| BRCASCCRI0D2 | 3 | 28.2 | 2026-08 | 8 | em_atraso×3, vencimento_fora_mes_base×3, identificador_duplicado×3 |
| 24E3191695 | 1 | 8.4 | 2026-08 | 8 | em_atraso×1, isin_repetido×1 |
| 21K0870291 | 2 | 0.0 | 2026-08 | 8 | serie_sem_isin×1, em_atraso×1, vencimento_fora_mes_base×1 |
| 11C0035926 | 6 | 714.6 | 2026-08 | 7 | serie_sem_isin×4, em_atraso×2, identificador_duplicado×2 |
| BRAPCSCRIIE5 | 3 | 130.6 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×2 |
| BRHBSCCRI452 | 12 | 103.3 | 2026-09 | 7 | vencido_com_saldo_adimplente×10, isin_repetido×2 |
| 16K2085767 | 2 | 18.0 | 2026-08 | 7 | serie_sem_isin×1, em_atraso×1, identificador_duplicado×1 |
| BRIMWLCRI0G8 | 2 | 12.9 | 2026-08 | 7 | em_atraso×2, vencimento_fora_mes_base×2 |
| BRAPCSCRICG3 | 2 | 11.1 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| 09H0003225 | 5 | 0.0 | 2026-02 | 7 | identificador_duplicado×2, isin_repetido×1, informe_defasado×1 |
| 12L0018386 | 5 | 0.0 | 2026-02 | 7 | identificador_duplicado×2, informe_defasado×3, isin_repetido×1 |
| 13J0119962 | 5 | 0.0 | 2026-02 | 7 | identificador_duplicado×2, informe_defasado×3, isin_repetido×1 |
| 14K0202980 | 3 | 0.0 | 2024-02 | 7 | isin_repetido×1, identificador_duplicado×1, informe_defasado×1 |
| 16D0718054 | 5 | 0.0 | 2026-02 | 7 | identificador_duplicado×2, informe_defasado×3, isin_repetido×1 |
| 19H0263644 | 5 | 0.0 | 2024-02 | 7 | identificador_duplicado×2, informe_defasado×2, isin_repetido×2 |
| 20E0929816 | 5 | 0.0 | 2024-02 | 7 | identificador_duplicado×1, informe_defasado×2, isin_repetido×2 |
| 21D0521612 | 6 | 0.0 | 2023-08 | 7 | identificador_duplicado×2, isin_repetido×2, informe_defasado×1 |
| 21F0929727 | 5 | 0.0 | 2023-08 | 7 | isin_repetido×2, identificador_duplicado×1, informe_defasado×1 |
| 22I1049939 | 3 | 0.0 | 2025-08 | 7 | isin_repetido×1, identificador_duplicado×2, informe_defasado×1 |
| 22J1019802 | 3 | 0.0 | 2025-08 | 7 | isin_repetido×1, identificador_duplicado×2, informe_defasado×2 |

## Pesos

`em_atraso` = 5, `vencido_com_saldo_adimplente` = 4, `informe_defasado` = 3, `vencimento_fora_mes_base` = 2, `isin_repetido` = 3, `serie_sem_isin` = 1, `identificador_duplicado` = 1

Pesos são uma proposta para ordenar a fila de aprofundamento; ajuste conforme o que importar mais.
