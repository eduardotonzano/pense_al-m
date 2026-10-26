# CRA Café Brasil (CRA022009VM): garantias e eventos de crédito

- Data: 2026-10-26
- Fontes (baixadas do Fundos.NET, SHA-256 em `document_versions`, texto por página em `document_text_pages`):
  Termo de Securitização 355426; Relatórios Anuais do Agente Fiduciário (Oliveira Trust)
  454117 (2022), 651262 (2023), 890020 (2024), 1175376 (2025); Fato Relevante 1074810.
- Parâmetros contratuais aprovados: `contract_parameters` (14, aprovados em 2026-10-26).
- Este documento reúne fatos com referência de página. Os cálculos marcados como **proposta**
  usam interpretações ainda não aprovadas.

## Evento de crédito (Fato Relevante 1074810, 02/01/2026, p.1)

- Em 30/12/2025 a devedora informou que não pagaria integralmente a parcela de juros e principal
  do CDCA vencida nessa data; pagou juros parcialmente em 31/12/2025 e pediu prazo até 30/01/2026.
- A securitizadora convocou Assembleia para 30/01/2026 para deliberar sobre o Vencimento
  Antecipado Automático do CDCA (Cláusula 4.2, inciso (i), do CDCA; Cláusula 5.12.7 do Termo) ou a
  repactuação da parcela.
- Coerente com os alertas já abertos: rentabilidade anômala em dez/2025 e jan/2026 e
  `Situacao = "Em atraso"` a partir de abr/2026 com campos de atraso zerados no Informe.

## Garantias segundo o Agente Fiduciário

| Data-base | Cessão Fiduciária | AF Estoque | AF Imóvel | Saldo devedor dos CRA (C) | Fonte |
|---|---|---|---|---|---|
| 31/12/2024 | R$ 4.420.160,88 (insuficiente) | R$ 56.633.612,77 (insuficiente) | R$ 46.148.975,04 (suficiente) | R$ 70.044.092,65 | 890020 p.2–3 |
| 31/12/2025 | R$ 2.243.443,20 (insuficiente) | R$ 37.884.631,95 (insuficiente) | R$ 49.980.777,00 (suficiente; laudo nov/2024) | R$ 30.926.620,08 | 1175376 p.2–3 |

Os relatórios de 2022 e 2023 não trazem valores de garantias; trazem a razão de lastro
(A+B)/C = 100,18% (2022) e 100,36% (2023).

## Confronto com os parâmetros aprovados (proposta de cálculo)

Interpretações pendentes: "valor nominal dos CRA" = saldo devedor (C) do AF; valores de 31/12
usados como aproximação da verificação de 15/12; saldo da Conta Garantia aproximado pelo
"saldo em conta" (B).

| Data-base | Soma das garantias + conta | Razão (mín. 120% set–dez) | Cessão Fiduciária (mín. R$ 65 mi em 15/12) |
|---|---|---|---|
| 31/12/2024 | R$ 107,31 mi | 153% | R$ 4,42 mi: **abaixo** do mínimo |
| 31/12/2025 | R$ 90,27 mi | 292% (com C do AF) / 226% (com saldo do Informe) | R$ 2,24 mi: **abaixo** do mínimo |

## Divergências entre documentos

1. **Garantias reais:** o Termo (p.41–42) e o AF listam alienação fiduciária de imóvel e de
   estoque; o Informe Mensal declara "não conta com garantias reais" e `VlrTotalGarantias = 0`.
2. **Data de vencimento:** Termo (p.33), Informe Mensal e AF 2022 trazem 30/09/2027; os AF de
   2023, 2024 e 2025 trazem 30/12/2026. Possível aditamento ausente do catálogo Fundos.NET.
3. **Saldo devedor em 31/12/2025:** AF R$ 30.926.620,08 (PU R$ 309,2662 × 100.000); Informe
   Mensal dez/2025 R$ 40.027.042,18. Em 31/12/2024 os dois conferem (R$ 70.044.092,65).
4. **Pagamentos em 2025:** o AF diz "não ocorreram pagamentos no período"; o Informe Mensal de
   dez/2025 registra pagamento sênior de R$ 57.226.190,28 e o Fato Relevante cita pagamento
   parcial de juros em 31/12/2025.
5. **Agente fiduciário:** o AF 2025 lista a Vórtx como custodiante e escrituradora e declara-se
   (Oliveira Trust) agente fiduciário, coerente com o Informe Mensal.

## Lacunas

- CDCA (covenants financeiros, hipóteses de vencimento antecipado) e eventuais aditamentos não
  estão no catálogo Fundos.NET do ativo.
- Resultado da Assembleia de 30/01/2026 não verificado (comunicados de jan–abr/2026 ainda não baixados).
