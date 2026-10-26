# Fundos (FIDC, FIC-FIDC, FIAGRO): descoberta

Documento de descoberta da frente de Fundos, para responder às regras F-01 a F-06 de [regras-de-exibicao-pendentes.md](regras-de-exibicao-pendentes.md). A "maior dor" do [README](../README.md) para esta frente é acompanhar o mercado de FIDCs e comparar os FIDCs da casa com o mercado.

**Escopo.** Só descoberta. Não há código de coleta, migration, banco ou dado interno neste trabalho, e nenhuma migration recebe número aqui. Nada foi consultado no Fundos.NET. Das fontes da CVM foram lidas só páginas públicas de dados abertos e dicionários de dados (cerca de 60 KB no total); nenhum arquivo de dados foi baixado e nenhum arquivo baixado está neste repositório.

**Data da conferência:** 26/10/2026. Tudo que não foi conferido está marcado como **não confirmado** e reunido na seção 8.

## Resumo

1. **Quase tudo de F-03 está nos dados abertos da CVM, sem navegador:** cadastro, informe mensal de FIDC, informe mensal de FIAGRO, CDA e medidas. No informe de FIDC faltam **gestora, custodiante e índice de subordinação**.
2. **O coletor do Fundos.NET do Enrico serve para o catálogo e o download de documentos, não para dado estruturado de fundos.** Dá para reaproveitar a camada de sessão, a paginação, a preservação da linha original, o download com SHA-256 e o padrão dry-run/commit com backup. Não dá para reaproveitar o que localiza o ativo (página de certificados, securitizadora, ISIN, emissão, devedor).
3. **Gestora vem do cadastro do fundo, custodiante do cadastro da classe, administradora do cadastro e do informe.** Subordinação não é publicada: precisa ser **calculada** das cotas por classe/série e depende de saber qual classe é sênior ou subordinada (o rótulo no informe é livre).
4. **FIC-FIDC:** o informe só traz o total aplicado em cotas de FIDC. Quais FIDCs e quanto em cada um vêm do CDA.
5. **FIAGRO:** informe próprio (133 campos, um arquivo por mês). Como separar as variantes (FIDC, FII, FIP) **não está confirmado** em nenhuma página.
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
| FIAGRO: Documentos: Informe Mensal | https://dados.cvm.gov.br/dataset/fiagro-doc-inf_mensal | ZIP mensal `inf_mensal_fiagro_AAAAMM.zip` (2,8 KB a 73 KB), **semanal**; conjunto novo (14/10/2025). Dicionário em `meta_inf_mensal_fiagro.zip` | Anexo VI da "Instrução CVM nº 175/2022" (como a página escreve), entrega pelo Fundos.NET; 133 campos por classe, mais arquivo de subclasse (6 campos) |
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
| Gestora | `registro_fundo.Gestor` e `CPF_CNPJ_Gestor`; FIAGRO: `Nome_Gestor`, `CNPJ_Gestor` | **ausente no informe de FIDC** |
| Administradora | `registro_fundo.Administrador` e `CNPJ_Administrador`; FIDC: `tab_I.ADMIN`, `CNPJ_ADMIN`; FIAGRO: `Nome_Administrador`, `CNPJ_Administrador` | conferido |
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
3. O informe de FIDC **não tem versão nem data de entrega**. Uma reapresentação aparece como mesma competência com valor diferente entre coletas semanais e deve ir para `data_conflicts`. O informe do FIAGRO tem `Versao` e `Data_Entrega`.
4. A camada compartilhada (`src/pense_alm/shared/entities/enums.py`) não tem tipo de entidade para administradora ou custodiante (`EntityType`, linhas 6-20) nem relação "investe em" (`RelationshipType`, linhas 85-102). Existem `MANAGES`, `ADMINISTERED_BY`, `PROVIDES_SERVICES_TO` e `ASSIGNS_RECEIVABLES_TO`. Proposta: gestora (`ASSET_MANAGER`) e fundo (`FIDC`, `FIAGRO` ou `FUND`) viram entidades; administradora e custodiante usam `FINANCIAL_INSTITUTION` ou `COMPANY` até um ADR decidir; as posições ficam em `holdings` (F-06).

## 6. FIC-FIDC e FIAGRO

**FIC-FIDC**

- **Como identificar: não confirmado.** Os domínios dos campos de tipo e classificação estão vazios no dicionário. Sinais candidatos: classificação do cadastro, `TAB_I2H_VL_COTA_FIDC` frente ao ativo e cotistas "cotas de FIDC" em `tab_X_1_1` do fundo investido. Nunca identificar por "FIC" no nome.
- **Posições:** CDA, Bloco 2 (`CNPJ_FUNDO_CLASSE_COTA`, `NM_FUNDO_CLASSE_SUBCLASSE_COTA`). Para FIDC e FIAGRO as posições estão no `cda_fie` desde 08/11/2025, mas o dicionário dele não mostra a coluna do fundo investido (a conferir).
- **Exibição (F-04), proposta:** lista dos fundos investidos com valor e % do PL. Não somar métricas "por transparência" (dupla contagem), a menos que seja pedido e calculado à parte.

