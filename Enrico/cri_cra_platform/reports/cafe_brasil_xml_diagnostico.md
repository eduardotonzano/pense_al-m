# Diagnóstico estrutural — Informes Mensais XML do CRA Café Brasil

- Data: 2026-10-21
- Ativo: `CRA022009VM` / `BRECOACRABX0`
- Diagnóstico: `credit_assets.xml_diagnostics` v0.1.0 (`scripts/run_xml_diagnostics.py`)
- Mapeamento: `config/xml_mappings/informe_mensal_cra.json` — `0.0.0-draft`, sem decisões
- `layout_validation_status`: **structural_only**
- Saídas: `reports/cafe_brasil_xml_union.{json,csv}` e `reports/xml_diagnostics/CRA022009VM_<id>.{json,csv}`

## Leiaute oficial

Não foi encontrado XSD público. O que existe:

- Base normativa: Suplemento F da Resolução CVM 60 (Informe Mensal de CRA).
- O modelo de formulário fica em "Materiais de Apoio" do Fundos.NET (Ofícios-Circulares
  CVM/SIN 08/19 e CVM/SSE 01/22); não está acessível na área pública consultada.
- CVM Dados Abertos publica um dicionário das colunas do CSV achatado (não do XML),
  guardado em `config/references/cvm/meta_inf_mensal_cra/` com URL e SHA-256.
  Ele traz `Versao` do documento, útil para identificar reapresentações.
- Contato indicado pela CVM para o sistema: B3, Superintendência de Suporte a Emissores.

Nenhum dos 17 XMLs declara versão de leiaute, `schemaLocation` ou namespace próprio.

## Amostra (17 arquivos, hashes conferidos contra o banco antes da análise)

`Versão` é o campo `versao` da grade do Fundos.NET (`document_versions.source_version`).

| Competência (`DadosGerais/Competencia`) | Versão 1 | Versão 2 |
|---|---|---|
| 2022-10-30 | 380870 (21/11/2022) | — |
| 2023-12-31 | 590722 (27/01/2024) | 692858 (05/07/2024) |
| 2024-01-31 | 601820 (13/02/2024) | 695313 (10/07/2024) |
| 2024-02-29 | 628066 (27/03/2024) | 699956 (16/07/2024) |
| 2024-03-31 | 648761 (30/04/2024) | 702007 (21/07/2024) |
| 2024-04-30 | 666963 (22/05/2024) | 703068 (23/07/2024) |
| 2024-05-31 | 688790 (28/06/2024) | — |
| 2024-06-30 | 707394 (30/07/2024) | — |
| 2024-12-31 | 833116 (07/02/2025) | — |
| 2025-01-31 | 849077 (27/02/2025) | — |
| 2026-07-31 | 1300722 (26/08/2026) | — |
| 2026-08-31 | 1328844 (25/09/2026) | — |

Fevereiro/2025 traz duas competências distintas, cada uma em versão 1. **Julho/2024 traz
reapresentações**: cinco documentos em versão 2 (dez/2023 a abr/2024) e a entrega regular
de jun/2024. (Uma versão anterior deste relatório dizia o contrário; foi corrigida após
consultar `source_version`.)

## Reapresentações e escala

- As versões 1 de dez/2023 a abr/2024 trazem os valores monetários em escala aparente de
  **milhares de reais** (ex.: `VlrCertificadosPorClasse = 100000`); as versões 2 trazem os
  mesmos campos em **reais** (`100000000`). Entre 13 e 18 campos mudam por par, quase todos
  por fator ~1000.
- A troca de escala começa na entrega de mai/2024 (688790, publicada em 28/06/2024, já em reais).
  O 380870 (2022, versão 1, nunca reapresentado na amostra) também está em milhares.
- No par de abr/2024 há também correção de conteúdo: `RendimentosDistribuidosPeriodo`
  passa de `773.39` (repetição do valor de março) para `0`.
- Consequências: a escala não é declarada no XML e muda entre entregas; a versão vigente de
  cada competência precisa considerar `source_version`; comparações entre períodos não podem
  usar versões 1 substituídas.

## Estrutura

- Raiz única `InformeMensalCRA`; encoding declarado UTF-8 e válido em todos; único namespace `xsi`.
- Profundidade máxima 5.
- **282 caminhos**: 170 folhas, 43 contêineres, 69 atributos.
- Classificação: 282 `pending_decision` (100% classificados; nenhuma decisão tomada).
- Nenhum bloco repetido na amostra (1 série, 1 devedor e 1 cedente >20%).
  O golden set precisará de um caso multissérie de outro ativo.
