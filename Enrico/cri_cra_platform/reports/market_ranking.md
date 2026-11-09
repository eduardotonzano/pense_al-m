# Triagem do mercado de CRI e CRA

Fonte: Informe Mensal dos dados abertos da CVM (`data/cvm_open.db`). Só leitura. **Candidatos a revisão, não conclusões**:
o dado é o do próprio Informe e erro de preenchimento vem junto.

## CRA (competência de referência 2026-09-01)

- 1208 emissões desde 2019; 630 com informe recente; 316 com algum sinal.
- Saldo das séries com informe recente: R$ 158,746,229,581.

| Sinal | Emissões com o sinal |
|---|---|
| `em_atraso` | 77 |
| `vencido_com_saldo_adimplente` | 27 |
| `informe_defasado` | 93 |
| `vencimento_fora_mes_base` | 126 |
| `isin_repetido` | 4 |
| `serie_sem_isin` | 0 |
| `identificador_duplicado` | 0 |
| `isin_invalido` | 11 |
| `saldo_incompativel` | 2 |
| `situacao_mista_na_classe` | 1 |

Top 30 por pontuação e saldo:

| Certificado | Séries | Saldo (R$ mi) | Última competência | Pontos | Sinais |
|---|---|---|---|---|---|
| BRAPCSCRA1Y9 | 3 | 1,109.8 | 2026-09 | 10 | vencimento_fora_mes_base×3, em_atraso×2, situacao_mista_na_classe×1 |
| BRAPCSCRA1B7 | 2 | 2,428.4 | 2026-09 | 7 | em_atraso×2, vencimento_fora_mes_base×2 |
| BRAPCSCRA0M6 | 2 | 1,400.1 | 2026-09 | 7 | em_atraso×2, vencimento_fora_mes_base×2 |
| BRAPCSCRA0U9 | 1 | 1,068.2 | 2026-09 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRAPCSCRA0T1 | 1 | 516.5 | 2026-09 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRECOACRABX0 | 1 | 45.7 | 2026-09 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRIMWLCRA3B1 | 2 | 1.0 | 2026-09 | 7 | em_atraso×2, vencimento_fora_mes_base×2 |
| BRRBRACRA5K9 | 2 | 0.0 | 2026-09 | 7 | vencido_com_saldo_adimplente×1, isin_repetido×1 |
| CRA02200ENV | 3 | 0.0 | 2026-09 | 7 | vencido_com_saldo_adimplente×1, isin_repetido×3 |
| BRAPCSCRA2J8 | 5 | 0.0 | 2026-09 | 7 | vencimento_fora_mes_base×5, em_atraso×3 |
| BRAPCSCRA0W5 | 4 | 0.0 | 2026-09 | 7 | em_atraso×2, vencimento_fora_mes_base×2 |
| BRAPCSCRA1U7 | 1 | 0.0 | 2026-09 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| BRAPCSCRA1W3 | 1 | 0.0 | 2026-09 | 7 | em_atraso×1, vencimento_fora_mes_base×1 |
| CRA017007KG | 2 | 1,772.8 | 2026-09 | 6 | vencido_com_saldo_adimplente×2, isin_invalido×2 |
| BRIMWLCRA1C3 | 2 | 115.3 | 2026-09 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×2 |
| BRIMWLCRA0U7 | 2 | 95.4 | 2026-09 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×2 |
| BRIMWLCRA093 | 2 | 65.4 | 2026-09 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×1 |
| BRIMWLCRA7Y4 | 2 | 40.3 | 2026-09 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×2 |
| BRECOACRA4K9 | 3 | 9.6 | 2026-09 | 6 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×3 |
| BRGAFLCRA0D0 | 1 | 0.0 | 2024-06 | 6 | isin_repetido×1, informe_defasado×1 |
| BRECOACRA8A1 | 2 | 914.6 | 2026-09 | 5 | em_atraso×2 |
| BRVERTCRA344 | 1 | 506.5 | 2026-09 | 5 | em_atraso×1 |
| BRECOACRAF93 | 2 | 421.4 | 2026-09 | 5 | em_atraso×2 |
| BRECOACRAC13 | 2 | 343.7 | 2026-09 | 5 | em_atraso×2 |
| BRECOACRACJ7 | 2 | 212.2 | 2026-09 | 5 | em_atraso×2 |
| BRECOACRAB97 | 3 | 122.7 | 2026-09 | 5 | em_atraso×3 |
| BRECOACRACX8 | 1 | 122.2 | 2026-09 | 5 | em_atraso×1 |
| BRVERTCRA4C9 | 2 | 118.3 | 2026-09 | 5 | em_atraso×2 |
| BRECOACRA0Q4 | 2 | 100.8 | 2026-09 | 5 | em_atraso×1 |
| BRCASCCRA0A6 | 1 | 96.0 | 2026-09 | 5 | em_atraso×1 |

## CRI (competência de referência 2026-09-01)

- 3845 emissões desde 2019; 2421 com informe recente; 797 com algum sinal.
- Saldo das séries com informe recente: R$ 170,176,877,863.

| Sinal | Emissões com o sinal |
|---|---|
| `em_atraso` | 293 |
| `vencido_com_saldo_adimplente` | 85 |
| `informe_defasado` | 218 |
| `vencimento_fora_mes_base` | 110 |
| `isin_repetido` | 38 |
| `serie_sem_isin` | 34 |
| `identificador_duplicado` | 0 |
| `isin_invalido` | 69 |
| `saldo_incompativel` | 57 |
| `situacao_mista_na_classe` | 20 |

