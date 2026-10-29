# Comparação do mesmo dado entre documentos

Verificações `0.1.0` (propostas). Só lê parâmetros e fatos não rejeitados. Este relatório lista; não decide qual fonte está certa.

| Ativo | Concordam | Compatíveis (texto) | Divergem | Uma fonte só |
|---|---|---|---|---|
| 24G2100031 | 9 | 1 | 0 | 4 |
| CRA022009VM | 3 | 1 | 1 | 8 |
| CRA02500C1D | 22 | 2 | 11 | 3 |

## 24G2100031: divergências

Nenhuma.
### 24G2100031: textos compatíveis (uma fonte traz só parte do que a outra diz)

- Remuneração da emissão (texto): remuneracao → idx=DI, mult=100; af_remuneracao → idx=DI, taxa=1.5; df_passivo_taxa_prazo → idx=DI, mult=100, taxa=1.5; df_passivo_taxa_prazo → idx=DI, mult=100, taxa=1.5; DadosGerais/Series/Serie/TaxaJuros → idx=DI, mult=100, taxa=1.5


## CRA022009VM: divergências

### Data de vencimento final

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 2026-12-30 |  | parâmetro | `data_vencimento_final_cdca_cra` | approved | Ata 619771, p.3, linhas 19-32 |
| 2027-09-30 |  | informe | `DadosGerais/Series/Serie/DataVencimento` | approved | Informe 2026-08-31 (doc 1328844) |

### CRA022009VM: textos compatíveis (uma fonte traz só parte do que a outra diz)

- Remuneração da emissão (texto): remuneracao → idx=DI, mult=100, taxa=4.5; df2024_remuneracao → idx=DI, mult=100, taxa=4.5; df_passivo_taxa_prazo → idx=DI, mult=100, taxa=4.5; df_passivo_taxa_prazo → idx=DI, mult=100, taxa=4.5; df_passivo_taxa_prazo → idx=DI, mult=100, taxa=4.5; DadosGerais/Series/Serie/TaxaJuros → idx=DI


## CRA02500C1D: divergências

### Quantidade por série (série 1)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 0 |  | fato | `af_serie_1_quantidade_emitida` | approved | Relatório de Agente Fiduciário 1175590, p.3 |
| 233142 |  | informe | `DetalhesSeries/Series/Serie/QtdCertificadosPorClasse` | approved | Informe 2026-09-30 (doc 1355952) |
| 233142 |  | fato | `anuncio_serie_1_quantidade` | approved | Anúncio de Início de Distribuição Pública 1065461, p.2 |
| 233142 |  | fato | `comunicado_quantidade_serie_1` | approved | Outros Comunicados Não Considerados Fatos Relevantes  1064843, p.2 |
| 233142 |  | parâmetro | `quantidade_serie_1` | approved | Termo 1065416, p.64, linhas 12-25 |

### Quantidade por série (série 2)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 0 |  | fato | `af_serie_2_quantidade_emitida` | approved | Relatório de Agente Fiduciário 1175590, p.4 |
| 16858 |  | informe | `DetalhesSeries/Series/Serie/QtdCertificadosPorClasse` | approved | Informe 2026-09-30 (doc 1355952) |
| 16858 |  | fato | `anuncio_serie_2_quantidade` | approved | Anúncio de Início de Distribuição Pública 1065461, p.2 |
| 16858 |  | fato | `comunicado_quantidade_serie_2` | approved | Outros Comunicados Não Considerados Fatos Relevantes  1064843, p.2 |
| 16858 |  | parâmetro | `quantidade_serie_2` | approved | Termo 1065416, p.64, linhas 12-25 |

### Quantidade por série (série 4)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 0 |  | fato | `af_serie_4_quantidade_emitida` | approved | Relatório de Agente Fiduciário 1175590, p.6 |
| 100000 |  | informe | `DetalhesSeries/Series/Serie/QtdCertificadosPorClasse` | approved | Informe 2026-09-30 (doc 1355952) |
| 100000 |  | fato | `anuncio_serie_4_quantidade` | approved | Anúncio de Início de Distribuição Pública 1065461, p.2 |
| 100000 |  | fato | `comunicado_quantidade_serie_4` | approved | Outros Comunicados Não Considerados Fatos Relevantes  1064843, p.2 |
| 100000 |  | parâmetro | `quantidade_serie_4` | approved | Termo 1065416, p.64, linhas 12-25 |

### Quantidade por série (série 5)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 0 |  | fato | `af_serie_5_quantidade_emitida` | approved | Relatório de Agente Fiduciário 1175590, p.7 |
| 150000 |  | informe | `DetalhesSeries/Series/Serie/QtdCertificadosPorClasse` | approved | Informe 2026-09-30 (doc 1355952) |
| 150000 |  | fato | `anuncio_serie_5_quantidade` | approved | Anúncio de Início de Distribuição Pública 1065461, p.2 |
| 150000 |  | fato | `comunicado_quantidade_serie_5` | approved | Outros Comunicados Não Considerados Fatos Relevantes  1064843, p.2 |
| 150000 |  | parâmetro | `quantidade_serie_5` | approved | Termo 1065416, p.64, linhas 12-25 |

### Vencimento por série (série 1)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 2029-07-16 |  | informe | `DadosGerais/Series/Serie/DataVencimento` | approved | Informe 2026-09-30 (doc 1355952) |
| 2030-12-18 |  | fato | `af_serie_1_data_vencimento` | approved | Relatório de Agente Fiduciário 1175590, p.3 |
| 2030-12-18 |  | fato | `def_serie_1_vencimento` | approved | Prospecto de Distribuição Pública 1065463, p.15 |
| 2030-12-18 |  | fato | `df_data_termino_serie_1` | pending | Demonstrações Financeiras 1328400, p.10 |
| 2030-12-18 |  | fato | `lamina_serie_1_vencimento` | approved | Lâmina de Oferta de Securitização 1040834, p.6 |
| 2030-12-18 |  | parâmetro | `vencimento_serie_1` | approved | Termo 1065416, p.66, linhas 15-28 |

