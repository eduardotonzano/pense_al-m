# CRI Almeida Junior (24G2100031 / BRRBRACRIP13): extração dos Informes Mensais

- Data: 2026-10-27
- Mapeamento: `config/xml_mappings/informe_mensal_cri.json` `cri-0.1.0` (aprovado em 2026-10-27,
  derivado do CRA 0.1.1). 26 informes (ago/2024–set/2026), todos na versão 1; 26 extrações sem falha.
- Revisão dos relatórios: `reports/report_review_informe_mensal_cri_cri-0.1.0.csv` (26 `decidir`).
- Golden set: `config/golden_sets/informe_mensal_cri_almeida_junior.json` (17 itens, **pendentes**);
  conferência extração × golden: 17/17. Página: `reports/24g2100031_revisao_pendente.html`.
- Sem relatório aprovado, não há comparação entre períodos nem alertas de qualidade.

## Estrutura (Informe)

Série única Sênior, 230.000 CRI, VNU R$ 1.000, emissão 29/08/2024, vencimento 29/08/2036,
"100% CDI + 1,5% a.a."; lastro: debênture (título de dívida); securitizadora Opea; AF e custodiante Vórtx.

## Achados

1. **`totalVlrCertificados` traz o PU, não o saldo.** 1000.45 em ago/2024; 230.000 × 1000.45 =
   230.103.500 ≈ `Passivo/VlrAtualizadoEmissao` 230.103.915,66. A regra `monetary_scale_suspect`
   (totalVlrCertificados / VlrTotalIntegralizado < 0,01) dispara em 25 meses e marca todos os valores
   monetários com `scale='unknown'`, embora os demais valores estejam em reais. **Decisão pendente.**
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