- Nenhum texto longo (>200), base64 ou dado pessoal suspeito. `CNPJ` de devedor/cedente
  aparece formatado (`31.943.818/0001-71`); em outros CRAs o mesmo campo pode conter CPF.

## Achados para decisão

1. **`xsi:nil` vs zero.** O 380870 (2022) marca 47 campos numéricos com `xsi:nil="true"`;
   nos outros 16 os mesmos campos vêm `0`. Nil, vazio (`<X></X>`) e zero são estados
   distintos e não podem ser normalizados entre si.
2. **Sempre vazios (9 folhas)**: 7 com `xsi:nil` em todos os arquivos (classificação de
   risco, índices de subordinação, concentração 5/10/20 maiores devedores) e 2 vazias sem nil
   (`TipoRetencaoRisco`, `AgenciaClassificadora`).
3. **Atributos `@total`** em 20 contêineres. 163 de 165 conferem com a soma das folhas
   numéricas. Divergem 2: `Passivo/@total` em 1300722 e 1328844, ambos por 0,02, nos
   arquivos com `Passivo/ReducaoVlrEmissao = -0.01`. Regra de soma precisa de decisão.
   `PrePgtosPeriodo` contém uma folha textual sob `@total`.
4. **Números**: separador decimal sempre ponto; mistura de inteiro e decimal no mesmo campo
   (`100000000` e `100891.09`). Nenhum `decimal_comma` nos campos numéricos.
5. **Percentuais**: `RentabilidadePeriodo = 0.0147` e `Percentual = 1` com
   `Concentracao = "Concentrado - mais de 20%"` sugerem fração (1 = 100%), mas a escala
   não está declarada no XML. Pendente de confirmação.
6. **Textos com unidade embutida**: `TaxaJuros = "CDI + 4,5000 a.a."` (vírgula decimal
   dentro de texto livre) — manter como texto original.
7. **Competência fora do fim do mês**: 380870 declara `2022-10-30`. Preservar como veio.
8. **Typo na fonte**: `CompanhiaEmissora = "Eco Securitizdora ..."`. Não corrigir na extração.

## Série completa (2026-10-26)

Todos os 52 Informes Mensais do Café Brasil baixados e verificados (ISIN da grade e do XML).
Cobrem **47 competências contínuas, de out/2022 a ago/2026**; só dez/2023 a abr/2024 têm
duas versões. Os 52 têm os mesmos 282 caminhos; nenhum valor estruturalmente inválido
(campo numérico com texto, data fora de ISO) e nenhum elemento ausente.

- Escala aparente de milhares em todas as versões 1 de out/2022 a abr/2024; reais a partir
  de mai/2024.
- Convenções de competência: fim de mês (maioria), 1º dia do mês (fev–ago/2023) e `2022-10-30`.
- `VlrCertificadosPorClasse = 108830.3693` (495975) com quatro casas decimais.
- Variação a revisar: 40027042.18 (dez/2025) → 72352716.52 (jan/2026) → 48274408.67
  (fev/2026). Observação objetiva; não classificada como erro.

## Checagem cruzada com CVM Dados Abertos (2026-10-26)

Arquivos `inf_mensal_cra_{2022,2023,2024}.zip` (tabela `classe`), ISIN `BRECOACRABX0`:

- A CVM publica **uma linha por competência, só na versão mais recente**: dez/2023 a
  abr/2024 aparecem como `Versao = 2`, com valores idênticos aos XMLs reapresentados.
- `Data_Referencia` é normalizada para o 1º dia do mês (`2022-10-01`), diferente do XML
  (`2022-10-30`). Não usar o CSV como fonte da competência literal.
- **Out/2022 a nov/2023 (14 competências) seguem em versão 1 e na escala de milhares**
  (`Valor_Certificados` de 100891.09 a 116615.65). O dado oficial da CVM herda o problema;
  não há correção posterior a usar.
- `Rentabilidade` também vem como fração (`0.0125`), coerente com o XML.

## Ativo multissérie (Alibem)

Aprovado em 2026-10-26: CRA Eco Securitizadora, 426ª emissão (Alibem), 5 séries
(Sênior 1–2, Mezanino 3–4, Subordinada 5), série 1 `CRA02500C1D` / `BRECOACRALJ8`,
identificada pelos Dados Abertos da CVM. Catálogo: 22 documentos (idFundo 23641), 10
Informes Mensais. Três XMLs baixados (1094453, 1200762, 1355952) mostram o mesmo leiaute
(235 caminhos, todos já existentes no Café Brasil), `Serie` repetida 5× em `DadosGerais/Series`
e em `DetalhesSeries/Series`, e `EspecificacaoTipoSegmento` ausente (caso `absent`).
Diagnóstico: `reports/alibem_xml_union.{json,csv}`.

