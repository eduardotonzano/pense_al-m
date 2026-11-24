# Fundos: sonda da PDD da carteira e do cedente relevante (FU11.0)

Sonda de leitura da fase 11 do plano de Fundos, antes da FU11.2 (cedentes) e da FU11.3 (PDD e cobertura). Responde a duas perguntas, só com o que foi lido:

- **A)** onde o informe mensal de FIDC traz a provisão da **carteira de direitos creditórios**, e se o FIAGRO tem campo equivalente;
- **B)** qual regra define o cedente que o fundo identifica no informe (norma, artigo e percentual).

**Escopo.** Só leitura, sem código, migration ou banco. Os arquivos ficam numa pasta local fora do repositório. Foram lidos em memória, em cópias, com a biblioteca padrão do Python e o `pdftotext`, e os originais tiveram o SHA-256 conferido antes e depois da leitura. Este documento traz só nomes de campo, descrições oficiais, trechos curtos da norma e contagens: nenhum CNPJ, CPF, nome de fundo ou de cedente, nem linha de dado.

**Data da leitura:** 24/11/2026.

## 1. Fontes

### 1.1 Arquivos locais (já baixados, seções 9.1, 10.1 e 12.1 de `docs/fundos-descoberta.md`)

| Arquivo | Bytes | SHA-256 | Uso |
|---|---|---|---|
| `meta_inf_mensal_fidc_txt.zip` (dicionário de FIDC, `Last-Modified` 2026-10-24) | 15.942 | `148ecadc9fc98991703873ed7ce98d528c92e51f88d3ad2724b57cd824a9edb1` | descrições dos campos (18 tabelas) |
| `inf_mensal_fidc_202609.zip` (informe de FIDC, competência 09/2026) | 3.637.109 | `365ef15fb1ba4e20a6a2adfefcd70c7f17cd9226135943739411e38f890d9ab0` | contagens na `tab_I` (4.444 classes) |
| `meta_inf_mensal_fiagro.zip` (dicionário de FIAGRO) | 2.546 | `b5a71cb9adceef00eb617c977d1d8c75ed95eecc3164af84d826c3f446e4b7c9` | busca de campo de provisão |
| `inf_mensal_fiagro_202609.zip` (informe de FIAGRO, 09/2026) | 74.365 | `a9700ab77db8f731f15be994b1462828bf0527d7aa2fb46233cd7d86bb9e0948` | não foi preciso contar (seção 2.4) |

### 1.2 Chamadas de rede (24/11/2026, horas UTC)

Cada chamada foi aprovada pelo Eduardo antes, uma por vez. Protocolo: HTTPS com TLS verificado, nenhum redirecionamento seguido, sem retentativa, User-Agent genérico e teto de bytes. Todas as respostas foram 200.

| # | Método e URL | Motivo | Bytes | SHA-256 | `Last-Modified` | UTC |
|---|---|---|---|---|---|---|
| N1 | GET `https://conteudo.cvm.gov.br/legislacao/resolucoes/resol175.html` | achar os links oficiais da Resolução CVM 175 | 66.188 | `63e04ba3777a0534077fbdb707912ee64ccf25e18e45bf214095f9b2fb9cf209` | a hora do pedido (página gerada) | 14:07:16 |
| N4 | HEAD `https://dados.cvm.gov.br/dados/FIDC/DOC/INF_MENSAL/META/meta_inf_mensal_fidc_txt.zip` | saber se o dicionário local ainda é o vigente | `Content-Length` 15.942 | n/a | Sat, 21 Nov 2026 14:37:46 GMT | 14:07:27 |
| N2 | GET `https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/100/resol175consolid_Anexo02.pdf` | texto consolidado do Anexo Normativo II (FIDC), 32 páginas | 246.670 | `c81634e94da81eef4918fb2ce7da945a50f55636e70e5a77f41cc5416c33babd` | Mon, 23 Nov 2026 11:05:11 GMT | 14:10:21 |
| N4b | GET (URL da N4) | comparar o dicionário de 21/11 com o local | 15.942 | `7f871c7f6f8f3b429e79baf7ef91915c88fd3b20e4a832f4b1247311f8691a9a` | Sat, 21 Nov 2026 14:37:46 GMT | 14:10:31 |
| N3 | GET `https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/100/resol175consolid_Suplementos.pdf` | Suplemento G (modelo do informe mensal de FIDC), 104 páginas | 1.576.608 | `99d65ccb033d8de62c59d17b49770b70e5df4753e60cd35747bbd14e74d5ca83` | Mon, 23 Nov 2026 11:13:37 GMT | 14:14:27 |

