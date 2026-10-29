# Comparação do mesmo dado entre documentos

Verificações `0.1.0` (propostas). Só lê parâmetros e fatos não rejeitados. Este relatório lista; não decide qual fonte está certa.

| Ativo | Concordam | Compatíveis (texto) | Divergem | Uma fonte só |
|---|---|---|---|---|
| 24G2100031 | 8 | 1 | 0 | 1 |
| CRA022009VM | 2 | 0 | 0 | 3 |
| CRA02500C1D | 20 | 2 | 5 | 3 |

## 24G2100031: divergências

Nenhuma.
### 24G2100031: textos compatíveis (uma fonte traz só parte do que a outra diz)

- Remuneração da emissão (texto): remuneracao → idx=DI, mult=100; af_remuneracao → idx=DI, taxa=1.5; df_passivo_taxa_prazo → idx=DI, mult=100, taxa=1.5; df_passivo_taxa_prazo → idx=DI, mult=100, taxa=1.5


## CRA022009VM: divergências

Nenhuma.

## CRA02500C1D: divergências

### Quantidade por série (série 1)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 0 |  | fato | `af_serie_1_quantidade_emitida` | approved | Relatório de Agente Fiduciário 1175590, p.3 |
| 233142 |  | fato | `anuncio_serie_1_quantidade` | approved | Anúncio de Início de Distribuição Pública 1065461, p.2 |
| 233142 |  | fato | `comunicado_quantidade_serie_1` | approved | Outros Comunicados Não Considerados Fatos Relevantes  1064843, p.2 |
| 233142 |  | parâmetro | `quantidade_serie_1` | approved | Termo 1065416, p.64, linhas 12-25 |

### Quantidade por série (série 2)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 0 |  | fato | `af_serie_2_quantidade_emitida` | approved | Relatório de Agente Fiduciário 1175590, p.4 |
| 16858 |  | fato | `anuncio_serie_2_quantidade` | approved | Anúncio de Início de Distribuição Pública 1065461, p.2 |
| 16858 |  | fato | `comunicado_quantidade_serie_2` | approved | Outros Comunicados Não Considerados Fatos Relevantes  1064843, p.2 |
| 16858 |  | parâmetro | `quantidade_serie_2` | approved | Termo 1065416, p.64, linhas 12-25 |

### Quantidade por série (série 4)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 0 |  | fato | `af_serie_4_quantidade_emitida` | approved | Relatório de Agente Fiduciário 1175590, p.6 |
| 100000 |  | fato | `anuncio_serie_4_quantidade` | approved | Anúncio de Início de Distribuição Pública 1065461, p.2 |
| 100000 |  | fato | `comunicado_quantidade_serie_4` | approved | Outros Comunicados Não Considerados Fatos Relevantes  1064843, p.2 |
| 100000 |  | parâmetro | `quantidade_serie_4` | approved | Termo 1065416, p.64, linhas 12-25 |

### Quantidade por série (série 5)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| 0 |  | fato | `af_serie_5_quantidade_emitida` | approved | Relatório de Agente Fiduciário 1175590, p.7 |
| 150000 |  | fato | `anuncio_serie_5_quantidade` | approved | Anúncio de Início de Distribuição Pública 1065461, p.2 |
| 150000 |  | fato | `comunicado_quantidade_serie_5` | approved | Outros Comunicados Não Considerados Fatos Relevantes  1064843, p.2 |
| 150000 |  | parâmetro | `quantidade_serie_5` | approved | Termo 1065416, p.64, linhas 12-25 |

### Remuneração por série (texto) (série 1)

| Valor | Fichas | Origem | Nome | Revisão | Fonte |
|---|---|---|---|---|---|
| CDI | idx=DI | fato | `af_serie_1_remuneracao` | approved | Relatório de Agente Fiduciário 1175590, p.3 |
| Prefixada 14,80% a.a., base 252 Dias Úteis | idx=PREFIXADA, taxa=14.8 | parâmetro | `remuneracao_serie_1` | approved | Termo 1065416, p.81, linhas 14-27 |

### CRA02500C1D: textos compatíveis (uma fonte traz só parte do que a outra diz)

- Remuneração por série (texto) (série 3): remuneracao_serie_3 → idx=DI, mult=100, taxa=1.5; af_serie_3_remuneracao → idx=DI, taxa=1.5
- Remuneração por série (texto) (série 4): remuneracao_serie_4 → idx=DI, mult=100, taxa=2.5; af_serie_4_remuneracao → idx=DI, taxa=2.5

