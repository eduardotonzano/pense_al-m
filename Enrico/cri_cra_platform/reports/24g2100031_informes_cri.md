# CRI Almeida Junior (24G2100031 / BRRBRACRIP13): extração dos Informes Mensais

- Data: 2026-10-27
- Mapeamento: `config/xml_mappings/informe_mensal_cri.json` `cri-0.1.1` (aprovado em 2026-10-27,
  derivado do CRA 0.1.1). 26 informes (ago/2024–set/2026), todos na versão 1; 26 extrações sem falha.
- Decisões de 2026-10-27: regra de escala usa `Passivo/VlrAtualizadoEmissao`; `VlrTotalCreditosRelacaoVlrTotalEmissao`
  como fração; `DurationCarteira` segue só literal; set/2026 tratado como erro de preenchimento.
- Revisão dos relatórios: `reports/report_review_informe_mensal_cri_cri-0.1.1.csv`: 25 aprovados, set/2026 rejeitado.
- Golden set: `config/golden_sets/informe_mensal_cri_almeida_junior.json` (17 itens, aprovados);
  conferência extração × golden: 17/17.
- Comparação entre períodos: `reports/24g2100031_mudancas_entre_periodos.csv` e `reports/24g2100031_serie_indicadores.csv`.
- Alertas de qualidade (`config/alert_rules/data_quality_informe_mensal_cri.json` cri-0.1.0, aprovado):
  6 abertos em `reports/24g2100031_alertas_qualidade.csv`: rentabilidade 0 em ago/2024 (primeiro mês, operação
  iniciada em 29/08) e 5 conciliações de saldo com resíduo de 0,10%–0,12% (fev, jul, ago, nov/2025 e ago/2026),
  quatro delas em meses com saldo exatamente R$ 230 mi (PU voltando a 1.000 após o pagamento).

## Estrutura (Informe)

Série única Sênior, 230.000 CRI, VNU R$ 1.000, emissão 29/08/2024, vencimento 29/08/2036,
"100% CDI + 1,5% a.a."; lastro: debênture (título de dívida); securitizadora Opea; AF e custodiante Vórtx.

## Achados

1. **`totalVlrCertificados` traz o PU, não o saldo.** 1000.45 em ago/2024; 230.000 × 1000.45 =
   230.103.500 ≈ `Passivo/VlrAtualizadoEmissao` 230.103.915,66. Em `cri-0.1.0` a regra `monetary_scale_suspect` disparava em 25 meses; **decidido** usar o saldo do passivo (`cri-0.1.1`).
2. **Set/2026 (doc 1357521) inconsistente.** `DadosGerais/Series` vazio, carteira (`CreditosTotais`) e
   passivo zerados, ativo R$ 6.936,55 (só caixa); no mesmo informe, 230.000 CRI, PU 1000.56,
   rendimentos R$ 2.652.679,24 e pagamentos sênior 0. Nenhum documento do catálogo trata de resgate
   ou vencimento antecipado; as DFs de 30/06/2026 (1298856 p.14) mostram 230.000 CRI e R$ 230.134 mil.
3. **`Ativo/@total` de set/2026:** `6936.55` contra a soma das folhas `6936.54999999999` (literal no XML),
   warning de 1E-11.
4. **`VlrTotalCreditosRelacaoVlrTotalEmissao` = 1** em todos os meses: indica fração. Hoje `pending_decision`.
5. **`DurationCarteira`** sem unidade e errática (4,31 → 1,23 → 4,24 em ago–out/2025; 4,04 → 6,11 → 6,04 → 3,94
   em mar–jun/2026). Segue `pending_decision`.
6. **`MesBaseApuracaoPagtoRemunAmort`** = número de série de data do Excel (45535 = 2024-08-31), literal mantido.
7. **ISIN com espaço final** (`"BRRBRACRIP13 "`) em 12 informes; literal mantido.
8. **`MaiorDevedor` = 0** em todos os meses, com devedor único.
9. Pagamentos sênior iguais aos rendimentos distribuídos, exceto em dez/2025 (pagamentos 2.824.303,17;
   rendimentos 2.966.425,23), jan/2026 (3.108.634,46; 2.966.425,23) e set/2026 (0; 2.652.679,24).
   Amortização 0 em todos os meses.