- **O dicionário não mudou.** O de 21/11 (N4b) tem os 18 TXT com conteúdo idêntico ao de 24/10; só mudaram as datas internas do ZIP. As descrições citadas abaixo valem para os dois.
- **Leitura dos PDFs.** O texto foi extraído com o `pdftotext` 4.06 em dois modos (`-layout` do arquivo inteiro e `-raw` página por página), e cada trecho citado aparece igual nos dois. Em 24/11/2026 os trechos do Suplemento G (itens a.10, a.11, b.10 e b.11), do art. 45 e do art. 27, § 3º, II do Anexo II foram conferidos também como imagem de página, numa segunda leitura independente. Os números de página citados neste documento são os do PDF.

## 2. (a) Provisão da carteira de direitos creditórios

### 2.1 Os campos

| Campo (`tab_I`) | Descrição no dicionário da CVM | No modelo oficial (Suplemento G da RCVM 175, item I.2) |
|---|---|---|
| `TAB_I2A11_VL_REDUCAO_RECUP` | "(I.2.a.11) Provisão para Redução no Valor de Recuperação (-)" | a.10, dentro de "a) Direitos Creditórios com Aquisição Substancial dos Riscos e Benefícios" (p. 29) |
| `TAB_I2B11_VL_REDUCAO_RECUP` | "(I.2.b.11) Provisão para Redução no Valor de Recuperação (-)" | b.10, dentro de "b) Direitos Creditórios sem Aquisição Substancial dos Riscos e Benefícios" (p. 30) |

- **São a provisão da carteira de direitos creditórios:** os dois campos ficam dentro dos blocos de direitos creditórios, no dicionário (I.2.a e I.2.b) e no modelo da norma.
- **O nome oficial não é "PDD".** Nenhuma das duas fontes usa "PDD" nem "provisão para perdas"; o nome é "Provisão para Redução no Valor de Recuperação". O Anexo Normativo II também não usa "provisão" nem "perdas". A equivalência com "PDD" fica **não confirmada** (seção 4).
- **A numeração difere** entre o dicionário e o modelo. O dicionário tem um item a mais, "(I.2.a.10) Outros créditos, de natureza diversa, não enquadráveis no disposto no inciso I do art. 2º da ICVM 356", que o modelo do Suplemento G não traz. Por isso a provisão é a.11 no dicionário e a.10 no modelo, e o cedente é a.12 no dicionário e a.11 no modelo. O mesmo vale para o bloco b.

### 2.2 Evidência no dado de 09/2026 (4.444 classes)

| Campo | Positivo | Zero | Vazio ou negativo | Nas classes com o bloco > 0 |
|---|---|---|---|---|
| `TAB_I2A11_VL_REDUCAO_RECUP` | 1.551 | 2.893 | 0 | 2.876 classes: 1.488 positivas e 1.388 zero |
| `TAB_I2B11_VL_REDUCAO_RECUP` | 791 | 3.653 | 0 | 1.103 classes: 765 positivas e 338 zero |

- **O sinal.** A descrição diz "(-)", mas o valor vem sempre positivo, e o arquivo entrega o valor a subtrair. A conferência aritmética abaixo, com tolerância de R$ 1, só descreve o dado e não define o campo:
  - o total I.2.a fecha com a soma dos itens a.1 a a.4 **menos** a provisão em 2.874 das 2.876 classes com I.2.a > 0, o que inclui pelo menos 1.486 das 1.488 com provisão positiva;
  - o total I.2.b fecha assim nas 1.103 classes com I.2.b > 0.
