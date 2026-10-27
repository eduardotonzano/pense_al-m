# Fundos (FIDC, FIC-FIDC, FIAGRO): descoberta

Documento de descoberta da frente de Fundos, para responder às regras F-01 a F-06 de [regras-de-exibicao-pendentes.md](regras-de-exibicao-pendentes.md). A "maior dor" do [README](../README.md) para esta frente é acompanhar o mercado de FIDCs e comparar os FIDCs da casa com o mercado.

**Escopo.** Só descoberta. Não há código de coleta, migration, banco ou dado interno neste trabalho, e nenhuma migration recebe número aqui. Nada foi consultado no Fundos.NET. Na primeira etapa (26/10/2026), das fontes da CVM foram lidas só páginas públicas de dados abertos e dicionários de dados (cerca de 60 KB no total). Em 27/10/2026 foram baixados dois arquivos pequenos da CVM, o informe mensal de FIAGRO de 09/2026 e o dicionário (seção 9); eles ficam numa pasta local fora do repositório, e nenhum arquivo baixado está neste repositório.

**Data da conferência:** 26/10/2026 (fontes e código) e 27/10/2026 (amostra de FIAGRO, seção 9). Tudo que não foi conferido está marcado como **não confirmado** e reunido na seção 8.

## Resumo

1. **Quase tudo de F-03 está nos dados abertos da CVM, sem navegador:** cadastro, informe mensal de FIDC, informe mensal de FIAGRO, CDA e medidas. No informe de FIDC faltam **gestora, custodiante e índice de subordinação**.
2. **O coletor do Fundos.NET do Enrico serve para o catálogo e o download de documentos, não para dado estruturado de fundos.** Dá para reaproveitar a camada de sessão, a paginação, a preservação da linha original, o download com SHA-256 e o padrão dry-run/commit com backup. Não dá para reaproveitar o que localiza o ativo (página de certificados, securitizadora, ISIN, emissão, devedor).
3. **Gestora vem do cadastro do fundo, custodiante do cadastro da classe, administradora do cadastro e do informe.** Subordinação não é publicada: precisa ser **calculada** das cotas por classe/série e depende de saber qual classe é sênior ou subordinada (o rótulo no informe é livre).
4. **FIC-FIDC:** o informe só traz o total aplicado em cotas de FIDC. Quais FIDCs e quanto em cada um vêm do CDA.
5. **FIAGRO:** informe próprio (133 campos por classe e 6 por subclasse; o ZIP mensal traz dois CSV). Numa amostra de 09/2026 (seção 9), a variante (FIDC, FII, FIP) **não sai do informe**: `Regra_Anexo` e `Classificacao_Autorregulada` são texto livre e pouco preenchidos. O cadastro continua sendo o candidato.
6. **"FIDCs da casa":** tabela interna, fora do repositório (seção 7).

## 1. Coletor do Fundos.NET do Enrico: o que reaproveitar

Código lido: `Enrico/cri_cra_platform/src/credit_assets/` (linhas conforme o commit `250112f`). A leitura foi só do código e dos relatórios já versionados; o Fundos.NET não foi acessado.

| Peça | Onde | Para fundos |
|---|---|---|
| Abrir o Edge com queda para o Chromium | `collectors/fundosnet_collector.py:505` (`_launch_browser`) | reaproveita |
| GET de JSON com `X-Requested-With`, 3 tentativas (0/2/5 s); resposta HTML vira "sessão inválida" | `:627` `_request_json`, `:664` `_page_fetch_json`, `:689` `_classify_html` | reaproveita; o `Referer` está fixo na página de certificados (`:641`) |
| Linhas da grade e paginação (`start`/`length`, `recordsFiltered`) | `:597` `_fetch_documentos`, `:717` `_extract_rows`, `:730` `_grid_text` | reaproveita; os filtros mudam |
| Guardar a linha original (`source_row_json`) e os campos oficiais da grade | `:738` `_to_document` | reaproveita a ideia; no schema de fundos vira `raw_records` |
| Diagnóstico sem cookie nem token | `:708` `_write_diagnostics` (grava em `reports/`, caminho relativo) | reaproveita, com pasta fora do Git |
| Download pela ação oficial "Download do Documento" (XML/PDF), SHA-256, teto de 25 MB | `services/document_download_service.py:260` `FundosNetBrowserDownloader`, `:60`; `download_diagnostics.py:70-131` | reaproveita; o relatório `reports/cafe_brasil_download_action_diagnostic.md` mostra `downloadDocumento?id=` devolvendo XML |
| Versões de arquivo por documento | `repositories/document_version_repository.py` | reaproveita o desenho |
| Migrations numeradas, backup, `apply_migration`, `--dry-run`/`--commit` | `database/migrations.py`, `database/backup.py`, `scripts/apply_migration.py` | reaproveita, em banco separado de fundos |
| Página `abrirGerenciadorDocumentosCertificadosCVM` e filtros `paginaCertificados`/`paraCerts` | `:89`, `:524-568` | **não serve** |
| Tipo de fundo `5` = CRI e `6` = CRA | `utils/fundosnet_normalization.py:29-35` | **não serve**: os códigos de FIDC e FIAGRO não estão confirmados |
| Escolher o "administrador" pela securitizadora, com alias fixo | `:186`, `:512-548` | **não serve** |
| Casar o certificado por ISIN, emissão e devedor | `:245`, `:550-595`, `:131`, `:385` | **não serve**: a chave de fundo é o CNPJ |
| `Asset`/`assets` e `documents.category` com 9 categorias de CRI/CRA, pastas por CETIP | `models/`, `schema.sql:41-51`, `document_download_service.py:41-46` | **não serve** como está |

