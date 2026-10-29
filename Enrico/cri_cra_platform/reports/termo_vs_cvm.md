# Termo de Securitização × Informe Mensal da CVM

Valores do Termo extraídos por regex (candidatos, não parâmetros aprovados) comparados com o Informe da CVM. Divergência pede leitura humana: pode ser erro do Informe, aditamento não lido ou extração errada.

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
| data_emissao | 29 | 1 | 0 | 1 |
| vencimento | 63 | 25 | 3 | 2 |
| remuneracao | 73 | 8 | 0 | 1 |
| devedor | 10 | 5 | 0 | 1 |
| valor_total | 25 | 5 | 0 | 0 |
| quantidade | 19 | 10 | 0 | 0 |
| valor_nominal_unitario | 27 | 3 | 0 | 0 |

## Resumo por ativo

| Ativo | Concorda | Diverge | Informe usa data do lastro | Sem valor no Termo | Sem dado CVM |
|---|---|---|---|---|---|
| 13D0358495 | 2 | 6 | 0 | 0 | 0 |
| 23C1835265 | 22 | 6 | 0 | 0 | 0 |
| 23H1753231 | 4 | 5 | 0 | 0 | 0 |
| CRA02500C1D | 10 | 5 | 0 | 0 | 0 |
| 23F2454937 | 7 | 3 | 0 | 0 | 0 |
| 23H1487992 | 6 | 3 | 0 | 0 | 0 |
| CRA020001P8 | 4 | 3 | 0 | 0 | 0 |
| 20L0504499 | 19 | 2 | 0 | 0 | 0 |
| 21L0967403 | 27 | 2 | 0 | 0 | 0 |
| 22D0836679 | 5 | 2 | 0 | 0 | 0 |
| 23I1698089 | 6 | 2 | 0 | 0 | 0 |
| 23K2122788 | 6 | 2 | 0 | 0 | 0 |
| CRA020001P7 | 5 | 2 | 0 | 0 | 0 |
| CRA02100001 | 4 | 2 | 0 | 0 | 0 |
| CRA0210026F | 4 | 2 | 0 | 0 | 0 |
| CRA022008C4 | 9 | 2 | 0 | 0 | 0 |
| CRA022009C1F | 4 | 2 | 0 | 0 | 0 |
| 21K0660418 | 8 | 1 | 0 | 0 | 0 |
| 23E2052239 | 8 | 1 | 0 | 0 | 0 |
| 24D3466320 | 14 | 1 | 0 | 0 | 0 |
| CRA022009VM | 5 | 1 | 0 | 0 | 0 |
| CRA02300TBL | 8 | 1 | 0 | 0 | 0 |
| CRA024007PW | 7 | 1 | 0 | 0 | 0 |
| 21A0870788 | 8 | 0 | 0 | 0 | 0 |
| 24G2100031 | 7 | 0 | 0 | 0 | 0 |
| CRA019003V3 | 0 | 0 | 0 | 5 | 0 |
| CRA021000S9 | 7 | 0 | 0 | 0 | 0 |
| CRA022007VI | 4 | 0 | 3 | 0 | 0 |
| CRA0230005N | 9 | 0 | 0 | 0 | 0 |
| CRA023000B5 | 6 | 0 | 0 | 0 | 0 |
| CRA02300JR5 | 11 | 0 | 0 | 0 | 0 |

## Divergências

