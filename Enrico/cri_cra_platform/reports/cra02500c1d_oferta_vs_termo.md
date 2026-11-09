# CRA Alibem (CRA02500C1D): documentos da oferta x Termo de Securitização

Ativo: 426ª emissão da Eco Securitizadora, 5 séries, R$ 750.000.000,00, ISIN da 1ª série BRECOACRALJ8 (asset_id 9).
Data da análise: 2026-10-28. Leitura somente de texto extraído (tabela `document_text_pages`); nada foi gravado no banco.
Este relatório registra diferenças e pontos de atenção. **Não decide qual documento prevalece.**

Abreviações: Av. = Aviso ao Mercado (1040833); Lâm. = Lâmina da Oferta (1040834); Anún. = Anúncio de Início (1065461);
Pp1 = Prospecto Preliminar (1040835); Pp2 = Prospecto Preliminar, segunda versão (1047358); Pd = Prospecto Definitivo (1065463);
TO = Termo de Securitização da oferta, 13/11/2025 (1040836, 154 pp.); TA = Termo atual (1065416, 183 pp.): **Adit.** = Primeiro
Aditamento de 17/12/2025 (pp. 1 a 27) e **Cons.** = Termo consolidado, Anexo D do Aditamento (pp. 28 a 183).
Numeração de página = página da extração em PDF. Nos Prospectos a página impressa é a da extração menos 10 (no corpo, até o Anexo I).

## 1. O que foi lido

| Documento | Doc. | Data no texto | Páginas lidas |
|---|---|---|---|
| Aviso ao Mercado | 1040833 | 14/11/2025 | 1 a 4 (todas) |
| Lâmina da Oferta | 1040834 | 14/11/2025 (rating) | 1 a 11 (todas) |
| Anúncio de Início | 1065461 | 17/12/2025 | 1 a 4 (todas) |
| Prospecto Preliminar | 1040835 (844 pp.) | 14/11/2025 | ver abaixo |
| Prospecto Preliminar, 2ª versão | 1047358 (842 pp.) | capa também diz 14/11/2025; rodapé V006 (a 1ª é V005) | 1, 14 e 120 diretamente; o resto por diferença de texto com 1040835 |
| Prospecto Definitivo | 1065463 (1.140 pp.) | 17/12/2025 | ver abaixo |
| Termo da oferta | 1040836 (154 pp.) | assinado 13/11/2025 (p. 125) | 36 a 43, 64 a 70, 117 a 121 diretamente; o resto por diferença de texto com o Termo atual |
| Termo atual | 1065416 (183 pp.) | Aditamento de 17/12/2025 | Aditamento (pp. 1 a 27) lido por inteiro; consolidado (pp. 28 a 183) por diferença de texto com o Termo da oferta e por busca nas páginas citadas |

Prospecto Definitivo (1065463), leitura direta: 1 a 9 (capa e índice completo), 13 a 31 (breve histórico da Emissora, sumário da oferta 2.3 a 2.6, destinação de recursos 3.1 a 3.5 e início dos fatores de risco), 61 a 67 (cronograma e dinâmica), 71, 73 a 78 (restrições, regime de distribuição, estrutura), 88 e 89 (Notas Comerciais), 120, 169 a 171 (custo da distribuição) e 1133 a 1138 (súmula de rating). Por busca de palavras-chave no texto das 1.140 páginas: "Vasos Comunicantes", "subclasse/Júnior", "Fundo de Despesas", "Valor Mínimo", "Comissão de Sucesso", "295.000", "Resgate Antecipado Facultativo", "quórum", "Garantia Firme", "Quantidade Máxima", "Índice Financeiro", "excluídos os CRA Subordinados", "Bradesco".
Prospecto Preliminar (1040835): 1, 14, 16, 33, 64, 73 e 170 por busca; súmula de rating 835 a 839 diretamente; todo o resto por diferença de texto.
Não li: fatores de risco da Devedora e macroeconômicos (Pd pp. 50 a 59), estatutos e atas, demonstrações financeiras anexas, formulário de referência, Contrato de Distribuição (resumo na seção 14, não lido por inteiro).

