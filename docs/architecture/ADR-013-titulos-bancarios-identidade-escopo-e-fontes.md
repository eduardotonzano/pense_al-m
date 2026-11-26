# ADR-013: Títulos bancários (CDB, LCI, LCA, LF, DPGE): identidade, escopo e fontes

**Status:** Proposta, de 26/11/2026. Nada foi implementado: não há código, tabela nem migration. Depende de aprovação do Enrico (dono da frente) e, para o ponto D2, do Fábio (camada compartilhada). O CLAUDE.md pede confirmar com o Eduardo o dono da frente antes de assumir.
**Autores:** Enrico e Claude, a partir da etapa 0 (amostras de 26/11/2026)
**Relacionados:** ADR-001 a 005 (camada compartilhada), ADR-007 (instrumento como entidade), ADR-010 (prioridade de fontes), ADR-011 (CNPJ alfanumérico), ADR-012 (papel na relação)

## 1. Contexto

A frente nova cobre títulos de emissão bancária: CDB, RDB, LCI, LCA, LC, LF (sênior e subordinada), LIG e DPGE. O objetivo é monitorar taxas, risco de crédito do emissor, a divisão entre pré e pós-fixado e a concentração, com prioridade para CDB, LCI e LCA.

As regras do CLAUDE.md valem inteiras: nenhum cadastro paralelo (1), proveniência em todo dado (2), hierarquia BACEN > CVM > ANBIMA > especializadas > institucionais (3), valor original preservado (4), CNPJ como identificador forte e match só por nome nunca une (6), gravação idempotente (7).

### O que a etapa 0 mostrou (amostras de 26/11/2026; só contagens e estrutura)

**BACEN IFData (Olinda).**
- `IfDataCadastro(AnoMes=…)` devolve, por instituição: `CodInst`, nome, segmento (`SegmentoTb`, `Tcb`), segmentação prudencial (`Sr`), `CodConglomeradoFinanceiro`, `CodConglomeradoPrudencial`, `CnpjInstituicaoLider` e `Situacao`.
- `CodInst` de instituição individual é a **raiz de 8 dígitos do CNPJ**, não o CNPJ completo. Conglomerados usam o código `C…` (por exemplo `C0080312`).
- `IfDataValores(AnoMes,TipoInstituicao,Relatorio)` com `TipoInstituicao=1` e `Relatorio='5'` devolveu Basileia, Capital Principal, Capital Nível I, alavancagem, imobilização e os RWA (24 contas para o conglomerado de teste). Com `TipoInstituicao=2` e relatório 5 devolveu vazio; os tipos 2 e 3 não foram validados.
- O saldo vem como fração (0,17 = 17%).

**CVM, CDA de 09/2026** (`cda_fi_BLC_n_AAAAMM.csv`; sem ISIN nos blocos 5 e 6):
- Bloco 5 ("Depósitos a prazo e outros títulos de IF"): 35.513 posições. `TP_ATIVO`: Letra Financeira 24.611; CDB/RDB 10.027; DPGE 548; Outros 267; "Letra de Câmbio / Letra Hipotecária / Letra Imobiliária" 54; CDB Vinculado 6. Traz `CNPJ_EMISSOR` (preenchido em todas as linhas), indexador, percentual do indexador, cupom, taxa prefixada, vencimento, posição e campos de risco.
- Bloco 6: o **LCA** está aqui (142 posições, cerca de R$ 14 milhões), com `CPF_CNPJ_EMISSOR`, `TITULO_CETIP`, `TITULO_GARANTIA` e coobrigado.
- **LCI não existe como tipo próprio** em nenhum bloco. Só há o agrupamento de letras do bloco 5. O mesmo vale para LIG.
- Não distingue LF sênior de subordinada, nem RDB de CDB.
- Indexador no bloco 5: DI de um dia em 31.098 linhas, IPCA em 1.097, Selic em 285, prefixado em 136, outros em 338, vazio em 2.558.
- Risco do emissor: `RISCO_EMISSOR = S` em 1.674 das 35.513 linhas (4,7%), e só essas têm agência e grau. Agências: Fitch, S&P e Moody's, além de "Em Desenvolvimento" (401), que não é nota.
- 1.645 linhas têm `DT_CONFID_APLIC` preenchida (divulgação adiada). Há 146 CNPJs de emissor distintos.
- O nome do emissor é inconsistente ("BCO SANTANDER", "CAIXAECONOMICAFEDERALCEF", "*** A Definir ***"). Só o CNPJ serve de chave.

