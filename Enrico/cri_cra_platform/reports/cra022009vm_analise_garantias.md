# CRA Café Brasil (CRA022009VM): garantias e eventos de crédito

- Data: 2026-10-26 (atualizado em 2026-10-27)
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
6. **Inadimplência em 31/03/2026:** as DFs auditadas do Patrimônio Separado (1232148 p.17) trazem
   R$ 7.089 mil "vencidos e não pagos"; o Informe Mensal de mar/2026 traz `DirCredVencidosNaoPagos = 0`,
   `VencidosNaoPagos/@total = 0` e `Situacao = "Adimplente"`. A parcela repactuada foi quitada em
   28/04/2026 (DFs p.18; ata 1189040).
7. **Encerramento e prazo:** as DFs (p.4) preveem o encerramento do Patrimônio Separado em 30/12/2026
   "conforme previsto no termo de securitização", coerente com os AF de 2023–2025 e divergente do
   Termo 355426 (30/09/2027). A mesma DF (p.20) informa prazo de 60 meses.
8. **Garantias nas DFs:** p.17 lista Aval, Cessão Fiduciária, AF de Imóvel e AF de Estoque, reforçando
   a divergência 1 com o Informe Mensal.

## Assembleias e comunicados 2025–2026

Fontes: 32 atas/editais (Ata/Edital) e 12 comunicados baixados; texto por página no banco.

| Data | Documento | Fato |
|---|---|---|
| 25/04 a 22/05/2025 | editais e termo de não instalação | AGT para **não** declarar vencimento antecipado por descumprimento da Recomposição de Garantia (itens xvi e xvii da Cl. 4.3 do CDCA); 1ª convocação sem quórum (17,08%) |
| 05/06/2025 | ata 918130 | Suspensa até 17/06 para análise de propostas da Devedora |
| 17/06/2025 | ata 927400 | Aprovada a não declaração (68,71%), **condicionada**: Razão 1º sem. ≥ 70% e 2º sem. ≥ 120% do Saldo Devedor; Direitos Creditórios + Conta Garantia ≥ R$ 10 mi no 2º sem.; verificação set–dez em 30/12; balancetes e calls trimestrais até dez/2025; dividendos limitados ao mínimo legal em 2025; CAPEX 2025 ≤ R$ 12 mi |
| 31/12/2025 | comunicado 1074300 | Pagamento parcial de juros: R$ 13.612.095,14 |
| 02/01/2026 | fato relevante 1074810 | Parcela de 30/12/2025 não paga integralmente; AGT convocada |
| 30/01 e 06/02/2026 | atas 1097871 e 1103828 | Suspensões; amortização extraordinária de R$ 15 mi (paga em 03/02) |
| 12/02/2026 | ata 1110477 | Não declaração do vencimento antecipado e repactuação aprovadas (72,09%), condicionadas a: mútuos novos ≤ R$ 39 mi em 2026 (a partir de jul); balancetes mensais; **amortização extraordinária de 10% do Saldo Devedor em 31/10/2026**; cash sweep |
| 26/02, 06/04 e 28/04/2026 | comunicados | Amortizações de R$ 10 mi, R$ 6,77 mi e R$ 0,55 mi |
| 13/05/2026 | ata 1189040 | Parcela repactuada, que deveria ser quitada até 31/03/2026, foi quitada em 28/04/2026; não declaração aprovada (73,87%). Covenants do CDCA (item xv da Cl. 4.3): Dívida Líquida/EBITDA ≤ 3x e liquidez corrente ≥ 1x |
| 15/05/2026 | ata 1194480 | Waiver dos índices financeiros (73,87%), condicionado a DFs auditadas até 30/05/2026 e **waiver fee de 0,5% do saldo devedor até 31/10/2026** |
| abr/2026 | editais e comunicado 1165691 | Assembleia especial sobre alteração de controle da Devedora (redesignada para 04/05/2026) |

As alterações de parâmetros acima estão em `contract_parameters`
(`config/contract_parameters/cra022009vm_assembleias_2025_2026.json`, 15 itens com âncora literal),
**aprovadas em 2026-10-27**. Os parâmetros originais do Termo que elas substituem valem até 16/06/2025.

### Avaliação com os parâmetros vigentes (regras 0.2.0, 2026-10-27)

| Data-base | Regra | Resultado |
|---|---|---|
| 31/12/2024 | Cessão Fiduciária ≥ R$ 65 mi (Termo) | R$ 4,42 mi: **abaixo** |
| 31/12/2025 | Direitos Creditórios + Conta Garantia ≥ R$ 10 mi (ata 927400) | R$ 2,40 mi: **abaixo** |
| 31/12/2025 | Razão de Garantia ≥ 120% do Saldo Devedor (ata 927400) | 292%: conforme |
| 31/10/2026 | Waiver fee 0,5% (ata 1194480) | prazo em 4 dias; cumprimento não verificado |
| 31/10/2026 | Amortização extraordinária 10% (ata 1110477) | prazo em 4 dias; cumprimento não verificado |
| 30/05/2026 | DFs auditadas da Devedora (ata 1194480) | prazo vencido; cumprimento não verificado |

O documento "Demonstrações Financeiras" 1232148 (publicado em 29/06/2026, baixado em 2026-10-27) é
das DFs do **Patrimônio Separado** (exercício findo em 31/03/2026, auditoria Grant Thornton), não da
Devedora: não comprova a entrega exigida pela ata 1194480. Os fatos lidos dele estão em
`config/reported_facts/cra022009vm_df_patrimonio_separado_2026.json` (6 fatos, **pendentes**,
valores em milhares de reais como publicados). A DF não constituiu provisão para perdas.

## Lacunas

- CDCA (covenants financeiros, hipóteses de vencimento antecipado) e eventuais aditamentos não
  estão no catálogo Fundos.NET do ativo.
- Resultado da Assembleia de 30/01/2026 não verificado (comunicados de jan–abr/2026 ainda não baixados).