Comparações por diferença de texto (palavra a palavra, página a página, sobre todas as páginas):
- Pp1 x Pp2: as únicas diferenças são paginação (Pp2 tem 2 páginas a menos, por reposicionamento de páginas em branco e de índices; por exemplo o Anexo XIV está na p. 825 em Pp1 e na p. 823 em Pp2) e o rótulo do rodapé (V005 em Pp1, V006 em Pp2). **O texto é o mesmo.**
- Pp2 x Pd: ~615 diferenças de texto; depois de tirar índices e paginação, são as da seção 4.
- TO x TA consolidado: 1.443 diferenças brutas, quase todas de numeração/diagramação; as de conteúdo estão na seção 5.

## 2. Classe da 4ª série (Termo: Subordinada; Informe: Mezanino)

No banco, `asset_series` traz classe_informe = Mezanino e classe_termo = Subordinada para a 4ª série (CRA02500C1G); 3ª = Mezanino/Mezanino e 5ª = Subordinada/Subordinada.

| Documento | O que diz (página) |
|---|---|
| Aviso | 3 classes: sênior, mezanino, subordinada (p. 1). Não separa por série |
| **Lâmina** | "os CRA objeto da 1ª e da 2ª séries são os 'CRA Sêniores', os CRA objeto da **3ª série são os 'CRA Mezanino'** e os CRA objeto da **4ª e 5ª séries são os 'CRA Subordinados'**" (p. 2) |
| Anúncio | Só "classe sênior, classe mezanino e classe subordinada" (pp. 1 e 2); não separa por série |
| **Pp1/Pp2/Pd, capa** | "CRA DA 2ª SÉRIE... CRA SÊNIORES; CRA DA 3ª SÉRIE OU CRA MEZANINO; CRA DA 4ª SÉRIE E CRA DA 5ª SÉRIE... OS 'CRA SUBORDINADOS'" (p. 1, nas três versões) |
| Pd corpo | Mezanino subordina-se aos Sêniores; Subordinados aos Sêniores e aos Mezanino (pp. 25 e 31); Mezanino e Subordinados sem rating (p. 36); garantia firme de R$ 250 mi para Mezanino e melhores esforços de R$ 250 mi para Subordinados (p. 73) |
| Termo (TO e TA) | "CRA da 4ª Série: ... da Classe Subordinada" (Adit. p. 5); 4ª e 5ª = Subordinados (TO p. 37) |
| Declaração do Agente Fiduciário | "Classe Subordinada: **1 subclasse Mezanino e 2 subclasses Subordinadas Júniores**" (TO p. 143: "até 2"; Adit. p. 26 e Pd p. 841: "2") |

Conclusão sobre o texto: todos os documentos da oferta e o Termo tratam a 4ª série como **Subordinada**; Mezanino é só a 3ª (única série da classe, R$ 250 mi, sempre "fixa" nas quantidades). A declaração do Agente Fiduciário fala em 1 subclasse Mezanino + 2 Subordinadas Júniores, o que combina com 3ª = Mezanino e 4ª/5ª = Júniores, e **não** com duas séries Mezanino (3ª e 4ª), que é o que o Informe sugere. Nenhum documento da oferta chama a 4ª série de Mezanino.

## 3. Tabela comparativa dos termos principais

Valores iguais em todos os documentos onde citados, salvo onde a coluna "Situação" diz o contrário.

