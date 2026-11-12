# Fila de revisão priorizada

Só leitura: nada aqui aprova item. Começar pelo nível 1; o nível 4 pode ser aprovado em bloco depois de você decidir o escopo.

| Nível | 24G2100031 | CRA022009VM | CRA02500C1D | todos | Total |
|---|---|---|---|---|---|
| 1. Decidir primeiro | 6 | 10 | 2 | 0 | 18 |
| 2. Importante | 21 | 14 | 4 | 2 | 41 |
| 3. Conferido visualmente, com observação | 53 | 34 | 23 | 0 | 110 |
| 4. Conferido, sem observação (aprovação em bloco) | 4 | 0 | 4 | 0 | 8 |
| 5. Sem conferência visual | 5 | 5 | 0 | 0 | 10 |

## Nível 1: Decidir primeiro (18)

| Ativo | Tipo | Id | Nome | Valor | Por quê | Fonte |
|---|---|---|---|---|---|---|
| 24G2100031 | fato | 455 | `lamina_garantia_af_titularidade_emissora` | texto da Lâmina: imóvel "de titularidade da Emissora" | nota com contradição/interpretação | Lâmina de Oferta de Securitização 727225, p.9 |
| 24G2100031 | fato | 498 | `prospecto_risco_rating_atualizacao_trimestral` | classificação de risco atualizada trimestralmente (texto do fator de r | nota com contradição/interpretação | Prospecto de Distribuição Pública 722286, p.37 |
| 24G2100031 | fato | 762 | `prosp_def_cronograma_bookbuilding` | 2024-08-26 | nota com contradição/interpretação | Prospecto de Distribuição Pública 727241, p.62 |
| 24G2100031 | fato | 778 | `prosp_def_fitch_tabela_rating_anterior_exp` | ISIN BRRBRACRIP13: AA-sf(bra), perspectiva Stable; coluna do rating an | conferência visual diverge; nota com contradição/interpretação | Prospecto de Distribuição Pública 727241, p.601 |
| 24G2100031 | fato | 789 | `enc_linha_parcial_1709_subscritores_221120_cri` | 1.709 subscritores; 221.120 CRI (tipo de investidor não identificável  | conferência visual diverge | Anúncio de Encerramento de Distribuição Pública 730623, p.2 |
| 24G2100031 | fato | 790 | `enc_linha_parcial_1_subscritor_8880_cri` | 1 subscritor; 8.880 CRI (tipo de investidor não identificável na extra | conferência visual diverge | Anúncio de Encerramento de Distribuição Pública 730623, p.2 |
| CRA022009VM | fato | 268 | `df_garantias_estrutura_nota_1` | A operação não conta com garantia | nota com contradição/interpretação | Demonstrações Financeiras 485809, p.10 |
| CRA022009VM | fato | 298 | `df_assembleias_periodo` | nenhuma | nota com contradição/interpretação | Demonstrações Financeiras 698040, p.19 |
| CRA022009VM | fato | 318 | `df_amortizacao_principal_cra_exercicio` | 30000 | nota com contradição/interpretação | Demonstrações Financeiras 935390, p.18 |
| CRA022009VM | fato | 327 | `df_assembleias_periodo` | nenhuma | nota com contradição/interpretação | Demonstrações Financeiras 935390, p.19 |
| CRA022009VM | fato | 331 | `comunicado_assembleia_data_citada` | 2023-03-14 | nota com contradição/interpretação | Outros Comunicados Não Considerados Fatos Relevantes  620811, p.1 |
| CRA022009VM | fato | 361 | `assembleia_dfs_2023_2a_convocacao_presenca` | presentes 17,11% dos CRA em Circulação; sem quórum de deliberação | nota com contradição/interpretação | AGO/E 538424, p.2 |
| CRA022009VM | fato | 376 | `assembleia_cdca_2024_presenca` | instalada em 1ª convocação; Titulares presentes: 77,87% dos CRA em Cir | conferência visual inconclusivo | AGO/E 619771, p.1 |
| CRA022009VM | fato | 403 | `assembleia_dfs_2024_2a_convocacao_edital_publicado` | edital de 2ª convocação publicado em 02/10/2024 (instrução de voto à d | nota com contradição/interpretação | AGO/E 750841, p.3 |
| CRA022009VM | fato | 405 | `assembleia_dfs_2024_2a_convocacao_nao_instalada` | não instalada: nenhum investidor presente (quórum mínimo de instalação | conferência visual inconclusivo | AGO/E 755722, p.2 |
| CRA022009VM | fato | 416 | `df2024_assembleias_no_exercicio` | a DF diz que não houve assembleias no exercício 01/04/2023 a 31/03/202 | nota com contradição/interpretação | AGO/E 725269, p.26 |
| CRA02500C1D | fato | 724 | `def_comissao_sucesso_nota` | não aplicável (nota 1d) | nota com contradição/interpretação | Prospecto de Distribuição Pública 1065463, p.170 |
| CRA02500C1D | fato | 809 | `enc_serie_3_total_cra` | 250000 | nota com contradição/interpretação | Anúncio de Encerramento de Distribuição Pública 1068059, p.3 |

## Nível 2: Importante (41)

| Ativo | Tipo | Id | Nome | Valor | Por quê | Fonte |
|---|---|---|---|---|---|---|
| 24G2100031 | fato | 811 | `af2024_quantidade_emitida` | 230000 | leitura por OCR | Relatório de Agente Fiduciário 892072, p.3 |
| 24G2100031 | fato | 812 | `af2024_volume_emitido` | 230000000.00 | leitura por OCR | Relatório de Agente Fiduciário 892072, p.3 |
| 24G2100031 | fato | 813 | `af2024_remuneracao` | CDI + 1,5% | leitura por OCR | Relatório de Agente Fiduciário 892072, p.3 |
| 24G2100031 | fato | 814 | `af2024_data_vencimento` | 2036-08-29 | leitura por OCR | Relatório de Agente Fiduciário 892072, p.3 |
| 24G2100031 | fato | 815 | `af2024_rating` | não existe rating para a operação no período analisado | alimenta alerta contratual; leitura por OCR | Relatório de Agente Fiduciário 892072, p.3 |
| 24G2100031 | fato | 816 | `af2024_primeiro_pagamento_previsto` | 2024-09-26 | leitura por OCR | Relatório de Agente Fiduciário 892072, p.4 |
| 24G2100031 | fato | 817 | `af2024_inadimplemento_periodo` | Adimplente | leitura por OCR | Relatório de Agente Fiduciário 892072, p.4 |
| 24G2100031 | fato | 818 | `af2024_contratos_listados` | AF imóvel; CF; CF - 1º aditamento; emissão CCI; emissão CCI - 1º adita | leitura por OCR | Relatório de Agente Fiduciário 892072, p.4 |
| 24G2100031 | fato | 819 | `af2024_certificados_em_circulacao` | 230000 | leitura por OCR | Relatório de Agente Fiduciário 892072, p.5 |
| 24G2100031 | fato | 820 | `af2024_saldo_devedor` | 230118275.40 | leitura por OCR | Relatório de Agente Fiduciário 892072, p.5 |
| 24G2100031 | fato | 821 | `af2024_pgto_juros_por_cri` | 10.02330500 | leitura por OCR | Relatório de Agente Fiduciário 892072, p.5 |
| 24G2100031 | fato | 822 | `af2024_pgto_juros_por_cri` | 9.72125200 | leitura por OCR | Relatório de Agente Fiduciário 892072, p.5 |
| 24G2100031 | fato | 823 | `af2024_pgto_juros_por_cri` | 9.91988900 | leitura por OCR | Relatório de Agente Fiduciário 892072, p.5 |
| 24G2100031 | fato | 824 | `af2024_pgto_juros_por_cri` | 9.90435399 | leitura por OCR | Relatório de Agente Fiduciário 892072, p.5 |
| 24G2100031 | fato | 825 | `af2024_relatorio_gestao_patrimonio_separado` | não disponibilizado ao Agente Fiduciário | leitura por OCR | Relatório de Agente Fiduciário 892072, p.7 |
| 24G2100031 | fato | 826 | `af2024_assembleias` | nenhuma no período | leitura por OCR | Relatório de Agente Fiduciário 892072, p.7 |
| 24G2100031 | fato | 827 | `af2024_garantias_constituicao` | alienação fiduciária de imóvel e cessão fiduciária de outros listadas  | leitura por OCR | Relatório de Agente Fiduciário 892072, p.8 |
| 24G2100031 | fato | 828 | `af2024_suficiencia_garantias` | remetida à aba 'Relatórios de Garantias' do site da Vórtx; não analisa | leitura por OCR | Relatório de Agente Fiduciário 892072, p.8 |
| 24G2100031 | fato | 829 | `af2024_declaracao_inadimplemento` | o AF declara não ter conhecimento de inadimplemento ou atraso na prest | leitura por OCR | Relatório de Agente Fiduciário 892072, p.10 |
| 24G2100031 | regra de alerta | contractual_24g2100031.json | `contractual_24g2100031` | pendente | regra proposta; só roda com --preview | config\alert_rules\contractual_24g2100031.json |
| 24G2100031 | regra de alerta | informe_cadastro_24g2100031.json | `informe_cadastro_24g2100031` | pendente | regra proposta; só roda com --preview | config\alert_rules\informe_cadastro_24g2100031.json |
| CRA022009VM | fato | 254 | `df_total_ativo` | 104657 | alimenta alerta contratual | Demonstrações Financeiras 485809, p.7 |
| CRA022009VM | fato | 308 | `df_total_ativo` | 72994 | alimenta alerta contratual | Demonstrações Financeiras 935390, p.7 |
| CRA022009VM | parâmetro | 267 | `numero_emissao` | 190 | campo core do catálogo | Termo 355426, p.1, linhas 4-17 |
| CRA022009VM | parâmetro | 270 | `devedora` | Café Brasil Indústria Comércio Importação e Exportação S.A. (sede em A | campo core do catálogo | Termo 355426, p.12, linhas 33-40 |
| CRA022009VM | parâmetro | 271 | `data_emissao` | 2022-09-21 | campo core do catálogo | Termo 355426, p.32, linhas 17-24 |
| CRA022009VM | parâmetro | 272 | `quantidade_total_cra` | 100000 | campo core do catálogo | Termo 355426, p.32, linhas 7-20 |
| CRA022009VM | parâmetro | 273 | `data_vencimento_termo_original` | 2027-09-30 | campo core do catálogo | Termo 355426, p.33, linhas 7-20 |
| CRA022009VM | parâmetro | 274 | `vencimento_antecipado_cra` | Não há vencimento antecipado dos CRA; apenas Resgate Antecipado (hipót | campo core do catálogo | Termo 355426, p.33, linhas 11-24 |
| CRA022009VM | parâmetro | 276 | `periodicidade_remuneracao` | Datas de Pagamento da Remuneração (Anexo II): 30/12/2022, 29/12/2023,  | campo core do catálogo | Termo 355426, p.101, linhas 2-15 |
| CRA022009VM | parâmetro | 278 | `rating_obrigacao` | Não há rating: não será atribuída nota de classificação de risco aos C | campo core do catálogo | Termo 355426, p.40, linhas 30-40 |
| CRA022009VM | parâmetro | 279 | `lastro` | Créditos do Agronegócio vinculados em caráter irrevogável e irretratáv | campo core do catálogo | Termo 355426, p.24, linhas 33-40 |
| CRA022009VM | parâmetro | 280 | `ordem_alocacao_itens_i_a_iii` | (i) despesas dos itens 15.2 e 15.3 e recomposição do Fundo de Despesas | campo core do catálogo | Termo 355426, p.66, linhas 24-37 |
| CRA022009VM | parâmetro | 281 | `ordem_alocacao_itens_iv_a_vi` | (iv) Remuneração dos CRA; (v) Valor Nominal Unitário dos CRA; (vi) sal | campo core do catálogo | Termo 355426, p.67, linhas 1-14 |
| CRA022009VM | regra de alerta | informe_cadastro_cra022009vm.json | `informe_cadastro_cra022009vm` | pendente | regra proposta; só roda com --preview | config\alert_rules\informe_cadastro_cra022009vm.json |
| CRA02500C1D | não se aplica | garantias.razao_minima | `garantias.razao_minima` | não se aplica | Os CRA não contam com garantia real ou fidejussória (Termo, p.14), então não há razão de garantia a monitorar. | parâmetro garantias_cra |
| CRA02500C1D | parâmetro | 282 | `numero_emissao` | 426 | campo core do catálogo | Termo 1065416, p.1, linhas 2-15 |
| CRA02500C1D | regra de alerta | contractual_cra02500c1d.json | `contractual_cra02500c1d` | pendente | regra proposta; só roda com --preview | config\alert_rules\contractual_cra02500c1d.json |
| CRA02500C1D | regra de alerta | informe_cadastro_cra02500c1d.json | `informe_cadastro_cra02500c1d` | pendente | regra proposta; só roda com --preview | config\alert_rules\informe_cadastro_cra02500c1d.json |
| todos | configuração | cross_checks.json | `verificações entre documentos` | proposto | define o que será extraído/comparado em todo ativo | config/contract_terms/cross_checks.json |
| todos | configuração | standard_fields.json | `catálogo de campos padrão` | proposto | define o que será extraído/comparado em todo ativo | config/contract_terms/standard_fields.json |

## Nível 3: Conferido visualmente, com observação (110)

| Ativo | Tipo | Id | Nome | Valor | Por quê | Fonte |
|---|---|---|---|---|---|---|
| 24G2100031 | fato | 419 | `aviso_rating_preliminar` | AA-(EXP)sf(bra) - Fitch Ratings, preliminar, realizada em 2024-07-29 | conferido visualmente; ler a observação da proposta | Aviso ao Mercado 722271, p.1 |
| 24G2100031 | fato | 421 | `aviso_publico_alvo` | Investidores Qualificados | conferido visualmente; ler a observação da proposta | Aviso ao Mercado 722271, p.1 |
| 24G2100031 | fato | 427 | `anuncio_rating_definitivo` | AA-(EXP)sf(bra) - Fitch Ratings, 'definitiva' segundo o Anúncio, reali | conferido visualmente; ler a observação da proposta | Anúncio de Início de Distribuição Pública 727228, p.1 |
| 24G2100031 | fato | 430 | `anuncio_cronograma_modificacao_oferta` | 2024-08-09 | conferido visualmente; ler a observação da proposta | Anúncio de Início de Distribuição Pública 727228, p.2 |
| 24G2100031 | fato | 436 | `lamina16_codigo_cvm_a_obter` | CVM: a ser obtido | conferido visualmente; ler a observação da proposta | Lâmina de Oferta de Securitização 722282, p.1 |
| 24G2100031 | fato | 446 | `lamina_spread_ate_2030_08_29` | 0.0150 | conferido visualmente; ler a observação da proposta | Lâmina de Oferta de Securitização 727225, p.2 |
| 24G2100031 | fato | 450 | `lamina_debentures_saldo_devedor_2024_06_30` | 1111934 | conferido visualmente; ler a observação da proposta | Lâmina de Oferta de Securitização 727225, p.4 |
| 24G2100031 | fato | 453 | `lamina_duration` | 4,86 anos, calculado em 2024-08-07 | conferido visualmente; ler a observação da proposta | Lâmina de Oferta de Securitização 727225, p.9 |
| 24G2100031 | fato | 456 | `lamina_garantia_af_a_ser_constituida` | a ser constituída (nos termos da Escritura Pública de Alienação Fiduci | conferido visualmente; ler a observação da proposta | Lâmina de Oferta de Securitização 727225, p.9 |
| 24G2100031 | fato | 459 | `lamina_rating` | AA-(EXP)sf(bra), em 2024-08-27 | conferido visualmente; ler a observação da proposta | Lâmina de Oferta de Securitização 727225, p.9 |
| 24G2100031 | fato | 463 | `prospecto_rating_preliminar_capa` | AA-(EXP)sf(bra) - Fitch Ratings, preliminar, realizada em 2024-07-29 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.1 |
| 24G2100031 | fato | 466 | `prospecto_garantias_capa` | AF de imóvel "a ser constituída"; cessão fiduciária de recebíveis "obs | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.1 |
| 24G2100031 | fato | 467 | `prospecto_contrato_cf_a_ser_celebrado` | Contrato de Cessão Fiduciária de Recebíveis "a ser celebrado" (capa) | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.1 |
| 24G2100031 | fato | 471 | `prospecto_duration` | 4,93 anos, calculado em 2024-07-24 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.8 |
| 24G2100031 | fato | 474 | `prospecto_resgate_facultativo_data_inicial` | 2027-08-29 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.11 |
| 24G2100031 | fato | 475 | `prospecto_premio_resgate_tabela` | 29/07/2026-29/07/2027: 1,50%; 29/07/2027-29/07/2028: 1,00%; 29/07/2028 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.12 |
| 24G2100031 | fato | 480 | `prospecto_rating_agencia_atualizacao_anual` | Fitch Ratings do Brasil Ltda. contratada pela Devedora; atualização an | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.14 |
| 24G2100031 | fato | 481 | `prospecto_spread_ate_72_mes` | 0.0150 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.14 |
| 24G2100031 | fato | 487 | `prospecto_prazo_escritura_af_imovel` | escritura de AF até 2024-08-25; constituição mediante registro no 1º R | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.17 |
| 24G2100031 | fato | 489 | `prospecto_cf_condicao_suspensiva` | condição suspensiva: registro do termo de liberação dos direitos credi | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.18 |
| 24G2100031 | fato | 495 | `prospecto_risco_af_nao_condicao_liquidacao` | registro da AF de imóvel não é condição precedente da liquidação finan | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.28 |
| 24G2100031 | fato | 508 | `prospecto_condicao_precedente_registro_cf_rtd` | comprovante de registro da cessão fiduciária de recebíveis no RTD, ant | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.106 |
| 24G2100031 | fato | 509 | `prospecto_condicao_precedente_protocolo_af` | comprovante de PROTOCOLO (não de registro) da escritura de AF no cartó | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.106 |
| 24G2100031 | fato | 510 | `prospecto_custo_rating_anual` | 30000.00 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.107 |
| 24G2100031 | fato | 517 | `prospecto_escritura_af_onus_existente_51pct` | 51% do imóvel já alienados fiduciariamente (instrumento de 2021, R-140 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.284 |
| 24G2100031 | fato | 518 | `prospecto_escritura_af_efeito_37_24_imediato` | 37,24% imediato; 51% apenas após registro da escritura e cancelamento  | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.285 |
| 24G2100031 | fato | 521 | `prospecto_escritura_debentures_vencimento` | 2036-08-27 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.291 |
| 24G2100031 | fato | 525 | `prospecto_fitch_rating_final_na_liquidacao` | o comunicado de rating da Fitch na liquidação incluirá os ratings fina | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 722286, p.530 |
| 24G2100031 | fato | 746 | `prosp_def_registro_cvm` | CVM/SRE/AUT/CRI/PRI/2024/622, concedido em 2024-08-27 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.1 |
| 24G2100031 | fato | 747 | `prosp_def_rating_capa` | AA-(EXP)sf(bra) - Fitch Ratings, rotulada 'definitiva' na capa, realiz | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.1 |
| 24G2100031 | fato | 748 | `prosp_def_publicacao_e_republicacao` | Prospecto publicado originalmente em 2024-07-29 e republicado em 2024- | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.1 |
| 24G2100031 | fato | 749 | `prosp_def_escritura_emissao_registro_aditamento` | Escritura de Emissão (26/07/2024) registrada na JUCESP em 2024-08-06 s | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.1 |
| 24G2100031 | fato | 750 | `prosp_def_escritura_af_data_celebracao` | 2024-08-23 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.1 |
| 24G2100031 | fato | 751 | `prosp_def_contrato_cf_celebracao_registro_rtd` | Contrato de Cessão Fiduciária celebrado em 2024-07-26 e registrado no  | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.1 |
| 24G2100031 | fato | 752 | `prosp_def_garantias_capa` | AF de imóvel "a ser constituída"; cessão fiduciária de recebíveis "cel | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.1 |
| 24G2100031 | fato | 753 | `prosp_def_duration` | 4,86 anos, calculado em 2024-08-07 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.8 |
| 24G2100031 | fato | 754 | `prosp_def_resgate_facultativo_data_inicial` | 2026-08-29 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.11 |
| 24G2100031 | fato | 755 | `prosp_def_premio_resgate_tabela` | 29/08/2026-29/08/2027: 1,50%; 29/08/2027-29/08/2028: 1,00%; 29/08/2028 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.12 |
| 24G2100031 | fato | 756 | `prosp_def_amortizacao_extraordinaria_data_inicial` | 2026-08-29 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.12 |
| 24G2100031 | fato | 757 | `prosp_def_amortizacao_extraordinaria_premio_tabela` | 29/08/2026-29/08/2027: 1,50%; 29/08/2027-29/08/2028: 1,00%; 29/08/2028 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.13 |
| 24G2100031 | fato | 758 | `prosp_def_follow_on_premio_condicao` | prêmio acrescido somente se o Percentual de Liberação das Garantias Fo | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.13 |
| 24G2100031 | fato | 760 | `prosp_def_spread_ate_2030_08_29` | 0.0150 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.14 |
| 24G2100031 | fato | 761 | `prosp_def_spread_a_partir_2030_08_29` | 0.0275 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.14 |
| 24G2100031 | fato | 771 | `prosp_def_intencoes_perante_coordenador_lider` | cada intenção de investimento foi realizada perante o Coordenador Líde | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.70 |
| 24G2100031 | fato | 772 | `prosp_def_bookbuilding_sem_rateio` | demanda não excedeu o Valor Total da Emissão; sem rateio | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.71 |
| 24G2100031 | fato | 775 | `prosp_def_divida_liquida_ebitda_ajustado_2024_06_30` | 4.74 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.44 |
| 24G2100031 | fato | 776 | `prosp_def_fitch_rating_final_atribuido` | AA-sf(bra), perspectiva estável, atribuído pela Fitch em 2024-08-27 à  | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.600 |
| 24G2100031 | fato | 779 | `prosp_def_fitch_spread_72_73_meses` | spread 1,5% a.a. até 72 meses após a integralização; a partir do 73º m | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.602 |
| 24G2100031 | fato | 780 | `prosp_def_fitch_documentos_finais_ate` | Fitch recebeu os documentos finais da transação até 2024-08-27, em con | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 727241, p.602 |
| 24G2100031 | fato | 783 | `enc_montante_total_data_emissao` | 230000000.00 | conferido visualmente; ler a observação da proposta | Anúncio de Encerramento de Distribuição Pública 730623, p.1 |
| 24G2100031 | fato | 784 | `enc_rating_definitiva_grafia` | AA-(EXP)sf(bra) - Fitch Ratings Brasil, rotulada 'definitiva', realiza | conferido visualmente; ler a observação da proposta | Anúncio de Encerramento de Distribuição Pública 730623, p.1 |
| 24G2100031 | fato | 787 | `enc_subscritores_total` | 1710 | conferido visualmente; ler a observação da proposta | Anúncio de Encerramento de Distribuição Pública 730623, p.2 |
| 24G2100031 | fato | 788 | `enc_total_cri_subscritos` | 230000 | conferido visualmente; ler a observação da proposta | Anúncio de Encerramento de Distribuição Pública 730623, p.2 |
| CRA022009VM | fato | 237 | `amortizacao_extraordinaria_pu_juros_moratorios_retificado` | 8.59505233 | conferido visualmente; ler a observação da proposta | Outros Comunicados Não Considerados Fatos Relevantes  1140992, p.2 |
| CRA022009VM | fato | 258 | `df_direitos_creditorios_nao_circulante` | 100000 | conferido visualmente; ler a observação da proposta | Demonstrações Financeiras 485809, p.17 |
| CRA022009VM | fato | 259 | `df_direitos_creditorios_circulante` | 4393 | conferido visualmente; ler a observação da proposta | Demonstrações Financeiras 485809, p.17 |
| CRA022009VM | fato | 282 | `df_caixa_equivalentes` | 345 | conferido visualmente; ler a observação da proposta | Demonstrações Financeiras 698040, p.16 |
| CRA022009VM | fato | 285 | `df_fundo_retencao` | 181 | conferido visualmente; ler a observação da proposta | Demonstrações Financeiras 698040, p.20 |
| CRA022009VM | fato | 286 | `df_direitos_creditorios_circulante` | 3724 | conferido visualmente; ler a observação da proposta | Demonstrações Financeiras 698040, p.7 |
| CRA022009VM | fato | 311 | `df_fundo_retencao` | 0 | conferido visualmente; ler a observação da proposta | Demonstrações Financeiras 935390, p.19 |
| CRA022009VM | fato | 313 | `df_direitos_creditorios_circulante` | 32909 | conferido visualmente; ler a observação da proposta | Demonstrações Financeiras 935390, p.7 |
| CRA022009VM | fato | 314 | `df_direitos_creditorios_nao_circulante` | 39998 | conferido visualmente; ler a observação da proposta | Demonstrações Financeiras 935390, p.17 |
| CRA022009VM | fato | 335 | `comunicado_waiver_fee_prazo_recebimento` | 2024-03-20 | conferido visualmente; ler a observação da proposta | Outros Comunicados Não Considerados Fatos Relevantes  620811, p.1 |
| CRA022009VM | fato | 339 | `reuniao_trimestral_devedora_anunciada` | 2024-05-15 | conferido visualmente; ler a observação da proposta | Outros Comunicados Não Considerados Fatos Relevantes  657326, p.1 |
| CRA022009VM | fato | 342 | `reuniao_trimestral_devedora_anunciada` | 2024-08-14 | conferido visualmente; ler a observação da proposta | Outros Comunicados Não Considerados Fatos Relevantes  713883, p.1 |
| CRA022009VM | fato | 345 | `reuniao_trimestral_devedora_anunciada` | 2024-11-26 | conferido visualmente; ler a observação da proposta | Outros Comunicados Não Considerados Fatos Relevantes  770804, p.1 |
| CRA022009VM | fato | 348 | `reuniao_trimestral_devedora_anunciada` | 2025-09-09 | conferido visualmente; ler a observação da proposta | Outros Comunicados Não Considerados Fatos Relevantes  982255, p.1 |
| CRA022009VM | fato | 355 | `assembleia_dfs_2023_1a_convocacao_presenca` | não instalada: presentes 12,17% dos CRA (abaixo do quórum de instalaçã | conferido visualmente; ler a observação da proposta | AGO/E 521170, p.2 |
| CRA022009VM | fato | 364 | `assembleia_cdca_2024_convocacao_1a` | 1ª convocação 2024-03-14 às 10:00 (Zoom); edital de 23/02/2024 | conferido visualmente; ler a observação da proposta | AGO/E 608832, p.1 |
| CRA022009VM | fato | 369 | `assembleia_cdca_2024_proposta_waiver_fee` | 0,5% sobre o Saldo Devedor do CDCA na próxima Data de Pagamento, desti | conferido visualmente; ler a observação da proposta | AGO/E 608832, p.2 |
| CRA022009VM | fato | 371 | `assembleia_cdca_2024_quorum_deliberacao_1a` | 2/3 mais um dos CRA em Circulação (cláusula 14.18 do Termo) | conferido visualmente; ler a observação da proposta | AGO/E 608832, p.3 |
| CRA022009VM | fato | 372 | `assembleia_cdca_2024_proposta_inicio_amortizacao_extraordinaria` | 01/04/2026 (proposta da Devedora) | conferido visualmente; ler a observação da proposta | AGO/E 608833, p.3 |
| CRA022009VM | fato | 373 | `assembleia_cdca_2024_proposta_limite_vencimento_recebiveis` | Duplicatas, CPR e Recebíveis de Compra e Venda (Cessão Fiduciária) sem | conferido visualmente; ler a observação da proposta | AGO/E 608833, p.3 |
| CRA022009VM | fato | 378 | `assembleia_cdca_2024_aprovacao_i_nao_declaracao_vencimento_antecipado` | aprovada por Titulares presentes que representam 77,87% dos CRA em Cir | conferido visualmente; ler a observação da proposta | AGO/E 619771, p.2 |
| CRA022009VM | fato | 379 | `assembleia_cdca_2024_aprovacao_ii_anuencia_divida_liquida_ebitda` | aprovada (77,87% dos CRA em Circulação, dos presentes), com ressalvas: | conferido visualmente; ler a observação da proposta | AGO/E 619771, p.3 |
| CRA022009VM | fato | 383 | `assembleia_cdca_2024_cronograma_amortizacao_2024_12_30` | 30000000.00 | conferido visualmente; ler a observação da proposta | AGO/E 619771, p.3 |
| CRA022009VM | fato | 384 | `assembleia_cdca_2024_cronograma_amortizacao_2025_12_30` | 30002000.00 | conferido visualmente; ler a observação da proposta | AGO/E 619771, p.3 |
| CRA022009VM | fato | 385 | `assembleia_cdca_2024_cronograma_amortizacao_2026_12_30` | 39998000.00 | conferido visualmente; ler a observação da proposta | AGO/E 619771, p.3 |
| CRA022009VM | fato | 386 | `assembleia_cdca_2024_cronograma_percentuais` | 0,0000% (2022); 0,0000% (2023); 30,0000% (2024); 42,8600% (2025); 100, | conferido visualmente; ler a observação da proposta | AGO/E 619771, p.3 |
| CRA022009VM | fato | 388 | `assembleia_cdca_2024_condicao_a_waiver_fee` | 0,75% sobre o saldo devedor dos CRA em 14/03/2024, parcela única, em a | conferido visualmente; ler a observação da proposta | AGO/E 619771, p.4 |
| CRA022009VM | fato | 391 | `assembleia_cdca_2024_condicao_d_capex` | CAPEX de 2024 limitado a R$ 15.000.000,00, apurado pela saída de caixa | conferido visualmente; ler a observação da proposta | AGO/E 619771, p.4 |
| CRA022009VM | fato | 401 | `assembleia_dfs_2024_convocacao_2a` | 2ª convocação 2024-10-10 às 11:15 (Zoom); ordem do dia: DFs do PS de 3 | conferido visualmente; ler a observação da proposta | AGO/E 750834, p.1 |
| CRA022009VM | fato | 407 | `df2024_parecer_auditor` | opinião sem modificação (Grant Thornton), relatório de 12/07/2024 | conferido visualmente; ler a observação da proposta | AGO/E 725269, p.10 |
| CRA022009VM | fato | 408 | `df2024_datas_inicio_termino_emissao` | 2022-09-21 a 2027-09-30 | conferido visualmente; ler a observação da proposta | AGO/E 725269, p.17 |
| CRA022009VM | fato | 412 | `df2024_pagamento_juros_exercicio` | 18846 | conferido visualmente; ler a observação da proposta | AGO/E 725269, p.26 |
| CRA022009VM | fato | 413 | `df2024_saldo_cra_31_03_2024` | 103724 | conferido visualmente; ler a observação da proposta | AGO/E 725269, p.26 |
| CRA022009VM | fato | 414 | `df2024_caracteristicas_amortizacao` | amortização anual parcial a partir de 30/12/2025 (cronograma original  | conferido visualmente; ler a observação da proposta | AGO/E 725269, p.26 |
| CRA02500C1D | fato | 539 | `aviso_coordenador_lider` | Itaú BBA Assessoria Financeira S.A. | conferido visualmente; ler a observação da proposta | Aviso ao Mercado 1040833, p.1 |
| CRA02500C1D | fato | 557 | `lamina_serie_4_e_5_classe` | 4ª e 5ª séries: CRA Subordinados | conferido visualmente; ler a observação da proposta | Lâmina de Oferta de Securitização 1040834, p.2 |
| CRA02500C1D | fato | 561 | `lamina_serie_1_taxa_teto_spread_sobre_di_futuro` | 0.012 | conferido visualmente; ler a observação da proposta | Lâmina de Oferta de Securitização 1040834, p.7 |
| CRA02500C1D | fato | 563 | `lamina_serie_1_taxa_teto_prefixada` | 0.148 | conferido visualmente; ler a observação da proposta | Lâmina de Oferta de Securitização 1040834, p.7 |
| CRA02500C1D | fato | 571 | `lamina_serie_1_prazo_dias_corridos` | 1829 | conferido visualmente; ler a observação da proposta | Lâmina de Oferta de Securitização 1040834, p.6 |
| CRA02500C1D | fato | 587 | `lamina_rating_classificacao_e_data` | A.br; realizada em 2025-11-14 | conferido visualmente; ler a observação da proposta | Lâmina de Oferta de Securitização 1040834, p.9 |
| CRA02500C1D | fato | 632 | `prelim1_serie_1_taxa_teto_definicao` | a maior entre (i) Taxa DI do contrato futuro com vencimento em 02/01/2 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 1040835, p.16 |
| CRA02500C1D | fato | 640 | `prelim2_serie_1_taxa_teto_definicao` | a maior entre (i) Taxa DI do contrato futuro com vencimento em 02/01/2 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 1047358, p.16 |
| CRA02500C1D | fato | 644 | `prelim1_moody_rating_proposta_notas_comerciais` | A.br (Notas Comerciais 1ª e 2ª Séries, proposta); rating preliminar, 1 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 1040835, p.837 |
| CRA02500C1D | fato | 645 | `prelim1_moody_alavancagem_proforma_carlos_lee` | 3.9x pró-forma (dívida bruta/EBITDA) contra 2.7x nos 12 meses até 2025 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 1040835, p.839 |
| CRA02500C1D | fato | 669 | `def_serie_5_vencimento` | 2035-12-19 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 1065463, p.15 |
| CRA02500C1D | fato | 678 | `def_serie_1_remuneracao_prefixada` | 0.148 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 1065463, p.16 |
| CRA02500C1D | fato | 700 | `def_destinacao_cronograma_percentual_semestral` | 0.05 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 1065463, p.29 |
| CRA02500C1D | fato | 703 | `def_destinacao_gastos_carnes_5_anos` | 3982332000.00 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 1065463, p.30 |
| CRA02500C1D | fato | 720 | `def_custo_total_distribuicao` | 12056725.39 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 1065463, p.169 |
| CRA02500C1D | fato | 725 | `def_fundo_despesas_valor_inicial` | 295000.00 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 1065463, p.377 |
| CRA02500C1D | fato | 726 | `def_fundo_despesas_valor_minimo` | 95000.00 | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 1065463, p.377 |
| CRA02500C1D | fato | 728 | `def_anexo_conflito_interesses_subclasses` | Classe Subordinada: 1 subclasse Mezanino e 2 subclasses Subordinadas J | conferido visualmente; ler a observação da proposta | Prospecto de Distribuição Pública 1065463, p.841 |
| CRA02500C1D | fato | 735 | `termo_oferta_quantidade_maxima_series_1_e_2` | 250000 | conferido visualmente; ler a observação da proposta | Documento 1040836, p.37 |
| CRA02500C1D | fato | 736 | `termo_oferta_serie_1_taxa_teto_prefixada` | 0.148 | conferido visualmente; ler a observação da proposta | Documento 1040836, p.40 |
| CRA02500C1D | fato | 803 | `enc_rating_definitivo_seniores` | Moody's Local BR; escala nacional A.br (CRA Sêniores); realizada em 20 | conferido visualmente; ler a observação da proposta | Anúncio de Encerramento de Distribuição Pública 1068059, p.1 |
| CRA02500C1D | fato | 807 | `enc_serie_1_total_subscritores_e_cra` | 998 subscritores; 233.142 CRA subscritos e integralizados | conferido visualmente; ler a observação da proposta | Anúncio de Encerramento de Distribuição Pública 1068059, p.3 |
| CRA02500C1D | fato | 808 | `enc_serie_2_total_subscritores_e_cra` | 173 subscritores; 16.858 CRA subscritos e integralizados | conferido visualmente; ler a observação da proposta | Anúncio de Encerramento de Distribuição Pública 1068059, p.3 |

## Nível 5: Sem conferência visual (10)

| Ativo | Tipo | Id | Nome | Valor | Por quê | Fonte |
|---|---|---|---|---|---|---|
| 24G2100031 | fato | 832 | `prosp_def_fitch_acao_rating` | Natl LT: AA-sf(bra), Rating Outlook Stable, New Rating; anterior (PRIO | sem conferência visual; tem observação na proposta | Prospecto de Distribuição Pública 727241, p.601 |
| 24G2100031 | fato | 833 | `enc_pessoas_naturais_subscritores` | 1709 | sem conferência visual; tem observação na proposta | Anúncio de Encerramento de Distribuição Pública 730623, p.2 |
| 24G2100031 | fato | 834 | `enc_pessoas_naturais_cri` | 221120 | sem conferência visual; tem observação na proposta | Anúncio de Encerramento de Distribuição Pública 730623, p.2 |
| 24G2100031 | fato | 835 | `enc_instituicoes_financeiras_ligadas_subscritores` | 1 | sem conferência visual; tem observação na proposta | Anúncio de Encerramento de Distribuição Pública 730623, p.2 |
| 24G2100031 | fato | 836 | `enc_instituicoes_financeiras_ligadas_cri` | 8880 | sem conferência visual; tem observação na proposta | Anúncio de Encerramento de Distribuição Pública 730623, p.2 |
| CRA022009VM | fato | 837 | `assembleia_cdca_2024_presenca_titulares` | Titulares presentes: 77,87% dos CRA em Circulação; também presentes De | sem conferência visual; tem observação na proposta | AGO/E 619771, p.1 |
| CRA022009VM | fato | 838 | `assembleia_dfs_2024_2a_convocacao_sem_quorum` | não instalada: sem investidores representativos do quórum mínimo de in | sem conferência visual; tem observação na proposta | AGO/E 755722, p.2 |
| CRA022009VM | parâmetro | 268 | `numero_series` | 1 (série única) | parâmetro sem conferência visual | Termo 355426, p.32, linhas 5-18 |
| CRA022009VM | parâmetro | 275 | `atualizacao_monetaria` | Não há atualização monetária | parâmetro sem conferência visual | Termo 355426, p.33, linhas 28-39 |
| CRA022009VM | parâmetro | 277 | `encargos_moratorios` | Multa moratória não compensatória de 2% + juros de mora de 1% ao mês,  | parâmetro sem conferência visual | Termo 355426, p.38, linhas 11-24 |

## Nível 4: Conferido, sem observação (aprovação em bloco)

- 24G2100031: golden set `IMCRI-AJ-018` (InfoCreditos/OutrasInfoCreditosAReceber/PeriodicidadeAvaliacaoGarantias)
- 24G2100031: golden set `IMCRI-AJ-019` (FluxoCaixaLiquidoMes/VariacaoLiquidaCaixaPatrimonioSeparado)
- CRA02500C1D: golden set `IMCRA-ALB-011` (DetalhesSeries/Series/Serie/IndiceSubordinacaoMinimo)
- CRA02500C1D: golden set `IMCRA-ALB-012` (Passivo/ReducaoVlrEmissao)
- CRA02500C1D: golden set `IMCRA-ALB-014` (DetalhesSeries/Series/Serie/RendimentosDistribuidosPeriodo)
- CRA02500C1D: golden set `IMCRA-ALB-015` (DadosGerais/Emissao/DataEmissao)
- 24G2100031: **2 fatos** (ids em `reports/fila_revisao_ids/24g2100031_nivel4_fatos.json`)

Para aprovar um bloco depois da sua decisão (exemplo):

```powershell
python scripts/review_reported_facts.py --cetip CRA02500C1D --status approved --by "Enrico Suman Marques" --ids-file reports/fila_revisao_ids/cra02500c1d_nivel4_fatos.json
```