**Recomendação.** Usar os dados abertos da CVM como fonte primária de cadastro e informes (sem Playwright; basta `requests`, que já está nas dependências). O Fundos.NET entra para o **catálogo e o download de documentos** (regulamento, demonstrações, fatos relevantes) e para conferência. Antes de qualquer código, fazer uma **sonda** da grade do Fundos.NET para fundos (página, `tipoFundo`, filtros). A sonda usa rede e precisa de aprovação.

## 2. Fontes oficiais

Todas são páginas do portal de dados abertos da CVM, conferidas em 26/10/2026. Foram lidas as páginas e os dicionários; os arquivos de dados não foram baixados.

| Fonte | Página | Formato e periodicidade | Conteúdo |
|---|---|---|---|
| Fundos de Investimento: Informação Cadastral | https://dados.cvm.gov.br/dataset/fi-cad | ZIP/CSV/TXT; **diária** (terça a sábado, 08:00). `registro_fundo_classe.zip` (7 MB), `cad_fi.csv` (17 MB, só fundos não adaptados à Res. 175), `cad_fi_hist.zip` (18 MB, ICVM 555). Dicionário em `meta_registro_fundo_classe.zip` | Fundo (21 campos: gestor, CPF/CNPJ do gestor, administrador, CNPJ do administrador, tipo, situação, PL, data de adaptação à Res. 175); classe (30: custodiante, CNPJ do custodiante, controlador, auditor, tipo da classe, classificação, ANBIMA, público-alvo, exclusivo, entidade de investimento); subclasse (14) |
| FIDC: Documentos: Informe Mensal | https://dados.cvm.gov.br/dataset/fidc-doc-inf_mensal | ZIP mensal `inf_mensal_fidc_AAAAMM.zip` (cerca de 3 MB cada), **semanal** (últimos 12 meses); histórico em `HIST/` por ano, desde 2013. Dicionário em `meta_inf_mensal_fidc_txt.zip` (16 KB, 18 tabelas) | Anexo A da ICVM 489/11, segundo a página (que não cita a Res. 175, embora o dicionário já traga campos dela). Tabelas I a X; ver seção 3 |
| FIAGRO: Documentos: Informe Mensal | https://dados.cvm.gov.br/dataset/fiagro-doc-inf_mensal | ZIP mensal `inf_mensal_fiagro_AAAAMM.zip` (2,8 KB a 73 KB; dois CSV por ZIP, classe e subclasse), **semanal**; conjunto novo (14/10/2025). Dicionário em `meta_inf_mensal_fiagro.zip` | Anexo VI da "Instrução CVM nº 175/2022" (como a página escreve), entrega pelo Fundos.NET; 133 campos por classe, mais arquivo de subclasse (6 campos), conferidos na amostra de 09/2026 (seção 9) |
| Fundos de Investimento: CDA | https://dados.cvm.gov.br/dataset/fi-doc-cda | ZIP mensal `cda_fi_AAAAMM.zip`; M-1 a M-3 atualizados de terça a sábado, M-4 a M-12 às segundas; posições confidenciais só consolidadas. Dicionário em `meta_cda_fi_txt.zip` (10 KB) | Carteira por fundo. Bloco 2 = cotas de fundos (`CNPJ_FUNDO_CLASSE_COTA`, `QT_POS_FINAL`, `VL_MERC_POS_FINAL`). FIDC e FIAGRO entraram em 08/11/2025 (`cda_fie_AAAAMM.csv` desde 15/11/2025) |
| Fundos Estruturados: Medidas | https://dados.cvm.gov.br/dataset/fie-medidas | CSV mensal `medidas_mes_fie_AAAAMM.csv`, **semanal** (12 meses; histórico desde 01/2017) | PL e número de cotistas de FIP, FIDC e FII "etc." (6 campos); FIAGRO **não é citado** |
| Novidades do portal | https://dados.cvm.gov.br/pages/novidades | HTML | Registro das mudanças nos conjuntos (ver seção 8) |

Todas as páginas declaram a licença **ODbL**. As obrigações dessa licença para uma base derivada publicada **não foram analisadas**; conferir antes de publicar dado derivado.

## 3. Estrutura do informe mensal de FIDC (pelo dicionário)

18 tabelas:

| Tabela | Conteúdo |
|---|---|
| `tab_I` (109 campos) | administrador e CNPJ, classe, condomínio, fundo exclusivo, ativo, carteira; **cedentes: CPF/CNPJ e % de participação, até 9 com risco e 9 sem risco** |
| `tab_II` (37) | carteira por segmento |
| `tab_III` | passivo |
| `tab_IV` | PL e PL médio |
| `tab_V`, `tab_VI` | prazos, inadimplência, antecipados |
| `tab_VII` | aquisições, alienações, substituições, recompra; cedente e partes relacionadas |
| `tab_VIII` | `VALOR`/`SEQUENCIAL` (descrição vazia no dicionário) |
| `tab_IX` | negociação de direitos creditórios: mínimo, médio e máximo |
| `tab_X` | SCR do devedor |
| `tab_X_1` | cotistas por classe/série |
| `tab_X_1_1` | cotistas por tipo, sênior e subordinada; **inclui "cotas de FIDC"** |
| `tab_X_2` | quantidade e **valor da cota** por classe/série |
| `tab_X_3` | rentabilidade no mês |
| `tab_X_4` | operações com cotas |
| `tab_X_5` | liquidez |
| `tab_X_6` | desempenho real e esperado |
| `tab_X_7` | garantias |

**O informe não tem:** versão, data de entrega, rating, spread nem índice de subordinação. Também não tem gestora nem custodiante (nenhuma ocorrência de "gestor" ou "custod" nas 18 tabelas do dicionário).

## 4. Campos da ficha (F-03) e de onde vêm

| Campo | Fonte e campo | Situação |
|---|---|---|
| Identificação, tipo, situação | `registro_fundo` (`CNPJ_Fundo`, `Tipo_Fundo`, `Situacao`); `registro_classe` (`CNPJ_Classe`, `Tipo_Classe`, `Classificacao`) | dicionário conferido; domínios dos campos **não confirmados** |
| Gestora | `registro_fundo.Gestor` e `CPF_CNPJ_Gestor`; FIAGRO: `Nome_Gestor`, `CNPJ_Gestor` | **ausente no informe de FIDC**; no de FIAGRO, nomes conferidos na amostra (seção 9) |
| Administradora | `registro_fundo.Administrador` e `CNPJ_Administrador`; FIDC: `tab_I.ADMIN`, `CNPJ_ADMIN`; FIAGRO: `Nome_Administrador`, `CNPJ_Administrador` | conferido; no de FIAGRO, nomes conferidos na amostra (seção 9) |
| Custodiante | `registro_classe.Custodiante` e `CNPJ_Custodiante` | só no cadastro da classe |
| Cotas | FIDC: `tab_X_2` (valor e quantidade), `tab_X_3` (rentabilidade), `tab_X_1` e `tab_X_1_1` (cotistas), `tab_X_4`. FIAGRO: `Valor_Patrimonial_Cotas`, `Cotas_Emitidas`, `Rentabilidade_*`, `Dividend_Yield_Mes`, `Numero_Cotistas*`, subclasse | conferido |
| Subordinação | **não existe pronta**; calcular a partir de `tab_X_2` por classe/série | depende do rótulo `TAB_X_CLASSE_SERIE` (alfanumérico livre; **não confirmado**) |
| Carteira de recebíveis | `tab_I` (I.2.a e I.2.b), `tab_II` (segmento), `tab_V` e `tab_VI`, `tab_VII`, `tab_IX`, `tab_X`. FIAGRO: `A_Vencer_*`, `Vencidos_*`, `Direitos_Creditorios_Agronegocio` | conferido |
| Cedentes | `tab_I.TAB_I2A12_*` e `TAB_I2B12_*` (CPF/CNPJ e %), só os 9 maiores; `tab_VII.B` | **o CPF aparece** no dado; proposta: não gravar CPF (LGPD); decisão da equipe |
| Cotas investidas (FIC-FIDC) | total em `tab_I.TAB_I2H_VL_COTA_FIDC`; posições no CDA, Bloco 2 | o detalhe de cada FIDC investido só existe no CDA |
| Spread, rating das cotas | não existem no informe | ficam "ausente" (regra de ausente com razão) |

## 5. Schema proposto

Mesmo esqueleto de `Eduardo/debenture-replica/migrations/001_initial_schema.sql` (sem numeração): `sources`, `collection_runs`, `raw_records`, `observations` (valor texto, numérico, data ou booleano; `observed_at`, `collected_at`, `confidence`, `checksum` único), `data_conflicts`, `audit_log` e a view `current_observations`. Muda o que identifica o assunto da observação:

- `funds` (no lugar de `issuers`): CNPJ de 14 dígitos único, denominação, `ID_Registro_Fundo`.
- `fund_classes` (no lugar de `debentures`): fundo, CNPJ da classe (RCVM 175), `ID_Registro_Classe`. As observações apontam para a classe.
- `quota_series`: classe/série/subclasse **com o rótulo exatamente como a fonte traz**, `ID_Subclasse` quando houver; `observations.quota_series_id` é anulável.
- `party_observations`: papel (gestor, administrador, custodiante, controlador, auditor, cedente), CNPJ (nunca CPF), nome, posição, % de participação, fonte, data, `raw_record_id`, `checksum`.
- `holdings`: fundo detentor, CNPJ e nome do fundo investido, data da posição, quantidade, valor de mercado, fonte, `raw_record_id`, `checksum`. É posição no tempo, não relação de identidade.
- `quota_class_map`: rótulo da série para sênior, mezanino ou subordinada, **curado e revisado**. Sem mapa, a subordinação sai "ausente (rótulo não mapeado)".

