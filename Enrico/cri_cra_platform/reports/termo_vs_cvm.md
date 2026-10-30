# Termo de Securitização × Informe Mensal da CVM

Valores do Termo extraídos por regex (candidatos, não parâmetros aprovados) comparados com o Informe da CVM. Divergência pede leitura humana: pode ser erro do Informe, aditamento não lido ou extração errada. Ativo com Termo lido por OCR vem marcado: número de OCR precisa de conferência no PDF.

## Acerto do extrator contra parâmetros aprovados (pilotos)

| Campo | Acertos | Erros |
|---|---|---|
| data_emissao | 2 | 0 |
| data_vencimento | 6 | 0 |
| quantidade | 2 | 0 |
| valor_nominal_unitario | 3 | 0 |
| valor_total | 3 | 0 |

## Resultado por campo

| Campo | Concorda | Diverge | Informe usa data do lastro | Sem valor no Termo |
|---|---|---|---|---|
| data_emissao | 61 | 3 | 0 | 3 |
| vencimento | 123 | 61 | 3 | 3 |
| remuneracao | 158 | 16 | 0 | 2 |
| devedor | 19 | 10 | 0 | 2 |
| valor_total | 48 | 13 | 0 | 0 |
| quantidade | 42 | 19 | 0 | 0 |
| valor_nominal_unitario | 53 | 9 | 0 | 0 |

## Resumo por ativo

| Ativo | Concorda | Diverge | Informe usa data do lastro | Sem valor no Termo | Sem dado CVM |
|---|---|---|---|---|---|
| 20H0225976 | 12 | 9 | 0 | 0 | 0 |
| 23F1829746 | 11 | 9 | 0 | 0 | 0 |
| 13D0358495 | 2 | 6 | 0 | 0 | 0 |
| 23C1835265 | 23 | 6 | 0 | 0 | 0 |
| 24E2495042 | 2 | 6 | 0 | 0 | 0 |
| 23F2472075 | 5 | 5 | 0 | 1 | 0 |
| 23H1753231 | 4 | 5 | 0 | 0 | 0 |
| 26F3681477 | 2 | 5 | 0 | 0 | 0 |
| CRA019000XD | 1 | 5 | 0 | 0 | 0 |
| CRA02500C1D | 10 | 5 | 0 | 0 | 0 |
| 23F2454937 | 7 | 3 | 0 | 0 | 0 |
| 23H1487992 | 6 | 3 | 0 | 0 | 0 |
| CRA020001P8 | 4 | 3 | 0 | 0 | 0 |
| CRA023000040H | 3 | 3 | 0 | 0 | 0 |
| CRA02400E1M | 8 | 3 | 0 | 0 | 0 |
| 20L0504499 | 19 | 2 | 0 | 0 | 0 |
| 21H0769214 | 19 | 2 | 0 | 0 | 0 |
| 21H1002745 | 10 | 2 | 0 | 0 | 0 |
| 21L0967403 | 27 | 2 | 0 | 0 | 0 |
| 22D0836679 | 5 | 2 | 0 | 0 | 0 |
| 23H1186528 | 8 | 2 | 0 | 0 | 0 |
| 23I1698089 | 6 | 2 | 0 | 0 | 0 |
| 23K2122788 | 6 | 2 | 0 | 0 | 0 |
| 24E2535171 | 7 | 2 | 0 | 0 | 0 |
| 24J0943210 | 8 | 2 | 0 | 0 | 0 |
| 25F8582172 | 6 | 2 | 0 | 0 | 0 |
| 25K3156592 | 6 | 2 | 0 | 0 | 0 |
| 26D4402695 | 4 | 2 | 0 | 0 | 0 |
| 26G2446032 | 5 | 2 | 0 | 0 | 0 |
| CRA02000130 | 7 | 2 | 0 | 0 | 0 |
| CRA020001P7 | 5 | 2 | 0 | 0 | 0 |
| CRA02100001 | 4 | 2 | 0 | 0 | 0 |
| CRA0210026F | 4 | 2 | 0 | 0 | 0 |
| CRA022008C4 | 9 | 2 | 0 | 0 | 0 |
| CRA022009C1F | 4 | 2 | 0 | 0 | 0 |
| CRA02300VY3 | 6 | 2 | 0 | 0 | 0 |
| 21K0660418 | 8 | 1 | 0 | 0 | 0 |
| 23E2052239 | 8 | 1 | 0 | 0 | 0 |
| 23H1097588 | 11 | 1 | 0 | 0 | 0 |
| 23I0096173 | 8 | 1 | 0 | 0 | 0 |
| 24D3466320 | 14 | 1 | 0 | 0 | 0 |
| 25C3273266 | 6 | 1 | 0 | 0 | 0 |
| 25L2378911 | 6 | 1 | 0 | 0 | 0 |
| 25L3279335 | 6 | 1 | 0 | 0 | 0 |
| CRA022009VM | 5 | 1 | 0 | 0 | 0 |
| CRA02300TBL | 8 | 1 | 0 | 0 | 0 |
| CRA024000GP | 7 | 1 | 0 | 0 | 0 |
| CRA024006N5 | 7 | 1 | 0 | 0 | 0 |
| CRA024007PW | 7 | 1 | 0 | 0 | 0 |
| 21A0870788 | 8 | 0 | 0 | 0 | 0 |
| 23G1576657 | 14 | 0 | 0 | 0 | 0 |
| 24G2100031 | 7 | 0 | 0 | 0 | 0 |
| 24L2327181 | 8 | 0 | 0 | 0 | 0 |
| 26D2618959 | 8 | 0 | 0 | 0 | 0 |
| 26D7086699 | 6 | 0 | 0 | 0 | 0 |
| CRA01500002 | 0 | 0 | 0 | 4 | 0 |
| CRA019003V3 | 0 | 0 | 0 | 5 | 0 |
| CRA021000S9 | 7 | 0 | 0 | 0 | 0 |
| CRA022001JL | 9 | 0 | 0 | 0 | 0 |
| CRA022007VI | 4 | 0 | 3 | 0 | 0 |
| CRA0230005N | 9 | 0 | 0 | 0 | 0 |
| CRA023000B5 | 6 | 0 | 0 | 0 | 0 |
| CRA0230018I | 6 | 0 | 0 | 0 | 0 |
| CRA02300JR5 | 11 | 0 | 0 | 0 | 0 |
| CRA024002S4 | 8 | 0 | 0 | 0 | 0 |
| CRA024003PF | 8 | 0 | 0 | 0 | 0 |
| CRA024004XT | 9 | 0 | 0 | 0 | 0 |