- **Os itens a.5 a a.10.** Somando também esses itens, o total deixa de fechar em 246 classes do bloco a e em 88 do b. Eles parecem ser recortes dos itens 1 a 4, e não parcelas a somar, mas o texto não diz isso (seção 4).

### 2.3 Provisões que não são da carteira de direitos creditórios

No modelo, três provisões ficam no nível do item 2 (Carteira), depois do item i), fora dos blocos de direitos creditórios.

| Campo | Descrição no dicionário | Positivo em |
|---|---|---|
| `TAB_I2_COTA_FIDC` | "(I.2) (-) Provisões sobre Cotas de Fundos de Investimento em Direitos Creditórios" | 5 classes |
| `TAB_I2_DEBENTURE_CRI` | "(I.2) (-) Provisões sobre Debêntures, CRI, Notas Promissórias e Letras Financeiras" | 11 |
| `TAB_I2_VL_OUTRO_ATIVO` | "(I.2) (-) Provisões sobre outros ativos" | 6 |

- **`TAB_I2_COTA_FIDC` é provisão sobre cotas de FIDC, e não sobre a carteira de direitos creditórios.**
- **A carteira (I.2) fecha** com os itens a a j menos essas três provisões nas 4.280 classes com carteira > 0.

### 2.4 FIAGRO

- **Nenhum campo de provisão da carteira foi confirmado.**
  - O dicionário do FIAGRO descreve só 13 dos 133 campos da classe.
  - O único campo com "provis" no nome é `Provisoes_Contigencias`, sem descrição.
- **O que não foi lido:** o Anexo Normativo VI (FIAGRO) e o modelo do informe do FIAGRO, porque não havia autorização de rede para eles nesta sonda.
- **Por isso não houve contagem:** sem descrição oficial que qualifique um campo, não há o que contar.

## 3. (b) Cedente identificado no informe

### 3.1 A regra

- **Norma:** Resolução CVM 175, Anexo Normativo II, art. 27, III. O administrador deve "encaminhar o informe mensal à CVM [...] conforme modelo disposto no Suplemento G", em até 15 dias após o fim do mês.
- **Regra:** no Suplemento G ("Informe Mensal – FIDC"), os itens I.2.a.11 e I.2.b.11 pedem "Direitos Creditórios (especificar o cedente quando representar mais de 10% do PL do fundo)", com as colunas "CNPJ/CPF" e "Participação Percentual (%)" (pp. 29 e 30).
- **Percentual:** o cedente é identificado quando representa **mais de 10% do PL do fundo**. A base é o PL, e não a carteira, e o corte é estrito ("mais de").
- **Leitura:** texto consolidado obtido em 24/11/2026 (N2 e N3), com `Last-Modified` de 23/11/2026.

**No dicionário,** os campos correspondentes são `TAB_I2A12_CPF_CNPJ_CEDENTE_1` a `_9` e `TAB_I2A12_PR_CEDENTE_1` a `_9`, mais os equivalentes `TAB_I2B12_*`. As descrições são "Cedente n - CPF ou CNPJ" e "Cedente n - Valor do Percentual de Participação". Não citam o corte de 10% nem a base do percentual, e o arquivo da CVM tem 9 posições por bloco.

### 3.2 O que o dado de 09/2026 mostra

As contagens tratam o identificador só como preenchido ou vazio.

