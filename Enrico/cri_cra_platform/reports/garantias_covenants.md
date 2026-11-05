# Garantias e covenants por ativo

Extrator `garantias_covenants 0.1` sobre o texto do Termo de Securitização e dos aditamentos (`document_text_pages`). **Triagem, não parâmetro aprovado:** cada item traz documento, página e trecho literal para conferência; trecho de OCR precisa de conferência no PDF. Garantia *presente* = 2+ menções fora de frase negativa; *citada* = 1; *negada* = só em frase negativa.

Ativos com Termo ou aditamento lido: **67**.

| Garantia | Ativos (presente) |
|---|---|
| Alienação fiduciária de imóvel | 31 |
| Alienação fiduciária de ações ou quotas | 31 |
| Alienação fiduciária de bens móveis | 7 |
| Cessão fiduciária de recebíveis ou direitos | 51 |
| Fiança | 26 |
| Aval | 38 |
| Hipoteca | 6 |
| Penhor | 1 |
| Coobrigação | 18 |
| Garantia flutuante da securitizadora | 3 |
| Fundo de reserva | 35 |
| Fundo de liquidez, retenção ou amortização | 7 |
| Fundo de despesas | 53 |
| Seguro garantia ou de crédito | 3 |

| Covenant | Ativos (citado) | Com limite lido |
|---|---|---|
| Razão mínima de garantia / cobertura | 30 | 10 |
| LTV (saldo / valor da garantia) | 9 | 6 |
| Dívida líquida / EBITDA | 7 | 7 |
| EBITDA / despesa financeira | 0 | 0 |
| Liquidez corrente | 7 | 5 |
| Endividamento / patrimônio líquido | 1 | 0 |

## Por ativo

