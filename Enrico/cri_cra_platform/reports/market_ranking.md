# Triagem do mercado de CRI e CRA

Fonte: Informe Mensal dos dados abertos da CVM (`data/cvm_open.db`). Só leitura. **Candidatos a revisão, não conclusões**:
o dado é o do próprio Informe e erro de preenchimento vem junto.

## CRA (competência de referência 2026-08-01)

- 1195 emissões desde 2019; 628 com informe recente; 285 com algum sinal.
- Saldo das séries com informe recente: R$ 159,980,641,302.

| Sinal | Emissões com o sinal |
|---|---|
| `em_atraso` | 43 |
| `vencido_com_saldo_adimplente` | 34 |
| `informe_defasado` | 83 |
| `vencimento_fora_mes_base` | 116 |
| `isin_repetido` | 14 |
| `serie_sem_isin` | 3 |
| `identificador_duplicado` | 0 |
| `isin_invalido` | 23 |
| `saldo_incompativel` | 4 |

Top 30 por pontuação e saldo:

| Certificado | Séries | Saldo (R$ mi) | Última competência | Pontos | Sinais |
|---|---|---|---|---|---|
| CRA022006BV | 27 | 235.4 | 2026-08 | 17 | em_atraso×1, vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×8, serie_sem_isin×10, isin_invalido×1, isin_repetido×1 |
| CRA02200ENV | 4 | 0.0 | 2026-09 | 9 | vencido_com_saldo_adimplente×1, isin_repetido×3, isin_invalido×1 |
| BRAPCSCRA0M6 | 2 | 1,391.9 | 2026-08 | 7 | em_atraso×2, vencimento_fora_mes_base×2 |
| BRAPCSCRA1Y9 | 3 | 1,102.4 | 2026-08 | 7 | vencimento_fora_mes_base×3, em_atraso×2 |
| BRAPCSCRA0U9 | 1 | 1,061.1 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRAPCSCRA0T1 | 1 | 513.2 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRECOACRABX0 | 1 | 45.0 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRIMWLCRA4Q7 | 3 | 28.9 | 2026-08 | 7 | vencimento_fora_mes_base×3, isin_invalido×1, isin_repetido×1 |
| BRRBRACRA5K9 | 2 | 0.0 | 2026-09 | 7 | vencido_com_saldo_adimplente×1, isin_repetido×1 |
| BRIMWLCRA3B1 | 2 | 0.0 | 2026-08 | 7 | em_atraso×2, vencimento_fora_mes_base×2 |
| CRA017007KG | 1 | 1,732.1 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, isin_invalido×1 |
| BRIMWLCRA1C3 | 2 | 114.9 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×2 |
| BRIMWLCRA0U7 | 2 | 95.4 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×1 |
| BRIMWLCRA1R1 | 2 | 70.8 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×1 |
| BRIMWLCRA093 | 2 | 64.6 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×1 |
| BRIMWLCRA7Y4 | 2 | 40.3 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×2 |
| BRECOACRA4K9 | 3 | 9.5 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×3 |
| CRA0220020E | 2 | 0.0 | 2026-08 | 6 | serie_sem_isin×1, em_atraso×1 |
| CRA0220020D | 2 | 0.0 | 2026-08 | 6 | serie_sem_isin×1, em_atraso×1 |
| BRRBRACRA1M4 | 3 | 0.0 | 2026-08 | 6 | vencido_com_saldo_adimplente×1, isin_invalido×1 |
| BRGAFLCRA0D0 | 1 | 0.0 | 2024-06 | 6 | isin_repetido×1, informe_defasado×1 |
| BROCTSCRA0K0 | 3 | 0.0 | 2025-12 | 6 | isin_repetido×1, informe_defasado×1 |
| BRAPCSCRA1B7 | 2 | 2,414.6 | 2026-08 | 5 | em_atraso×2 |
| BRVERTCRA344 | 1 | 506.5 | 2026-08 | 5 | em_atraso×1 |
| BRECOACRAF93 | 2 | 421.1 | 2026-08 | 5 | em_atraso×2 |
| BRECOACRAC13 | 2 | 339.5 | 2026-08 | 5 | em_atraso×2 |
| BRECOACRACJ7 | 2 | 217.7 | 2026-08 | 5 | em_atraso×2 |
| BRECOACRAB97 | 3 | 120.6 | 2026-08 | 5 | em_atraso×3 |
| BRECOACRACX8 | 1 | 120.3 | 2026-08 | 5 | em_atraso×1 |
| BRVERTCRA4C9 | 2 | 118.3 | 2026-08 | 5 | em_atraso×2 |

## CRI (competência de referência 2026-08-01)

- 3690 emissões desde 2019; 2312 com informe recente; 745 com algum sinal.
- Saldo das séries com informe recente: R$ 167,976,797,368.

| Sinal | Emissões com o sinal |
|---|---|
| `em_atraso` | 200 |
| `vencido_com_saldo_adimplente` | 92 |
| `informe_defasado` | 216 |
| `vencimento_fora_mes_base` | 101 |
| `isin_repetido` | 48 |
| `serie_sem_isin` | 89 |
| `identificador_duplicado` | 0 |
| `isin_invalido` | 95 |
| `saldo_incompativel` | 32 |

Top 30 por pontuação e saldo:

| Certificado | Séries | Saldo (R$ mi) | Última competência | Pontos | Sinais |
|---|---|---|---|---|---|
| 23G1914605 | 67 | 1,275.3 | 2026-09 | 17 | serie_sem_isin×7, isin_invalido×2, isin_repetido×1, em_atraso×4, vencido_com_saldo_adimplente×4, vencimento_fora_mes_base×3 |
| 11C0035926 | 9 | 692.2 | 2026-08 | 12 | serie_sem_isin×5, em_atraso×1, isin_invalido×1, vencido_com_saldo_adimplente×1 |
| 22J1379218 | 2 | 24.6 | 2026-08 | 11 | vencido_com_saldo_adimplente×2, vencimento_fora_mes_base×1, isin_invalido×2, isin_repetido×1 |
| BRRBRACRI8T6 | 3 | 0.0 | 2026-09 | 11 | vencido_com_saldo_adimplente×1, isin_invalido×1, em_atraso×2 |
| BRAPCSCRIJL8 | 4 | 41.2 | 2026-08 | 10 | em_atraso×1, serie_sem_isin×2, vencido_com_saldo_adimplente×1 |
| BRCBSCCRI2O4 | 2 | 0.1 | 2026-08 | 9 | vencido_com_saldo_adimplente×1, em_atraso×1 |
| 13C0017641 | 2 | 0.0 | 2026-08 | 9 | serie_sem_isin×1, em_atraso×1, saldo_incompativel×1 |
| 13A0016692 | 2 | 50.5 | 2026-08 | 8 | em_atraso×1, serie_sem_isin×1, isin_invalido×1 |
| BRTSSACRI0K0 | 3 | 27.6 | 2026-08 | 8 | em_atraso×2, serie_sem_isin×1, isin_invalido×1 |
| 24E3191695 | 1 | 8.4 | 2026-08 | 8 | em_atraso×1, isin_repetido×1 |
| 11L0015528 | 3 | 1.0 | 2026-08 | 8 | em_atraso×3, serie_sem_isin×1, isin_invalido×1 |
| 21K0870291 | 2 | 0.0 | 2026-08 | 8 | serie_sem_isin×1, em_atraso×1, vencimento_fora_mes_base×1 |
| BRCASCCRI4O1 | 1 | 0.0 | 2026-08 | 8 | em_atraso×1, saldo_incompativel×1 |
| BRAPCSCRIQK5 | 5 | 317.1 | 2026-08 | 7 | vencimento_fora_mes_base×1, saldo_incompativel×2, isin_invalido×2 |
| BRHBSCCRI452 | 12 | 103.3 | 2026-09 | 7 | vencido_com_saldo_adimplente×10, isin_repetido×2 |
| BRAPCSCRIIE5 | 2 | 60.0 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×2 |
| 16B0742429 | 7 | 14.9 | 2026-08 | 7 | serie_sem_isin×3, isin_invalido×3, vencido_com_saldo_adimplente×2 |
| BRIMWLCRI0G8 | 2 | 12.9 | 2026-08 | 7 | em_atraso×2, vencimento_fora_mes_base×2 |
| BRAPCSCRICG3 | 2 | 11.1 | 2026-08 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| 12E0031990 | 2 | 9.9 | 2026-08 | 7 | vencido_com_saldo_adimplente×2, serie_sem_isin×1, isin_invalido×1 |
| 14J0105981 | 3 | 9.4 | 2026-08 | 7 | serie_sem_isin×1, isin_invalido×2, vencido_com_saldo_adimplente×1 |
| 13H0072616 | 4 | 7.2 | 2026-08 | 7 | serie_sem_isin×2, isin_invalido×2, vencido_com_saldo_adimplente×1 |
| 17C0995498 | 6 | 6.3 | 2026-08 | 7 | serie_sem_isin×3, isin_invalido×3, vencido_com_saldo_adimplente×2 |
| 16L0139227 | 6 | 2.9 | 2026-08 | 7 | serie_sem_isin×3, vencido_com_saldo_adimplente×2, isin_invalido×2 |
| BRREICCRI068 | 3 | 2.6 | 2026-08 | 7 | em_atraso×3, isin_invalido×1 |
| BRRBRACRI2J0 | 2 | 1.6 | 2026-08 | 7 | em_atraso×2, isin_invalido×1 |
| 17D0097824 | 4 | 1.6 | 2026-08 | 7 | serie_sem_isin×2, isin_invalido×2, vencido_com_saldo_adimplente×1 |
| 17H0182068 | 4 | 1.4 | 2026-08 | 7 | serie_sem_isin×2, vencido_com_saldo_adimplente×1, isin_invalido×1 |
| BRBSCSCRI780 | 2 | 0.6 | 2026-08 | 7 | em_atraso×2, isin_invalido×1 |
| 15E0186329 | 2 | 0.6 | 2026-08 | 7 | em_atraso×2, isin_invalido×2 |

## Pesos

`em_atraso` = 5, `vencido_com_saldo_adimplente` = 4, `informe_defasado` = 3, `vencimento_fora_mes_base` = 2, `isin_repetido` = 3, `serie_sem_isin` = 1, `identificador_duplicado` = 1, `isin_invalido` = 2, `saldo_incompativel` = 3

Pesos são uma proposta para ordenar a fila de aprofundamento; ajuste conforme o que importar mais.
