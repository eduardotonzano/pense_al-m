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

Nenhum dos 11 XMLs declara versão de leiaute, `schemaLocation` ou namespace próprio.

## Amostra (11 arquivos, hashes conferidos contra o banco antes da análise)

| source_document_id | Publicação | Competência (`DadosGerais/Competencia`) |
|---|---|---|
| 380870 | 21/11/2022 | 2022-10-30 |
| 692858 | 05/07/2024 | 2023-12-31 |
| 695313 | 10/07/2024 | 2024-01-31 |
| 699956 | 16/07/2024 | 2024-02-29 |
| 702007 | 21/07/2024 | 2024-03-31 |
| 703068 | 23/07/2024 | 2024-04-30 |
| 707394 | 30/07/2024 | 2024-06-30 |
| 833116 | 07/02/2025 | 2024-12-31 |
| 849077 | 27/02/2025 | 2025-01-31 |
| 1300722 | 26/08/2026 | 2026-07-31 |
| 1328844 | 25/09/2026 | 2026-08-31 |

Julho/2024 e fevereiro/2025 são entregas de competências distintas, não reapresentações.
A competência 2024-05 não está na amostra.

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
   nos outros 10 os mesmos campos vêm `0`. Nil, vazio (`<X></X>`) e zero são estados
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

## Próximo passo

Montar o golden set a partir destes 11 arquivos (nil, vazio, zero, monetário, percentual,
texto, `@total` divergente) e acrescentar um ativo multissérie para cobrir blocos repetidos.
