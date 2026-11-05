# Monitoramentos da Bari (Relatório de Gestão / Acompanhamento do CRI)

Fonte: portal de emissões da Bari Securitizadora (Strapi e páginas Next.js públicas), relatório de gestão mais recente (até 180 dias) de cada série viva; leitor `bari_relatorio_acompanhamento 1.0`. Site da securitizadora é a fonte de menor prioridade: complementa, não substitui CVM nem Termo. Os valores são copiados do relatório; a situação (Enquadrado = atendido, Desenquadrado = não atendido) é a que a Bari informa. Quando o relatório traz mínimo e apurado sem situação, a situação fica vazia (não é deduzida). O CSV tem uma linha por item e por série; as contagens abaixo são por item do relatório.

Séries vivas no catálogo: **147**; séries com relatório lido: **104**; relatórios lidos: **91** (sem nenhum item lido: 33); itens: **143**.

| Situação informada | Itens |
|---|---|
| atendido | 130 |
| nao_atendido | 13 |

| Tipo de item | Itens |
|---|---|
| Fundo | 98 |
| Índice | 41 |
| Covenant | 4 |

| Modelo de relatório | Relatórios |
|---|---|
| acompanhamento_cri | 65 |
| mensal_paineis | 25 |
| gerenciamento | 1 |

## Itens não atendidos (13 em 9 relatórios)

| Emissão | Séries | Lastro | Universo | Competência | Item não atendido | Exigido | Apurado | Situação |
|---|---|---|---|---|---|---|---|---|
| 1 | S84 20G0703191 | Comercial | sim | Outubro/2026 | FUNDO DE RESERVA: FUNDO DE RESERVA | 1.217.578,82 mínimo | 1.146.646,49 | DESENQUADRADO |
| 7 | S1 22G1000969 | Nota Comercial | sim | Maio/2026 | Análise Fundos da Operação: Saldo do Fundo Reserva | 1.727.113,10 mínimo | - | Desenquadrado |
| 7 | S1 22G1000969 | Nota Comercial | sim | Maio/2026 | Análise Fundos da Operação: Saldo Fundo Despesas | 40.000,00 mínimo | 5.071,82 | Desenquadrado |
| 35 | S1 24K0003601 | Nota Comercial | sim | Agosto/2026 | Posição Fundos: Verificação mensal fundo despesas | 90.000,00 target/mínimo | 83.691,20 | Desenquadrado |
| 42 | S1 24L1252219 | Créditos Imobiliários | sim | Agosto/2026 | FUNDO DE DESPESAS: FUNDO DE DESPESAS | 85.000,00 gatilho | 66.474,67 | DESENQUADRADO |
| 52 | S1 25I2439595 | Nota Comercial | sim | Agosto/2026 | Amortização: ICM | 1,30 mínimo | 1,29 | Desenquadrado |
| 60 | S1 24K1685332 | Nota Comercial | sim | Agosto/2026 | Índice de Término de Obras: Índice de Término de Obras | 105% mínimo | 81,67% | Desenquadrado |
| 63 | S1 25J4157736 | Nota Comercial | sim | Agosto/2026 | Saldo dos fundos: Fundo de reserva | 1.150.292,07 mínimo | 202.979,38 | Desenquadrado |
| 63 | S1 25J4157736 | Nota Comercial | sim | Agosto/2026 | Saldo dos fundos: Fundo de liquidez | 1.697.920,98 mínimo | - | Desenquadrado |
| 64 | S1 25K3391487 | Nota Comercial | sim | Agosto/2026 | FUNDO DE RESERVA: FUNDO DE RESERVA | 575.242,74 mínimo | 565.529,87 | DESENQUADRADO |
| 64 | S1 25K3391487 | Nota Comercial | sim | Agosto/2026 | ÍNDICE DE TÉRMINO DE OBRAS (ITO): ÍNDICE DE TÉRMINO DE OBRAS (ITO) | 105,0% mínimo | 85,9% | Desenquadrado - waiver |
| 64 | S1 25K3391487 | Nota Comercial | sim | Agosto/2026 | TERMÔMETRO DOS COVENANTS: Índice de Término de Obras |   |  | Desenquadrado - waiver |
| 67 | S1 26C3724930 | CCV | sim | Setembro/2026 | FUNDO DE RESERVA: FUNDO DE RESERVA | 2.827.637,32 mínimo | 2.214.137,41 | DESENQUADRADO |