## Mapping 0.1.0 e extração 0.2.0 (2026-10-26)

Regras aprovadas: escala marcada e não convertida; percentuais como fração; séries ligadas
por `NumeroSerie`; `xsi:nil` = `present_empty` + `xsi_nil=1`; `invalid` coberto por testes
sintéticos. 282 caminhos: 183 `mapped`, 97 `ignored` (contêineres e atributos nil),
2 `pending_decision` (`DurationCarteira`, `VlrTotalDirCredRelacaoVlrTotalEmissao`).

Resultado em 55 arquivos (52 Café Brasil, 3 Alibem): 39/39 itens dos golden sets conferem,
incluindo `zero` e `absent`. Validação automática:

- `monetary_scale_suspect` dispara em exatamente 19 relatórios: todas as versões 1 de
  out/2022 a abr/2024 do Café Brasil. Nenhuma v2 nem relatório de mai/2024 em diante.
- `totals_consistency` em `Passivo/@total`: nos 13 casos com `ReducaoVlrEmissao ≠ 0`
  (Café Brasil nov/2025–ago/2026 e os 3 do Alibem), `@total = soma das folhas − 2 × Reducao`,
  isto é, o total trata `ReducaoVlrEmissao` com o sinal oposto ao informado no campo.
  Convenção a decidir; a regra atual só gera warning.
- Jun/2023 (495975, quatro casas decimais): diferenças de arredondamento (ex.: 0.0007) em
  seis `@total`.
- Café Brasil: 23 relatórios `valid`, 29 `warning`; Alibem: 3 `warning`. Nenhum `invalid`.

## Mapping 0.1.1 e extração 0.2.1 (2026-10-26)

Decidido: `Passivo/@total` soma `ReducaoVlrEmissao` com sinal invertido
(`rules.totals_consistency.sign_inverted_paths`); valor gravado não muda. Padrões conservadores
de 0.1.0 confirmados. Resultado: Café Brasil 33 `valid` e 19 `warning` (todos por
`monetary_scale_suspect`; jun/2023 também com 6 diferenças de arredondamento), Alibem 3 `valid`.
Golden sets 39/39.

## Versões vigentes e comparação entre períodos (2026-10-26)

Revisão aprovada em 2026-10-26: 50 relatórios vigentes (47 Café Brasil, 3 Alibem); as 5 v1
substituídas rejeitadas; as 14 competências em milhares (out/2022–nov/2023) vigentes, com
valores R$ excluídos das comparações. Saídas: `reports/<cetip>_serie_indicadores.csv` e
`reports/<cetip>_mudancas_entre_periodos.csv` (tabela `period_comparisons`).

Observações objetivas do Café Brasil para revisão (não são alertas; não há limites definidos):

- `Situacao` passa de "Adimplente" para "Em atraso" em abr/2026, enquanto
  `DirCredVencidosNaoPagos`, `DirCredAVencerComParcelasAtraso` e `VlrTotalParcelasAtraso`
  permanecem 0 em todos os meses.
- Dez/2025: saldo 82,3 mi → 40,0 mi com pagamento sênior de 57,2 mi e
  `RentabilidadePeriodo = 0.181`. Jan/2026: saldo 72,4 mi sem pagamento e
  `RentabilidadePeriodo = 0.8076`. Fev/2026: pagamento de 25 mi e saldo 48,3 mi.
- `DevedoresRepresentamMais20Porcento/Devedor/CNPJ` muda em nov/2022
  (23.357.072/0001-81 → 31.943.818/0001-71).

## Golden set

`config/golden_sets/informe_mensal_cra_cafe_brasil.json` — 27 itens congelados por SHA-256,
com linha e trecho do XML bruto; todos `human_review_status = pending`.
Planilha de revisão: `reports/golden_set_review_informe_mensal_cra_cafe_brasil.csv`.
Gerado e verificado por `scripts/build_golden_set.py` (itens congelados nunca são reescritos).

Cobertura obrigatória ausente: `absent`, `repeated_block` (exige ativo multissérie) e
`invalid`. Enquanto houver lacunas ou itens pendentes, nenhuma `mapping_version` pode ser publicada.