`field_name` recebe `tabela.coluna` da CVM, sem renomear; a escolha do que exibir é F-03.

**Diferenças em relação às debêntures, a decidir:**

1. `raw_records` guarda um manifesto (nome, tamanho, SHA-256, linhas) e o arquivo fica em pasta fora do Git, porque o ZIP de FIDC tem cerca de 3 MB e muda toda semana.
2. A escala de `priority` precisa de um ADR antes do uso. Nas debêntures a view ordena `priority DESC` e a ANBIMA (300) passaria à frente da CVM (200).
3. O informe de FIDC **não tem versão nem data de entrega**. Uma reapresentação aparece como mesma competência com valor diferente entre coletas semanais e deve ir para `data_conflicts`. O informe do FIAGRO tem `Versao` e `Data_Entrega` (confirmado na amostra de 09/2026), mas, no arquivo da amostra, a única linha com `Versao` 2 não vem acompanhada da versão 1, e a chave (`CNPJ_Classe`, `Data_Referencia`) se repetiu em 2 casos que não são reapresentações (seção 9). O schema não deve pressupor histórico de versões dentro do arquivo nem unicidade dessa chave.
4. A camada compartilhada (`src/pense_alm/shared/entities/enums.py`) não tem tipo de entidade para administradora ou custodiante (`EntityType`, linhas 6-20) nem relação "investe em" (`RelationshipType`, linhas 85-102). Existem `MANAGES`, `ADMINISTERED_BY`, `PROVIDES_SERVICES_TO` e `ASSIGNS_RECEIVABLES_TO`. Proposta: gestora (`ASSET_MANAGER`) e fundo (`FIDC`, `FIAGRO` ou `FUND`) viram entidades; administradora e custodiante usam `FINANCIAL_INSTITUTION` ou `COMPANY` até um ADR decidir; as posições ficam em `holdings` (F-06).

## 6. FIC-FIDC e FIAGRO

**FIC-FIDC**

- **Como identificar: não confirmado.** Os domínios dos campos de tipo e classificação estão vazios no dicionário. Sinais candidatos: classificação do cadastro, `TAB_I2H_VL_COTA_FIDC` frente ao ativo e cotistas "cotas de FIDC" em `tab_X_1_1` do fundo investido. Nunca identificar por "FIC" no nome.
- **Posições:** CDA, Bloco 2 (`CNPJ_FUNDO_CLASSE_COTA`, `NM_FUNDO_CLASSE_SUBCLASSE_COTA`). Para FIDC e FIAGRO as posições estão no `cda_fie` desde 08/11/2025, mas o dicionário dele não mostra a coluna do fundo investido (a conferir).
- **Exibição (F-04), proposta:** lista dos fundos investidos com valor e % do PL. Não somar métricas "por transparência" (dupla contagem), a menos que seja pedido e calculado à parte.

**FIAGRO**

- Mesmo cadastro dos demais fundos, mas informe próprio por classe (`CNPJ_Classe`), com `Codigo_ISIN`, `Mercado_Negociacao` e valores investidos em cotas de fundos: total em `Cotas_Fundos_Investimento` e abertura em `FIF`, `FIDC`, `FII`, `FIP`, `FIIM` e `FIAGRO` (o dicionário não descreve `FIIM`). São valores, sem identificar o fundo investido (isso vem do CDA), e não a variante do próprio fundo.
- **Variante: não sai do informe de FIAGRO (confirmado na amostra de 09/2026).** `Regra_Anexo` é texto livre, preenchido em 25% das linhas, e cita Anexo Normativo I, II ou III; `Classificacao_Autorregulada` é texto livre preenchido em 9%, com conteúdo misto; `Classe_Unica` é S/N e não indica variante. O candidato que resta é o cadastro (`Tipo_Classe`, `Classificacao`, `Entidade_Investimento`), a conferir na FU1.2.
- O modelo aceita as duas escolhas de F-05 (variante como observação da classe). Páginas juntas ou separadas é decisão de exibição.
- **Subclasses:** o arquivo de subclasse traz `Nome_Subclasse`, `Numero_Cotas` e `Valor_Patrimonial_Cota`, mas o nome é ordinal (`Subclasse 1 (ou classe única)`, `Subclasse 2`, ...) e não diz sênior ou subordinada. A subordinação de um FIAGRO-FIDC não sai do informe, como no FIDC.
- **Risco:** o mesmo FIAGRO-FIDC pode aparecer nos dois informes. Chavear por CNPJ da classe. A conferência depende dos informes de FIDC e de FII e está **pendente para a FU1.2**.

## 7. FIDCs da casa

- A tabela é **privada**, fora do repositório e do banco versionados. Local: **pasta interna, fora dos dois clones Git, com acesso restrito à equipe, local a ser definido pela equipe.**
- O `.gitignore` não protege uma pasta dentro do clone: o arquivo continua no disco do clone e um `git add -f` ou um clone mal configurado o publica. Por isso o local precisa ficar fora dos clones.
- **Forma:** SQLite próprio (`fundos_casa.sqlite3`) ou planilha, com o caminho só na variável de ambiente `PENSE_INTERNAL_DIR`, nunca no código nem nos documentos. O comparativo "casa x mercado" é montado só em ambiente interno (`ATTACH` somente leitura); o banco público e o site não carregam o marcador.
- **Colunas propostas:**

