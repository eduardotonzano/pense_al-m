# Triagem do mercado de CRI e CRA

Fonte: Informe Mensal dos dados abertos da CVM (`data/cvm_open.db`). Só leitura. **Candidatos a revisão, não conclusões**:
o dado é o do próprio Informe e erro de preenchimento vem junto.

## CRA (competência de referência 2026-08-01)

- 1263 emissões desde 2019; 635 com informe recente; 385 com algum sinal.
- Saldo das séries com informe recente: R$ 166,626,859,729.

| Sinal | Emissões com o sinal |
|---|---|
| `em_atraso` | 44 |
| `vencido_com_saldo_adimplente` | 34 |
| `informe_defasado` | 114 |
| `vencimento_fora_mes_base` | 116 |
| `isin_repetido` | 28 |
| `serie_sem_isin` | 2 |
| `identificador_duplicado` | 107 |
| `isin_invalido` | 14 |
| `saldo_incompativel` | 5 |

Top 30 por pontuação e saldo:

| Certificado | Séries | Saldo (R$ mi) | Última competência | Pontos | Sinais |
|---|---|---|---|---|---|
| BRAPCSCRA1Y9 | 6 | 1,669.0 | 2026-08 | 10 | vencimento_fora_mes_base×5, saldo_incompativel×2, em_atraso×2 |
| CRA02200ENV | 4 | 0.0 | 2026-09 | 9 | vencido_com_saldo_adimplente×1, isin_repetido×3, isin_invalido×1 |
| BRAPCSCRA0M6 | 4 | 2,779.2 | 2026-08 | 8 | identificador_duplicado×4, em_atraso×2, vencimento_fora_mes_base×2 |
| BRAPCSCRA0U9 | 2 | 1,552.7 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRAPCSCRA0T1 | 2 | 1,550.4 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRECOACRABX0 | 1 | 45.0 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRIMWLCRA4Q7 | 3 | 28.9 | 2026-08 | 7 | vencimento_fora_mes_base×3, isin_invalido×1, isin_repetido×1 |
| BRRBRACRA5K9 | 2 | 0.0 | 2026-09 | 7 | vencido_com_saldo_adimplente×1, isin_repetido×1 |
| BRIMWLCRA3B1 | 2 | 0.0 | 2026-08 | 7 | em_atraso×2, vencimento_fora_mes_base×2 |
| CRA023000B5 | 2 | 0.0 | 2025-08 | 7 | isin_repetido×1, identificador_duplicado×1, informe_defasado×1 |
| CRA0230040I | 3 | 0.0 | 2025-08 | 7 | isin_repetido×1, identificador_duplicado×2, informe_defasado×1 |
| CRA02300IZD | 3 | 0.0 | 2025-07 | 7 | isin_repetido×1, identificador_duplicado×2, informe_defasado×1 |
| X | 3 | 0.0 | 2021-09 | 7 | identificador_duplicado×2, informe_defasado×3, isin_repetido×1 |
| CRA017007KG | 2 | 1,732.7 | 2026-08 | 6 | vencido_com_saldo_adimplente×2, isin_invalido×2 |
| BRIMWLCRA1R1 | 3 | 164.9 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×2 |
| BRIMWLCRA1C3 | 2 | 114.9 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×2 |
| BRCASCCRA0A6 | 1 | 96.0 | 2026-08 | 6 | em_atraso×1, identificador_duplicado×1 |
| BRIMWLCRA0U7 | 2 | 95.4 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×1 |
| BRIMWLCRA093 | 2 | 64.6 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×1 |
| BRCASCCRA0K5 | 1 | 52.6 | 2026-08 | 6 | em_atraso×1, identificador_duplicado×1 |
| BRIMWLCRA7Y4 | 2 | 40.3 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×2 |
| CRA0220020E | 2 | 0.0 | 2026-08 | 6 | serie_sem_isin×1, em_atraso×1 |
| CRA0220020D | 2 | 0.0 | 2026-08 | 6 | serie_sem_isin×1, em_atraso×1 |
| BRRBRACRA1M4 | 3 | 0.0 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, isin_invalido×1 |
| BRGAFLCRA0D0 | 1 | 0.0 | 2024-06 | 6 | isin_repetido×1, informe_defasado×1 |
| BROCTSCRA2W1 | 2 | 0.0 | 2025-12 | 6 | isin_repetido×1, informe_defasado×1 |
| CRA022006BV | 7 | 0.0 | 2025-08 | 6 | informe_defasado×3, isin_repetido×1 |
| CRA0220073L | 5 | 0.0 | 2024-12 | 6 | informe_defasado×2, isin_repetido×1 |
| CRA0220073M | 2 | 0.0 | 2023-11 | 6 | informe_defasado×1, isin_repetido×1 |
| CRA0220073N | 4 | 0.0 | 2023-11 | 6 | informe_defasado×3, isin_repetido×1 |

## CRI (competência de referência 2026-08-01)

- 4039 emissões desde 2019; 2402 com informe recente; 1203 com algum sinal.
- Saldo das séries com informe recente: R$ 183,368,014,642.

| Sinal | Emissões com o sinal |
|---|---|
| `em_atraso` | 203 |
| `vencido_com_saldo_adimplente` | 96 |
| `informe_defasado` | 362 |
| `vencimento_fora_mes_base` | 104 |
| `isin_repetido` | 161 |
| `serie_sem_isin` | 74 |
| `identificador_duplicado` | 464 |
| `isin_invalido` | 118 |
| `saldo_incompativel` | 36 |

Top 30 por pontuação e saldo:

