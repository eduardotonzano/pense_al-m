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
"""