## Documentos (Termo, AF, DFs, atas)

- Parâmetros: `config/contract_parameters/24g2100031_termo_722251.json` (94, **aprovados em 2026-10-27**; 11 do
  Primeiro Aditamento 722252, vigentes desde 2024-08-08). Fatos:
  `config/reported_facts/24g2100031_documentos_2024_2026.json` (105, **aprovados em 2026-10-27**).
- O Relatório do AF de 2024 (892072, 199 páginas) não tem texto extraível (PDF em imagem): nenhum fato dele.

### Estrutura (Termo 722251 + Aditamento 722252)

- Série única, sem subordinação; 230.000 CRI, VNU R$ 1.000; emissão 29/08/2024, vencimento 29/08/2036.
  Lastro: debêntures da 4ª emissão da Almeida Junior (vencimento 27/08/2036), via CCI.
- Remuneração: 100% DI + 1,50% a.a. até 29/08/2030 (exclusive) e + 2,75% a.a. depois (Aditamento;
  o Termo original dizia "até o 72º mês").
- Juros mensais desde 30/09/2024; amortização mensal de 29/09/2027 a 29/08/2036.
- Garantias: alienação fiduciária de 88,24% do Shopping Neumarkt (LTV máx. 60%, anual, sobre DFs
  consolidadas da Devedora); cessão fiduciária de recebíveis de locação sob condição suspensiva
  (ICSD mín. 1,20x, trimestral). Sem fiança, aval, fundo de reserva ou de liquidez. Fundo de despesas
  de 12 meses de despesas recorrentes, sem valor em reais no Termo.
- Sem covenant financeiro de manutenção; limite de endividamento de R$ 1,25 bi (IPCA desde 2021),
  excedível com Dívida Líquida/EBITDA ≤ 4,95x pro forma após registro na categoria A.
- Vencimento antecipado: 10 hipóteses automáticas e 22 não automáticas (inclui ICSD, LTV, endividamento,
  cross-default ≥ R$ 25 MM).
- Resgate total e amortização extraordinária (até 98%) facultativos a partir de 29/08/2026 (Aditamento;
  original 2027), com prêmio decrescente.

### Divergências

1. **Garantias não constituídas:** o AF 2025 (1172041 p.7) marca a alienação fiduciária e a cessão
   fiduciária como "NÃO" constituídas, coerente com o Informe (`VlrTotalGarantias = 0`); as DFs de 2025 e
   2026 dizem que a emissão "conta com" essas garantias.
2. **Rating:** o Termo exige rating anual da Fitch (preliminar AA-(EXP)sf(bra), 29/07/2024, comunicado
   725619); o AF 2025 e as duas DFs dizem que não há rating contratado. Possível descumprimento.
3. **Remuneração:** AF e Informe trazem só "CDI + 1,5%", sem o step-up para 2,75% em 29/08/2030.
4. **Datas do lastro:** step-up e vencimento das debêntures em 27/08 contra 29/08 dos CRI; 1º pagamento
   26/09/2024 no AF contra 30/09/2024 no Anexo III do Termo.
5. **DF 2025:** resgate facultativo "a partir de 29/08/2027" (ignora o Aditamento); início da operação
   19/08/2024 no relatório do auditor contra 29/08/2024 nas demonstrações.
6. **Auditor:** Grant Thornton nas DFs de 2025; CLA nas de 30/06/2026.
7. **Assembleias:** o AF 2025 diz que não houve assembleias; houve convocações em dez/2025 não instaladas.
8. **Set/2026:** nenhum documento aponta resgate; DFs de 30/06/2026 com CRI de R$ 230.134 mil e sem
   eventos subsequentes até 21/08/2026; o edital de 28/09/2026 e o termo de 19/10/2026 tratam os CRI
   como em circulação. Resgate facultativo é possível desde 29/08/2026, sem comunicado.
9. **Classe:** o Informe diz "Sênior"; o Termo não define classes (série única) e as DFs dizem "classe Única".
