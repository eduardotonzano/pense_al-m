# Fichas contratuais

Uma ficha por ativo com Termo ou aditamento baixado: o trecho literal de cada um dos 36 campos padrão, com documento e página, o parâmetro aprovado (quando há) e a comparação do Termo com o Informe da CVM. Material de leitura para a revisão humana; nada aqui é parâmetro aprovado. Gerado por `scripts/build_contract_sheets.py`.

**Qualidade nos parâmetros aprovados (datas, valores em R$, quantidades e taxas):** em 46 de 55 (84%) o valor aprovado aparece escrito nas páginas que a ficha mostra para o campo.

Pela página: em 96 de 195 (49%) a página da evidência aprovada está dentro das páginas mostradas (tolerância de 1 página). A medida é estrita: a ficha prefere o texto mais recente (Termo consolidado do aditamento) e a lista de características, e a evidência aprovada muitas vezes está no Termo original ou na cláusula detalhada, com o mesmo valor.

| Ativo | Tipo | Docs | Páginas | OCR | Campos com trecho | Essenciais | Aprovados | Essenciais sem trecho |
|---|---|---|---|---|---|---|---|---|
| [13D0358495](13d0358495.md) | CRI | 1 | 45 |  | 18/36 | 13/23 |  | isin, numero_emissao, devedor, periodicidade, razao_minima, fundo_despesas, indices_financeiros, hipoteses, limites_e_prazos, ordem_pagamentos |
| [20H0225976](20h0225976.md) | CRI | 2 | 250 |  | 29/36 | 18/23 |  | isin, devedor, classe_serie, fundo_despesas, indices_financeiros |
| [20L0504499](20l0504499.md) | CRI | 4 | 430 |  | 30/36 | 20/23 |  | isin, fundo_despesas, indices_financeiros |
| [21A0870788](21a0870788.md) | CRI | 8 | 719 | 18 | 35/36 | 22/23 |  | classe_serie |
| [21H0769214](21h0769214.md) | CRI | 2 | 371 |  | 31/36 | 19/23 |  | isin, classe_serie, razao_minima, fundo_despesas |
| [21H1002745](21h1002745.md) | CRI | 4 | 588 |  | 29/36 | 20/23 |  | isin, limites_e_prazos, ordem_pagamentos |
| [21K0660418](21k0660418.md) | CRI | 5 | 346 |  | 31/36 | 20/23 |  | isin, classe_serie, indices_financeiros |
| [21L0967403](21l0967403.md) | CRI | 2 | 274 |  | 31/36 | 20/23 |  | isin, indices_financeiros, rating |
| [22D0836679](22d0836679.md) | CRI | 1 | 152 |  | 33/36 | 21/23 |  | isin, ordem_pagamentos |
| [23C1835265](23c1835265.md) | CRI | 5 | 611 |  | 32/36 | 21/23 |  | isin, classe_serie |
| [23E2052239](23e2052239.md) | CRI | 3 | 460 |  | 32/36 | 21/23 |  | classe_serie, indices_financeiros |
| [23F1829746](23f1829746.md) | CRI | 7 | 993 |  | 25/36 | 18/23 |  | isin, devedor, classe_serie, limites_e_prazos, ordem_pagamentos |
| [23F2454937](23f2454937.md) | CRI | 3 | 752 |  | 31/36 | 20/23 |  | classe_serie, amortizacao, razao_minima |
| [23F2472075](23f2472075.md) | CRI | 2 | 191 |  | 35/36 | 22/23 |  | isin |
| [23G1576657](23g1576657.md) | CRI | 3 | 652 |  | 29/36 | 19/23 |  | isin, devedor, classe_serie, fundo_despesas |
| [23H1097588](23h1097588.md) | CRI | 2 | 179 |  | 30/36 | 19/23 |  | isin, devedor, classe_serie, fundo_despesas |
| [23H1186528](23h1186528.md) | CRI | 4 | 302 |  | 29/36 | 19/23 |  | classe_serie, amortizacao, razao_minima, fundo_despesas |
| [23H1487992](23h1487992.md) | CRI | 4 | 96 |  | 31/36 | 19/23 |  | isin, classe_serie, razao_minima, indices_financeiros |
| [23H1753231](23h1753231.md) | CRI | 3 | 111 |  | 27/36 | 18/23 |  | isin, classe_serie, indices_financeiros, limites_e_prazos, ordem_pagamentos |
| [23I0096173](23i0096173.md) | CRI | 2 | 121 |  | 28/36 | 18/23 |  | isin, devedor, classe_serie, razao_minima, fundo_despesas |
| [23I1698089](23i1698089.md) | CRI | 2 | 314 |  | 29/36 | 20/23 |  | isin, devedor, classe_serie |
| [23K2122788](23k2122788.md) | CRI | 4 | 227 |  | 28/36 | 19/23 |  | isin, classe_serie, razao_minima, hipoteses |
| [24D3466320](24d3466320.md) | CRI | 2 | 151 |  | 30/36 | 19/23 |  | isin, devedor, classe_serie, razao_minima |
| [24E2495042](24e2495042.md) | CRI | 2 | 18 |  | 11/36 | 7/23 |  | isin, lastro, classe_serie, valor_total, valor_nominal_unitario, quantidade_titulos, periodicidade, amortizacao, razao_minima, fundo_despesas, indices_financeiros, hipoteses, limites_e_prazos, dfs_e_relatorios, rating, ordem_pagamentos |
| [24E2535171](24e2535171.md) | CRI | 3 | 130 |  | 29/36 | 20/23 |  | isin, classe_serie, razao_minima |
| [24G2100031](24g2100031.md) | CRI | 2 | 195 |  | 35/36 | 22/23 | 94 | classe_serie |
| [24J0943210](24j0943210.md) | CRI | 2 | 263 |  | 31/36 | 21/23 |  | classe_serie, ordem_pagamentos |
| [24L2327181](24l2327181.md) | CRI | 3 | 380 |  | 33/36 | 20/23 |  | isin, classe_serie, ordem_pagamentos |
| [25C3273266](25c3273266.md) | CRI | 3 | 158 |  | 34/36 | 21/23 |  | isin, classe_serie |
| [25F8582172](25f8582172.md) | CRI | 1 | 188 |  | 31/36 | 20/23 |  | devedor, classe_serie, ordem_pagamentos |
| [25K3156592](25k3156592.md) | CRI | 2 | 152 |  | 32/36 | 20/23 |  | classe_serie, indices_financeiros, ordem_pagamentos |
| [25L2378911](25l2378911.md) | CRI | 2 | 158 |  | 32/36 | 22/23 |  | classe_serie |
| [25L3279335](25l3279335.md) | CRI | 2 | 216 |  | 31/36 | 22/23 |  | classe_serie |
| [26D2618959](26d2618959.md) | CRI | 4 | 936 |  | 33/36 | 22/23 |  | classe_serie |
| [26D4402695](26d4402695.md) | CRI | 1 | 252 |  | 34/36 | 21/23 |  | isin, classe_serie |
| [26D7086699](26d7086699.md) | CRI | 1 | 116 |  | 28/36 | 20/23 |  | classe_serie, amortizacao, indices_financeiros |
| [26F3681477](26f3681477.md) | CRI | 2 | 332 |  | 32/36 | 20/23 |  | isin, classe_serie, ordem_pagamentos |
| [26G2446032](26g2446032.md) | CRI | 2 | 321 |  | 33/36 | 21/23 |  | isin, razao_minima |
| [CRA01500002](cra01500002.md) | CRA | 1 | 9 |  | 5/36 | 4/23 |  | isin, devedor, classe_serie, valor_total, valor_nominal_unitario, quantidade_titulos, taxa, periodicidade, amortizacao, descricao, razao_minima, fundo_despesas, indices_financeiros, hipoteses, limites_e_prazos, facultativo, dfs_e_relatorios, rating, ordem_pagamentos |
| [CRA019000XD](cra019000xd.md) | CRA | 1 | 114 |  | 32/36 | 22/23 |  | classe_serie |
| [CRA019003V3](cra019003v3.md) | CRA | 1 | 9 |  | 3/36 | 1/23 |  | isin, devedor, lastro, classe_serie, data_emissao, data_vencimento, valor_total, valor_nominal_unitario, quantidade_titulos, taxa, periodicidade, amortizacao, descricao, razao_minima, fundo_despesas, indices_financeiros, hipoteses, limites_e_prazos, facultativo, dfs_e_relatorios, rating, ordem_pagamentos |
| [CRA02000130](cra02000130.md) | CRA | 2 | 139 |  | 29/36 | 21/23 |  | isin, indices_financeiros |
| [CRA020001P7](cra020001p7.md) | CRA | 1 | 217 |  | 31/36 | 20/23 |  | classe_serie, razao_minima, indices_financeiros |
| [CRA020001P8](cra020001p8.md) | CRA | 1 | 217 |  | 31/36 | 20/23 |  | classe_serie, razao_minima, indices_financeiros |
| [CRA02100001](cra02100001.md) | CRA | 4 | 2002 |  | 33/36 | 22/23 |  | classe_serie |
| [CRA021000S9](cra021000s9.md) | CRA | 3 | 306 |  | 33/36 | 20/23 |  | isin, razao_minima, fundo_despesas |
| [CRA0210026F](cra0210026f.md) | CRA | 2 | 262 |  | 31/36 | 19/23 |  | isin, classe_serie, amortizacao, razao_minima |
| [CRA022001JL](cra022001jl.md) | CRA | 2 | 254 |  | 34/36 | 22/23 |  | isin |
| [CRA022007VI](cra022007vi.md) | CRA | 1 | 238 |  | 29/36 | 20/23 |  | isin, devedor, razao_minima |
| [CRA022008C4](cra022008c4.md) | CRA | 1 | 150 |  | 31/36 | 21/23 |  | isin, razao_minima |
| [CRA022009C1F](cra022009c1f.md) | CRA | 2 | 259 |  | 32/36 | 21/23 |  | classe_serie, amortizacao |
| [CRA022009VM](cra022009vm.md) | CRA | 1 | 137 |  | 33/36 | 21/23 | 10 | isin, classe_serie |
| [CRA023000040H](cra023000040h.md) | CRA | 2 | 260 |  | 26/36 | 17/23 |  | isin, classe_serie, quantidade_titulos, razao_minima, indices_financeiros, ordem_pagamentos |
| [CRA0230005N](cra0230005n.md) | CRA | 2 | 343 |  | 31/36 | 19/23 |  | isin, classe_serie, razao_minima, indices_financeiros |
| [CRA023000B5](cra023000b5.md) | CRA | 2 | 135 |  | 32/36 | 21/23 |  | isin, classe_serie |
| [CRA0230018I](cra0230018i.md) | CRA | 1 | 109 |  | 32/36 | 20/23 |  | isin, classe_serie, indices_financeiros |
| [CRA02300JR5](cra02300jr5.md) | CRA | 2 | 656 |  | 30/36 | 19/23 |  | classe_serie, amortizacao, razao_minima, indices_financeiros |
| [CRA02300TBL](cra02300tbl.md) | CRA | 3 | 1077 |  | 30/36 | 20/23 |  | isin, classe_serie, razao_minima |
| [CRA02300VY3](cra02300vy3.md) | CRA | 6 | 579 |  | 32/36 | 20/23 |  | isin, classe_serie, indices_financeiros |
| [CRA024000GP](cra024000gp.md) | CRA | 3 | 174 |  | 32/36 | 21/23 |  | classe_serie, razao_minima |
| [CRA024002S4](cra024002s4.md) | CRA | 3 | 301 |  | 32/36 | 22/23 |  | classe_serie |
| [CRA024003PF](cra024003pf.md) | CRA | 2 | 322 |  | 25/36 | 18/23 |  | isin, devedor, classe_serie, razao_minima, indices_financeiros |
| [CRA024004XT](cra024004xt.md) | CRA | 3 | 542 |  | 34/36 | 22/23 |  | isin |
| [CRA024006N5](cra024006n5.md) | CRA | 2 | 294 |  | 31/36 | 20/23 |  | isin, classe_serie, razao_minima |
| [CRA024007PW](cra024007pw.md) | CRA | 2 | 428 |  | 34/36 | 22/23 |  | classe_serie |
| [CRA02400E1M](cra02400e1m.md) | CRA | 1 | 139 |  | 28/36 | 19/23 |  | isin, devedor, indices_financeiros, rating |
| [CRA02500C1D](cra02500c1d.md) | CRA | 2 | 337 |  | 33/36 | 22/23 | 91 | razao_minima |