| Coluna | Uso |
|---|---|
| `cnpj_classe` | identificador público do fundo |
| `relacao_com_a_casa` | valores a definir em F-02 |
| `grupo_de_comparacao` | pares para o comparativo |
| `desde`, `ate` | vigência da classificação |
| `fonte_interna` | de onde veio a informação |
| `observacao` | texto livre |
| `atualizado_em`, `atualizado_por` | auditoria da tabela |

- **Exemplos neste repositório só fictícios e marcados** (por exemplo, "FIDC Exemplo Alfa (fictício)", CNPJ de teste `00.000.000/0000-00`). Nenhuma lista de fundos da casa, carteira ou nome interno entra em arquivo versionado.

## 8. F-01 a F-06 e o que falta

| Regra | O que a descoberta responde | Em aberto |
|---|---|---|
| **F-01** Fonte e coleta | CVM dados abertos como fonte primária de cadastro e informes; Fundos.NET para documentos (seções 1 e 2) | sonda do Fundos.NET; dono da frente; formato real dos CSV de FIDC (o de FIAGRO está confirmado na seção 9) |
| **F-02** FIDCs da casa x mercado | Métricas disponíveis: rentabilidade (`tab_X_3`), PL, cotistas, inadimplência, segmento. Subordinação é derivada. **Spread não existe** no informe. Tabela da casa na seção 7 | definição de "da casa" e dos grupos de comparação; mapa de rótulos sênior/subordinada |
| **F-03** Ficha | Campo a campo na seção 4 | tratamento do CPF dos cedentes; domínios dos campos de tipo |
| **F-04** FIC-FIDC | Total no informe, posições no CDA (seção 6) | como identificar um FIC-FIDC; coluna do fundo investido no `cda_fie` |
| **F-05** FIAGRO | Informe próprio; modelo aceita as duas escolhas (seção 6); a variante não sai do informe (seção 9) | variante pelo cadastro e sobreposição com os informes de FIDC e de FII (FU1.2) |
| **F-06** Relacionamentos | `holdings` e `party_observations` (seção 5) | ADR para administradora e custodiante e para a relação "investe em" |

### Divergências entre dicionário e Novidades

- O dicionário do FIDC não tem `ID_SUBCLASSE` na `tab_X_1`, embora as Novidades de 02/02/2026 digam que o campo entrou.
- O dicionário do FIDC lista `CNPJ_FUNDO` nas tabelas X.1 a X.4 e X.6, embora as Novidades de 06/01/2025 digam que `CNPJ_FUNDO_CLASSE` o substituiu.
- Conferir no dado real antes de fixar o schema.

### Datas relevantes das Novidades

07/10/2024 (cadastro reorganizado em fundo, classe e subclasse); 06/01/2025 (`TP_FUNDO_CLASSE`); 14/10/2025 (FIAGRO); 08/11/2025 (CDA com FIDC e FIAGRO); 05/04/2026 (FIDC de 2019 a 2024 movido para `HIST/`); 13/08/2026 (`tab_VIII` incluída); 06/09/2026 (histórico de 2013 a 2024 atualizado).

### Não confirmado