### Vencimento por série (série 2)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 2030-12-18 |  | fato | `def_serie_2_vencimento` | approved | Prospecto de Distribuição Pública 1065463, p.15 |
| 2030-12-18 |  | fato | `df_data_termino_serie_2` | pending | Demonstrações Financeiras 1328400, p.10 |
| 2030-12-18 |  | fato | `lamina_serie_2_vencimento` | approved | Lâmina de Oferta de Securitização 1040834, p.6 |
| 2030-12-18 |  | parâmetro | `vencimento_serie_2` | approved | Termo 1065416, p.66, linhas 15-28 |
| 2032-07-15 |  | informe | `DadosGerais/Series/Serie/DataVencimento` | approved | Informe 2026-09-30 (doc 1355952) |

### Vencimento por série (série 3)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 2030-12-18 |  | fato | `def_serie_3_vencimento` | approved | Prospecto de Distribuição Pública 1065463, p.15 |
| 2030-12-18 |  | fato | `df_data_termino_serie_3` | pending | Demonstrações Financeiras 1328400, p.10 |
| 2030-12-18 |  | fato | `lamina_serie_3_vencimento` | approved | Lâmina de Oferta de Securitização 1040834, p.6 |
| 2030-12-18 |  | parâmetro | `vencimento_serie_3` | approved | Termo 1065416, p.66, linhas 15-28 |
| 2035-07-16 |  | informe | `DadosGerais/Series/Serie/DataVencimento` | approved | Informe 2026-09-30 (doc 1355952) |

### Vencimento por série (série 4)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 2030-07-15 |  | informe | `DadosGerais/Series/Serie/DataVencimento` | approved | Informe 2026-09-30 (doc 1355952) |
| 2032-12-17 |  | fato | `af_serie_4_data_vencimento` | approved | Relatório de Agente Fiduciário 1175590, p.6 |
| 2032-12-17 |  | fato | `def_serie_4_vencimento` | approved | Prospecto de Distribuição Pública 1065463, p.15 |
| 2032-12-17 |  | fato | `df_data_termino_serie_4` | pending | Demonstrações Financeiras 1328400, p.10 |
| 2032-12-17 |  | fato | `lamina_serie_4_vencimento` | approved | Lâmina de Oferta de Securitização 1040834, p.7 |
| 2032-12-17 |  | parâmetro | `vencimento_serie_4` | approved | Termo 1065416, p.66, linhas 25-38 |

### Vencimento por série (série 5)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 2030-07-15 |  | informe | `DadosGerais/Series/Serie/DataVencimento` | approved | Informe 2026-09-30 (doc 1355952) |
| 2035-12-17 |  | fato | `df_data_termino_serie_5` | approved | Demonstrações Financeiras 1328400, p.10 |
| 2035-12-19 |  | fato | `af_serie_5_data_vencimento` | approved | Relatório de Agente Fiduciário 1175590, p.7 |
| 2035-12-19 |  | fato | `def_serie_5_vencimento` | pending | Prospecto de Distribuição Pública 1065463, p.15 |
| 2035-12-19 |  | fato | `lamina_serie_5_vencimento` | approved | Lâmina de Oferta de Securitização 1040834, p.7 |
| 2035-12-19 |  | parâmetro | `vencimento_serie_5` | approved | Termo 1065416, p.66, linhas 25-38 |

### Remuneração por série (texto) (série 1)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| CDI | idx=DI | fato | `af_serie_1_remuneracao` | approved | Relatório de Agente Fiduciário 1175590, p.3 |
| PRÉ 14,8000 % a.a | idx=PREFIXADA, taxa=14.8 | informe | `DadosGerais/Series/Serie/TaxaJuros` | approved | Informe 2026-09-30 (doc 1355952) |
| Taxa prefixada 14,8% a.a. | idx=PREFIXADA, taxa=14.8 | fato | `df_remuneracao_serie_1` | pending | Demonstrações Financeiras 1328400, p.20 |
| Prefixada 14,80% a.a., base 252 Dias Úteis | idx=PREFIXADA, taxa=14.8 | parâmetro | `remuneracao_serie_1` | approved | Termo 1065416, p.81, linhas 14-27 |

### Classe da série (sênior, mezanino, subordinada) (série 4)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| Mezanino |  | informe | `DadosGerais/Series/Serie/Classe` | approved | Informe 2026-09-30 (doc 1355952) |
| Subordinada |  | parâmetro | `classe_serie_4` | approved | Termo 1065416, p.35, linhas 12-25 |
| Subordinada |  | fato | `df_classe_serie_4` | pending | Demonstrações Financeiras 1328400, p.21 |

### CRA02500C1D: textos compatíveis (uma fonte traz só parte do que a outra diz)

- Remuneração por série (texto) (série 3): remuneracao_serie_3 → idx=DI, mult=100, taxa=1.5; af_serie_3_remuneracao → idx=DI, taxa=1.5; df_remuneracao_serie_3 → idx=DI, mult=100, taxa=1.5; DadosGerais/Series/Serie/TaxaJuros → idx=DI, taxa=1.5
- Remuneração por série (texto) (série 4): remuneracao_serie_4 → idx=DI, mult=100, taxa=2.5; af_serie_4_remuneracao → idx=DI, taxa=2.5; df_remuneracao_serie_4 → idx=DI, mult=100, taxa=2.5; DadosGerais/Series/Serie/TaxaJuros → idx=DI, taxa=2.5