| | Bloco a (com aquisição substancial) | Bloco b (sem aquisição substancial) |
|---|---|---|
| Classes com o bloco > 0 | 2.876 | 1.103 |
| … sem nenhum cedente identificado | 1.324 | 569 |
| … com as 9 posições preenchidas | 0 | 4 |
| Classes com o bloco vazio ou ≤ 0 e algum cedente | 101 | 143 |
| Classes por número de cedentes (0 a 9) | 2.791; 1.098; 339; 137; 44; 12; 9; 3; 11; 0 | 3.767; 422; 145; 58; 33; 9; 3; 2; 0; 5 |
| Percentuais preenchidos | 2.586 | 1.140 |
| … iguais a 0 | 75 | 67 |
| … acima de 0 e até 10 | 159 (em 74 classes) | 44 (em 23 classes) |
| … acima de 10 e até 100 | 2.046 | 950 |
| … acima de 100 | 306 | 79 |
| Classes com a soma dos percentuais acima de 100 | 328 de 1.653 | 87 de 677 |

Nenhuma posição tem identificador sem percentual, nem percentual sem identificador. Os 385 percentuais acima de 100 são os mesmos já registrados no `Gui/fundos/README.md`. Os 203 percentuais de 0 a 10 e os 142 iguais a 0 não combinam com o corte de "mais de 10% do PL". Se a base do campo é outra, ou se o corte não é seguido, fica **não confirmado**.

### 3.3 O que não é a regra do cedente

- **Art. 45 do Anexo Normativo II: o limite é por devedor.** A aplicação em direitos creditórios e outros ativos "de um mesmo devedor está limitada a 20% (vinte por cento) do patrimônio líquido da classe de cotas" (p. 27).
  - O § 1º trata o grupo econômico como um único devedor.
  - O § 3º permite aumentar o limite em classes para qualificados.
  - O § 5º manda cumprir o limite mensalmente.
  - O § 7º dispensa a classe só de profissionais ou do mesmo grupo econômico.
  - O § 8º isenta as receitas públicas.

  O número de 20% que circulou por fonte secundária está certo **para devedor**, não para cedente. O texto oficial distingue "devedor" (art. 2º, XI), "cedente" (art. 2º, IV: "aquele que realiza cessão de direitos creditórios para o FIDC") e "originador" (art. 2º, XVIII).
- **Art. 27, § 3º, II: originadores de 10% ou mais, no relatório trimestral.** O relatório trimestral do gestor trata dos **originadores** "que representem individualmente 10% (dez por cento) ou mais da carteira de direitos creditórios no trimestre" (p. 14). O sujeito (originador), a base (carteira), o corte ("ou mais") e o documento (trimestral) são outros.
- **Arts. 30, § 3º, VI e 32, § 3º, VI: exposição a cada cedente.** Os demonstrativos trimestrais divulgam "a exposição da classe a cada cedente" só no caso em que o cedente ou o originador guarda os documentos. Esse caso vale para a classe só de profissionais, sem negociação, que compra créditos inadimplidos.
- **Item VIII do Suplemento G: devedores.** O item é a "Relação do Valor Devido dos 25 Maiores Devedores (Sacados) do Fundo", com "Descrição", "CPF/CNPJ", "Valor (R$)" e "% PL" (p. 36).
  - A `tab_VIII` dos dados abertos tem até 25 `SEQUENCIAL` por classe e só `VALOR` (`docs/fundos-descoberta.md`, seção 10.2), e o dicionário não descreve esses dois campos.
  - Que a `tab_VIII` seja esse item VIII, publicado sem identificação e sem % do PL, fica **não confirmado**.

## 4. (c) Não confirmado

1. Se a "Provisão para Redução no Valor de Recuperação" equivale ao que se chama de PDD (provisão para perdas). A norma contábil não foi lida.
2. Se os itens a.5 a a.10 do dicionário são recortes dos itens a.1 a a.4. Só a aritmética sugere isso (seção 2.2).
3. Por que o dicionário tem o item "Outros créditos, de natureza diversa" (a.10) e o modelo do Suplemento G não, o que desloca a numeração da provisão e dos cedentes em um.
4. A base do percentual informado em `PR_CEDENTE`. O dicionário diz só "Valor do Percentual de Participação", e o dado tem valores iguais a 0, de 0 a 10 e acima de 100.
5. Se a classe com o bloco > 0 e sem cedente identificado não tem cedente acima de 10% do PL ou deixou de informar.
6. Se as 9 posições cortam a lista. São 4 classes do bloco b com as 9 preenchidas, e o modelo não limita a quantidade.
7. A correspondência entre a `tab_VIII` e o item VIII do Suplemento G.
8. A provisão da carteira no FIAGRO: não há campo descrito, e o Anexo Normativo VI e o modelo do informe do FIAGRO não foram lidos.
9. Se o mesmo retrato vale para outros meses. Foi lido um só mês (09/2026).