**FIAGRO**

- Mesmo cadastro dos demais fundos, mas informe próprio por classe (`CNPJ_Classe`), com `Codigo_ISIN`, `Mercado_Negociacao` e campos de investimentos em FIDC, FII, FIP, FIAGRO e FIF. São valores investidos, não a variante do próprio fundo.
- **Variante: não confirmado.** `Regra_Anexo`, `Classe_Unica`, `Classificacao_Autorregulada` e o cadastro são candidatos.
- O modelo aceita as duas escolhas de F-05 (variante como observação da classe). Páginas juntas ou separadas é decisão de exibição.
- **Risco:** o mesmo FIAGRO-FIDC pode aparecer nos dois informes. Chavear por CNPJ da classe e conferir numa amostra.

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
| **F-01** Fonte e coleta | CVM dados abertos como fonte primária de cadastro e informes; Fundos.NET para documentos (seções 1 e 2) | sonda do Fundos.NET; dono da frente; formato real dos CSV |
| **F-02** FIDCs da casa x mercado | Métricas disponíveis: rentabilidade (`tab_X_3`), PL, cotistas, inadimplência, segmento. Subordinação é derivada. **Spread não existe** no informe. Tabela da casa na seção 7 | definição de "da casa" e dos grupos de comparação; mapa de rótulos sênior/subordinada |
| **F-03** Ficha | Campo a campo na seção 4 | tratamento do CPF dos cedentes; domínios dos campos de tipo |
| **F-04** FIC-FIDC | Total no informe, posições no CDA (seção 6) | como identificar um FIC-FIDC; coluna do fundo investido no `cda_fie` |
| **F-05** FIAGRO | Informe próprio; modelo aceita as duas escolhas (seção 6) | como separar as variantes; sobreposição com os informes de FIDC e de FII |
| **F-06** Relacionamentos | `holdings` e `party_observations` (seção 5) | ADR para administradora e custodiante e para a relação "investe em" |

### Divergências entre dicionário e Novidades

- O dicionário do FIDC não tem `ID_SUBCLASSE` na `tab_X_1`, embora as Novidades de 02/02/2026 digam que o campo entrou.
- O dicionário do FIDC lista `CNPJ_FUNDO` nas tabelas X.1 a X.4 e X.6, embora as Novidades de 06/01/2025 digam que `CNPJ_FUNDO_CLASSE` o substituiu.
- Conferir no dado real antes de fixar o schema.

### Datas relevantes das Novidades

07/10/2024 (cadastro reorganizado em fundo, classe e subclasse); 06/01/2025 (`TP_FUNDO_CLASSE`); 14/10/2025 (FIAGRO); 08/11/2025 (CDA com FIDC e FIAGRO); 05/04/2026 (FIDC de 2019 a 2024 movido para `HIST/`); 13/08/2026 (`tab_VIII` incluída); 06/09/2026 (histórico de 2013 a 2024 atualizado).

### Não confirmado

- **(a)** A grade de FIDC e FIAGRO no Fundos.NET (página, `tipoFundo`, categorias de documento): não consultada.
- **(b)** O domínio dos campos `Tipo_Fundo`, `Tipo_Classe`, `Classificacao`, `Entidade_Investimento`, `Regra_Anexo`, `Classe_Unica` e `Classificacao_Autorregulada`: o dicionário os deixa vazios.
- **(c)** Se o FIAGRO-FIDC aparece também no informe de FIDC e o FIAGRO-FII no de FII (a página do FII, <https://dados.cvm.gov.br/dataset/fii-doc-inf_mensal>, não cita FIAGRO).
- **(d)** Cobertura de FIDC nos balancetes (`fie-doc-balancete`, `fi-doc-balancete`): a descrição das páginas está truncada.
- **(e)** Se o `cda_fie` identifica o fundo investido pelo CNPJ.
- **(f)** Codificação, separador e linhas dos CSV de FIDC e FIAGRO (os de CRI/CRA eram latin-1 e `;`).
- **(g)** Prazos regulatórios de entrega dos informes.
- **(h)** A ANBIMA como fonte.

### Próximos passos, sem código

1. Aprovar a sonda do Fundos.NET.
2. Autorizar a leitura de **uma amostra pequena** (um mês de FIAGRO, cerca de 73 KB) para fechar os domínios.
3. Decidir F-01 e o dono da frente.
4. Escrever o ADR de prioridade de fontes.
5. Decidir o tratamento do CPF dos cedentes.