## Divergências

| Ativo | Campo | Termo | CVM | Fonte no Termo | OCR |
|---|---|---|---|---|---|
| 13D0358495 | vencimento BRTSSACRI0K0 | 2028-04-25 | 2024-11-25 |  |  |
| 13D0358495 | vencimento série 23 | 2028-04-25 | 2024-11-25 |  |  |
| 13D0358495 | quantidade | 146 | 71 |  |  |
| 13D0358495 | remuneracao BRTSSACRI0K0 | taxa=1; taxa=12.5 | 12,00% + IPCA a.a. |  |  |
| 13D0358495 | remuneracao série 23 | taxa=1; taxa=12.5 | 1% + IPCA a.a. |  |  |
| 13D0358495 | valor_nominal_unitario | 301683.18; 7772779.87 | 629224.92 |  |  |
| 20H0225976 | vencimento BRFSECCRIC65 | 2025-07-20 | 2030-07-22 |  |  |
| 20H0225976 | vencimento BRFSECCRIC73 | 2025-07-20 | 2030-07-22 |  |  |
| 20H0225976 | vencimento BRFSECCRIC81 | 2025-07-20 | 2030-07-22 |  |  |
| 20H0225976 | vencimento BRFSECCRIC99 | 2025-07-20 | 2030-07-22 |  |  |
| 20H0225976 | vencimento BRFSECCRICA9 | 2025-07-20 | 2030-07-22 |  |  |
| 20H0225976 | vencimento BRFSECCRICB7 | 2025-07-20 | 2030-07-22 |  |  |
| 20H0225976 | vencimento BRFSECCRICC5 | 2025-07-20 | 2030-07-22 |  |  |
| 20H0225976 | vencimento BRFSECCRICD3 | 2025-07-20 | 2030-07-22 |  |  |
| 20H0225976 | devedor | 03.751.794/0001-13 | 00.369.161/0001-57 |  |  |
| 20L0504499 | quantidade | 50000; 150000 | 445979 |  |  |
| 20L0504499 | valor_nominal_unitario | 1000.00; 1000.00 | 1010.77 |  |  |
| 21H0769214 | data_emissao | 2021-08-09 | 2021-08-19 | 206861 p.9 |  |
| 21H0769214 | quantidade | 14800; 22200; 32800; 37200; 49200; 82800 | 230571 |  |  |
| 21H1002745 | valor_total | 119903483.82 | 3001000000.00 |  |  |
| 21H1002745 | remuneracao BRAPCSCRIAW4 | taxa=0; taxa=0.7; taxa=0.91; taxa=0.99; taxa=1.17; taxa=1.21; taxa=1.2 | IGPM + 6.0000% a.a. |  |  |
| 21K0660418 | valor_nominal_unitario | 12932000.00 | 1000.00 |  |  |
| 21L0967403 | vencimento BRHBSCCRIB59 | 2024-12-24; lastro 2021-12-20; lastro 2024-03-14; lastro 2024-12-23; l | 2027-04-26 |  |  |
| 21L0967403 | vencimento BRHBSCCRIB67 | 2024-12-24; lastro 2021-12-20; lastro 2024-03-14; lastro 2024-12-23; l | 2027-04-26 |  |  |
| 22D0836679 | remuneracao BRAPCSCRICG3 | mult=100; taxa=0; taxa=10.5; taxa=2; taxa=3.75 | CDI + 4,2500% a.a. |  |  |
| 22D0836679 | devedor | 12.392.983/0001-38 | 08.065.557/0001-12 |  |  |
| 23C1835265 | vencimento BRFSECCRIJW8 | 2026-03-20; lastro 2026-03-18 | 2036-03-20 |  |  |
| 23C1835265 | vencimento BRFSECCRIJY4 | 2026-03-20; lastro 2026-03-18 | 2036-03-20 |  |  |
| 23C1835265 | vencimento BRFSECCRIJO5 | 2026-03-20; lastro 2026-03-18 | 2036-03-20 |  |  |
| 23C1835265 | vencimento BRFSECCRIJQ0 | 2026-03-20; lastro 2026-03-18 | 2036-03-20 |  |  |
| 23C1835265 | vencimento BRFSECCRIJS6 | 2026-03-20; lastro 2026-03-18 | 2036-03-20 |  |  |
| 23C1835265 | vencimento BRFSECCRIJU2 | 2026-03-20; lastro 2026-03-18 | 2036-03-20 |  |  |
| 23E2052239 | devedor | 04.403.408/0001-65; 26.502.794/0001-85; 30.433.252/0001-75; 31.986.976 | 20.456.189/0001-39 |  |  |
| 23F1829746 | vencimento BRPVSCCRI2E6 | 2025-08-05; 2026-12-16; 2027-07-08; 2028-05-30 | 2043-01-20 |  |  |
| 23F1829746 | vencimento BRPVSCCRI2F3 | 2025-08-05; 2026-12-16; 2027-07-08; 2028-05-30 | 2043-01-20 |  |  |
| 23F1829746 | vencimento BRPVSCCRI2O5 | 2025-08-05; 2026-12-16; 2027-07-08; 2028-05-30 | 2043-01-20 |  |  |
| 23F1829746 | vencimento BRPVSCCRI2P2 | 2025-08-05; 2026-12-16; 2027-07-08; 2028-05-30 | 2043-01-20 |  |  |
| 23F1829746 | vencimento BRPVSCCRI2V0 | 2025-08-05; 2026-12-16; 2027-07-08; 2028-05-30 | 2043-01-20 |  |  |
| 23F1829746 | vencimento BRPVSCCRI2W8 | 2025-08-05; 2026-12-16; 2027-07-08; 2028-05-30 | 2043-01-20 |  |  |
| 23F1829746 | vencimento BRPVSCCRI3B0 | 2025-08-05; 2026-12-16; 2027-07-08; 2028-05-30 | 2043-01-20 |  |  |
| 23F1829746 | vencimento BRPVSCCRI3C8 | 2025-08-05; 2026-12-16; 2027-07-08; 2028-05-30 | 2043-01-20 |  |  |
| 23F1829746 | quantidade | 450; 461; 993; 1094; 4058; 4149; 8937; 9849; 20000 | 29930 |  |  |
| 23F2454937 | vencimento BRAPCSCRIIT3 | 2026-07-15; 2027-07-15; 2028-07-17; lastro 2026-07-13; lastro 2027-07- | 2028-07-15 |  |  |
| 23F2454937 | valor_total | 1000000000.00; 1070846000.00; 1250000000.00 | 925125000.00 |  |  |
| 23F2454937 | quantidade | 1000000; 1070846 | 925125 |  |  |
| 23F2472075 | vencimento BRAPCSCRIIZ0 | 2027-12-07; 2032-05-17; 2034-10-15 | 2026-10-15 |  |  |
| 23F2472075 | vencimento BRAPCSCRIJ03 | 2027-12-07; 2032-05-17; 2034-10-15 | 2026-10-15 |  |  |
| 23F2472075 | vencimento BRAPCSCRIJ11 | 2027-12-07; 2032-05-17; 2034-10-15 | 2026-10-15 |  |  |
| 23F2472075 | vencimento BRAPCSCRIJ29 | 2027-12-07; 2032-05-17; 2034-10-15 | 2026-10-15 |  |  |
| 23F2472075 | valor_total | 809.16; 1490.00 | 27800000.00 |  |  |
| 23H1097588 | vencimento BRBASECRI0X9 | 2040-04-18; 2040-04-20; lastro 2040-04-18 | 2028-08-20 |  |  |
| 23H1186528 | valor_total | 3385372.41; 8559611.00; 13369702.84; 45019662.20; 60000000.00; 7842102 | 350000000.00 |  |  |
| 23H1186528 | quantidade | 700000 | 350000 |  |  |
| 23H1487992 | vencimento série 3 | 2027-01-25 | 2026-04-27 |  |  |
| 23H1487992 | quantidade | 29100 | 40100 |  |  |
| 23H1487992 | remuneracao BRRBRACRIVC2 | taxa=13 | IPCA + 16,0000% a.a. |  |  |
| 23H1753231 | vencimento BRHBSCCRIAB3 | 2026-08-21; 2026-08-24 | 2030-11-21 |  |  |
| 23H1753231 | vencimento BRHBSCCRICD5 | 2026-08-21; 2026-08-24 | 2030-11-21 |  |  |
| 23H1753231 | remuneracao BRHBSCCRIAB3 | taxa=12.68 | 10,68 % IPCA |  |  |
| 23H1753231 | remuneracao BRHBSCCRICD5 | taxa=12.68 | 14,68 % IPCA |  |  |
| 23H1753231 | devedor | 09.569.513/0001-92; 34.271.171/0007-62; 34.337.707/0001-00 | 44.662.886/0001-04 |  |  |
| 23I0096173 | vencimento BRFSECCRIKC8 | 2027-03-20; 2038-09-20; lastro 2023-09-04 | 2027-03-22 |  |  |
| 23I1698089 | vencimento BRBASECRI115 | 2026-09-20; 2036-09-20; lastro 2026-09-17; lastro 2036-09-20 | 2027-09-20 |  |  |
| 23I1698089 | vencimento BRBASECRI123 | 2026-09-20; 2036-09-20; lastro 2026-09-17; lastro 2036-09-20 | 2036-09-22 |  |  |
| 23K2122788 | vencimento BRBASECRI131 | 2023-11-24 | 2026-11-23 |  |  |
| 23K2122788 | vencimento BRBASECRI149 | 2023-11-24 | 2043-11-23 |  |  |
| 24D3466320 | quantidade | 20000; 26700; 55000; 165000; 390000 | 550036 |  |  |
| 24E2495042 | vencimento BRLSECCRI0Q9 | lastro 2028-05-20 | 2027-11-22 |  |  |
| 24E2495042 | vencimento série 3 | lastro 2028-05-20 | 2028-01-22 |  |  |
| 24E2495042 | vencimento BRLSECCRI0T3 | lastro 2028-05-20 | 2028-01-22 |  |  |
| 24E2495042 | remuneracao BRLSECCRI0Q9 | taxa=15; taxa=2; taxa=8 | IPCA + 16.000 % a.a. |  |  |
| 24E2495042 | remuneracao BRLSECCRI0T3 | taxa=15; taxa=2; taxa=8 | IPCA + 16.000 % a.a. |  |  |
| 24E2495042 | devedor | 40.654.622/0001-58; 44.847.027/0001-90 | 04.800.830/0001-54 |  |  |
| 24E2535171 | quantidade | 150000; 350000 | 389570 |  |  |
| 24E2535171 | devedor | 03.751.794/0001-13; 35.082.277/0001-95; 43.533.100/0001-96; 67.030.395 | 23.853.792/0001-42 |  |  |
| 24J0943210 | valor_total | 809.16; 1490.00; 10441.00; 3385372.41; 8559611.00; 9176398.47; 1336970 | 108703.00 |  |  |
| 24J0943210 | valor_nominal_unitario | 1000.00; 1000.00 | 1.00 |  |  |
| 25C3273266 | vencimento BRLSECCRI2L6 | 2025-03-07 | 2029-02-24 |  |  |
| 25F8582172 | vencimento BRCASCCRI5V3 | 2028-02-14; 2034-07-20 | 2030-07-25 |  |  |
| 25F8582172 | vencimento BRCASCCRI5W1 | 2028-02-14; 2034-07-20 | 2030-07-26 |  |  |
| 25K3156592 | valor_total | 40000000.00 | 15000000.00 |  |  |
| 25K3156592 | valor_nominal_unitario | 1000.00; 40000000.00 | 375.00 |  |  |
| 25L2378911 | devedor | 03.997.580/0001-21; 11.863.002/0001-20; 17.409.378/0001-46; 29.507.878 | 04.800.830/0001-54 |  |  |
| 25L3279335 | devedor | 12.164.139/0001-50; 49.076.534/0001-90; 51.618.470/0001-54 | 04.800.830/0001-54 |  |  |
| 26D4402695 | vencimento BRLSECCRI4P3 | 2026-04-14 | 2034-04-26 |  |  |
| 26D4402695 | vencimento BRLSECCRI4Q1 | 2026-04-14 | 2034-05-26 |  |  |
| 26F3681477 | vencimento BRLSECCRI5H7 | 2031-06-20 | 2031-06-24 |  |  |
| 26F3681477 | vencimento série 2 | 2031-06-20 | 2031-06-24 |  |  |
| 26F3681477 | vencimento série 3 | 2031-06-20 | 2031-06-24 |  |  |
| 26F3681477 | remuneracao série 2 | mult=100; taxa=1; taxa=100; taxa=4 | CDI + 0.000 % a.a. |  |  |
| 26F3681477 | remuneracao série 3 | mult=100; taxa=1; taxa=100; taxa=4 | CDI + 0.000 % a.a. |  |  |
| 26G2446032 | vencimento série 2 | 2026-07-07; 2030-06-26 | 2030-07-26 |  |  |
| 26G2446032 | valor_nominal_unitario | 46035000.00; 46035000.00 | 1000.00 |  |  |
| CRA019000XD | data_emissao | 2026-02-18 | 2019-03-18 | 128215 p.32 |  |
| CRA019000XD | vencimento BRIMWLCRA093 | 2026-02-18; 2028-02-15 | 2023-03-15 |  |  |
| CRA019000XD | vencimento BRIMWLCRA0A9 | 2026-02-18; 2028-02-15 | 2029-03-14 |  |  |
| CRA019000XD | valor_total | 250000000.00 | 370000000.00 |  |  |
| CRA019000XD | quantidade | 250000 | 270000 |  |  |
| CRA02000130 | remuneracao BRFSECCRA010 | mult=100; taxa=4; taxa=52.21; taxa=8 | 7,5% + CDI |  |  |
| CRA02000130 | remuneracao BRFSECCRA028 | mult=100; taxa=4; taxa=52.21; taxa=8 | 10% + CDI |  |  |
| CRA020001P7 | valor_total | 3385372.41; 8559611.00; 9176398.47; 12794898.60; 13369702.84; 14919362 | 352426000.00 |  |  |
| CRA020001P7 | quantidade | 1080482 | 352426 |  |  |
| CRA020001P8 | vencimento BRAPCSCRA0U9 | 2027-06-15 | 2030-06-17 |  |  |
| CRA020001P8 | valor_total | 3385372.41; 8559611.00; 9176398.47; 12794898.60; 13369702.84; 14919362 | 728056000.00 |  |  |
| CRA020001P8 | quantidade | 1080482 | 728056 |  |  |
| CRA02100001 | data_emissao | 2026-02-18 | 2021-02-15 | 146935 p.33 |  |
| CRA02100001 | vencimento BRIMWLCRA0V5 | 2026-02-18; 2028-02-15; lastro 2026-02-12; lastro 2028-02-11 | 2028-08-15 |  |  |
| CRA0210026F | valor_total | 150000000.00 | 83000000.00 |  |  |
| CRA0210026F | quantidade | 150000 | 83000 |  |  |
| CRA022008C4 | remuneracao BRECOACRAB97 | mult=100; taxa=1; taxa=4.2; taxa=5; taxa=7; taxa=75 | CDI 100% + 5,0000 % a.a. |  |  |
| CRA022008C4 | remuneracao BRECOACRABA8 | mult=100; taxa=1; taxa=4.2; taxa=5; taxa=7; taxa=75 | CDI 100% + 7,0000 % a.a. |  |  |
| CRA022009C1F | valor_total | 6000.00 | 229314000.00 |  |  |
| CRA022009C1F | quantidade | 82780; 162216; 205004; 244966; 244996; 450000 | 229314 |  |  |
| CRA022009VM | devedor | 01.486.546/0001-67; 09.346.601/0001-25; 10.830.108/0001-65; 17.118.468 | 31.943.818/0001-71 |  |  |
| CRA023000040H | valor_total | 60000000.00 | 33000000.00 |  |  |
| CRA023000040H | quantidade | 60000 | 44320 |  |  |
| CRA023000040H | valor_nominal_unitario | 1000.00; 1000.00 | 744.58 |  |  |
| CRA02300TBL | devedor | 00.405.805/0001-15; 02.392.738/0001-77; 06.116.723/0001-37; 33.866.324 | 27.490.581/0001-43 |  |  |
| CRA02300VY3 | valor_total | 200000000.00 | 71294000.00 |  |  |
| CRA02300VY3 | quantidade | 63000; 137000; 200000 | 71294 |  |  |
| CRA024000GP | valor_nominal_unitario | 1000.00 | 347.77 |  |  |
| CRA024006N5 | quantidade | 120000 | 76301 |  |  |
| CRA024007PW | quantidade | 113293; 114222 | 112232 |  |  |
| CRA02400E1M | quantidade | 120000 | 60000 |  |  |
| CRA02400E1M | remuneracao BRECOACRAIF2 | mult=70; taxa=0; taxa=25; taxa=33.33; taxa=5.2; taxa=50; taxa=6.4; tax | CDI + 5,0000% a.a. |  |  |
| CRA02400E1M | valor_nominal_unitario | 1000.00 | 1200.00 |  |  |
| CRA02500C1D | vencimento BRECOACRALJ8 | 2030-12-18; 2032-12-17; 2035-12-19; lastro 2030-12-16; lastro 2032-12- | 2029-07-16 |  |  |
| CRA02500C1D | vencimento BRECOACRALK6 | 2030-12-18; 2032-12-17; 2035-12-19; lastro 2030-12-16; lastro 2032-12- | 2032-07-15 |  |  |
| CRA02500C1D | vencimento BRECOACRALL4 | 2030-12-18; 2032-12-17; 2035-12-19; lastro 2030-12-16; lastro 2032-12- | 2035-07-16 |  |  |
| CRA02500C1D | vencimento BRECOACRALM2 | 2030-12-18; 2032-12-17; 2035-12-19; lastro 2030-12-16; lastro 2032-12- | 2030-07-15 |  |  |
| CRA02500C1D | vencimento BRECOACRALN0 | 2030-12-18; 2032-12-17; 2035-12-19; lastro 2030-12-16; lastro 2032-12- | 2030-07-15 |  |  |