## Itens com exigido e apurado mas sem situação informada (0)

A Bari não informa a situação; ela não é deduzida aqui (comparar com o Termo).

| Emissão | Séries | Competência | Item | Exigido | Apurado |
|---|---|---|---|---|---|

## Relatórios sem item lido (33)

Relatório baixado e aberto, mas sem índice, fundo nem posição de cobrança reconhecidos (em geral só saldos e pagamentos das séries).

| Emissão | Séries | Competência | Título | Arquivo |
|---|---|---|---|---|
| 1 | S52 17B0174140 | Maio/2026 | CRI 1ª Emissão 52ª série - Relatório de Gestão - 05.2026 | data/documents/bari/1/2026-05_58949.pdf |
| 1 | S63 17I0000002 | Outubro/2026 | CRI 1ª Emissão 63ª série - Relatório de Gestão - 10.2026 | data/documents/bari/1/2026-10_59892.pdf |
| 6 | S1 22J1206765 | Outubro/2026 | CRI 6ª Emissão 1ª série - Relatório de Gestão - 10.2026 | data/documents/bari/6/2026-10_59904.pdf |
| 7 | S2 22L0001401 | Junho/2026 | CRI 7ª Emissão 2ª série - Relatório de Gestão - 06.2026 | data/documents/bari/7/2026-06_59378.pdf |
| 7 | S3 23E0002201 | Junho/2026 | CRI 7ª Emissão 3ª série - Relatório de Gestão - 06.2026 | data/documents/bari/7/2026-06_59380.pdf |
| 7 | S4 23J0000201 | Junho/2026 | CRI 7ª Emissão 4ª série - Relatório de Gestão - 06.2026 | data/documents/bari/7/2026-06_59382.pdf |
| 13 | S1 22J1202552 | Agosto/2026 | CRI 13ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/13/2026-08_59709.pdf |
| 17 | S1 23A1253566 | Agosto/2026 | CRI 17ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/17/2026-08_59705.pdf |
| 18 | S2 23F1241818 | Maio/2026 | CRI 18ª Emissão 2ª série - Relatório de Gestão - 05.2026 | data/documents/bari/18/2026-05_58805.pdf |
| 18 | S1 23D1175169 | Agosto/2026 | CRI 18ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/18/2026-08_59703.pdf |
| 24 | S1 23H1234723 | Agosto/2026 | CRI 24ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/24/2026-08_59699.pdf |
| 25 | S1 24B0013801 | Agosto/2026 | CRI 25ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/25/2026-08_59770.pdf |
| 27 | S2 24B1276266 | Junho/2026 | CRI 27ª Emissão 2ª série - Relatório de Gestão - 06.2026 | data/documents/bari/27/2026-06_59218.pdf |
| 27 | S3 24B1276268 | Junho/2026 | CRI 27ª Emissão 3ª série - Relatório de Gestão - 06.2026 | data/documents/bari/27/2026-06_59220.pdf |
| 27 | S1 24B1276213 | Julho/2026 | CRI 27ª Emissão 1ª série - Relatório de Gestão - 07.2026 | data/documents/bari/27/2026-07_59516.pdf |
| 30 | S1 24I1177541, S2 24I1177731 | Agosto/2026 | CRI 30ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/30/2026-08_59766.pdf |
| 32 | S1 24C1924689 | Agosto/2026 | CRI 32ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/32/2026-08_59764.pdf |
| 34 | S1 24I1768824 | Agosto/2026 | CRI 34ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/34/2026-08_59756.pdf |
| 41 | S8 25I0951607 | Junho/2026 | CRI 41ª Emissão 8ª série - Relatório de Gestão - 06.2026 | data/documents/bari/41/2026-06_59192.pdf |
| 41 | S9 25I0968297 | Junho/2026 | CRI 41ª Emissão 9ª série - Relatório de Gestão - 06.2026 | data/documents/bari/41/2026-06_59194.pdf |
| 41 | S2 24K2132150 | Julho/2026 | CRI 41ª Emissão 2ª série - Relatório de Gestão - 07.2026 | data/documents/bari/41/2026-07_59490.pdf |
| 41 | S3 24K2132152 | Julho/2026 | CRI 41ª Emissão 3ª série - Relatório de Gestão - 07.2026 | data/documents/bari/41/2026-07_59492.pdf |
| 41 | S4 25C3917302 | Julho/2026 | CRI 41ª Emissão 4ª série - Relatório de Gestão - 07.2026 | data/documents/bari/41/2026-07_59494.pdf |
| 41 | S5 25C3917323 | Julho/2026 | CRI 41ª Emissão 5ª série - Relatório de Gestão - 07.2026 | data/documents/bari/41/2026-07_59496.pdf |
| 41 | S6 25C3917341 | Julho/2026 | CRI 41ª Emissão 6ª série - Relatório de Gestão - 07.2026 | data/documents/bari/41/2026-07_59498.pdf |
| 41 | S7 25I0814514 | Julho/2026 | CRI 41ª Emissão 7ª série - Relatório de Gestão - 07.2026 | data/documents/bari/41/2026-07_59500.pdf |
| 41 | S1 24K2132148 | Outubro/2026 | CRI 41ª Emissão 1ª série - Relatório de Gestão - 10.2026 | data/documents/bari/41/2026-10_59926.pdf |
| 45 | S1 25B2793257 | Agosto/2026 | CRI 45ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/45/2026-08_59751.pdf |
| 47 | S1 24L1853110 | Agosto/2026 | CRI 47ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/47/2026-08_59749.pdf |
| 48 | S1 24L3368837 | Agosto/2026 | CRI 48ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/48/2026-08_59747.pdf |
| 68 | S1 25L4153713 | Agosto/2026 | CRI 68ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/68/2026-08_59673.pdf |
| 70 | S1 24L6097789 | Julho/2026 | CRI 70ª Emissão 1ª série - Relatório de Gestão - 07.2026 | data/documents/bari/70/2026-07_59430.pdf |
| 82 | S1 26E2843645, S2 26E2846962 | Agosto/2026 | CRI 82ª Emissão 1ª série - Relatório de Gestão - 08.2026 | data/documents/bari/82/2026-08_59776.pdf |

## Código IF no relatório diferente do catálogo da Bari (2)

Provável cópia de modelo no relatório (ou série com mais de um código); os itens seguem atribuídos à série da página onde o relatório foi publicado.

- E42 S1 24L1252219: o relatório traz 25K3391487 (data/documents/bari/42/2026-08_59754.pdf)
- E67 S1 26C3724930: o relatório traz 25L4153713 (data/documents/bari/67/2026-09_59946.pdf)

## Séries sem relatório próprio que usam o da emissão (13)

- E16 S2 22L1565004: emissao (serie 1)
- E16 S3 22L1565064: emissao (serie 1)
- E30 S2 24I1177731: emissao (serie 1)
- E53 S2 25H3737312: emissao (serie 1)
- E54 S2 25H3737686: emissao (serie 1)
- E57 S2 25I2145967: emissao (serie 1)
- E59 S2 26A3075493: emissao (serie 1)
- E72 S2 26C5211803: emissao (serie 1)
- E72 S3 26C5178542: emissao (serie 1)
- E72 S4 26C5211962: emissao (serie 1)
- E72 S5 26C5210992: emissao (serie 1)
- E78 S1 26J4382124: emissao (serie 2)
- E82 S2 26E2846962: emissao (serie 1)