## 5. (d) O que isto muda

### 5.1 FU11.2 (cedentes)

- **A lista não é completa.** O informe só identifica o cedente que passa de 10% do PL do fundo. Uma classe sem cedente listado pode ter cedentes abaixo do corte. Uma métrica de concentração de cedentes tirada do informe cobre só os cedentes acima do corte, e precisa dizer isso.
- **O percentual não pode ser usado como "% do PL" sem uma regra.** Há 385 valores acima de 100, 142 iguais a 0 e 203 de 0 a 10. A regra é decisão da FU11.2.
- **Há dois blocos por classe** (com e sem aquisição substancial). Somar por cedente ou não é decisão da FU11.2.
- **CPF:** o cedente pessoa física continua sem identificador, e o CPF nunca é gravado (decisão 3 de `docs/decisoes-em-aberto.md`).
- **Agregado disponível:** "(X.9.1) Valor total dos direitos creditórios cedidos por cedentes que possuem débitos tributários inscritos em dívida Ativa da União" (`tab_X.TAB_X_DEBITO_TRIBUT`, item 9.1 de "Outras Informações" no Suplemento G).
- **O limite do art. 45 é por devedor, e não entra na FU11.2.** No dicionário, os campos com "devedor" são só os totais por classificação de risco no SCR (X.8.1); a relação dos 25 maiores devedores do modelo só aparece nos dados abertos, se for a `tab_VIII`, sem identificação (seção 3.3).

### 5.2 FU11.3 (PDD e cobertura)

- **Provisão da carteira:** `TAB_I2A11_VL_REDUCAO_RECUP` e `TAB_I2B11_VL_REDUCAO_RECUP`, que vêm positivas e são subtraídas do total do bloco.
  - As provisões sobre cotas de FIDC, sobre títulos e sobre outros ativos (seção 2.3) são outra coisa e não entram na cobertura da carteira de direitos creditórios.
- **Inadimplência disponível:**
  - na `tab_I`, por bloco: "Créditos Existentes a Vencer com Parcelas Inadimplentes" (a.2), "Valor Total das Parcelas Inadimplentes" (a.2.1) e "Créditos Existentes Inadimplentes" (a.3), e os equivalentes do bloco b;
  - nas `tab_V` e `tab_VI`: "Inadimplentes (Valor das Parcelas Inadimplentes, em R$)" por faixa de atraso, de 1 a 30 dias até acima de 1080 dias. No Suplemento G, a V é o "Comportamento da Carteira de Direitos Creditórios com Aquisição Substancial dos Riscos e Benefícios" e a VI, o mesmo "sem Aquisição Substancial" (pp. 32 e 33).
- **A fórmula da cobertura não é escolhida aqui.** Numerador, denominador (parcelas ou créditos inadimplentes, por bloco ou somados) e o que fazer com a provisão zero ficam para a FU11.3. Em 09/2026, a provisão do bloco a é zero em 1.388 das 2.876 classes com o bloco > 0.

## 6. Nota sobre `docs/fundos-descoberta.md`

As seções 4 e 10.4 dizem que "`TAB_I2_COTA_FIDC` é provisão". Pela descrição oficial (seção 2.3), é **provisão sobre cotas de FIDC**, e não sobre a carteira de direitos creditórios. A seção 10.10 diz também que o significado da `tab_VIII` não é descrito, e o Suplemento G dá uma pista (seção 3.3).

Proposta: corrigir as duas frases num commit futuro. Esta sonda alterou só este arquivo.