**CVM, ofertas** (`oferta_distribuicao.zip`, com `oferta_distribuicao.csv` e `oferta_resolucao_160.csv`): só 115 ofertas de Letras Financeiras entre 48,9 mil. Tem `Especie_Ativo` (Sem Preferência, Quirografária, Subordinada). Não traz CDB, LCI nem LCA. O arquivo da Resolução 160 serve a CRI/CRA, não a esta frente.

**Não conferidos:** B3 (estoque de balcão), ANBIMA (Feed, por assinatura) e FGC (página web). Nada abaixo depende deles.

## 2. Decisões propostas

### D1. O emissor é entidade da camada compartilhada; o título não é

- O banco é uma `Entity` identificada por CNPJ completo (`IdentifierType.CNPJ`). Não se cria cadastro de bancos na frente.
- **A posição do CDA não é entidade.** Cada linha é a posição de um fundo num mês, sem ISIN nem código de ativo. Criar uma entidade por linha geraria títulos sem chave, duplicáveis e impossíveis de reconciliar (regra 7).
- Um título só vira entidade quando houver identificador forte (ISIN ou código B3/CETIP), nos moldes do ADR-007. Hoje nenhuma fonte amostrada o oferece para CDB, LCI, LCA e LF. Quando a primeira oferecer, a decisão é um ADR próprio (novo `EntityType` e adaptador).

### D2. Conglomerado e raiz de CNPJ

- O conglomerado prudencial e o financeiro do BACEN não são pessoa jurídica. Proposta: uma entidade com `IdentifierType.BACEN_CODE` (`C0080312`) e as instituições ligadas por `BELONGS_TO_GROUP`.
- Isso pede **um `EntityType` novo** (nome sugerido: `FINANCIAL_CONGLOMERATE`). Pelo ADR-007, `entity_type` é texto sem `CHECK`, então não há migration, mas bancos gravados com o valor novo não abrem em código antigo. **Decisão do Fábio.** Alternativa: `OTHER`, que perde o filtro por tipo.
- A raiz de 8 dígitos do `CodInst` **não é CNPJ** e não cria entidade sozinha. Ela só resolve para uma entidade que já tenha CNPJ completo com a mesma raiz, e só se houver exatamente uma. Zero ou várias vão para revisão, nunca para união automática (regra 6).
- A entidade do emissor nasce do CNPJ completo (CDA, ofertas, ou cadastro). O IFData complementa com código BACEN, grupo e indicadores.
- O tipo da entidade fica neutro (`FINANCIAL_INSTITUTION`, como no ADR-012 D1). O segmento do `IfDataCadastro` (banco múltiplo, comercial, caixa econômica, cooperativa) é observação com proveniência, não tipo. Se preferirem `BANK` para os bancos, é decisão a registrar com o Eduardo e o Fábio.

### D3. Fontes e prioridade

Escala do ADR-010 (número maior vence), mapeada pelo nome da camada (`SourceType`), não pelo número, porque a camada compartilhada usa a escala inversa:

| Fonte | Camada | Prioridade proposta | O que fornece | Estado |
|---|---|---|---|---|
| BACEN IFData | BACEN | 550 | Basileia, capital, alavancagem, ativo, PL, captações, lucro, carteira, cadastro e grupo | Amostrada |
| BACEN SGS (`api.bcb.gov.br`) | BACEN | 540 | Séries de referência (CDI, Selic, IPCA) para converter "% do CDI" e calcular spread | Testada (série 4391 respondeu) |
| CVM, ofertas de LF | CVM | 450 | Emissão de LF, espécie (sênior, subordinada) | Amostrada |
| CVM, CDA (blocos 5 e 6) | CVM | 440 | Posições, indexador, taxa, vencimento, risco informado | Amostrada |
| ANBIMA | ANBIMA | 350, inativa | Taxas de LF | Só com assinatura; não decidida |
| B3 | Especializada | 250, inativa | Estoque de balcão; possível origem de LCI | Arquivo não localizado |
| FGC | Institucional | 150 | Associadas e conglomerados | Página web; não amostrada |

