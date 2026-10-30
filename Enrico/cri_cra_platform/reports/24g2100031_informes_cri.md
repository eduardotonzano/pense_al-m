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

## Revisão de 2026-10-28: documentos que não tinham sido lidos

### Documentos de oferta (baixados e lidos em 28/10)
- Lidos: Aviso ao Mercado 722271, Lâminas 722282 e 727225, Anúncio de Início 727228 e o Prospecto preliminar
  722286 (539 páginas: parte lida por inteiro e parte por palavra-chave; as páginas estão em
  `reports/24g2100031_oferta_vs_termo.md`). 110 fatos pendentes em `config/reported_facts/24g2100031_oferta_2024.json`.
- **Prospecto definitivo 727241 (610 páginas) e Anúncio de Encerramento 730623:** baixados depois, com `--max-megabytes 80`
  (o prospecto tem 28,4 MB). Lidos: páginas 1 a 20, trechos principais e o relatório da Fitch (pp.596-610); comparação
  com o preliminar das páginas 1 a 125 e por palavra-chave no restante. 52 fatos pendentes em
  `config/reported_facts/24g2100031_oferta_definitiva_2024.json`; comparação em
  `reports/24g2100031_prospecto_definitivo_vs_preliminar.md`.
- **Definitivo × preliminar:** o definitivo fixa o step-up em 29/08/2030 (CRI) e 27/08/2030 (debêntures), traz o resgate
  facultativo a partir de 29/08/2026 e a duration de 4,86; a escritura de AF "celebrada em 23/08/2024" e o contrato de CF
  "celebrado em 26/07/2024, registrado no 2º RTD de São Paulo sob nº 3.792.419". Os anexos do próprio definitivo ainda trazem
  72º/73º mês, 2027 e 4,93.
- **Rating:** o relatório da Fitch anexo ao definitivo (27/08/2024, pp.600-602) traz AA-sf(bra), perspectiva estável, sem
  "(EXP)"; a capa e os anúncios ainda escrevem AA-(EXP)sf(bra). A leitura "preliminar → final" é interpretação, porque a tabela
  da p.601 está quebrada na extração. O que aconteceu depois de 27/08/2024 (atualização anual, retirada) continua sem resposta.
- **Garantias:** o definitivo não diz que a condição suspensiva da cessão fiduciária foi implementada nem que o Termo de
  Liberação foi averbado; a alienação "será constituída mediante registro" (p.18). Continua compatível com o "não constituída"
  do AF 2025, e só as matrículas atualizadas e o RTD confirmam.
- **Não baixados:** nenhum. O serviço passou a aceitar o Anúncio de Encerramento por identificador explícito.
- Diferenças entre a oferta e o Termo (17 no relatório): step-up marcado como "73º mês" na oferta e 29/08/2030 no
  Aditamento (mesmos valores, 1,50% e 2,75%); resgate facultativo a partir de 29/08/2027 no prospecto e
  29/08/2026 no Aditamento; duration 4,93 e 4,86; texto da Lâmina diz imóvel "de titularidade da Emissora",
  enquanto o Termo diz Devedora.
- **Garantias, o que a oferta ajuda a entender (inferência, não fato):** a cessão fiduciária nasce sob condição
  suspensiva (registro do termo de liberação de 23/09/2021; Termo p.40, Prospecto p.18) e a alienação fiduciária
  depende de um Termo de Liberação averbado: 51% do imóvel já estavam alienados em 2021 e só 37,24% passam de
  imediato (minuta da escritura, p.284-285 do Prospecto). Isso é compatível com o "não constituída" do AF 2025,
  mas só matrículas, registro em cartório e o Termo de Liberação registrado confirmam. O prazo final da condição
  suspensiva não aparece nas páginas lidas (deve estar no contrato de cessão fiduciária, que não foi baixado).
- **Rating, o que a oferta ajuda a entender:** a atualização anual está no Termo, no Prospecto e na Escritura de
  Debêntures (a cargo da Devedora). O rating nos documentos é sempre o preliminar AA-(EXP)sf(bra), inclusive no
  Anúncio de Início de 27/08/2024; a Fitch diz que o final viria no comunicado da liquidação (Prospecto p.530),
  que não foi localizado. Falta consultar a Fitch e a CVM para saber se houve rating final, retirada ou nunca
  contratação.

### Relatório anual do AF de 2024 (892072): OCR com conferência visual
O PDF (199 páginas) é imagem. Em 28/10 foi feito OCR das 199 páginas (`scripts/ocr_document_pages.py`; rapidocr-onnxruntime
1.4.4 sobre imagens de 150 dpi), gravado em `document_text_pages` com extrator `ocr: ...` ao lado da linha vazia do pdftotext. O OCR
perde acentos e pode descartar linhas (a coluna "Constituição" da tabela de garantias não foi captada), então **cada valor foi
conferido nas imagens das páginas 3 a 10**. 19 fatos pendentes em `config/reported_facts/24g2100031_af_2024_ocr.json`, método
`ocr_com_conferencia_visual`. As páginas 11 a 199 são "Outras emissões" da Opea e não dizem respeito a este ativo.
- Série única, IF 24G2100031, ISIN BRRBRACRIP13, PU R$ 1.000,00, 230.000 CRI, R$ 230.000.000,00; "CDI + 1,5%";
  amortização "Mensal"; emissão 29/08/2024; vencimento 29/08/2036; juros mensais; 1º pagamento previsto
  26/09/2024; rating: "Não existe rating para esse operação no período analisado"; inadimplência no período:
  "Adimplente".
- Em 31/12/2024: 230.000 em circulação, 0 resgatadas, saldo R$ 230.118.275,40, que confere com o Informe de
  dez/2024 (`VlrAtualizadoEmissao` 230118275.4).
- Pagamentos de juros por CRI: 30/09 10,02330500; 29/10 9,72125200; 29/11 9,91988900; 30/12 9,90435399; sem amortização.
- Contratos listados: AF de imóvel, CF (e 1º aditamento), emissão de CCI e de debêntures (e 1º aditamento), TS (e 1º aditamento).
- Garantias (item 9.1): alienação fiduciária de imóvel e cessão fiduciária de outros com Constituição "-" (sem
  marcação). No relatório de 2025 a mesma tabela traz "NÃO". Não é a mesma informação e não deve ser tratada
  como equivalente. Suficiência e covenants: remetidos ao site da Vórtx.
- Assembleias: "Não foram realizadas assembleias no período". Relatório de gestão do patrimônio separado: não disponibilizado.
- Divergência já conhecida: o AF diz que o 1º pagamento previsto é 26/09/2024; os Informes e o Anexo III do Termo trazem 30/09/2024.
