"""Indicadores calculados na leitura, a partir do informe de FIDC ja carregado.

Nada e gravado: cada indicador e calculado por cima das observacoes, que
continuam sendo o dado original, sem tabela nova nem migration.

values: tipos de valor (estado presente ou sem_dado, motivo, proveniencia).
reading: conexao so de leitura e leitura das observacoes por competencia.
overdue: vencidos na carteira, faixas de atraso e evolucao entre
competencias.
prazo_de_vencimento: a distribuicao "Por Prazo de Vencimento (R$)", como o
informe a traz (indicador 10).
cedentes: os cedentes gravados (com CNPJ) por bloco, com o percentual como
informado; o cedente com CPF nao e gravado.
partes_relacionadas: as ALIENACOES do mes para o cedente e para prestadores
de servicos e partes relacionadas (tab_VII, itens VII.b.1 e VII.b.2).
reducao_valor_recuperacao: a "Provisao para Reducao no Valor de
Recuperacao" de cada bloco, como informada, e a cobertura dos vencidos.
subordinacao: a subordinacao das classes de FIDC pelas series da tab_X_2,
classificadas pelo quota_class_map (FU6.3).
segmentos: a "Carteira por Segmento" (tab_II), com o % de cada segmento no
total da propria tabela e a concentracao nos 11 segmentos de topo (FU11.4).
garantias: o valor (7.1) e o percentual (7.2) das garantias (tab_X_7), como
informados, sem conta entre os dois (FU11.4).
estrutura_report: as linhas do relatorio de segmento e garantias, so
contagens.
liquidez: as 7 faixas da liquidez (tab_X_5), como informadas, sem soma
(FU11.5).
rentabilidade: a rentabilidade apurada no mes, por serie (tab_X_3), como
informada (FU11.5).
desempenho: o desempenho esperado e o realizado, por serie (tab_X_6), como
informados, sem conta entre os dois, com a conferencia do realizado com a
tab_X_3 (FU11.5).
desempenho_report: as linhas do relatorio de liquidez, rentabilidade e
desempenho, so contagens.
"""