**Acesso observado em 26/11/2026** (da mais fácil para a mais difícil):

| Fonte | Acesso | Formato | Observação |
|---|---|---|---|
| IFData | aberto | JSON (OData) | Relatório 5 inteiro numa chamada (32.808 linhas); relatório 1 do tipo 1 em cerca de 5 s (13.980 linhas). Última competência com dado: 06/2026. |
| SGS | aberto | JSON | Série 4391 com dado de 11/2026. |
| CDA | aberto | ZIP de CSVs | Cerca de 15 MB por mês; 10/2026 já publicado em 26/11. A CVM republica arquivos antigos (o de 11/2025 foi modificado em 21/11/2026), então a carga guarda o SHA-256 e é idempotente. |
| Ofertas | aberto | ZIP de CSVs | 5,8 MB; só LF. |
| FGC | aberto, sem arquivo | página web | A lista não está no HTML lido (provável carga por JavaScript, não confirmada); sem data de atualização. |
| B3 | parte pública, parte paga | a confirmar | Existe arquivo público de Estoque de balcão e Data Reports pagos (DATAWISE). Link, formato e campos não confirmados; pode trazer só volume agregado, sem emissor. |
| ANBIMA | credencial | API OAuth | Exige cadastro; a documentação de preços cobre debêntures e não achei endpoint de LF. |

A CVM também tem API de metadados (CKAN, `package_show`), útil para detectar arquivo novo sem baixá-lo.

As prioridades de CVM-ofertas e CDA (450 e 440) são propostas e devem ser conferidas no plano de schema com o teste de escala do ADR-010. Pela regra 3, fonte de menor prioridade complementa e nunca sobrescreve. Pela regra 4, o valor de cada fonte é preservado antes de qualquer reconciliação. Pelo ADR-010 b), a prioridade só decide dentro da mesma competência.

Indicadores prudenciais (BACEN) e posições de fundos (CDA) são medidas diferentes e gravam em campos próprios; não disputam valor.

### D4. A CDA é evidência de mercado, não estoque nem emissão

A CDA mostra o que os fundos tinham em carteira no fim do mês. Ela não é o universo de emissões, subestima o que fica fora de fundos (varejo, LCI e LCA de pessoa física) e a taxa é a do carregamento do fundo, que pode ser de compra no secundário, não a taxa de emissão. A plataforma não pode apresentá-la como estoque do emissor nem como taxa de captação. Cada exibição deve dizer "posição em carteiras de fundos, competência AAAA-MM".

### D5. Classificação do título: só o que a fonte diz

Normalização, sem inferência por nome do emissor ou por texto livre:

| Rótulo da fonte | Classe adotada |
|---|---|
| Bloco 5, "CDB/ RDB" | CDB/RDB (a fonte não separa) |
| Bloco 5, "CDB Vinculado" | CDB vinculado |
| Bloco 5, "Letra Financeira" | LF, sem distinção sênior ou subordinada |
| Bloco 5, "DPGE" | DPGE |
| Bloco 6, "LCA" | LCA |
| Bloco 5, "Letra de Câmbio/ Letra Hipotecária/ Letra Imobiliária" | **Grupo de letras, sem separar LCI** |
| Bloco 5, "Outros" | Não classificado |

LCI, LIG, LC e a distinção sênior e subordinada ficam sem classe própria até uma fonte nova trazer o dado. Só as ofertas de LF informam a espécie. A classe de pré ou pós vem de `CD_INDEXADOR_POSFX` e `TITULO_POSFX`, e as linhas com indexador vazio ficam "sem indexador informado".

### D6. Risco de crédito: dois níveis, sem nota própria