| Certificado | Séries | Saldo (R$ mi) | Última competência | Pontos | Sinais |
|---|---|---|---|---|---|
| 22J1379218 | 2 | 24.6 | 2026-08 | 12 | vencido_com_saldo_adimplente×2, vencimento_fora_mes_base×1, isin_invalido×2, identificador_duplicado×1, isin_repetido×1 |
| 22J1381567 | 2 | 21.6 | 2026-08 | 12 | vencido_com_saldo_adimplente×2, vencimento_fora_mes_base×1, isin_invalido×2, identificador_duplicado×1, isin_repetido×1 |
| 22J1381764 | 2 | 17.2 | 2026-08 | 12 | vencido_com_saldo_adimplente×2, vencimento_fora_mes_base×1, isin_invalido×2, identificador_duplicado×1, isin_repetido×1 |
| BRRBRACRI8T6 | 3 | 0.0 | 2026-09 | 12 | vencido_com_saldo_adimplente×1, isin_invalido×1, identificador_duplicado×3, em_atraso×2 |
| 22E1273339 | 6 | 182.9 | 2026-08 | 11 | serie_sem_isin×2, isin_invalido×2, isin_repetido×1, vencido_com_saldo_adimplente×1, identificador_duplicado×2 |
| 23A1772203 | 2 | 32.5 | 2026-08 | 11 | isin_invalido×2, isin_repetido×1, em_atraso×1, identificador_duplicado×1 |
| 22C1024589 | 3 | 16.0 | 2026-08 | 11 | serie_sem_isin×1, isin_invalido×1, isin_repetido×1, em_atraso×1 |
| BRAPCSCRIJL8 | 5 | 67.9 | 2026-08 | 10 | em_atraso×2, serie_sem_isin×2, vencido_com_saldo_adimplente×1 |
| BRRBCSCRI2P4 | 4 | 0.0 | 2026-09 | 10 | vencido_com_saldo_adimplente×1, identificador_duplicado×4, em_atraso×2 |
| 11C0035926 | 6 | 714.6 | 2026-08 | 9 | serie_sem_isin×4, em_atraso×2, isin_invalido×2, identificador_duplicado×2 |
| 16K2085767 | 2 | 18.0 | 2026-08 | 9 | serie_sem_isin×1, em_atraso×1, isin_invalido×1, identificador_duplicado×1 |
| BRCBSCCRI2O4 | 2 | 0.1 | 2026-08 | 9 | vencido_com_saldo_adimplente×1, em_atraso×1 |
| 13C0017641 | 2 | 0.0 | 2026-08 | 9 | serie_sem_isin×1, em_atraso×1, saldo_incompativel×1 |
| 13A0016692 | 2 | 50.5 | 2026-08 | 8 | em_atraso×1, serie_sem_isin×1, isin_invalido×1 |
| BRCASCCRI0D2 | 3 | 28.2 | 2026-08 | 8 | em_atraso×3, vencimento_fora_mes_base×3, identificador_duplicado×3 |
| BRTSSACRI0K0 | 3 | 27.6 | 2026-08 | 8 | em_atraso×2, serie_sem_isin×1, isin_invalido×1 |
| 24E3191695 | 1 | 8.4 | 2026-08 | 8 | em_atraso×1, isin_repetido×1 |
| 11L0015528 | 3 | 1.0 | 2026-08 | 8 | em_atraso×3, serie_sem_isin×1, isin_invalido×1 |
| 21K0870291 | 2 | 0.0 | 2026-08 | 8 | serie_sem_isin×1, em_atraso×1, vencimento_fora_mes_base×1 |
| BRCASCCRI4O1 | 1 | 0.0 | 2026-08 | 8 | em_atraso×1, saldo_incompativel×1 |
| BRAPCSCRIQK5 | 5 | 317.1 | 2026-08 | 7 | vencimento_fora_mes_base×1, saldo_incompativel×2, isin_invalido×2 |
| BRAPCSCRIIE5 | 3 | 130.6 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×2 |
| BRHBSCCRI452 | 12 | 103.3 | 2026-09 | 7 | vencido_com_saldo_adimplente×10, isin_repetido×2 |
| 23D1293668 | 4 | 28.1 | 2026-08 | 7 | isin_invalido×2, isin_repetido×1, identificador_duplicado×1, serie_sem_isin×1 |
| 16B0742429 | 7 | 14.9 | 2026-08 | 7 | serie_sem_isin×3, isin_invalido×3, vencido_com_saldo_adimplente×2 |
| BRIMWLCRI0G8 | 2 | 12.9 | 2026-08 | 7 | em_atraso×2, vencimento_fora_mes_base×2 |
| BRAPCSCRICG3 | 2 | 11.1 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| 12E0031990 | 2 | 9.9 | 2026-08 | 7 | vencido_com_saldo_adimplente×2, serie_sem_isin×1, isin_invalido×1 |
| 14J0105981 | 3 | 9.4 | 2026-08 | 7 | serie_sem_isin×1, isin_invalido×2, vencido_com_saldo_adimplente×1 |
| 13H0072616 | 4 | 7.2 | 2026-08 | 7 | serie_sem_isin×2, isin_invalido×2, vencido_com_saldo_adimplente×1 |

## Pesos

`em_atraso` = 5, `vencido_com_saldo_adimplente` = 4, `informe_defasado` = 3, `vencimento_fora_mes_base` = 2, `isin_repetido` = 3, `serie_sem_isin` = 1, `identificador_duplicado` = 1, `isin_invalido` = 2, `saldo_incompativel` = 3

Pesos são uma proposta para ordenar a fila de aprofundamento; ajuste conforme o que importar mais.
