# Ficha contratual: CRA02300TBL (CRA)

- Securitizadora: Eco Securitizadora de Direitos Creditórios do Agronegócio.
- Documentos lidos (3, do mais antigo para o mais novo; 1077 páginas): Termo de Securitização 559866 (2023-11-28); Termo de Securitização 574175 (2023-12-21); Termo de Securitização 574430 (2023-12-21).
- **Material de leitura, não parâmetro aprovado.** Trechos localizados por palavras-chave (`config/contract_terms/field_topics.json`): a definição vem do documento mais recente que a traz; a cláusula é a página do corpo com mais menções do campo, com as páginas vizinhas que também o mencionam; anexos aparecem à parte. Página de OCR pode ter erro de leitura: conferir no PDF.
**Cobertura:** 30 de 36 campos com trecho; essenciais 20 de 23.
Sem trecho: `identificacao.isin`, `identificacao.classe_serie`, `garantias.razao_minima`, `garantias.liberacao`, `vencimento_antecipado.pagamento_e_quorum`, `resgate.waiver_fee`.


## Identificação

### ISIN (`identificacao.isin`, essencial)

- Sem trecho localizado: o campo pode não se aplicar ou estar com outra redação.

### Número da emissão (`identificacao.numero_emissao`, essencial)

- Cláusula, doc 559866 p. 32:

  > 5.2. Emissão: 223ª (ducentésima vigésima terceira) emissão de CRA da Emissora. 5.3. Séries: A Emissão será composta por até 2 (duas) Séries. A quantidade de Séries da Emissão, bem como a quantidade de CRA a ser alocada em cada Série serão definidas após a conclusão do Procedimento de Bookbuilding, observado (i) que a alocação dos CRA entre as Séries previstas neste Termo de Securitização ocorrerá no sistema de vasos…

- Também em: 559866 p. 1, 559866 p. 3, 559866 p. 15, 559866 p. 26, 559866 p. 86, 559866 p. 87, 574175 p. 1, 574175 p. 2

- Em anexos: 559866 p. 88, 559866 p. 302, 559866 p. 304, 574175 p. 21, 574175 p. 23, 574175 p. 35, 574175 p. 46, 574175 p. 47

### Número de séries (`identificacao.numero_series`, importante)

- Cláusula, doc 559866 p. 32:

  > 5.3. Séries: A Emissão será composta por até 2 (duas) Séries. A quantidade de Séries da Emissão, bem como a quantidade de CRA a ser alocada em cada Série serão definidas após a conclusão do Procedimento de Bookbuilding, observado (i) que a alocação dos CRA entre as Séries previstas neste Termo de Securitização ocorrerá no sistema de vasos comunicantes, de acordo com o qual a quantidade de CRA emitida em uma das Séri…

- Também em: 559866 p. 1, 559866 p. 3, 559866 p. 9, 559866 p. 15, 559866 p. 23, 559866 p. 26, 574175 p. 1, 574175 p. 2

- Em anexos: 559866 p. 88, 559866 p. 302, 559866 p. 304, 574175 p. 21, 574175 p. 23, 574175 p. 29, 574175 p. 35, 574175 p. 43

### Devedor / cedente / avalista (`identificacao.devedor`, essencial)

- Termo (regex) × CVM, devedor: **diverge**; Termo: 00.405.805/0001-15; 02.392.738/0001-77; 06.116.723/0001-37; 33.866.324/0001-66; 60.746.948; CVM: 27.490.581/0001-43
- Definição, doc 559866 p. 13:

  > “Devedora”:: significa a LAVORO AGRO HOLDING S.A., sociedade por ações de capital fechado, com sede na Cidade de Rondonópolis, Estado do Mato Grosso, na Avenida Daniel Clemente, nº 87, Lote B, Quadra Ind-4, Bairro Loteamento Distrito Industrial, CEP 78745-830, inscrita no CNPJ/MF sob o nº 06.116.723/0001-37;