| Ativo | Campo | Termo | CVM | Fonte no Termo |
|---|---|---|---|---|
| 13D0358495 | vencimento BRTSSACRI0K0 | 2028-04-25 | 2024-11-25 |  |
| 13D0358495 | vencimento série 23 | 2028-04-25 | 2024-11-25 |  |
| 13D0358495 | quantidade | 146 | 71 |  |
| 13D0358495 | remuneracao BRTSSACRI0K0 | taxa=1; taxa=12.5 | 12,00% + IPCA a.a. |  |
| 13D0358495 | remuneracao série 23 | taxa=1; taxa=12.5 | 1% + IPCA a.a. |  |
| 13D0358495 | valor_nominal_unitario | 301683.18; 7772779.87 | 629224.92 |  |
| 20L0504499 | quantidade | 50000; 150000 | 445979 |  |
| 20L0504499 | valor_nominal_unitario | 1000.00; 1000.00 | 1010.77 |  |
| 21K0660418 | valor_nominal_unitario | 12932000.00 | 1000.00 |  |
| 21L0967403 | vencimento BRHBSCCRIB59 | 2024-12-24; lastro 2021-12-20; lastro 2024-03-14; lastro 2024-12-23; l | 2027-04-26 |  |
| 21L0967403 | vencimento BRHBSCCRIB67 | 2024-12-24; lastro 2021-12-20; lastro 2024-03-14; lastro 2024-12-23; l | 2027-04-26 |  |
| 22D0836679 | remuneracao BRAPCSCRICG3 | mult=100; taxa=0; taxa=10.5; taxa=2; taxa=3.75 | CDI + 4,2500% a.a. |  |
| 22D0836679 | devedor | 12.392.983/0001-38 | 08.065.557/0001-12 |  |
| 23C1835265 | vencimento BRFSECCRIJW8 | 2026-03-20; lastro 2026-03-18 | 2036-03-20 |  |
| 23C1835265 | vencimento BRFSECCRIJY4 | 2026-03-20; lastro 2026-03-18 | 2036-03-20 |  |
| 23C1835265 | vencimento BRFSECCRIJO5 | 2026-03-20; lastro 2026-03-18 | 2036-03-20 |  |
| 23C1835265 | vencimento BRFSECCRIJQ0 | 2026-03-20; lastro 2026-03-18 | 2036-03-20 |  |
| 23C1835265 | vencimento BRFSECCRIJS6 | 2026-03-20; lastro 2026-03-18 | 2036-03-20 |  |
| 23C1835265 | vencimento BRFSECCRIJU2 | 2026-03-20; lastro 2026-03-18 | 2036-03-20 |  |
| 23E2052239 | devedor | 04.403.408/0001-65; 26.502.794/0001-85; 30.433.252/0001-75; 31.986.976 | 20.456.189/0001-39 |  |
| 23F2454937 | vencimento BRAPCSCRIIT3 | 2026-07-15; 2027-07-15; 2028-07-17; lastro 2026-07-13; lastro 2027-07- | 2028-07-15 |  |
| 23F2454937 | valor_total | 1000000000.00; 1070846000.00; 1250000000.00 | 925125000.00 |  |
| 23F2454937 | quantidade | 1000000; 1070846 | 925125 |  |
| 23H1487992 | vencimento série 3 | 2027-01-25 | 2026-04-27 |  |
| 23H1487992 | quantidade | 29100 | 40100 |  |
| 23H1487992 | remuneracao BRRBRACRIVC2 | taxa=13 | IPCA + 16,0000% a.a. |  |
| 23H1753231 | vencimento BRHBSCCRIAB3 | 2026-08-21; 2026-08-24 | 2030-11-21 |  |
| 23H1753231 | vencimento BRHBSCCRICD5 | 2026-08-21; 2026-08-24 | 2030-11-21 |  |
| 23H1753231 | remuneracao BRHBSCCRIAB3 | taxa=12.68 | 10,68 % IPCA |  |
| 23H1753231 | remuneracao BRHBSCCRICD5 | taxa=12.68 | 14,68 % IPCA |  |
| 23H1753231 | devedor | 09.569.513/0001-92; 34.271.171/0007-62; 34.337.707/0001-00 | 44.662.886/0001-04 |  |
| 23I1698089 | vencimento BRBASECRI115 | 2026-09-20; 2036-09-20; lastro 2026-09-17; lastro 2036-09-20 | 2027-09-20 |  |
| 23I1698089 | vencimento BRBASECRI123 | 2026-09-20; 2036-09-20; lastro 2026-09-17; lastro 2036-09-20 | 2036-09-22 |  |
| 23K2122788 | vencimento BRBASECRI131 | 2023-11-24 | 2026-11-23 |  |
| 23K2122788 | vencimento BRBASECRI149 | 2023-11-24 | 2043-11-23 |  |
| 24D3466320 | quantidade | 20000; 26700; 55000; 165000; 390000 | 550036 |  |
| CRA020001P7 | valor_total | 3385372.41; 8559611.00; 9176398.47; 12794898.60; 13369702.84; 14919362 | 352426000.00 |  |
| CRA020001P7 | quantidade | 1080482 | 352426 |  |
| CRA020001P8 | vencimento BRAPCSCRA0U9 | 2027-06-15 | 2030-06-17 |  |
| CRA020001P8 | valor_total | 3385372.41; 8559611.00; 9176398.47; 12794898.60; 13369702.84; 14919362 | 728056000.00 |  |
| CRA020001P8 | quantidade | 1080482 | 728056 |  |
| CRA02100001 | data_emissao | 2026-02-18 | 2021-02-15 | 146935 p.33 |
| CRA02100001 | vencimento BRIMWLCRA0V5 | 2026-02-18; 2028-02-15; lastro 2026-02-12; lastro 2028-02-11 | 2028-08-15 |  |
| CRA0210026F | valor_total | 150000000.00 | 83000000.00 |  |
| CRA0210026F | quantidade | 150000 | 83000 |  |
| CRA022008C4 | remuneracao BRECOACRAB97 | mult=100; taxa=1; taxa=4.2; taxa=5; taxa=7; taxa=75 | CDI 100% + 5,0000 % a.a. |  |
| CRA022008C4 | remuneracao BRECOACRABA8 | mult=100; taxa=1; taxa=4.2; taxa=5; taxa=7; taxa=75 | CDI 100% + 7,0000 % a.a. |  |
| CRA022009C1F | valor_total | 6000.00 | 229314000.00 |  |
| CRA022009C1F | quantidade | 82780; 162216; 205004; 244966; 244996; 450000 | 229314 |  |
| CRA022009VM | devedor | 09.346.601/0001-25; 10.830.108/0001-65; 17.118.468/0001-88; 22.610.500 | 31.943.818/0001-71 |  |
| CRA02300TBL | devedor | 00.405.805/0001-15; 02.392.738/0001-77; 06.116.723/0001-37; 33.866.324 | 27.490.581/0001-43 |  |
| CRA024007PW | quantidade | 113293; 114222 | 112232 |  |
| CRA02500C1D | vencimento BRECOACRALJ8 | 2030-12-18; 2032-12-17; 2035-12-19; lastro 2030-12-16; lastro 2032-12- | 2029-07-16 |  |
| CRA02500C1D | vencimento BRECOACRALK6 | 2030-12-18; 2032-12-17; 2035-12-19; lastro 2030-12-16; lastro 2032-12- | 2032-07-15 |  |
| CRA02500C1D | vencimento BRECOACRALL4 | 2030-12-18; 2032-12-17; 2035-12-19; lastro 2030-12-16; lastro 2032-12- | 2035-07-16 |  |
| CRA02500C1D | vencimento BRECOACRALM2 | 2030-12-18; 2032-12-17; 2035-12-19; lastro 2030-12-16; lastro 2032-12- | 2030-07-15 |  |
| CRA02500C1D | vencimento BRECOACRALN0 | 2030-12-18; 2032-12-17; 2035-12-19; lastro 2030-12-16; lastro 2032-12- | 2030-07-15 |  |