| Ativo | Tipo | Garantias presentes | Negadas | Covenants (limite) |
|---|---|---|---|---|
| 13D0358495 | CRI | Fundo de reserva | Garantia flutuante da securitizadora | — |
| 20H0225976 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Fiança, Coobrigação, Fundo de reserva, Seguro garantia ou de crédito | Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura |
| 20L0504499 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Fiança, Coobrigação, Fundo de reserva, Seguro garantia ou de crédito | — | Razão mínima de garantia / cobertura |
| 21A0870788 | CRI | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura |
| 21H0769214 | CRI | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Alienação fiduciária de bens móveis, Cessão fiduciária de recebíveis ou direitos, Fiança, Hipoteca, Coobrigação | Garantia flutuante da securitizadora | — |
| 21H1002745 | CRI | Alienação fiduciária de imóvel, Aval, Coobrigação, Fundo de reserva | Garantia flutuante da securitizadora | LTV (saldo / valor da garantia) |
| 21K0660418 | CRI | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Coobrigação, Garantia flutuante da securitizadora, Fundo de despesas | — | Razão mínima de garantia / cobertura |
| 21L0967403 | CRI | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura >= 115%, LTV (saldo / valor da garantia) |
| 22D0836679 | CRI | Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | — |
| 23C1835265 | CRI | Alienação fiduciária de imóvel, Cessão fiduciária de recebíveis ou direitos, Fiança, Aval, Hipoteca, Coobrigação, Fundo de reserva, Fundo de despesas | Garantia flutuante da securitizadora | LTV (saldo / valor da garantia) <= 70% |
| 23E2052239 | CRI | Alienação fiduciária de imóvel, Cessão fiduciária de recebíveis ou direitos, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | LTV (saldo / valor da garantia) |
| 23F1829746 | CRI | Coobrigação, Fundo de reserva, Fundo de despesas | — | LTV (saldo / valor da garantia) > 300 |
| 23F2454937 | CRI | Hipoteca, Garantia flutuante da securitizadora, Fundo de despesas | — | — |
| 23F2472075 | CRI | Cessão fiduciária de recebíveis ou direitos, Fiança, Fundo de despesas | Coobrigação | — |
| 23G1576657 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Fiança, Coobrigação, Fundo de reserva, Seguro garantia ou de crédito | Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura |
| 23H1097588 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Fiança, Fundo de reserva | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura |
| 23H1186528 | CRI | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Alienação fiduciária de bens móveis, Cessão fiduciária de recebíveis ou direitos, Fiança | Coobrigação | — |
| 23H1487992 | CRI | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Hipoteca, Fundo de reserva, Fundo de despesas | Coobrigação | — |
| 23H1753231 | CRI | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de reserva, Fundo de despesas | Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura |
| 23I0096173 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Fiança, Coobrigação, Fundo de reserva | Garantia flutuante da securitizadora | — |
| 23I1698089 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Fiança, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura |
| 23K2122788 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Fiança, Coobrigação, Fundo de reserva, Fundo de liquidez, retenção ou amortização, Fundo de despesas | Garantia flutuante da securitizadora | — |
| 24D3466320 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Fiança, Coobrigação, Fundo de reserva, Fundo de liquidez, retenção ou amortização | — | — |
| 24E2495042 | CRI | Alienação fiduciária de imóvel, Cessão fiduciária de recebíveis ou direitos, Aval | — | — |
| 24E2535171 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | — |
| 24G2100031 | CRI | Alienação fiduciária de imóvel, Cessão fiduciária de recebíveis ou direitos, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | LTV (saldo / valor da garantia) <= 60%, Dívida líquida / EBITDA <= 4.95x |
| 24J0943210 | CRI | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Alienação fiduciária de bens móveis, Cessão fiduciária de recebíveis ou direitos, Fiança, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | LTV (saldo / valor da garantia) <= 60% |
| 24L2327181 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura, Liquidez corrente |
| 25C3273266 | CRI | Alienação fiduciária de ações ou quotas, Aval, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura > 5 |
| 25F8582172 | CRI | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de reserva, Fundo de despesas | — | Razão mínima de garantia / cobertura >= 130% |
| 25K3156592 | CRI | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura > 140% |
| 25L2378911 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Fiança, Fundo de reserva, Fundo de despesas | Coobrigação, Fundo de liquidez, retenção ou amortização | Razão mínima de garantia / cobertura, Dívida líquida / EBITDA < 2 |
| 25L3279335 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura < 170%, Endividamento / patrimônio líquido |
| 26D2618959 | CRI | Alienação fiduciária de imóvel, Fiança, Aval, Coobrigação, Fundo de reserva, Fundo de despesas | Garantia flutuante da securitizadora | LTV (saldo / valor da garantia) <= 55% |
| 26D4402695 | CRI | Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Fiança, Coobrigação, Fundo de reserva, Fundo de liquidez, retenção ou amortização, Fundo de despesas | — | Razão mínima de garantia / cobertura > 135% |
| 26D7086699 | CRI | Alienação fiduciária de imóvel, Fundo de despesas | Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura < 1.30, LTV (saldo / valor da garantia) > 60% |
| 26F3681477 | CRI | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Coobrigação, Garantia flutuante da securitizadora, Fundo de reserva, Fundo de despesas | — | Razão mínima de garantia / cobertura |
| 26G2446032 | CRI | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | — |
| CRA01500002 | CRA | Aval | — | — |
| CRA019000XD | CRA | Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura |
| CRA019003V3 | CRA | — | — | — |
| CRA02000130 | CRA | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Fiança, Aval, Hipoteca, Coobrigação, Fundo de reserva, Fundo de despesas | Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura >= 50% |
| CRA020001P7 | CRA | Fiança, Fundo de despesas | Coobrigação | — |
| CRA020001P8 | CRA | Fiança, Fundo de despesas | Coobrigação | — |
| CRA02100001 | CRA | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Alienação fiduciária de bens móveis, Cessão fiduciária de recebíveis ou direitos, Fiança, Aval, Penhor, Coobrigação, Fundo de despesas | Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura |
| CRA021000S9 | CRA | Alienação fiduciária de imóvel, Cessão fiduciária de recebíveis ou direitos, Fiança, Fundo de reserva | Coobrigação, Garantia flutuante da securitizadora | — |
| CRA0210026F | CRA | Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | — |
| CRA022001JL | CRA | Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de liquidez, retenção ou amortização, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura, Liquidez corrente >= 0.90 |
| CRA022007VI | CRA | Cessão fiduciária de recebíveis ou direitos, Fiança, Aval, Fundo de despesas | — | — |
| CRA022008C4 | CRA | Alienação fiduciária de imóvel, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de liquidez, retenção ou amortização, Fundo de despesas | Coobrigação | — |
| CRA022009C1F | CRA | Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura, Dívida líquida / EBITDA <= 3.25, Liquidez corrente >= 1.1 |
| CRA022009VM | CRA | Alienação fiduciária de imóvel, Alienação fiduciária de bens móveis, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de liquidez, retenção ou amortização, Fundo de despesas | Coobrigação | Razão mínima de garantia / cobertura >= 70% |
| CRA023000040H | CRA | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de despesas | Coobrigação | — |
| CRA0230005N | CRA | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Cessão fiduciária de recebíveis ou direitos, Aval, Hipoteca, Fundo de despesas | Coobrigação | — |
| CRA023000B5 | CRA | Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura |
| CRA0230018I | CRA | Alienação fiduciária de imóvel, Cessão fiduciária de recebíveis ou direitos, Aval, Coobrigação, Fundo de reserva, Fundo de despesas | — | Razão mínima de garantia / cobertura <= 5 |
| CRA02300JR5 | CRA | Alienação fiduciária de imóvel, Alienação fiduciária de ações ou quotas, Alienação fiduciária de bens móveis, Cessão fiduciária de recebíveis ou direitos, Fiança, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | — |
| CRA02300TBL | CRA | Cessão fiduciária de recebíveis ou direitos, Fiança, Fundo de despesas | — | — |
| CRA02300VY3 | CRA | Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de despesas | Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura |
| CRA024000GP | CRA | Cessão fiduciária de recebíveis ou direitos, Fiança, Aval, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Dívida líquida / EBITDA <= 2.0x, Liquidez corrente |
| CRA024002S4 | CRA | Alienação fiduciária de imóvel, Aval, Fundo de despesas | Coobrigação | Razão mínima de garantia / cobertura |
| CRA024003PF | CRA | Alienação fiduciária de imóvel, Aval, Coobrigação, Fundo de despesas | — | — |
| CRA024004XT | CRA | Alienação fiduciária de imóvel, Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Liquidez corrente > 1.2 |
| CRA024006N5 | CRA | Alienação fiduciária de bens móveis, Cessão fiduciária de recebíveis ou direitos, Fiança, Aval, Fundo de reserva, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Dívida líquida / EBITDA <= 3.0x, Liquidez corrente >= 1.0x |
| CRA024007PW | CRA | Cessão fiduciária de recebíveis ou direitos, Aval, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Razão mínima de garantia / cobertura, Dívida líquida / EBITDA <= 1 |
| CRA02400E1M | CRA | Cessão fiduciária de recebíveis ou direitos, Fundo de liquidez, retenção ou amortização, Fundo de despesas | Coobrigação | Razão mínima de garantia / cobertura |
| CRA02500C1D | CRA | Aval, Fundo de despesas | Coobrigação, Garantia flutuante da securitizadora | Dívida líquida / EBITDA <= 3.0x, Liquidez corrente <= 3.0x |
