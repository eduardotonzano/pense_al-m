"""FIC-FIDC: classificacao e conferencia com o CDA, calculadas na leitura (FU6.1).

classification: a regra da decisao 6 de Fundos. O sinal e a parcela do
ativo em cotas de FIDC no informe mensal de FIDC (tab_I.TAB_I2H_VL_COTA_FIDC
sobre tab_I.TAB_I_VL_ATIVO, na mesma competencia): 95% ou mais e FIC-FIDC;
de 67% a menos de 95% fica em revisao manual; abaixo de 67% nao e
classificado. A faixa sai da multiplicacao cruzada em Decimal, nunca da
divisao. Nunca classifica pelo nome.

Nada aqui grava a classificacao: ela e calculada por cima das observacoes,
que continuam sendo o dado original, sem tabela nova nem migration.
"""