| Tema | Oferta (preliminar) | Oferta (definitiva) | Termo da oferta (TO) | Termo atual (TA) | Situação |
|---|---|---|---|---|---|
| Valor total, VNU, data de emissão | R$ 750.000.000,00; R$ 1.000,00; 15/12/2025 (Av. p. 1 e 2; Lâm. p. 2; Pp p. 1) | Igual (Anún. p. 2; Pd p. 1 e 14) | Igual (TO p. 37 e 38) | Igual (Adit. p. 10 e 12) | Sem diferença |
| Número de séries | "até 5" (Av. p. 1; Pp p. 1) | "5" (Anún. p. 1; Pd p. 1) | "até 5" (TO p. 36) | "5" (Adit. p. 11; Cons. p. 63) | Mudou (consequência do Bookbuilding) |
| Classes por série | 1ª e 2ª Sêniores, 3ª Mezanino, 4ª e 5ª Subordinadas (Lâm. p. 2; Pp p. 1) | Igual (Pd p. 1) | Igual (TO p. 36 e 37) | Igual (Adit. pp. 5 e 11) | Sem diferença |
| Quantidades por série | Só máximos: 1ª+2ª até 250.000; 3ª fixa 250.000; 4ª+5ª até 250.000 (Pp p. 14) | 233.142; 16.858; 250.000; 100.000; 150.000 (Anún. p. 2; Pd p. 1 e 14) | Só máximos (TO p. 37) | 233.142; 16.858; 250.000; 100.000; 150.000 (Adit. pp. 5 e 12; Cons. p. 64) | Mudou (Bookbuilding de 16/12/2025). Soma = 750.000 |
| 1ª série, remuneração | Prefixada limitada ao maior entre DI futuro de 02/01/2030 + 1,20% a.a. e 14,80% a.a. (Lâm. p. 2 e 7; Pp p. 1 e 16) | **14,80% a.a. prefixada** (Pd p. 1 e 16) | Teto como na oferta; taxa a definir (TO pp. 40 e 54) | 14,80% a.a. prefixada (Adit. p. 14; Cons. p. 67 e 81) | Mudou: taxa final = teto prefixado |
| 2ª série | 108,00% da Taxa DI (Lâm. p. 7; Pp p. 16) | Igual (Pd p. 16) | Igual (TO p. 41 e 55) | Igual (Cons. p. 68 e 82) | Sem diferença |
| 3ª série | 100% DI + 1,50% a.a. (Lâm. p. 7) | Igual (Pd p. 17) | Igual (TO p. 41 e 56) | Igual (Cons. p. 68 e 83) | Sem diferença |
| 4ª série | 100% DI + 2,50% a.a. (Lâm. p. 7) | Igual (Pd p. 18) | Igual (TO p. 41 e 58) | Igual (Cons. p. 68 e 85) | Sem diferença |
| 5ª série | 8,88% a.a. + IPCA (Lâm. p. 7) | Igual (Pd p. 19) | Igual (TO p. 41 e 60) | Igual (Cons. p. 68 e 87) | Sem diferença |
| Vencimentos (CRA) | 18/12/2030 (1ª a 3ª; 1.829 dias); 17/12/2032 (4ª; 2.559 dias); 19/12/2035 (5ª; 3.656 dias) (Lâm. pp. 6 e 7) | Igual (Pd p. 15) | Igual (TO p. 39) | Igual (Cons. p. 66) | Sem diferença |
| Vencimentos (Notas Comerciais) | 16/12/2030; 15/12/2032; 17/12/2035 (1.827; 2.557; 3.654 dias) (Pp p. 88) | Igual (Pd p. 88) | Igual (TO Anexo II, pp. 132 e 133) | Igual (Adit. pp. 21 e 22) | Sem diferença (dois dias a menos que os CRA, por desenho) |
| Pagamento de juros | Semestral; 1º em 17/06/2026 (Lâm. p. 7; Pd p. 19) | Igual | Igual (TO p. 43; cl. 6.9) | Igual (Cons. p. 70 e 89) | Sem diferença. Notas Comerciais: 15/06/2026 (Pd p. 88; Adit. p. 25) |
| Amortização | 1ª a 3ª: semestral desde 17/06/2027; 4ª e 5ª: desde 17/12/2027 (Lâm. p. 8) | Igual (Pd p. 21) | Anexo I, pp. 127 a 129 | Anexo I, pp. 153 a 156 | Sem diferença: 64 percentuais e 64 datas idênticos, em Pp, Pd, TO e TA (conferido por programa) |
| Garantias | Aval da Carlos Lee só nas Notas Comerciais 1ª a 3ª; 4ª e 5ª sem garantia (Lâm. p. 9; Pp p. 77) | Igual (Pd p. 22 e 77) | Igual (TO p. 38 e 39) | Igual (Adit. pp. 13 e 14) | Sem diferença |
| Covenants | Liquidez corrente >= 1,20; Dívida Líquida/EBITDA <= 3,0x, com exceção de caixa (Pp p. 96; Moody's p. 838) | Igual (Pd p. 96; Moody's p. 1134) | Igual (TO p. 68 e 69) | Igual (Cons. p. 95 e 96) | Sem diferença |
| Vencimento antecipado | Automático e não automático, limite cruzado R$ 25 mi (Pp p. 93 a 96) | Igual (Pd p. 93 a 96) | Igual (TO p. 64 a 70) | Igual (Cons. p. 91 a 97) | Sem diferença |
| Resgate/amortização facultativos | Pp p. 13 (remissão) e p. 183 a 185 | Igual (Pd p. 13 e 183 a 185) | A partir de 15/06/2028, só 1ª e 2ª; amortização extraordinária limitada a 98% do VNU; prêmio de 1,00% a.a. flat na 2ª; aquisição facultativa pela Emissora vedada (TO p. 117 a 121) | Igual (Cons. p. 144 a 148) | Sem diferença |
| Fundo de despesas | Inicial R$ 295.000,00 (Termo de Emissão anexado, Pp p. 379 e 431) | Inicial R$ 295.000,00; mínimo R$ 95.000,00; recomposição em até 5 Dias Úteis (Pd p. 377 e 1135) | Igual (TO p. 27, 106 e 107) | Igual (Cons. p. 54, 133 e 134) | Sem diferença |
| Quóruns | "CRA em Circulação" exclui os CRA Subordinados (Pp p. 193) | Igual (Pd p. 193) | Não vencimento antecipado: 2/3 em 1ª convocação; 50% + 1 dos presentes com 20% de instalação em 2ª (TO p. 69); "CRA em Circulação" exclui Subordinados (TO p. 8); demais quóruns TO p. 103 e 104 | Igual (Cons. p. 34, 96, 130 e 131) | Sem diferença |
| Garantia firme e distribuição | R$ 500 mi com garantia firme (R$ 250 mi Sêniores + R$ 250 mi Mezanino); R$ 250 mi em melhores esforços (Subordinados) (Pp p. 73) | Igual (Pd p. 73) e válida até 19/12/2025 (Pd p. 74) | Subscrição total dos Subordinados é condição precedente; sem distribuição parcial (TO p. 45) | Igual (Cons. p. 72) | Sem diferença |
| Rating | A.br (Moody's) para os CRA Sêniores, 14/11/2025 (Av. p. 1; Lâm. p. 9) | A.br (sf) definitivo para a 1ª e 2ª séries, 17/12/2025 (Anún. p. 1; Pd pp. 1 e 1133) | n/d | n/d | Mudou: rating definitivo. Mezanino e Subordinados sem rating (Pd p. 36) |
| Participantes especiais | "poderá contar" (Av. p. 3) | BTG Pactual, Bocom BBM, Santander, Genial, RB Investimentos, XP (Anún. pp. 1 e 2; Pd p. 1) | n/d | n/d | Mudou: lista definida |
| Cronograma | Reservas 21/11 a 15/12/2025; preço 16/12; liquidação 19/12 (Lâm. p. 11) | Igual (Pd p. 61) | n/d | n/d | Sem diferença |

## 4. Diferenças entre o Prospecto Preliminar e o Definitivo

1. **Capa (Pd p. 1 x Pp p. 1).** "PRELIMINAR" vira "DEFINITIVO"; "em até 5 séries" vira "em 5 séries"; some "DATA ESTIMADA DE OBTENÇÃO DOS REGISTROS: 17/12/2025"; entram os cinco registros automáticos (CVM/SRE/AUT/CRA/PRI/2025/261 a 265, 17/12/2025); a classificação passa a "CLASSIFICAÇÃO DEFINITIVA ... 17 de dezembro de 2025" (era 14/11/2025); entram as quantidades e os valores por série e os seis Participantes Especiais; o Termo de Emissão e o Termo de Securitização passam a "conforme aditado em 17 de dezembro de 2025".
2. **Quantidades e montantes.** O preliminar fixa só os limites (Pp p. 14: 1ª+2ª até 250.000; 3ª 250.000; 4ª+5ª até 250.000). O definitivo traz 233.142 / 16.858 / 250.000 / 100.000 / 150.000 e R$ 233.142.000,00 / 16.858.000,00 / 250.000.000,00 / 100.000.000,00 / 150.000.000,00 (Pd p. 14; mesmos números no Anún. p. 2 e no Aditamento p. 12).
3. **Taxa da 1ª série.** O preliminar traz o teto: maior entre (i) Taxa DI do contrato futuro de 02/01/2030 + 1,20% a.a. e (ii) 14,80% a.a. (Pp p. 1 e 16). O definitivo fixa **14,80% a.a. prefixada**, "Taxa: 14,8000, conforme apurada na data de realização do Procedimento de Bookbuilding" (Pd p. 16). O texto do definitivo ainda cita a Taxa Teto como parte do procedimento (Pd p. 62 a 64 e 74).
4. **Mesmo texto, no passado.** O definitivo troca o futuro por passado ("será" por "foi", "serão" por "foram", "poderá afetar" por "pode ter afetado") em quase toda a seção 2, 5 e 8. Não muda regra.
5. **Sem mudança numérica nas tabelas.** Datas e percentuais de juros e amortização (pp. 19 a 22 e 89 a 92), custo da distribuição (R$ 12.056.725,39; 1,61%; líquido R$ 737.943.274,61; Pd p. 169), garantia firme (R$ 500 mi), quantidades máximas históricas, covenants, destinação (5,00% por semestre; R$ 37.500.000,00; Pd p. 29) e índices financeiros pró-forma (p. 120) são iguais; a diferença em p. 120 é só de diagramação.
6. **Anexos.** O definitivo traz o Termo de Emissão e o Termo de Securitização **com seus Primeiros Aditamentos** (Pd Anexos VI e VII; Aditamento do Termo de Securitização na p. 670 e seguintes). O preliminar traz só os Termos originais.
7. **Súmula de rating (Anexo XIV).** O preliminar (Pp1 pp. 837 a 839) é o comunicado de 14/11/2025 sobre a **proposta das Notas Comerciais 1ª e 2ª séries**, "baseado em documentação preliminar", e discute a Carlos Lee (alavancagem pró-forma 3,9x contra 2,7x; caixa R$ 1,3 bi contra dívida de curto prazo de R$ 538 mi; dívida bruta R$ 1,7 bi; captação de até R$ 1,2 bi no 4º trim. 2025; desembolso de ~R$ 900 mi em 2026). O definitivo (Pd pp. 1133 a 1138) é o comunicado de 17/12/2025 que atribui **A.br (sf) às 1ª e 2ª séries dos CRA**, com fundo de despesas (saldo inicial R$ 295 mil; mínimo R$ 95 mil), conta no Bradesco e aplicações permitidas; não repete a análise de alavancagem e liquidez. A data do rating inicial aparece como 14/11/2025 (Pd p. 1138).
8. **Pp1 x Pp2.** Nenhuma diferença de conteúdo (seção 1).

## 5. Diferenças entre o Termo da oferta (TO, 13/11/2025) e o Termo atual (TA)

Cada linha traz a página nos dois lados. "Adit." = texto novo do Aditamento; "Cons." = Termo consolidado. Nada abaixo decide qual prevalece.

| # | Tema | TO (13/11/2025) | TA (17/12/2025) |
|---|---|---|---|
| 1 | Título e número de séries | "em até 5 (cinco) Séries" (p. 1) | "em 5 (cinco) Séries" (Adit. p. 4; Cons. p. 28) |
| 2 | Cl. 3.1 (ii): Número de séries | "será realizada em até 5 séries"; qualquer série "poderá não ser emitida" (p. 36) | "é realizada em 5 séries"; "poderia não ter sido emitida" (Adit. p. 11; Cons. p. 63) |
| 3 | Cl. 3.1 (v) e (vi): valor e quantidade por série | Só limites: 1ª+2ª até 250.000; 3ª 250.000; 4ª+5ª até 250.000 (p. 37). Sem número final por série | 233.142 / 16.858 / 250.000 / 100.000 / 150.000 CRA e R$ 233.142.000,00 / 16.858.000,00 / 250.000.000,00 / 100.000.000,00 / 150.000.000,00 (Adit. p. 12; Cons. p. 64) |
| 4 | Definições de "CRA", "CRA da Nª Série", "Notas Comerciais Escriturais da Nª Série", "Valor Total das Notas Comerciais" | Sem quantidade por série (pp. 7 a 10, 16, 17, 28) | Com quantidade e montante por série (Adit. pp. 5 a 9; Cons. pp. 33, 34, 43, 54) |
| 5 | Cl. 3.1 (vii) Bookbuilding | "Será realizado... definir (i) a taxa... observada a Taxa Teto da 1ª Série" (p. 38) | "Foi realizado... a taxa..." sem Taxa Teto (Adit. p. 13; Cons. p. 65) |
| 6 | Cl. 3.1 (xviii) e 6.2: remuneração da 1ª série | Prefixada limitada à maior entre DI futuro de 02/01/2030 + 1,20% a.a. e 14,80% a.a.; "taxa de juros fixa... a ser definida no Bookbuilding, limitada à Taxa Teto" (pp. 40, 41, 54, 55) | **14,80% a.a.**; "Taxa: 14,8000" (Adit. pp. 14 e 15; Cons. pp. 67 e 81) |
| 7 | Definição "Taxa-Teto da 1ª Série" e "Índice" | "Taxa Teto da 1ª Série" definida por remissão à cl. 6.2 (p. 26). Não achei verbete "Índice" | O Aditamento manda excluir "o Índice, bem como a definição de Taxa-Teto da 1ª Série" (Adit. p. 4, cl. 3.2 (ii)) |
| 8 | Cl. 1.4 e 1.5: aprovações societárias | Sem número de registro das atas (pp. 28 e 29) | Atas arquivadas na JUCISRS em 18/11/2025: Devedora nº 11331829; Avalista nº 11331827 (Adit. pp. 2 e 10; Cons. pp. 55 e 56) |
| 9 | Cl. 1.13: Aditamento Bookbuilding | "serão objeto do Aditamento Bookbuilding" (p. 29) | "foram objeto do Aditamento Bookbuilding, datado de 17 de dezembro de 2025" (Adit. p. 10; Cons. p. 56) |
| 10 | Cl. 2.1.3: valor dos Direitos Creditórios | Só total (p. 30) | Total e por série (Adit. p. 10; Cons. p. 57) |
| 11 | Cl. 4.3 Oferta a Mercado | "realizará" (p. 45) | "realizou" (Adit. p. 14; Cons. p. 72) |
| 12 | Cl. 6.11 | "As Partes ficam desde já autorizadas e obrigadas a celebrar o Aditamento Bookbuilding" (p. 62) | "este Termo de Securitização foi aditado" (Adit. p. 15; Cons. p. 89) |
| 13 | Definições de "Aviso ao Mercado" e "Prospecto Preliminar" | Definidas sem a data de divulgação (pp. 6, 21 e 22; a extração embaralha a tabela de definições) | Aviso "datado de 14 de novembro de 2025" (Adit. p. 4); Prospecto Preliminar "disponibilizado aos Investidores em 14 de novembro de 2025, quando da divulgação do Aviso ao Mercado" (Adit. p. 8; Cons. pp. 32 e 48) |
| 14 | Definições de "Termo de Securitização" e "Termo de Emissão" | Termos de 13/11/2025 | "datado de 13 de novembro de 2025, conforme aditado" (Adit. p. 9; Cons. pp. 53 e 56) |
| 15 | Anexo II (características dos Direitos Creditórios) | "Serão emitidas", valor por série "a ser alocado", Quantidade Máxima (pp. 130 a 137) | "Serão emitidas... sendo (i) 233.142... (v) 150.000", tempos no passado, Taxa Teto removida (Adit. Anexo A, pp. 18 a 25; Cons. pp. 157 a 165) |
| 16 | Anexo V: declaração do Agente Fiduciário | "Número de Séries: Até 5; Séries da Classe Sênior: Até 2; ... até 2 subclasses Subordinadas Júniores" (p. 143) | "5 séries; 2 séries; ... 2 subclasses Subordinadas Júniores" (Adit. p. 26; Cons. p. 171) |
| 17 | Anexo VI: declaração de custódia | Refere só o Termo de Securitização de 13/11/2025, "em até 5 (cinco) Séries" (p. 144) | Refere também o Aditamento e o Primeiro Aditamento ao Termo de Emissão, de 17/12/2025 (Adit. p. 27; Cons. p. 173) |
| 18 | Numeração das cláusulas | Itens da Cláusula Segunda numerados 1.x (p. 30) e da Cláusula Quarta numerados 3.x (p. 44) | Corrigida: Cláusula Segunda 2.x (Cons. p. 57), Cláusula Quarta 4.x (Cons. p. 71) |
| 19 | Erro de digitação | "CRI" no lugar de "CRA" (p. 46) | "CRA" (Cons. p. 73) |
| 20 | Assinaturas | Folhas de assinatura de 13/11/2025 (pp. 125 e 126) | Consolidado sem folhas de assinatura (marca "***", Cons. p. 152); Aditamento assinado em 17/12/2025 (Adit. pp. 16 e 17) |

**Sem diferença de conteúdo** (por diferença de texto, páginas TO 44 a 124 e Anexos): classes e subordinação, prazos e datas de vencimento, remuneração das séries 2 a 5, atualização pelo IPCA, pagamento de juros e amortização (Anexo I idêntico), garantias (aval só para 1ª a 3ª), destinação dos recursos, ordem de alocação dos recursos (TO pp. 42 e 98; Cons. pp. 69 e 125), vencimento antecipado automático e não automático (limites de R$ 25 mi, 10% da receita líquida, auditores), covenants (1,20 e 3,0x; primeira verificação em até 5 Dias Úteis após as demonstrações de 31/12/2025), resgate antecipado facultativo, amortização extraordinária, oferta de resgate, fundo de despesas (R$ 295.000,00 e R$ 95.000,00), quóruns e assembleia, fatores de risco, Anexos III, IV, VII e VIII (históricos da Emissora, só diagramação). Nas páginas 44 a 124 do TO só diferem: "realizará/realizou", "CRI/CRA", "deverá ser/foi" e a numeração.

## 6. Itens fracos ou ambíguos para revisão humana

1. **Informe x oferta na 4ª série.** O Informe chama a 4ª série de Mezanino; Lâmina, Prospectos, Anúncio, Termo e Aditamento a tratam como Subordinada. Nenhuma página da oferta usa "Mezanino" para a 4ª. A declaração do AF (1 subclasse Mezanino + 2 Júniores) é coerente com 3ª = Mezanino. Sugiro tratar a diferença do Informe como erro de preenchimento até que o Agente Fiduciário ou a Emissora confirmem.
2. **Comissão de sucesso.** Pd p. 66 e p. 39 advertem que "há, na presente oferta comissão de sucesso atrelada à redução da taxa de remuneração"; a nota (1d) da p. 170 diz "Comissão de Sucesso: não aplicável"; a tabela da p. 169 traz uma linha "Comissão de Sucesso (1d)" com valores desalinhados. O texto é contraditório; o preliminar tem o mesmo conteúdo.
3. **Capa do Prospecto, 2ª série.** Em Pp1, Pp2 e Pd (p. 1) a frase com 108,00% da Taxa DI fala em "CRA DA 3ª SÉRIE" quando a remuneração da 2ª série é a descrita; a 3ª série vem logo depois (DI + 1,50%). Erro de redação; o corpo (p. 16) está correto.
4. **Prospecto Preliminar, 2ª versão.** O doc. 1047358 (rodapé V006) tem capa datada de 14/11/2025, mas está arquivado como de 26/11/2025; o texto não muda em relação ao 1040835. Não achei no texto o que justificaria a reapresentação.
5. **Aviso, CNPJ do Coordenador Líder.** "04.845.753/001-59" no Aviso (p. 1); "04.845.753/0001-59" no Anúncio e no Prospecto. Erro de digitação no Aviso.
6. **Lâmina, base legal do lastro.** A Lâmina (p. 4) cita "artigo 2º, parágrafo 4º, inciso II" do Anexo Normativo II da Resolução CVM 60; Aviso (p. 2), Anúncio (p. 2) e Prospecto (p. 27) citam "inciso III".
7. **Garantias "não constituídas".** A Lâmina (p. 9), o Prospecto (p. 22) e o Termo (cl. 3.1 (xiii)) começam com "Não serão constituídas garantias específicas, reais ou pessoais, em benefício dos Titulares dos CRA" e só depois descrevem o Aval da Carlos Lee para as Notas Comerciais 1ª a 3ª. Quem ler só a primeira frase conclui que não há garantia.
8. **Numeração e datas com erro no texto.** Pd p. 15: a 5ª série aparece como "(iii)"; Pd p. 21: "(inclusive)e o último" sem espaço; Av. p. 3 e Pd p. 61: "21/11/225" no cronograma; Pd p. 66: "Como não foi não seja verificado excesso de demanda".
9. **Tabelas desalinhadas.** Os cronogramas do Aviso (pp. 3 e 4), do Anúncio (pp. 3 e 4) e do Pd (p. 61) saem com datas separadas dos eventos; só usei as datas da Lâmina (p. 11). As tabelas de amortização e de custo (Pd pp. 20, 21, 169) saem com linhas e colunas deslocadas; conferi por conjunto de datas e percentuais, não por linha. A linha 01/01/2026 a 30/06/2026 do cronograma de destinação sai sem valores.
10. **Páginas de Anexo, não do corpo.** Os fatos `def_fundo_despesas_*` citam a p. 377 do Pd, que é do Termo de Emissão anexado (Anexo VI); `def_anexo_conflito_interesses_subclasses` cita a p. 841, do Aditamento anexado.
11. **Notas Comerciais x CRA.** Notas Comerciais vencem 2 dias antes dos CRA (16/12/2030 contra 18/12/2030; 15/12/2032 contra 17/12/2032; 17/12/2035 contra 19/12/2035) e pagam juros em 15/06 e 15/12 contra 17/06 e 17/12 dos CRA. É desenho declarado (Moody's, Pd p. 1135), não erro; vale lembrar ao cruzar fluxos.
12. **Moody's e a Carlos Lee.** O rating A.br dos CRA reflete a visão consolidada da Carlos Lee (aval), não só a Alibem (Pd p. 1134). As séries 3ª a 5ª não têm rating; a 3ª tem aval mas não rating, a 4ª e 5ª nem aval nem rating.
13. **Sentido de "Índice" no Aditamento.** O Aditamento (p. 4, cl. 3.2 (ii)) manda excluir "o Índice" junto com a definição de Taxa-Teto. O TO não tem verbete "Índice" (só "Índice de Liquidez Corrente", "Índice Financeiro de Endividamento" e "Índices Financeiros"); o consolidado mantém os covenants, então a exclusão parece ser de outro "Índice" (talvez o sumário). Não está claro.
14. **Não li** a seção 14 do Prospecto por inteiro (Contrato de Distribuição, condições precedentes) nem os fatores de risco da Devedora; o Contrato de Distribuição não está no banco.

## 7. Arquivos

- `config/reported_facts/cra02500c1d_oferta_2025.json`: 218 fatos (Aviso 27, Lâmina 44, Anúncio 30, Prospecto Preliminar 1040835 13, Prospecto Preliminar 1047358 8, Prospecto Definitivo 86 e Termo da oferta 1040836 10), cada um com página e trecho literal. Não foi carregado (`scripts/load_reported_facts.py` não foi executado).
- Validação somente leitura: `scratchpad/validate_oferta_asset9.py` (mesma busca de página e conferência de trecho com espaços colapsados do carregador; 218 de 218 aprovados).
