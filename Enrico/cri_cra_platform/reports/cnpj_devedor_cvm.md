# CNPJ do devedor pelo Informe Mensal da CVM

Liga cada ativo do catálogo ao certificado do Informe Mensal (CETIP ou ISIN da série) e lê os devedores da última competência e versão informadas. Só leitura: nada foi gravado no cadastro. CPF e identificador inválido não saem no relatório, só na contagem. O dado é o que a securitizadora informou à CVM (erros vêm junto).

Ativos no catálogo: **2959**; com CNPJ do devedor no cadastro: **1**; linhas no CSV: **1485** (1377 ativos).

| Resultado por ativo | Ativos |
|---|---|
| um CNPJ | 1298 |
| certificado sem devedor informado | 674 |
| só CPF, inválido ou não informado | 664 |
| mais de um certificado (não escolhido) | 244 |
| vários CNPJs (pulverizado) | 79 |

| Identificadores fora do relatório | Linhas |
|---|---|
| nao_informado | 1470 |
| invalido | 98 |
| cpf | 41 |

Ativo com um CNPJ é candidato direto para a camada compartilhada preencher o devedor (com a fonte). Ativo pulverizado (carteira com muitos devedores) não tem "o" devedor: o cadastro deve ficar vazio ou indicar a carteira. Ativo ligado a mais de um certificado não foi escolhido (conflito de identificador bloqueia).