Top 30 por pontuação e saldo:

| Certificado | Séries | Saldo (R$ mi) | Última competência | Pontos | Sinais |
|---|---|---|---|---|---|
| BRAPCSCRIDX6 | 2 | 45.2 | 2026-09 | 12 | em_atraso×1, vencido_com_saldo_adimplente×1, situacao_mista_na_classe×1 |
| BRAPCSCRI7N1 | 2 | 72.1 | 2026-09 | 11 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×2, em_atraso×1 |
| BRRBRACRIW55 | 4 | 623.3 | 2026-09 | 10 | em_atraso×2, vencimento_fora_mes_base×4, situacao_mista_na_classe×1 |
| BRAPCSCRIHI8 | 5 | 45.7 | 2026-09 | 10 | vencimento_fora_mes_base×5, em_atraso×3, situacao_mista_na_classe×1 |
| BRBSCSCRI4Y1 | 2 | 10.7 | 2026-09 | 10 | em_atraso×2, saldo_incompativel×1, isin_invalido×1 |
| BRBSCSCRI780 | 3 | 9.8 | 2026-09 | 10 | em_atraso×2, isin_invalido×1, situacao_mista_na_classe×1 |
| 14J0045610 | 3 | 0.6 | 2026-09 | 10 | em_atraso×2, isin_invalido×1, saldo_incompativel×1 |
| BRCBSCCRI2O4 | 2 | 76.0 | 2026-09 | 9 | vencido_com_saldo_adimplente×1, em_atraso×1 |
| BRFSECCRIKK1 | 5 | 737.1 | 2026-09 | 8 | em_atraso×1, situacao_mista_na_classe×1 |
| BRBASECRI131 | 2 | 704.0 | 2026-09 | 8 | em_atraso×1, situacao_mista_na_classe×1 |
| 11C0035926 | 4 | 618.8 | 2026-09 | 8 | em_atraso×2, isin_invalido×2, serie_sem_isin×2 |
| BRFSECCRIKC8 | 2 | 616.4 | 2026-09 | 8 | em_atraso×1, situacao_mista_na_classe×1 |
| BRBASECRI198 | 2 | 509.7 | 2026-09 | 8 | em_atraso×1, situacao_mista_na_classe×1 |
| BRBASECRI0X9 | 4 | 469.3 | 2026-09 | 8 | em_atraso×3, situacao_mista_na_classe×1 |
| BRFSECCRIK73 | 5 | 410.6 | 2026-09 | 8 | em_atraso×3, situacao_mista_na_classe×1 |
| BRAPCSCRIET2 | 7 | 157.5 | 2026-09 | 8 | em_atraso×3, situacao_mista_na_classe×1 |
| BRAPCSCRIAZ7 | 2 | 156.0 | 2026-09 | 8 | em_atraso×1, situacao_mista_na_classe×1 |
| BRAPCSCRIF72 | 12 | 97.2 | 2026-09 | 8 | em_atraso×5, situacao_mista_na_classe×1 |
| BRAPCSCRIBE0 | 2 | 70.6 | 2026-09 | 8 | em_atraso×1, situacao_mista_na_classe×1 |
| 13A0016692 | 2 | 50.5 | 2026-09 | 8 | em_atraso×2, serie_sem_isin×1, isin_invalido×1 |
| BRAPCSCRIHD9 | 3 | 47.9 | 2026-09 | 8 | em_atraso×1, situacao_mista_na_classe×1 |
| BRCASCCRI5V3 | 2 | 42.6 | 2026-09 | 8 | em_atraso×1, situacao_mista_na_classe×1 |
| BRAPCSCRIL09 | 3 | 35.4 | 2026-09 | 8 | em_atraso×2, situacao_mista_na_classe×1 |
| BRAPCSCRIAU8 | 5 | 32.6 | 2026-09 | 8 | em_atraso×1, saldo_incompativel×1 |
| BRAPCSCRIP54 | 1 | 20.6 | 2026-09 | 8 | em_atraso×1, isin_repetido×1 |
| BRPVSCCRI2E6 | 8 | 18.6 | 2026-09 | 8 | em_atraso×1, situacao_mista_na_classe×1 |
| BRIMWLCRILH5 | 2 | 15.6 | 2026-09 | 8 | em_atraso×1, situacao_mista_na_classe×1 |
| 22J1381764 | 1 | 6.3 | 2026-09 | 8 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×1, isin_invalido×1 |
| 22J1381567 | 1 | 5.8 | 2026-09 | 8 | vencido_com_saldo_adimplente×1, vencimento_fora_mes_base×1, isin_invalido×1 |
| 24E3191695 | 1 | 5.6 | 2026-09 | 8 | em_atraso×1, isin_repetido×1 |

## Pesos

`em_atraso` = 5, `vencido_com_saldo_adimplente` = 4, `informe_defasado` = 3, `vencimento_fora_mes_base` = 2, `isin_repetido` = 3, `serie_sem_isin` = 1, `identificador_duplicado` = 1, `isin_invalido` = 2, `saldo_incompativel` = 3, `situacao_mista_na_classe` = 3

Pesos são uma proposta para ordenar a fila de aprofundamento; ajuste conforme o que importar mais.