- **(a)** A grade de FIDC e FIAGRO no Fundos.NET (página, `tipoFundo`, categorias de documento): não consultada.
- **(b)** O domínio dos campos `Tipo_Fundo`, `Tipo_Classe`, `Classificacao` e `Entidade_Investimento` (do cadastro): o dicionário os deixa vazios; segue **não confirmado**, para a FU1.2. **Confirmado em 27/10/2026 para o informe de FIAGRO:** `Regra_Anexo`, `Classe_Unica` e `Classificacao_Autorregulada` (seção 9). `Regra_Anexo` e `Classificacao_Autorregulada` são texto livre, não domínios controlados.
- **(c)** Se o FIAGRO-FIDC aparece também no informe de FIDC e o FIAGRO-FII no de FII (a página do FII, <https://dados.cvm.gov.br/dataset/fii-doc-inf_mensal>, não cita FIAGRO). **Pendente para a FU1.2**: depende dos informes de FIDC e de FII; a amostra de FIAGRO sozinha não responde.
- **(d)** Cobertura de FIDC nos balancetes (`fie-doc-balancete`, `fi-doc-balancete`): a descrição das páginas está truncada.
- **(e)** Se o `cda_fie` identifica o fundo investido pelo CNPJ.
- **(f)** Codificação, separador e linhas dos CSV de FIDC (os de CRI/CRA eram latin-1 e `;`): segue **não confirmado**, para a FU1.2. **Confirmado em 27/10/2026 para o FIAGRO:** `;`, cp1252, CRLF, cabeçalho na primeira linha, 312 linhas de classe e 697 de subclasse (seção 9).
- **(g)** Prazos regulatórios de entrega dos informes. A amostra de FIAGRO mostra entregas de 05/10 a 15/10/2026 para a competência 09/2026, com 226 das 312 linhas em 14 e 15/10; o prazo da norma segue **não confirmado**.
- **(h)** A ANBIMA como fonte.

### Próximos passos, sem código

1. Aprovar a sonda do Fundos.NET.
2. **Feito para o FIAGRO em 27/10/2026** (seção 9). Falta a mesma leitura de uma amostra pequena do informe de FIDC, do cadastro (`registro_fundo_classe`) e do CDA (FU1.2), que precisa de nova autorização de rede.
3. Decidir F-01 e o dono da frente.
4. Escrever o ADR de prioridade de fontes.
5. Decidir o tratamento do CPF dos cedentes.

## 9. Amostra de FIAGRO (27/10/2026)

Leitura de um mês do informe mensal de FIAGRO e do dicionário, para fechar os pontos do FIAGRO que a seção 8 deixava abertos. Só agregados: esta seção não traz linhas de fundos, CNPJs, ISINs nem nomes. Os arquivos ficam numa pasta local fora do repositório.

### 9.1 Origem e integridade

As URLs saíram da página do conjunto (<https://dados.cvm.gov.br/dataset/fiagro-doc-inf_mensal>), que lista os informes de 10/2025 a 09/2026 e o dicionário. O mais recente era 09/2026; não havia arquivo de 10/2026, então 09/2026 é o último mês completo. Foi feita uma requisição GET a cada arquivo, por HTTPS, sem redirecionamento; as duas respostas foram 200 `application/zip`.

| Arquivo | Tamanho | SHA-256 | Baixado (UTC) |
|---|---|---|---|
| `inf_mensal_fiagro_202609.zip` | 74.365 bytes | `a9700ab77db8f731f15be994b1462828bf0527d7aa2fb46233cd7d86bb9e0948` | 2026-10-27 13:22:07 |
| `meta_inf_mensal_fiagro.zip` | 2.546 bytes | `b5a71cb9adceef00eb617c977d1d8c75ed95eecc3164af84d826c3f446e4b7c9` | 2026-10-27 13:22:07 |

URLs: `https://dados.cvm.gov.br/dados/FIAGRO/DOC/INF_MENSAL/DADOS/inf_mensal_fiagro_202609.zip` e `https://dados.cvm.gov.br/dados/FIAGRO/DOC/INF_MENSAL/META/meta_inf_mensal_fiagro.zip`. O conjunto é atualizado toda semana: o hash do arquivo de 09/2026 vai mudar quando a CVM o atualizar, e o hash acima identifica o que foi lido. Depois da análise, os dois hashes foram conferidos de novo e não mudaram.

### 9.2 Estrutura dos arquivos (item a)

| Arquivo | Conteúdo | Descomprimido | Linhas de dados | Campos |
|---|---|---|---|---|
| `inf_mensal_fiagro_202609.csv` | informe por classe | 316.587 bytes | 312 | 133 |
| `inf_mensal_fiagro_subclasse_202609.csv` | subclasses | 68.732 bytes | 697 | 6 |
| `meta_inf_mensal_fiagro.txt` | dicionário da classe | 23.745 bytes | n/a | 133 |
| `meta_inf_mensal_fiagro_subclasse.txt` | dicionário da subclasse | 988 bytes | n/a | 6 |

- **Formato dos CSV:** separador `;`, cabeçalho na primeira linha (nomes únicos), fim de linha CRLF, sem aspas, sem BOM, uma quebra de linha no fim, e todas as linhas com o número de campos do cabeçalho.
- **Codificação:** não é UTF-8 (a leitura estrita falha). Decodifica sem erro como cp1252. Nenhum byte cai na faixa 0x80 a 0x9F, então cp1252 e ISO-8859-1 não se distinguem na amostra. Os caracteres não ASCII são letras do português e "º", sem sinal de dupla codificação. Os dois dicionários (TXT) têm a mesma codificação e CRLF.
- **Números e datas:** decimal com ponto e sem separador de milhar; datas `AAAA-MM-DD`; identificadores sem máscara.
- **Confere com o dicionário:** 133 campos no CSV de classe e 133 no dicionário; 6 e 6 na subclasse. A única diferença é um nome truncado no dicionário (`Numero_Cotistas_Entidade_Previdencia_Complementar_`, contra `Numero_Cotistas_Entidade_Previdencia_Complementar_Exceto_RPPS` no CSV). O dicionário não segue a ordem das colunas; é uma lista de blocos por campo.
- **O dicionário é pobre:** descreve 13 dos 133 campos e informa domínio em 9 (`S/N`, `AAAA-MM-DD`, "Alfanumérico", "Numérico"). Não serve para fechar domínios. Tipos declarados: 98 numeric, 19 varchar, 11 int, 3 date, 1 tinyint, 1 bigint. Alguns tamanhos declarados são maiores que o dado (CNPJ de classe e de administrador com 30 caracteres, de gestor com 255, ISIN com 18; o dado tem 14 e 12).

### 9.3 Domínios (item b)

| Campo | Preenchidos | Valores (contagem de linhas) |
|---|---|---|
| `Data_Referencia` | 312 | um valor: o dia 1 do mês (2026-09-01) |
| `Versao` | 312 | 1 (311) e 2 (1) |
| `Classe_Unica` | 312 | N (300) e S (12) |
| `Publico_Alvo` | 312 | INVESTIDOR PROFISSIONAL (190), INVESTIDOR QUALIFICADO (68), INVESTIDORES EM GERAL (54) |
| `Cotistas_Vinculo_Familiar` | 312 | N (310) e S (2) |
| `Mercado_Negociacao` | 312 | BALCAO (152), BOLSA (104), BALCAO NAO ORGANIZADO (56) |
| `Regra_Anexo` | 78 (25%) | texto livre, 8 textos distintos, até 91 caracteres; cita Anexo Normativo II em 53 linhas (5 como "aplicável subsidiariamente"), III em 24 e I em 1; 8 linhas trazem frases inteiras em vez de um código; a grafia varia ("ANEXO NORMATIVO II", "ANEXO III", "Anexo Normativo II") |
| `Classificacao_Autorregulada` | 27 (9%) | texto livre, 13 textos distintos: "FIAGRO" (8), "SIM" (7), "não" (1), listas separadas por vírgula (por exemplo "Papel" ou "Tijolo, Híbrido, Gestão Ativa, Multicategoria") e variações de "Agro, Indústria e Comércio"; uma linha traz a frase copiada de `Regra_Anexo` |
| `Entidade_Administradora` | 74 (24%) | B3 (31), BM&FBOVESPA (22), BM&FBOVESPA e CETIP (9), CETIP (3); 8 linhas trazem um telefone e 1 traz "0". Pelos valores, é a entidade administradora do mercado (B3, CETIP), não a administradora do fundo |
| `Prazo_Duracao` | 312 | texto livre, 33 valores, misturando "ANO/ANOS", "DIA/DIAS", "DIAS/DIAS" e "MÊS/MESES"; 268 linhas têm 0, 99, 999, 1000, 9999 ou 99999 (provável marcador de prazo indeterminado: **não confirmado**) |
| `Encerramento_Exercicio_Social` | 312 | 30 datas `dd/mm` distintas; 31/12 (136) e 30/06 (72) lideram |
| `Nome_Subclasse` (arquivo de subclasse) | 697 | 22 valores: 15 ordinais usados por 3 ou mais classes (`Subclasse 1 (ou classe única)` em 270 linhas, `Subclasse 2` em 191, até `Subclasse 14`) e 7 nomes usados por menos de 3 classes (8 linhas). A primeira também aparece com outra grafia (`Subclasse 1(ou classe única)`, 42 linhas) |

Conclusões: `Regra_Anexo` e `Classificacao_Autorregulada` não são domínios controlados, e o informe de FIAGRO não tem campo de tipo ou variante. `Classe_Unica` e `Cotistas_Vinculo_Familiar` são S/N. Cruzando `Regra_Anexo` com a composição do ativo, o sinal é fraco: das 24 linhas que citam o Anexo III, 11 têm `Imoveis_Rurais` maior que zero; das 53 que citam o Anexo II, 3 têm `Direitos_Creditorios_Agronegocio` maior que zero. O significado de cada anexo na norma não foi verificado nesta etapa.

### 9.4 Chave, versões e entregas (item c)

- **Chave:** 312 linhas e 310 `CNPJ_Classe` distintos. Como `Data_Referencia` tem um só valor, há 310 pares (`CNPJ_Classe`, `Data_Referencia`): duas chaves se repetem (4 linhas).
- **As duas repetições não são reapresentações.** Em cada uma, as duas linhas têm a mesma `Versao` (1 e 1) e a mesma `Data_Entrega`, mas `Nome_Classe`, `CNPJ_Gestor`, `Patrimonio_Liquido` e `Data_Registro` diferentes, `Codigo_ISIN` diferente (vazio em uma delas) e o mesmo `CNPJ_Administrador`. Parecem classes distintas com o mesmo `CNPJ_Classe` (**não confirmado**; conferir no cadastro, FU1.2). O par (`CNPJ_Classe`, `Nome_Classe`) é único nas 312 linhas.
- **`Versao`:** 311 linhas com 1 e 1 com 2. A classe da linha de `Versao` 2 aparece uma só vez no arquivo: a versão 1 não vem junto. No arquivo da amostra, portanto, a versão anterior não aparece; se ela some entre as atualizações semanais só se vê comparando dois instantâneos (não feito).
- **`Data_Entrega`:** de 05/10 a 15/10/2026, em 9 datas; 226 das 312 linhas em 14 e 15/10 (99 e 127). A linha de `Versao` 2 foi entregue em 15/10. Não há entrega depois de 15/10, embora o arquivo tenha sido baixado em 27/10.
- **Subclasse:** 697 linhas para 310 classes. Toda classe do arquivo de classe tem ao menos uma linha de subclasse (inclusive as 12 com `Classe_Unica` igual a S), e toda subclasse pertence a uma classe do arquivo. Há uma linha `Subclasse 1` para cada linha do arquivo de classe (270 mais 42 igual a 312). O arquivo de subclasse não tem `Versao` nem `Data_Entrega`: com chave repetida na classe, as linhas de subclasse não se ligam a uma versão. Três pares (`CNPJ_Classe`, `Nome_Subclasse`) se repetem (um com valores idênticos e dois com valores diferentes). Em 11 classes todas as subclasses têm `Numero_Cotas` igual a zero.

### 9.5 Formatos e dados pessoais (item d)

- **CNPJ:** `CNPJ_Classe`, `CNPJ_Administrador` e `CNPJ_Gestor` têm 14 dígitos sem máscara em 312 de 312 linhas, nenhum vazio, um valor por célula, e todos passam na verificação dos dígitos. O arquivo de subclasse usa o mesmo formato, e todos os seus CNPJ existem no arquivo de classe.
- **`Codigo_ISIN`:** preenchido em 191 linhas (61%) e vazio em 121 (39%). Os 191 têm 12 caracteres, maiúsculas, padrão `[A-Z]{2}[A-Z0-9]{9}[0-9]`, país BR e nenhum separador (um ISIN por célula). O trecho de tipo (posições 7 a 9) é `CTF` em 188 e `R01` em 3. Três ISIN aparecem em duas classes distintas cada (6 linhas), sempre do mesmo gestor e do mesmo administrador e com `Nome_Classe` diferente: o ISIN não é único por classe. Preenchimento por `Mercado_Negociacao`: BOLSA 73 de 104, BALCAO 87 de 152, BALCAO NAO ORGANIZADO 31 de 56.
- **CPF:** nenhum valor com padrão de CPF em nenhuma coluna de texto, inclusive `CNPJ_Gestor`.
- **Dados de contato:** `Email_Administrador` (311 preenchidos, 29 distintos, 308 com padrão de e-mail), `Servico_Atendimento_Cotista` (texto livre, 311 preenchidos, 107 com e-mail e 158 com padrão de telefone), `Site` (296 preenchidos, 6 com e-mail) e `Entidade_Administradora` (8 linhas com telefone). São contatos da administradora ou da classe; a amostra não permite dizer se algum é de pessoa natural. Proposta: não gravar nem exibir esses campos sem decisão.
- **Nomes:** `Nome_Gestor`, `Nome_Administrador` e `Nome_Classe` são texto livre e não normalizado: há mais nomes distintos que CNPJs (172 nomes para 99 CNPJ de gestor; 81 para 25 de administrador). A chave tem que ser o CNPJ.
- **Qualidade observada:** `Patrimonio_Liquido` menor ou igual a zero em 10 linhas e `Cotas_Emitidas` menor ou igual a zero em 11; `Data_Registro` vai de 2000-01-01 (possível valor padrão: não confirmado) a 2026-09-30. `Numero_Cotistas_Pessoa_Natural` e `Devedor_Pessoa_Natural_*` são contagens e valores agregados, não dado pessoal.

### 9.6 Colunas de gestora, administradora e investimentos (item e)

| Papel | Colunas | Observação |
|---|---|---|
| Gestora | `Nome_Gestor`, `CNPJ_Gestor` | um CNPJ por linha; 99 CNPJ distintos |
| Administradora | `CNPJ_Administrador`, `Nome_Administrador` | 25 CNPJ distintos |
| Contato da administradora | `Email_Administrador` | ver 9.5 |
| Não é a administradora | `Entidade_Administradora` | pelos valores, entidade administradora do mercado (B3, CETIP) |
| Investimento em cotas de fundos | `Cotas_Fundos_Investimento` (total) e, em seguida, `FIF`, `FIDC`, `FII`, `FIP`, `FIIM`, `FIAGRO` | valores; `FIIM` não é descrito no dicionário |

Os nomes batem com os que o documento já citava e com o dicionário. Nas 115 linhas com valor, o total é igual à soma das seis aberturas (diferença menor que 0,01); as outras 197 têm tudo zero. Linhas com valor por abertura: `FIAGRO` 60, `FIDC` 59, `FIF` 13, `FII` 13, `FIP` 1 e `FIIM` 0. Combinações mais comuns: só FIAGRO (40), só FIDC (34), FIDC e FIAGRO (15) e só FIF (10). Os campos não identificam o fundo investido; para saber qual FIDC ou FIAGRO é a posição, continua valendo o CDA (seção 6). `Numero_Cotistas_Fundos_Investimento` é número de cotistas que são fundos, e não posição.

### 9.7 O que a amostra não confirma (item f)

- Se o FIAGRO-FIDC e o FIAGRO-FII aparecem também nos informes de FIDC e de FII: **pendente para a FU1.2**.
- A variante de cada FIAGRO: o informe não a traz; falta conferir o cadastro (`Tipo_Classe`, `Classificacao`, `Entidade_Investimento`) na FU1.2.
- Se o `CNPJ_Classe` do informe é o mesmo do cadastro e do CDA, e se as duas chaves repetidas são classes distintas ou erro de preenchimento: FU1.2.
- Como as reapresentações aparecem ao longo do tempo: um só mês e um só instantâneo; a amostra não mostra se a versão 1 desaparece quando chega a versão 2, nem reapresentações de outros meses.
- O significado jurídico dos Anexos Normativos citados em `Regra_Anexo`, e o prazo regulatório de entrega.
- Se `Prazo_Duracao` com 0, 99, 999, 1000, 9999 ou 99999 significa prazo indeterminado.
- O que é `FIIM` (o dicionário não descreve).