- **Indicador principal: Índice de Basileia** (IFData, relatório 5, conta 79664; também no relatório 1), por competência trimestral. Vem com os componentes do mesmo relatório: Capital Principal (79659), Capital Nível I (79660), Razão de Alavancagem (79661) e Imobilização (79662). Escolha do Enrico em 26/11/2026. A última competência com dado em 26/11/2026 é 06/2026; a defasagem é de pelo menos dois meses e deve aparecer junto do valor.
- **Complementares do IFData:** inadimplência (relatório 16, conta 148834) e ativos problemáticos (conta 148833), em relação à carteira de crédito (relatório 1, conta 141873). A definição da conta 148834 (por exemplo, atraso acima de 90 dias) não foi confirmada e deve ser lida antes de qualquer exibição.
- **Cobertura:** o IFData não traz LCR nem NSFR, e o estoque de provisões não apareceu nos relatórios 1 a 4. Cobertura de provisão e liquidez ficam como pendência (seção 5), não como decisão.
- **Risco informado pelo fundo:** `RISCO_EMISSOR`, agência e grau da CDA. Só 4,7% das posições têm, então é complemento e não série. "Em Desenvolvimento" não é nota e não entra como grau.
- **Fora desta decisão:** qualquer score proprietário. A camada de score (Health, Risk, Opportunity) continua fora do escopo (ADR-001).

### D7. Posições confidenciais

Linhas com `DT_CONFID_APLIC` preenchida têm divulgação adiada. Elas são gravadas com a data de confidencialidade e **não entram em agregados** (concentração, exposição por emissor) até a data passar. Em 09/2026 são 1.645 de 35.513 posições (4,6%). Como gravar a data fica para o plano de schema.

## 3. Alternativas consideradas

1. **Entidade por título a partir do CDA.** Descartada (D1): sem chave, gera duplicidade.
2. **Cadastro próprio de bancos na frente**, por conveniência do IFData. Descartada: é o cadastro paralelo que a regra 1 proíbe.
3. **Casar a raiz de 8 dígitos com a primeira entidade encontrada.** Descartada: viola a regra 6. Raiz de CNPJ compartilhada entre entidades de nomes parecidos já é caso de revisão.
4. **Inferir LCI pelo nome do emissor (bancos com carteira imobiliária) ou pelo vencimento.** Descartada: é palpite sem fonte.
5. **Dar à CDA a prioridade de BACEN.** Descartada: a regra 3 coloca o BACEN acima da CVM.

## 4. Consequências

**Positivas:**
- um banco, um registro, com proveniência de todas as fontes;
- taxas, pré e pós e concentração já saem de dado público e amostrado;
- as lacunas (LCI, sênior e subordinada) ficam declaradas, não escondidas.

**Negativas e riscos:**
- **A prioridade do usuário, LCI, é a menos coberta.** Sem a B3 ou outra fonte, só há o grupo de letras, com 54 posições em 09/2026.
- A amostra é de **um único mês de CDA e uma competência do IFData**; as proporções acima podem mudar. A medição precisa ser repetida em vários meses antes de virar regra.
- O CDA só tem fundos; um emissor pequeno pode não aparecer.
- Os tipos 2 e 3 do IFData e a relação de `CodInst` com o CNPJ completo precisam ser validados no código.
- O `EntityType` novo (D2) tem o custo do ADR-007: código antigo não abre bancos novos.

## 5. Pendências

- Fábio: aceitar ou trocar o `EntityType` do conglomerado (D2).
- Eduardo: confirmar o dono da frente e a pasta (`Enrico/titulos_bancarios/`, sugestão).
- Localizar a fonte de LCI e do estoque de balcão (B3), e decidir sobre ANBIMA e FGC.
- Validar o `IfDataValores` para os tipos 2 e 3, e os relatórios 8 e 17 em diante, que vieram vazios para o conglomerado de teste.
- Cobertura: decidir entre liquidez (LCR por Pilar 3 de cada banco, coleta à parte) e cobertura de provisão (precisa achar o estoque de provisões). Não bloqueia o Basileia.
- Confirmar a definição das contas 148833 e 148834 do relatório 16.
- Repetir a medição em mais meses e com o `IfDataCadastro` de outras competências.
- Plano de schema (próximo documento), com tabelas, migration numerada, teste de idempotência e `--dry-run`, conforme "Mudança de schema" do CLAUDE.md.

## 6. Fora do escopo

- Código, tabelas e migrations.
- Score de risco, saúde financeira ou oportunidade.
- Layout e interface (ADR-001).
- Taxas de balcão e de captação por emissor (dependem de ANBIMA ou B3).
- Escolha final do tipo de entidade para título com identificador forte.
