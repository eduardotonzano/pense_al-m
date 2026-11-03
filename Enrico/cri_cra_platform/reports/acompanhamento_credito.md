# Acompanhamento de crédito dos ativos do catálogo

Ordena por gravidade os sinais que a plataforma já tem: Informe Mensal da CVM, decisões das atas (regras de texto), DFs do patrimônio separado e contágio do devedor. **Triagem para leitura, não alerta:** cada motivo aponta a fonte, e as decisões de ata precisam ser conferidas na ata. Gerado por `scripts/build_credit_watchlist.py`.

| Nível | Situação | Ativos |
|---|---|---|
| 1 | evento grave nas atas | 11 |
| 2 | atraso no Informe | 33 |
| 3 | estresse recente | 6 |
| 4 | outros sinais | 15 |
| 5 | sem sinal | 5 |

| Nível | Ativo | Tipo | Securitizadora | Saldo (R$ mi) | Séries em atraso | Informe | Motivos |
|---|---|---|---|---|---|---|---|
| 1 | [CRA022008NB](fichas/cra022008nb.md) | CRA | OPEA SECURITIZADORA S.A | 2,428.4 | 2 | 2026-09 | ata de 2026-06-22: recuperacao judicial aprovado ; devedor com outras emissões em atraso ; Informe em 12 meses: entrou_em_atraso, saldo_caiu_sem_amortizacao ; ranking de triagem: 7 pontos |
| 1 | [CRA02300JR5](fichas/cra02300jr5.md) | CRA | OPEA SECURITIZADORA S.A | 1,109.8 | 2 | 2026-09 | ata de 2026-06-22: recuperacao judicial aprovado ; devedor com outras emissões em atraso ; Informe em 12 meses: entrou_em_atraso, saldo_caiu_sem_amortizacao ; ranking de triagem: 10 pontos |
| 1 | [CRA020001P7](fichas/cra020001p7.md) | CRA | OPEA SECURITIZADORA S.A | 516.5 | 1 | 2026-09 | ata de 2026-06-22: recuperacao judicial aprovado ; devedor com outras emissões em atraso ; Informe em 12 meses: entrou_em_atraso, saldo_caiu_sem_amortizacao, taxa_mudou, vencimento_mudou ; ranking de triagem: 7 pontos |
| 1 | [14L0157828](fichas/14l0157828.md) | CRI | RIZA II SECURITIZADORA S.A. | 487.2 | 4 | 2026-09 | ata de 2026-02-24: dacao em pagamento aprovado ; ranking de triagem: 5 pontos |
| 1 | [CRA02300TBL](fichas/cra02300tbl.md) | CRA | Eco Securitizadora de Direitos C | 421.4 | 2 | 2026-09 | ata de 2025-07-30: recuperacao judicial aprovado em bloco ; Informe em 12 meses: entrou_em_atraso ; ranking de triagem: 5 pontos |
| 1 | [CRA022009C1F](fichas/cra022009c1f.md) | CRA | Eco Securitizdora de Direitos Cr | 343.7 | 2 | 2026-09 | ata de 2025-11-07: recuperacao judicial aprovado ; ranking de triagem: 5 pontos |
| 1 | [CRA024002S4](fichas/cra024002s4.md) | CRA | CANAL COMPANHIA DE SECURITIZAÇÃO | 79.1 | 2 | 2026-09 | ata de 2024-11-25: vencimento antecipado declarado ; Informe em 12 meses: entrou_em_atraso, saldo_caiu_sem_amortizacao, vencimento_mudou ; ranking de triagem: 5 pontos |
| 1 | [CRA024006N5](fichas/cra024006n5.md) | CRA | CANAL COMPANHIA DE SECURITIZAÇÃO | 64.8 | 2 | 2026-09 | ata de 2026-10-20: recuperacao judicial aprovado ; atas em 12 meses: aporte titulares aprovado, vencimento antecipado nao declarado em bloco, waiver aprovado ; Informe em 12 meses: entrou_em_atraso, saldo_caiu_sem_amortizacao ; ranking de triagem: 5 pontos |
| 1 | [CRA023000B5](fichas/cra023000b5.md) | CRA | CANAL COMPANHIA DE SECURITIZAÇÃO | 52.6 | 1 | 2026-09 | ata de 2024-04-24: vencimento antecipado declarado ; atas em 12 meses: aporte titulares aprovado em bloco ; ranking de triagem: 5 pontos |
| 1 | [CRA024003PF](fichas/cra024003pf.md) | CRA | RIZA SECURITIZADORA S.A. | 40.3 | 0 | 2026-09 | ata de 2026-03-23: recuperacao judicial aprovado ; atas em 12 meses: prorrogacao repactuacao aprovado ; Informe em 12 meses: saldo_zerou ; ranking de triagem: 6 pontos |
| 1 | [21K0660418](fichas/21k0660418.md) | CRI | RIZA SECURITIZADORA S.A. | 2.7 | 0 | 2026-09 | ata de 2026-03-10: dacao em pagamento aprovado ; atas em 12 meses: aporte titulares aprovado ; Informe em 12 meses: saldo_caiu_sem_amortizacao, saldo_zerou ; ranking de triagem: 6 pontos |
| 2 | [CRA019003V3](fichas/cra019003v3.md) | CRA | OPEA SECURITIZADORA S.A | 1,400.1 | 2 | 2026-09 | 2 série(s) em atraso no Informe ; devedor com outras emissões em atraso ; Informe em 12 meses: entrou_em_atraso, saldo_caiu_sem_amortizacao ; ranking de triagem: 7 pontos |
| 2 | [CRA020001P8](fichas/cra020001p8.md) | CRA | OPEA SECURITIZADORA S.A | 1,068.2 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; devedor com outras emissões em atraso ; Informe em 12 meses: entrou_em_atraso, saldo_caiu_sem_amortizacao, taxa_mudou, vencimento_mudou ; ranking de triagem: 7 pontos |
| 2 | [20L0504499](fichas/20l0504499.md) | CRI | FORTE SECURITIZADORA S.A. | 935.5 | 6 | 2026-09 | 6 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso ; ranking de triagem: 5 pontos |
| 2 | [24D3466320](fichas/24d3466320.md) | CRI | FORTE SECURITIZADORA S.A. | 737.1 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso ; ranking de triagem: 8 pontos |
| 2 | [23I1698089](fichas/23i1698089.md) | CRI | BASE SECURITIZADORA S.A. | 721.2 | 2 | 2026-09 | 2 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso, vencimento_mudou ; ranking de triagem: 5 pontos |
| 2 | [23K2122788](fichas/23k2122788.md) | CRI | BASE SECURITIZADORA S.A. | 704.0 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso ; ranking de triagem: 8 pontos |
| 2 | [23C1835265](fichas/23c1835265.md) | CRI | FORTE SECURITIZADORA S.A. | 664.8 | 12 | 2026-09 | 12 série(s) em atraso no Informe ; devedor com outras emissões em atraso ; Informe em 12 meses: entrou_em_atraso ; ranking de triagem: 5 pontos |
| 2 | [23I0096173](fichas/23i0096173.md) | CRI | FORTE SECURITIZADORA S.A. | 616.4 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso ; ranking de triagem: 8 pontos |
| 2 | [20H0225976](fichas/20h0225976.md) | CRI | FORTE SECURITIZADORA S.A. | 609.8 | 8 | 2026-09 | 8 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso, saiu_do_atraso, vencimento_mudou ; ranking de triagem: 5 pontos |
| 2 | [24E2535171](fichas/24e2535171.md) | CRI | BASE SECURITIZADORA S.A. | 509.7 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso ; ranking de triagem: 8 pontos |
| 2 | [23H1097588](fichas/23h1097588.md) | CRI | BASE SECURITIZADORA S.A. | 469.3 | 3 | 2026-09 | 3 série(s) em atraso no Informe ; ranking de triagem: 8 pontos |
| 2 | [21H0769214](fichas/21h0769214.md) | CRI | FORTE SECURITIZADORA S.A. | 439.6 | 6 | 2026-09 | 6 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso, saiu_do_atraso, vencimento_mudou ; ranking de triagem: 5 pontos |
| 2 | [23G1576657](fichas/23g1576657.md) | CRI | FORTE SECURITIZADORA S.A. | 410.6 | 3 | 2026-09 | 3 série(s) em atraso no Informe ; DF: Com ressalva ; ranking de triagem: 8 pontos |
| 2 | [CRA0230005N](fichas/cra0230005n.md) | CRA | Eco Securitizdora de Direitos Cr | 212.2 | 2 | 2026-09 | 2 série(s) em atraso no Informe ; atas em 12 meses: prorrogacao repactuacao aprovado ; ranking de triagem: 5 pontos |
| 2 | [CRA022008C4](fichas/cra022008c4.md) | CRA | Eco Securitizdora de Direitos Cr | 122.7 | 3 | 2026-09 | 3 série(s) em atraso no Informe ; atas em 12 meses: prorrogacao repactuacao aprovado, prorrogacao repactuacao aprovado em bloco, vencimento antecipado nao declarado, vencimento antecipado nao declarado em bloco, waiver aprovado ; devedor com outras emissões em atraso ; Informe em 12 meses: entrou_em_atraso, saldo_caiu_sem_amortizacao ; ranking de triagem: 5 pontos |
| 2 | [CRA023000040H](fichas/cra023000040h.md) | CRA | Eco Securitizdora de Direitos Cr | 122.2 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; atas em 12 meses: vencimento antecipado nao declarado ; Informe em 12 meses: entrou_em_atraso ; ranking de triagem: 5 pontos |
| 2 | [CRA024007PW](fichas/cra024007pw.md) | CRA | Vert Companhia Securitizadora | 118.3 | 2 | 2026-09 | 2 série(s) em atraso no Informe ; atas em 12 meses: prorrogacao repactuacao aprovado ; Informe em 12 meses: entrou_em_atraso ; ranking de triagem: 5 pontos |
| 2 | [CRA01500002](fichas/cra01500002.md) | CRA | Eco Securitizdora de Direitos Cr | 100.8 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; devedor com outras emissões em atraso ; ranking de triagem: 5 pontos |
| 2 | [CRA0230018I](fichas/cra0230018i.md) | CRA | CANAL COMPANHIA DE SECURITIZAÇÃO | 96.0 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso ; ranking de triagem: 5 pontos |
| 2 | [CRA022001JL](fichas/cra022001jl.md) | CRA | Eco Securitizdora de Direitos Cr | 87.9 | 2 | 2026-09 | 2 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso ; ranking de triagem: 5 pontos |
| 2 | [CRA02300VY3](fichas/cra02300vy3.md) | CRA | CANAL COMPANHIA DE SECURITIZAÇÃO | 85.3 | 2 | 2026-09 | 2 série(s) em atraso no Informe ; atas em 12 meses: waiver aprovado ; Informe em 12 meses: entrou_em_atraso, vencimento_mudou ; ranking de triagem: 5 pontos |
| 2 | [CRA02400E1M](fichas/cra02400e1m.md) | CRA | Eco Securitizdora de Direitos Cr | 76.7 | 3 | 2026-09 | 3 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso ; ranking de triagem: 5 pontos |
| 2 | [CRA02000130](fichas/cra02000130.md) | CRA | FORTE SECURITIZADORA S.A. | 72.1 | 2 | 2026-09 | 2 série(s) em atraso no Informe ; DF: Com ressalva ; ranking de triagem: 5 pontos |
| 2 | [CRA024004XT](fichas/cra024004xt.md) | CRA | OPEA SECURITIZADORA S.A | 63.3 | 2 | 2026-09 | 2 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso, saldo_caiu_sem_amortizacao ; ranking de triagem: 5 pontos |
| 2 | [23E2052239](fichas/23e2052239.md) | CRI | OPEA SECURITIZADORA S.A | 59.4 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso, saiu_do_atraso, saldo_zerou ; ranking de triagem: 7 pontos |
| 2 | [CRA022009VM](fichas/cra022009vm.md) | CRA | Eco Securitizadora de Direitos C | 45.7 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; atas em 12 meses: prorrogacao repactuacao aprovado, vencimento antecipado nao declarado, waiver aprovado ; devedor com outras emissões em atraso ; Informe em 12 meses: entrou_em_atraso, saldo_caiu_sem_amortizacao ; ranking de triagem: 7 pontos |
| 2 | [25F8582172](fichas/25f8582172.md) | CRI | CANAL COMPANHIA DE SECURITIZAÇÃO | 42.6 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; Informe em 12 meses: saldo_caiu_sem_amortizacao ; ranking de triagem: 8 pontos |
| 2 | [21H1002745](fichas/21h1002745.md) | CRI | OPEA Securitizadora S.A. | 32.6 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; Informe em 12 meses: entrou_em_atraso, saiu_do_atraso, saldo_caiu_sem_amortizacao, vencimento_mudou ; ranking de triagem: 8 pontos |
| 2 | [13D0358495](fichas/13d0358495.md) | CRI | Travessia Securitizadora S.A | 27.8 | 2 | 2026-09 | 2 série(s) em atraso no Informe ; DF: Com ressalva ; ranking de triagem: 7 pontos |
| 2 | [23F1829746](fichas/23f1829746.md) | CRI | Companhia Província de Securitiz | 18.6 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; Informe em 12 meses: saldo_caiu_sem_amortizacao ; ranking de triagem: 8 pontos |
| 2 | [24L2327181](fichas/24l2327181.md) | CRI | RIZA SECURITIZADORA S.A. | 15.6 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; ranking de triagem: 8 pontos |
| 2 | [15L0790665](fichas/15l0790665.md) | CRI | RIZA SECURITIZADORA S.A. | 12.9 | 2 | 2026-09 | 2 série(s) em atraso no Informe ; Informe em 12 meses: saldo_caiu_sem_amortizacao ; ranking de triagem: 7 pontos |
| 2 | [22D0836679](fichas/22d0836679.md) | CRI | OPEA SECURITIZADORA S.A | 10.4 | 1 | 2026-09 | 1 série(s) em atraso no Informe ; devedor com outras emissões em atraso ; Informe em 12 meses: entrou_em_atraso, saldo_caiu_sem_amortizacao, taxa_mudou ; ranking de triagem: 7 pontos |
| 3 | [CRA02500C1D](fichas/cra02500c1d.md) | CRA | Eco Securitizadora de Direitos C | 785.5 | 0 | 2026-09 | devedor com outras emissões em atraso ; ranking de triagem: 2 pontos |
| 3 | [21L0967403](fichas/21l0967403.md) | CRI | HABITASEC SECURITIZADORA S.A. | 103.3 | 0 | 2026-09 | atas em 12 meses: prorrogacao repactuacao aprovado em bloco, vencimento antecipado nao declarado em bloco ; Informe em 12 meses: taxa_mudou, vencimento_mudou ; ranking de triagem: 7 pontos |
| 3 | [21A0870788](fichas/21a0870788.md) | CRI | Companhia Província de Securitiz | 90.2 | 0 | 2026-09 | atas em 12 meses: prorrogacao repactuacao aprovado em bloco, vencimento antecipado nao declarado, vencimento antecipado nao declarado em bloco ; Informe em 12 meses: saldo_caiu_sem_amortizacao, saldo_zerou ; ranking de triagem: 6 pontos |
| 3 | [23F2472075](fichas/23f2472075.md) | CRI | OPEA Securitizadora S.A. | 25.3 | 0 | 2026-09 | atas em 12 meses: vencimento antecipado nao declarado, waiver aprovado ; Informe em 12 meses: entrou_em_atraso, saiu_do_atraso, saldo_caiu_sem_amortizacao |
| 3 | [23H1753231](fichas/23h1753231.md) | CRI | HABITASEC SECURITIZADORA S.A. | 18.1 | 0 | 2026-09 | atas em 12 meses: vencimento antecipado nao declarado em bloco ; Informe em 12 meses: taxa_mudou, vencimento_mudou |
| 3 | [24E2495042](fichas/24e2495042.md) | CRI | Leverage Companhia Securitizador | 11.0 | 0 | 2026-09 | atas em 12 meses: prorrogacao repactuacao aprovado em bloco ; Informe em 12 meses: saldo_zerou, taxa_mudou, vencimento_mudou ; ranking de triagem: 2 pontos |
| 4 | [23F2454937](fichas/23f2454937.md) | CRI | OPEA Securitizadora S.A. | 947.7 | 0 | 2026-09 | Informe em 12 meses: saldo_caiu_sem_amortizacao, saldo_zerou, vencimento_mudou ; ranking de triagem: 2 pontos |
| 4 | [23H1186528](fichas/23h1186528.md) | CRI | OPEA Securitizadora S.A. | 352.1 | 0 | 2026-09 | Informe em 12 meses: saldo_zerou ; ranking de triagem: 4 pontos |
| 4 | [24J0943210](fichas/24j0943210.md) | CRI | OPEA SECURITIZADORA S.A | 202.4 | 0 | 2026-09 | Informe em 12 meses: saldo_caiu_sem_amortizacao ; ranking de triagem: 5 pontos |
| 4 | [CRA024000GP](fichas/cra024000gp.md) | CRA | OPEA Securitizadora S.A. | 150.2 | 0 | 2026-09 | Informe em 12 meses: entrou_em_atraso, saiu_do_atraso, saldo_caiu_sem_amortizacao, saldo_zerou, taxa_mudou |
| 4 | [CRA021000S9](fichas/cra021000s9.md) | CRA | RIZA SECURITIZADORA S.A. | 115.3 | 0 | 2026-09 | Informe em 12 meses: saldo_zerou ; ranking de triagem: 6 pontos |
| 4 | [CRA02100001](fichas/cra02100001.md) | CRA | RIZA SECURITIZADORA S.A. | 95.4 | 0 | 2026-09 | Informe em 12 meses: saldo_caiu_sem_amortizacao, saldo_zerou ; ranking de triagem: 6 pontos |
| 4 | [CRA019000XD](fichas/cra019000xd.md) | CRA | RIZA SECURITIZADORA S.A. | 65.4 | 0 | 2026-09 | Informe em 12 meses: saldo_caiu_sem_amortizacao ; ranking de triagem: 6 pontos |
| 4 | [23H1487992](fichas/23h1487992.md) | CRI | OPEA Securitizadora S.A. | 41.7 | 0 | 2026-09 | Informe em 12 meses: saiu_do_atraso, saldo_zerou, vencimento_mudou |
| 4 | [26D2618959](fichas/26d2618959.md) | CRI | Leverage Companhia Securitizador | 35.8 | 0 | 2026-09 | Informe em 12 meses: vencimento_mudou |
| 4 | [CRA022007VI](fichas/cra022007vi.md) | CRA | RIZA SECURITIZADORA S.A. | 29.3 | 0 | 2026-09 | Informe em 12 meses: saldo_caiu_sem_amortizacao ; ranking de triagem: 4 pontos |
| 4 | [25K3156592](fichas/25k3156592.md) | CRI | Leverage Companhia Securitizador | 20.0 | 0 | 2026-09 | Informe em 12 meses: saldo_caiu_sem_amortizacao |
| 4 | [26D4402695](fichas/26d4402695.md) | CRI | Leverage Companhia Securitizador | 19.7 | 0 | 2026-09 | Informe em 12 meses: saldo_caiu_sem_amortizacao |
| 4 | [26G2446032](fichas/26g2446032.md) | CRI | Leverage Companhia Securitizador | 9.0 | 0 | 2026-09 | ranking de triagem: 2 pontos |
| 4 | [26F3681477](fichas/26f3681477.md) | CRI | Leverage Companhia Securitizador | 7.9 | 0 | 2026-09 | Informe em 12 meses: taxa_mudou ; ranking de triagem: 2 pontos |
| 4 | [CRA0210026F](fichas/cra0210026f.md) | CRA | RIZA SECURITIZADORA S.A. | 0.0 | 0 | 2026-08 | Informe em 12 meses: saldo_caiu_sem_amortizacao, saldo_zerou |
| 5 | [26D7086699](fichas/26d7086699.md) | CRI | Leverage Companhia Securitizador | 70.7 | 0 | 2026-09 |  |
| 5 | [25C3273266](fichas/25c3273266.md) | CRI | Leverage Companhia Securitizador | 44.7 | 0 | 2026-09 |  |
| 5 | [25L2378911](fichas/25l2378911.md) | CRI | Leverage Companhia Securitizador | 30.1 | 0 | 2026-09 |  |
| 5 | [25L3279335](fichas/25l3279335.md) | CRI | Leverage Companhia Securitizador | 7.1 | 0 | 2026-09 |  |
| 5 | [24G2100031](fichas/24g2100031.md) | CRI | Opea Securitizadora S.A. | 0.0 | 0 | 2026-09 |  |