- Cláusula, doc 574430 p. 3:

  > Holding S.A., inscrita no CNPJ/MF nº 27.490.581/0001-43 (“Notas Comerciais Escriturais” e “Devedora”, respectivamente), nos termos do Termo da 1ª (Primeira) Emissão de Notas Comerciais Escriturais, em até 2 (Duas) Séries, para Colocação Privada, da Lavoro Agro Holding S.A.”, celebrado entre a Devedora, a Securitizadora, a Lavoro Agrocomercial S.A., inscrita no CNPJ/MF sob o nº 06.116.723/0001-37 (“Lavoro Agrocomerci…

- Também em: 574175 p. 3

- Em anexos: 574175 p. 33, 574430 p. 33

### Agente fiduciário e remuneração (`identificacao.agente_fiduciario`, complementar)

- Cláusula, doc 574430 p. 2:

  > dos Titulares de CRA, nomeado nos termos da Resolução CVM 17, neste ato representada na forma de seu estatuto social (“Agente Fiduciário” e em conjunto com a Securitizadora, as “Partes”); CONSIDERANDO QUE: (i) a Emissora e o Agente Fiduciário celebraram, em 24 de novembro de 2023, o “Termo de Securitização de Direitos Creditórios do Agronegócio para Emissão de

- Também em: 559866 p. 3, 559866 p. 71, 559866 p. 72, 574175 p. 2

- Em anexos: 574175 p. 23, 574175 p. 91, 574175 p. 92, 574430 p. 23, 574430 p. 91, 574430 p. 92

### Lastro (créditos que originam os CRI/CRA) (`identificacao.lastro`, essencial)

- Cláusula, doc 559866 p. 46:

  > como outros documentos comprobatórios que tenham sido solicitados pelo Agente Fiduciário dos CRA (“Documentos Comprobatórios Lastro”). 5.19.5. Uma vez entregues as cópias eletrônicas dos Documentos Comprobatórios Lastro, pela Emissora e pelas Cedentes Fiduciantes, à Securitizadora e ao Agente Fiduciário, nos termos da Cláusula 5.19 acima, a Emissora fica desobrigada com relação às comprovações da utilização do Reemb…

- Também em: 559866 p. 2, 559866 p. 28, 559866 p. 59, 559866 p. 70, 559866 p. 78, 574175 p. 13, 574430 p. 13

- Em anexos: 574175 p. 22, 574175 p. 48, 574175 p. 66, 574175 p. 78, 574175 p. 90, 574175 p. 98, 574430 p. 22, 574430 p. 48

### Classe da série (sênior, mezanino, subordinada) (`identificacao.classe_serie`, essencial)

- Sem trecho localizado: o campo pode não se aplicar ou estar com outra redação.

## Emissão

### Data de emissão (`emissao.data_emissao`, essencial)

- Termo (regex) × CVM, data_emissao: **concorda**; Termo: 2023-12-22; CVM: 2023-12-22
- Definição, doc 559866 p. 11:

  > “Data de Emissão”: significa a data de emissão dos CRA, qual seja, 22 de dezembro de 2023; “Data de Integralização”: significa cada data que ocorrer a integralização dos CRA; “Data de Pagamento da significa as datas em que a Emissora deverá realizar o Remuneração dos CRA”: pagamento da Remuneração dos CRA, conforme descrito

- Cláusula, doc 559866 p. 32–33 (trecho da p. 33):

  > 5.7. Data da Emissão: A Data de Emissão dos CRA é 22 de dezembro de 2023. 5.8. Local da Emissão: O local da Emissão é a Cidade de São Paulo, Estado de São Paulo. 5.9. Data de Vencimento: Observadas as hipóteses de Resgate Antecipado previstas neste Termo de Securitização, a Data de Vencimento dos CRA é 22 de dezembro de

- Também em: 559866 p. 12, 559866 p. 29, 559866 p. 40, 559866 p. 54, 559866 p. 74, 574175 p. 6, 574175 p. 7, 574175 p. 8

- Em anexos: 559866 p. 89, 559866 p. 305, 559866 p. 306, 559866 p. 307, 559866 p. 308, 559866 p. 309, 559866 p. 310, 559866 p. 311

### Data de vencimento final (`emissao.data_vencimento`, essencial)

- Termo (regex) × CVM, vencimento BRECOACRAF93: **concorda**; Termo: 2027-12-22; CVM: 2027-12-22
- Termo (regex) × CVM, vencimento BRECOACRAFA9: **concorda**; Termo: 2027-12-22; CVM: 2027-12-22
- Cláusula, doc 559866 p. 33:

  > 5.9. Data de Vencimento: Observadas as hipóteses de Resgate Antecipado previstas neste Termo de Securitização, a Data de Vencimento dos CRA é 22 de dezembro de 2027. 5.10. Forma e Comprovação de Titularidade: Os CRA serão emitidos de forma escritural. A titularidade dos CRA será comprovada por extrato emitido pela B3, enquanto estiverem eletronicamente custodiados na B3. Os CRA que não estiverem

- Também em: 559866 p. 11, 559866 p. 12, 559866 p. 37, 559866 p. 39, 559866 p. 40, 559866 p. 68, 559866 p. 78, 574175 p. 15

- Em anexos: 559866 p. 89, 559866 p. 90, 559866 p. 305, 559866 p. 306, 559866 p. 307, 559866 p. 308, 559866 p. 309, 559866 p. 310

### Valor total da emissão (`emissao.valor_total`, essencial)

- Termo (regex) × CVM, valor_total: **concorda**; Termo: 420000000.00; CVM: 420000000.00
- Definição, doc 574430 p. 6:

  > “Valor Total da Emissão”: Significa o valor da totalidade dos CRA emitidos no âmbito desta Oferta, qual seja, R$ 420.000.000,00 (quatrocentos e vinte milhões de reais) na Data de Emissão dos CRA, sendo (i) R$ 68.088.000,00 (sessenta e oito milhões e oitenta e oito mil reais) relativos aos CRA da Primeira Série; e (ii) R$ 351.912.000,00 (trezentos e cinquenta e um milhões e novecentos e doze mil reais) relativos aos

- Cláusula, doc 559866 p. 33:

  > 5.6. Valor Total da Emissão: O valor total da Emissão é de R$ 420.000.000,00 (quatrocentos e vinte milhões de reais), na Data de Emissão, sendo certo que o valor total de cada uma das Séries será definido de acordo com a demanda verificada no Procedimento de Bookbuilding, podendo tal valor ser aumentado em até 25% (vinte e cinco por cento), ou seja, R$ 105.000.000,00 (cento e cinco milhões de reais) em virtude do ex…

- Também em: 559866 p. 27, 574175 p. 3, 574175 p. 4, 574175 p. 6, 574175 p. 8, 574430 p. 3, 574430 p. 4, 574430 p. 8

- Em anexos: 574175 p. 47, 574175 p. 53, 574175 p. 71, 574430 p. 47, 574430 p. 53, 574430 p. 71

### Valor nominal unitário (`emissao.valor_nominal_unitario`, essencial)

- Termo (regex) × CVM, valor_nominal_unitario: **concorda**; Termo: 1000.00; 1000.00; 1000.00; CVM: 1000.00
- Definição, doc 559866 p. 27:

  > “Valor Mínimo”: significa o valor mínimo referente 20% (vinte por cento) do “Valor Nominal Unitário”: Valor Total da Emissão, o qual as Cedentes Fiduciantes se comprometeram, nos termos do Contrato de Cessão Fiduciária, a instruir os seus respectivos Clientes a realizarem os pagamentos devidos, decorrentes da comercialização de Insumos, nas Contas Garantias, observado que a Securitizadora verificará o atendimento ao…

- Cláusula, doc 559866 p. 33–34 (trecho da p. 33):

  > 5.5. Valor Nominal Unitário: Os CRA têm Valor Nominal Unitário de R$ 1.000,00 (mil reais) na Data de Emissão. 5.6. Valor Total da Emissão: O valor total da Emissão é de R$ 420.000.000,00 (quatrocentos e vinte milhões de reais), na Data de Emissão, sendo certo que o valor total de cada uma das Séries será definido de acordo com a demanda verificada no Procedimento de Bookbuilding, podendo tal valor ser aumentado em a…

- Também em: 559866 p. 22, 559866 p. 24, 559866 p. 37, 559866 p. 38, 559866 p. 39, 559866 p. 40, 559866 p. 41, 559866 p. 42

- Em anexos: 559866 p. 88, 559866 p. 89, 559866 p. 90, 574175 p. 42, 574175 p. 44, 574175 p. 47, 574175 p. 52, 574175 p. 53

### Quantidade de CRI/CRA (`emissao.quantidade_titulos`, essencial)

- Termo (regex) × CVM, quantidade: **concorda**; Termo: 420000; CVM: 420000
- Cláusula, doc 559866 p. 32:

  > 5.4. Quantidade de CRA: Serão emitidos 420.000 (quatrocentos e vinte mil) CRA, na Data de Emissão, podendo tal valor ser aumentado em até 25% (vinte e cinco por cento), ou seja, 105.000 (cento e cinco mil) em virtude do exercício da Opção de Lote Adicional, totalizando o montante agregado de até 525.000 (quinhentos e vinte e cinco mil). A quantidade de CRA a serem alocados como CRA da Primeira Série e como CRA da Se…

- Também em: 559866 p. 49, 574175 p. 7, 574175 p. 8, 574175 p. 12, 574430 p. 7, 574430 p. 8, 574430 p. 12

- Em anexos: 574175 p. 52, 574175 p. 60, 574175 p. 68, 574430 p. 52, 574430 p. 60, 574430 p. 68

## Remuneração e amortização

### Remuneração (indexador, taxa, spread) (`remuneracao.taxa`, essencial)

- Termo (regex) × CVM, remuneracao BRECOACRAF93: **concorda**; Termo: mult=100; taxa=0; taxa=100; taxa=14.2; taxa=3; taxa=5; CVM: CDI + 3,0000% a.a.
- Termo (regex) × CVM, remuneracao BRECOACRAFA9: **concorda**; Termo: mult=100; taxa=0; taxa=100; taxa=14.2; taxa=3; taxa=5; CVM: 14,2000% a.a.
- Definição, doc 559866 p. 24:

  > “Remuneração dos CRA”: Significa a Remuneração dos CRA da Primeira Série e a Remuneração dos CRA da Segunda Série, em conjunto; “Remuneração dos CRA significa a remuneração que será paga aos Titulares dos da Primeira Série”: CRA da Primeira Série, incidente sobre o Valor Nominal Unitário ou sobre o saldo do Valor Nominal Unitário, conforme o caso, desde a primeira Data de Integralização

- Cláusula, doc 559866 p. 34–39 (trecho da p. 36):

  > A Taxa DI deverá ser utilizada considerando idêntico número de casas decimais divulgado pela entidade responsável pelo seu cálculo. Para efeito do cálculo de DIk será sempre considerado a Taxa DI, divulgada no terceiro dia anterior à data de pagamento dos CRA (exemplo: para pagamento dos CRA no dia 15, o DIk considerado será o publicado no dia 12 pela B3, pressupondo-se que tanto os dias 12, 13, 14 e 15 são Dias Úte…

- Também em: 559866 p. 26, 559866 p. 40, 559866 p. 42, 559866 p. 43, 574175 p. 8, 574175 p. 9, 574175 p. 10, 574175 p. 11

- Em anexos: 559866 p. 89, 574175 p. 44, 574175 p. 46, 574175 p. 54, 574175 p. 55, 574175 p. 56, 574175 p. 57, 574175 p. 58

### Periodicidade de pagamento (`remuneracao.periodicidade`, essencial)

- Cláusula, doc 574430 p. 14–15 (trecho da p. 15):

  > aplicável, a Remuneração das Notas Comerciais Escriturais da Primeira Série (“Data de Pagamento da Remuneração das Notas Comerciais Escriturais da Primeira Série”) e da Segunda Série (“Data de Pagamento da Remuneração das Notas Comerciais Escriturais da Segunda Série”, e em conjunto com a Data de Pagamento da Remuneração das Notas Comerciais Escriturais da Primeira Série, a “Datas de Pagamento da Remuneração das Not…

- Também em: 559866 p. 2, 559866 p. 11, 559866 p. 22, 559866 p. 33, 559866 p. 34, 559866 p. 35, 559866 p. 37, 559866 p. 38

- Em anexos: 559866 p. 89, 559866 p. 90, 559866 p. 299, 574175 p. 22, 574175 p. 31, 574175 p. 42, 574175 p. 53, 574175 p. 54

### Primeira data de pagamento (`remuneracao.primeira_data_pagamento`, importante)

- Cláusula, doc 574430 p. 8:

  > Valor Nominal Unitário dos CRA da Primeira Série, desde a primeira Data de Integralização ou Data de Pagamento da Remuneração dos CRA da Primeira Série imediatamente anterior, conforme o caso até a respectiva Data de Pagamento da Remuneração dos CRA da Primeira Série ou até a data em que ocorrer o Resgate Antecipado. A Remuneração será paga, conforme o cronograma de pagamentos constante do Anexo III deste Termo de J…

- Também em: 559866 p. 34, 559866 p. 35, 559866 p. 37, 559866 p. 38, 559866 p. 39, 574175 p. 8, 574175 p. 10, 574175 p. 11

- Em anexos: 559866 p. 89, 574175 p. 54, 574175 p. 55, 574175 p. 57, 574175 p. 58, 574175 p. 59, 574175 p. 107, 574430 p. 54

### Cronograma e regra de amortização (`remuneracao.amortizacao`, essencial)

- Cláusula, doc 574430 p. 8:

  > ocorrer o Resgate Antecipado. A Remuneração será paga, conforme o cronograma de pagamentos constante do Anexo III deste Termo de JUR_SP - 50264066v12 - 1313099.505332

- Também em: 559866 p. 38, 574175 p. 8, 574175 p. 11, 574430 p. 11

- Em anexos: 574175 p. 57, 574430 p. 57

### Atualização monetária (`remuneracao.atualizacao_monetaria`, importante)

- Cláusula, doc 574430 p. 14:

  > modalidade de fiança (“Fiança”): a (i) Lavoro Agrocomercial S.A; Atualização Monetária (ii) Distribuidora Pitangueiras de Produtos Agropecuários S.A.; (iii) das Notas Comerciais Produtec Comércio e Representações S.A.; (iv) Futuragro Escriturais Distribuidora de Insumos Agrícolas Ltda.; (v) Denorpi Distribuidora Remuneração da de Insumos Agrícolas Ltda.; e (vi) Deragro Distribuidora de Primeira Série das Insumos Agr…

- Também em: 559866 p. 72, 574175 p. 14

- Em anexos: 559866 p. 88, 574175 p. 91, 574175 p. 106, 574430 p. 91, 574430 p. 106

### Encargos moratórios (`remuneracao.encargos_moratorios`, complementar)

- Cláusula, doc 559866 p. 42–44 (trecho da p. 44):

  > 5.16. Encargos Moratórios: Sem prejuízo da Remuneração, na hipótese de atraso no pagamento de qualquer quantia devida aos Titulares de CRA, incidirão, a partir do inadimplemento até a data de seu efetivo pagamento, multa moratória não compensatória de 2% (dois por cento) e juros de mora de 1% (um por cento) ao mês,

- Também em: 559866 p. 13, 559866 p. 14, 574175 p. 15, 574175 p. 16, 574430 p. 15, 574430 p. 16

- Em anexos: 559866 p. 90, 574175 p. 33, 574175 p. 34, 574175 p. 62, 574175 p. 64, 574175 p. 108, 574430 p. 33, 574430 p. 34

## Garantias e fundos

### Garantias da emissão (`garantias.descricao`, essencial)

- Definição, doc 559866 p. 7:

  > “Cessão Fiduciária”: significa a garantia constituída ou a ser constituída, pelas Cedentes Fiduciantes em favor da Securitizadora, nos termos do Contrato de Cessão Fiduciária, por meio da qual os Direitos Creditórios em Garantia foram ou serão cedidos fiduciariamente em garantia do pontual e integral adimplemento das obrigações da Devedora no âmbito do Termo de Emissão de Notas Comerciais Escriturais;

- Cláusula, doc 559866 p. 29–30 (trecho da p. 30):

  > 4.5.2. Cessão Fiduciária. As Notas Comerciais Escriturais contarão com garantia real, representada pela Cessão Fiduciária, observado que as Cedentes Fiduciantes se obrigaram a constituir a Cessão Fiduciária sobre os Direitos Creditórios em Garantia, nos termos do Contrato de Cessão Fiduciária, observado o Valor Mínimo. Aquisição dos Direitos Creditórios do Agronegócio

- Também em: 559866 p. 9, 559866 p. 12, 559866 p. 14, 559866 p. 24, 559866 p. 27, 559866 p. 67, 559866 p. 80, 559866 p. 81

- Em anexos: 559866 p. 305, 559866 p. 306, 559866 p. 307, 559866 p. 308, 559866 p. 309, 559866 p. 310, 559866 p. 311, 559866 p. 312

### Razão mínima de garantia (`garantias.razao_minima`, essencial)

- Sem trecho localizado: o campo pode não se aplicar ou estar com outra redação.

### Liberação e substituição de garantias (`garantias.liberacao`, importante)

- Sem trecho localizado: o campo pode não se aplicar ou estar com outra redação.

### Fundo de despesas (valor inicial, mínimo, recomposição) (`garantias.fundo_despesas`, essencial)

- Definição, doc 559866 p. 16:

  > “Fundo de Despesas”: significa o fundo de despesas composto por recursos mantidos na Conta de Fundo de Despesas e obtidos por meio (i) de dedução do Preço de Aquisição dos Direitos Creditórios do Agronegócio, (ii) de depósito direto pela Devedora; ou (iii) de recursos do Patrimônio Separado, o qual será utilizado para pagamento das Despesas e, enquanto seus recursos não forem utilizados, deverão ser

- Cláusula, doc 559866 p. 52–54 (trecho da p. 53):

  > CLÁUSULA VIII – DO FUNDO DE DESPESAS 8.1. O Fundo de Despesas será composto por meio de dedução do Preço de Aquisição, no montante equivalente a R$ 440.000,00 (quatrocentos e quarenta mil reais), e será utilizado para pagamento das despesas indicadas na Cláusula XV abaixo.

- Também em: 559866 p. 2, 559866 p. 8, 559866 p. 22, 559866 p. 31, 559866 p. 45, 559866 p. 57, 559866 p. 74, 559866 p. 79

- Em anexos: 574175 p. 22, 574175 p. 28, 574175 p. 36, 574175 p. 42, 574175 p. 51, 574175 p. 64, 574175 p. 72, 574175 p. 73

### Fundo de reserva, retenção ou liquidez (`garantias.fundo_reserva_retencao`, importante)

- Cláusula, doc 574430 p. 325:

  > Garantias: (i) Fiança; (ii) Fundo de Liquidez; Emissora: ECO SECURITIZADORA DE DIREITOS CREDITORIOS DO AGRONEGOCIO SA Ativo: CRA Série: 1 Emissão: 103

- Também em: 559866 p. 307, 559866 p. 312, 559866 p. 313, 559866 p. 319, 559866 p. 324, 559866 p. 328, 574175 p. 325, 574175 p. 330

## Covenants

### Covenants financeiros (dívida líquida/EBITDA, liquidez, endividamento) (`covenants.indices_financeiros`, essencial)

- Cláusula, doc 559866 p. 61:

  > (a) os cálculos dos Índices Financeiros da Devedora verificados pela Securitizadora, até 10 (dez) Dias Úteis após sua verificação conforme previsto no item (xviii) da Cláusula 8.2 do Termo de Emissão de Notas Comerciais Escriturais, para fins de acompanhamento do resultado pelo Agente Fiduciário; (b) dentro de 10 (dez) Dias Úteis contados do respectivo evento, cópias de todos os seus demonstrativos financeiros e/ou…

- Em anexos: 574175 p. 81, 574430 p. 81

### Restrições (dividendos, capex, mútuos) (`covenants.restricoes`, importante)

- Cláusula, doc 559866 p. 64:

  > (xii) não pagar dividendos com os recursos vinculados ao Patrimônio Separado; (xiii) manter em estrita ordem a sua contabilidade, por meio da contratação de prestador de serviço especializado, a fim de atender as exigências contábeis impostas pela CVM às companhias abertas, bem como efetuar os respectivos registros de acordo com os Princípios Fundamentais da Contabilidade do Brasil, permitindo ao Agente Fiduciário o…

- Em anexos: 574175 p. 84, 574430 p. 84

## Vencimento antecipado

### Hipóteses de vencimento antecipado (`vencimento_antecipado.hipoteses`, essencial)

- Cláusula, doc 559866 p. 62:

  > (g) comunicar em até 2 (dois) Dias Úteis do seu conhecimento a ocorrência de qualquer evento de vencimento antecipado das Notas Comerciais Escriturais (h) informar e enviar o organograma do grupo societário da Emissora, todos os dados financeiros e atos societários necessários à realização do relatório anual, conforme Resolução CVM 17, que venham a ser solicitados pelo Agente Fiduciário, os quais deverão ser devidam…

- Também em: 559866 p. 11, 559866 p. 31, 559866 p. 40, 559866 p. 71, 559866 p. 77, 574175 p. 13, 574175 p. 15, 574430 p. 13

- Em anexos: 574175 p. 31, 574175 p. 51, 574175 p. 59, 574175 p. 82, 574175 p. 90, 574175 p. 107, 574175 p. 108, 574430 p. 31

### Limites (cross default, protesto) e prazos de cura (`vencimento_antecipado.limites_e_prazos`, essencial)

- Cláusula, doc 559866 p. 69:

  > certidões atualizadas dos distribuidores cíveis, das Varas de Fazenda Pública, cartórios de protesto, das Varas do Trabalho, Procuradoria da Fazenda Pública ou outros órgãos pertinentes, onde se localiza o domicílio ou a sede do estabelecimento principal da Emissora e/ou da Devedora e/ou das Fiadoras; (xi) solicitar, quando considerar necessário, auditoria externa da Emissora ou do Patrimônio Separado, a custo do re…

- Em anexos: 574175 p. 88, 574430 p. 88

### Pagamento após vencimento antecipado e quórum de não declaração (`vencimento_antecipado.pagamento_e_quorum`, importante)

- Sem trecho localizado: o campo pode não se aplicar ou estar com outra redação.

### Eventos de liquidação do patrimônio separado (`vencimento_antecipado.liquidacao_ps`, importante)

- Cláusula, doc 559866 p. 56–57 (trecho da p. 56):

  > 10.5.1. Ocorrido um Evento de Liquidação do Patrimônio Separado, os Titulares de CRA deverão: (i) se submeter às decisões exaradas em Assembleia de Titulares de CRA; e (ii) possuir todos os requisitos necessários para assumir eventuais obrigações inerentes aos CRA emitidos e bens inerentes ao Patrimônio Separado. 10.6. Em caso de insuficiência dos créditos do Patrimônio Separado deverá ser

- Também em: 559866 p. 78

- Em anexos: 574175 p. 76, 574175 p. 98, 574430 p. 76, 574430 p. 98

## Resgate e waiver

### Resgate antecipado e amortização extraordinária (regras e datas) (`resgate.facultativo`, essencial)

- Definição, doc 559866 p. 25:

  > “Resgate Antecipado”:: significa o resgate antecipado dos CRA que será realizado na hipótese e na forma da Cláusula 5.14.2 deste Termo de Securitização;

- Cláusula, doc 559866 p. 37–42 (trecho da p. 40):

  > 5.14.2. Resgate Antecipado: A Emissora deverá realizar o Resgate Antecipado, na hipótese de ocorrência do Resgate Antecipado Facultativo das Notas Comerciais Escriturais, independentemente da anuência ou aceite prévio dos Titulares de CRA, conforme termos e condições previstos no Termo de Emissão. 5.14.2.1. Oferta de Resgate Antecipado Obrigatório dos CRA: A Emissora deverá, obrigatoriamente, de forma irrevogável e…

- Também em: 559866 p. 11, 559866 p. 20, 559866 p. 21, 559866 p. 22, 559866 p. 27, 559866 p. 33, 559866 p. 34, 559866 p. 43

- Em anexos: 559866 p. 89, 559866 p. 90, 574175 p. 31, 574175 p. 40, 574175 p. 41, 574175 p. 42, 574175 p. 45, 574175 p. 47

### Waiver fee e prêmios (`resgate.waiver_fee`, importante)

- Sem trecho localizado: o campo pode não se aplicar ou estar com outra redação.

## Obrigações de informação

### Prazos de entrega de DFs, relatórios e informações (`obrigacoes.dfs_e_relatorios`, essencial)

- Cláusula, doc 559866 p. 61–63 (trecho da p. 61):

  > (i) administrar o Patrimônio Separado, mantendo para o mesmo registro contábil próprio e independente de suas demonstrações financeiras; (ii) utilizar os recursos decorrentes dos pagamentos dos Direitos Creditórios do Agronegócio exclusivamente para o pagamento dos valores devidos aos Titulares dos CRA, conforme ordem de pagamento descrita na Cláusula 13.1 abaixo, conforme aplicável;

- Também em: 559866 p. 5, 559866 p. 42, 559866 p. 53, 559866 p. 54, 559866 p. 68, 559866 p. 70

- Em anexos: 559866 p. 346, 574175 p. 25, 574175 p. 61, 574175 p. 73, 574175 p. 74, 574175 p. 81, 574175 p. 82, 574175 p. 88

### Obrigação de rating (`obrigacoes.rating`, essencial)

- Cláusula, doc 559866 p. 47:

  > 5.20. Classificação de Risco: Não será atribuída nota de classificação de risco aos CRA. 5.21. Classificação ANBIMA dos CRA: Concentrado. Esta classificação foi realizada no momento inicial da Oferta, estando as características deste CRA sujeitas a

- Também em: 559866 p. 5

- Em anexos: 574175 p. 25, 574175 p. 67, 574430 p. 25, 574430 p. 67

### Destinação de recursos (`obrigacoes.destinacao_recursos`, importante)

- Cláusula, doc 559866 p. 45–46 (trecho da p. 45):

  > 5.19. Destinação dos Recursos: Os recursos obtidos com a subscrição dos CRA serão utilizados pela Emissora para (i) constituição do Fundo de Despesas; e (ii) pagamento do Preço de Aquisição. 5.19.1. Os recursos obtidos pela Devedora por meio da integralização das Notas

- Também em: 559866 p. 70, 574175 p. 14, 574430 p. 14

- Em anexos: 574175 p. 64, 574175 p. 66, 574175 p. 90, 574430 p. 64, 574430 p. 66, 574430 p. 90

## Governança

### Convocação, instalação e quóruns de assembleia (`governanca.quorum_assembleia`, importante)

- Cláusula, doc 559866 p. 72–77 (trecho da p. 75):

  > 14.1. Assembleia de Titulares de CRA: Os Titulares de CRA poderão, a qualquer tempo, reunir-se em Assembleia de Titulares de CRA, a fim de deliberarem sobre matéria de interesse da comunhão dos Titulares de CRA. 14.2. Competência: Sem prejuízo do disposto neste Termo de Securitização, compete privativamente à Assembleia de Titulares de CRA deliberar sobre as seguintes matérias:

- Também em: 559866 p. 5, 559866 p. 10, 559866 p. 37, 559866 p. 39, 559866 p. 48, 559866 p. 51, 559866 p. 52, 559866 p. 55

- Em anexos: 574175 p. 25, 574175 p. 31, 574175 p. 56, 574175 p. 57, 574175 p. 58, 574175 p. 59, 574175 p. 67, 574175 p. 68

### Ordem de pagamentos e alocação (cascata) (`governanca.ordem_pagamentos`, essencial)

- Cláusula, doc 559866 p. 74:

  > CLÁUSULA XIII – DA ORDEM DE ALOCAÇÃO DE RECURSOS 13.1. A partir da Data de Emissão até a quitação integral dos CRA, a Emissora obriga- se a utilizar os recursos financeiros decorrentes de quaisquer pagamentos relacionados aos Direitos Creditórios do Agronegócio, observada, obrigatoriamente, a seguinte ordem de alocação (“Ordem de Alocação de Recursos”):

- Também em: 559866 p. 2, 559866 p. 21, 559866 p. 58

- Em anexos: 574175 p. 22, 574175 p. 41, 574175 p. 77, 574175 p. 94, 574430 p. 22, 574430 p. 41, 574430 p. 77, 574430 p. 94

