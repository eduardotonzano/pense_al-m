# Fundos (FIDC, FIC-FIDC, FIAGRO): descoberta

Documento de descoberta da frente de Fundos, para responder às regras F-01 a F-06 de [regras-de-exibicao-pendentes.md](regras-de-exibicao-pendentes.md). A "maior dor" do [README](../README.md) para esta frente é acompanhar o mercado de FIDCs e comparar os FIDCs da casa com o mercado.

**Escopo.** Só descoberta. Não há código de coleta, migration, banco ou dado interno neste trabalho, e nenhuma migration recebe número aqui. O Fundos.NET foi consultado só na sonda de 27/10/2026 (seção 11): 10 requisições GET de leitura à página pública e à grade, sem download de documento. Na primeira etapa (26/10/2026), das fontes da CVM foram lidas só páginas públicas de dados abertos e dicionários de dados (cerca de 60 KB no total). Em 27/10/2026 foram baixados seis arquivos da CVM: o informe mensal de FIAGRO de 09/2026 e o dicionário (seção 9); o cadastro de fundos, classes e subclasses, o informe mensal de FIDC de 09/2026 e os dois dicionários (seção 10). Eles ficam numa pasta local fora do repositório, e nenhum arquivo baixado está neste repositório. O informe de FII e o CDA não foram baixados. As respostas da sonda do Fundos.NET também ficam fora do repositório. As oito decisões da Fase 0 de Fundos, aprovadas pelo Gui em 27/10/2026, estão em `docs/decisoes-em-aberto.md` (parte "Fundos: decisões da Fase 0"); este documento remete a elas pelo número e mantém como pendente o que elas não decidem.

**Data da conferência:** 26/10/2026 (fontes e código) e 27/10/2026 (amostra de FIAGRO, seção 9; amostra do cadastro e do informe de FIDC, seção 10; sonda da grade do Fundos.NET, seção 11; texto sincronizado com as decisões da Fase 0 de Fundos). Tudo que não foi conferido está marcado como **não confirmado** e reunido na seção 8 e nas seções 9.7, 10.10 e 11.8.

## Resumo

1. **Quase tudo de F-03 está nos dados abertos da CVM, sem navegador:** cadastro, informe mensal de FIDC, informe mensal de FIAGRO, CDA e medidas. No informe de FIDC faltam **gestora, custodiante e índice de subordinação** (conferido no dado de 09/2026, seção 10).
2. **O coletor do Fundos.NET do Enrico serve para o catálogo e o download de documentos, não para dado estruturado de fundos.** Dá para reaproveitar a camada de sessão, a paginação, a preservação da linha original, o download com SHA-256 e o padrão dry-run/commit com backup. Não dá para reaproveitar o que localiza o ativo (página de certificados, securitizadora, ISIN, emissão, devedor).
3. **Gestora vem do cadastro do fundo (uma linha por gestor), custodiante do cadastro da classe, administradora do cadastro e do informe.** Subordinação não é publicada: precisa ser **calculada** das cotas por série (`tab_X_2`). O rótulo da série não tem domínio no dicionário, mas segue um molde fixo (`Subclasse Senior`, `Subclasse Subordinada Subordinada`, `Subclasse Subordinada Mezanino`) que, em 09/2026, classifica todas as séries (seção 10.6).
4. **FIC-FIDC:** nenhum campo do cadastro ou do informe marca um FIC-FIDC. O sinal que existe é a parcela do ativo em cotas de FIDC (`TAB_I2H_VL_COTA_FIDC`), conferida na seção 10.4. O corte foi decidido pelo Gui em 27/10/2026: 95% ou mais classifica como FIC-FIDC, e de 67% a menos de 95% vai para revisão manual (decisão 6 de `docs/decisoes-em-aberto.md`). O informe só traz o total aplicado em cotas de FIDC; quais FIDCs e quanto em cada um vêm do CDA.
5. **FIAGRO:** informe próprio (133 campos por classe e 6 por subclasse; o ZIP mensal traz dois CSV). A variante (FIDC, FII, FIP) **não sai do informe** (seção 9: `Regra_Anexo` e `Classificacao_Autorregulada` são texto livre e pouco preenchidos) **nem do cadastro** (seção 10.5: `Tipo_Classe` só diz FIAGRO, e `Classificacao` e `Entidade_Investimento` vêm vazios). Em 09/2026, só 1 das 310 classes do informe de FIAGRO também aparece no informe de FIDC.
6. **"FIDCs da casa":** lista manual por CNPJ da classe, em tabela interna fora do Git, decidido pelo Gui em 27/10/2026 (decisões 2 e 4 de `docs/decisoes-em-aberto.md`). A criação da pasta interna está pendente (seção 7).
7. **CNPJ e dados pessoais:** o informe de FIDC traz o CNPJ com máscara e o cadastro, sem; o casamento só fecha depois de normalizar (4.444 de 4.444), e o cadastro repete o CNPJ entre registros (seção 10.9). Há CPF no cadastro (225 gestores e 8 auditores pessoa física) e nos cedentes do informe (120 valores), e `Diretor` é nome de pessoa natural (seção 10.8). Decidido pelo Gui em 27/10/2026: o CPF nunca é gravado, só CNPJ, e os campos de pessoa natural e de contato não são carregados (decisão 3 de `docs/decisoes-em-aberto.md`). Se a regra vale também para o arquivo original da CVM continua **pendente**.
8. **Fundos.NET (sonda de 27/10/2026, seção 11):** a grade filtra por `tipoFundo` (FIDC = `2`, FIAGRO = `11`). FIC-FIDC não tem código próprio, e o FIAGRO não é separado por variante. Há 17 categorias de documento para FIDC e 18 para FIAGRO. A linha da grade tem 37 campos e **não traz o CNPJ** do fundo nem da classe, só o nome em texto. O link do documento sai do `id` da linha (`downloadDocumento?id=<id>`). Nas 4 semanas até 27/10/2026, a grade informa 8.930 documentos de FIDC e 891 de FIAGRO.

## 1. Coletor do Fundos.NET do Enrico: o que reaproveitar

Código lido: `Enrico/cri_cra_platform/src/credit_assets/` (linhas conforme o commit `250112f`). A leitura foi só do código e dos relatórios já versionados; o Fundos.NET não foi acessado nesta etapa (a sonda de 27/10/2026 está na seção 11).

| Peça | Onde | Para fundos |
|---|---|---|
| Abrir o Edge com queda para o Chromium | `collectors/fundosnet_collector.py:505` (`_launch_browser`) | reaproveita |
| GET de JSON com `X-Requested-With`, 3 tentativas (0/2/5 s); resposta HTML vira "sessão inválida" | `:627` `_request_json`, `:664` `_page_fetch_json`, `:689` `_classify_html` | reaproveita; o `Referer` está fixo na página de certificados (`:641`); `_classify_html` marca a página normal como proteção (seção 11.7) |
| Linhas da grade e paginação (`start`/`length`, `recordsFiltered`) | `:597` `_fetch_documentos`, `:717` `_extract_rows`, `:730` `_grid_text` | reaproveita; os filtros mudam; a página envia `d`/`s`/`l`, e não `draw`/`start`/`length` (seção 11.5) |
| Guardar a linha original (`source_row_json`) e os campos oficiais da grade | `:738` `_to_document` | reaproveita a ideia; no schema de fundos vira `raw_records` |
| Diagnóstico sem cookie nem token | `:708` `_write_diagnostics` (grava em `reports/`, caminho relativo) | reaproveita, com pasta fora do Git |
| Download pela ação oficial "Download do Documento" (XML/PDF), SHA-256, teto de 25 MB | `services/document_download_service.py:260` `FundosNetBrowserDownloader`, `:60`; `download_diagnostics.py:70-131` | reaproveita; o relatório `reports/cafe_brasil_download_action_diagnostic.md` mostra `downloadDocumento?id=` devolvendo XML |
| Versões de arquivo por documento | `repositories/document_version_repository.py` | reaproveita o desenho |
| Migrations numeradas, backup, `apply_migration`, `--dry-run`/`--commit` | `database/migrations.py`, `database/backup.py`, `scripts/apply_migration.py` | reaproveita, em banco separado de fundos |
| Página `abrirGerenciadorDocumentosCertificadosCVM` e filtros `paginaCertificados`/`paraCerts` | `:89`, `:524-568` | **não serve** |
| Tipo de fundo `5` = CRI e `6` = CRA | `utils/fundosnet_normalization.py:29-35` | **não serve**: na página geral, FIDC é `2` e FIAGRO é `11` (seção 11.3) |
| Escolher o "administrador" pela securitizadora, com alias fixo | `:186`, `:512-548` | **não serve** |
| Casar o certificado por ISIN, emissão e devedor | `:245`, `:550-595`, `:131`, `:385` | **não serve**: a chave de fundo é o CNPJ |
| `Asset`/`assets` e `documents.category` com 9 categorias de CRI/CRA, pastas por CETIP | `models/`, `schema.sql:41-51`, `document_download_service.py:41-46` | **não serve** como está |

**Recomendação.** Usar os dados abertos da CVM como fonte primária de cadastro e informes (sem Playwright; basta `requests`, que já está nas dependências). O Fundos.NET entra para o **catálogo e o download de documentos** (regulamento, demonstrações, fatos relevantes) e para conferência. A **sonda** da grade do Fundos.NET para fundos (página, `tipoFundo`, filtros) foi feita em 27/10/2026, com aprovação (seção 11).

## 2. Fontes oficiais

Todas são páginas do portal de dados abertos da CVM, conferidas em 26/10/2026; nessa data foram lidas só as páginas e os dicionários. Em 27/10/2026 foram baixadas amostras do informe de FIAGRO (seção 9), do cadastro e do informe de FIDC (seção 10); o CDA, as medidas e o informe de FII não foram baixados.

| Fonte | Página | Formato e periodicidade | Conteúdo |
|---|---|---|---|
| Fundos de Investimento: Informação Cadastral | https://dados.cvm.gov.br/dataset/fi-cad | ZIP/CSV/TXT; **diária** (terça a sábado, 08:00). `registro_fundo_classe.zip` (6,9 MB; três CSV, 45 MB descomprimidos), `cad_fi.csv` (17 MB, só fundos não adaptados à Res. 175), `cad_fi_hist.zip` (18 MB, ICVM 555). Dicionário em `meta_registro_fundo_classe.zip` | Fundo (21 campos: gestor, CPF/CNPJ do gestor, administrador, CNPJ do administrador, tipo, situação, PL, data de adaptação à Res. 175); classe (30: custodiante, CNPJ do custodiante, controlador, auditor, tipo da classe, classificação, ANBIMA, público-alvo, exclusivo, entidade de investimento); subclasse (14). Contagens conferidas no dado (seção 10.2) |
| FIDC: Documentos: Informe Mensal | https://dados.cvm.gov.br/dataset/fidc-doc-inf_mensal | ZIP mensal `inf_mensal_fidc_AAAAMM.zip` (cerca de 3 MB cada; 3,6 MB e 18 CSV em 09/2026, seção 10), **semanal** (últimos 12 meses); histórico em `HIST/` por ano, desde 2013. Dicionário em `meta_inf_mensal_fidc_txt.zip` (16 KB, 18 tabelas) | Anexo A da ICVM 489/11, segundo a página (que não cita a Res. 175, embora o dicionário já traga campos dela). Tabelas I a X; ver seção 3 |
| FIAGRO: Documentos: Informe Mensal | https://dados.cvm.gov.br/dataset/fiagro-doc-inf_mensal | ZIP mensal `inf_mensal_fiagro_AAAAMM.zip` (2,8 KB a 73 KB; dois CSV por ZIP, classe e subclasse), **semanal**; conjunto novo (14/10/2025). Dicionário em `meta_inf_mensal_fiagro.zip` | Anexo VI da "Instrução CVM nº 175/2022" (como a página escreve), entrega pelo Fundos.NET; 133 campos por classe, mais arquivo de subclasse (6 campos), conferidos na amostra de 09/2026 (seção 9) |
| Fundos de Investimento: CDA | https://dados.cvm.gov.br/dataset/fi-doc-cda | ZIP mensal `cda_fi_AAAAMM.zip`; M-1 a M-3 atualizados de terça a sábado, M-4 a M-12 às segundas; posições confidenciais só consolidadas. Dicionário em `meta_cda_fi_txt.zip` (10 KB) | Carteira por fundo. Bloco 2 = cotas de fundos (`CNPJ_FUNDO_CLASSE_COTA`, `QT_POS_FINAL`, `VL_MERC_POS_FINAL`). FIDC e FIAGRO entraram em 08/11/2025 (`cda_fie_AAAAMM.csv` desde 15/11/2025) |
| Fundos Estruturados: Medidas | https://dados.cvm.gov.br/dataset/fie-medidas | CSV mensal `medidas_mes_fie_AAAAMM.csv`, **semanal** (12 meses; histórico desde 01/2017) | PL e número de cotistas de FIP, FIDC e FII "etc." (6 campos); FIAGRO **não é citado** |
| Novidades do portal | https://dados.cvm.gov.br/pages/novidades | HTML | Registro das mudanças nos conjuntos (ver seção 8) |

Todas as páginas declaram a licença **ODbL**. Decidido pelo Gui em 27/10/2026: o banco de Fundos é tratado como interno por enquanto (decisão 5 de `docs/decisoes-em-aberto.md`). Pelo ajuste de redação registrado por Eduardo na mesma data, a conferência da licença não bloqueia nenhuma etapa do uso interno; só vale antes de publicar o banco ou dado derivado dele fora da casa (obrigações a conferir: citar a fonte e manter a mesma licença).

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

**O informe não tem:** versão, data de entrega, rating, spread nem índice de subordinação. Também não tem gestora nem custodiante (nenhuma ocorrência de "gestor" ou "custod" nas 18 tabelas do dicionário). **Conferido no dado de 09/2026 (seção 10):** as 18 tabelas estão no ZIP, com 461 campos; o único campo de data é `DT_COMPTC`, e nenhum cabeçalho tem gestor, custodiante, versão ou entrega. Nas tabelas X.1 a X.4 e X.6, o dado traz `TP_FUNDO_CLASSE` e `CNPJ_FUNDO_CLASSE`, e não o `CNPJ_FUNDO` do dicionário.

## 4. Campos da ficha (F-03) e de onde vêm

| Campo | Fonte e campo | Situação |
|---|---|---|
| Identificação, tipo, situação | `registro_fundo` (`CNPJ_Fundo`, `Tipo_Fundo`, `Situacao`); `registro_classe` (`CNPJ_Classe`, `Tipo_Classe`, `Classificacao`) | domínios conferidos no dado (seção 10.3); o dicionário não os traz. `Classificacao` vem vazia em FIDC e FIAGRO |
| Gestora | `registro_fundo.Gestor` e `CPF_CNPJ_Gestor` (com `Tipo_Pessoa_Gestor`); FIAGRO: `Nome_Gestor`, `CNPJ_Gestor` | **ausente no informe de FIDC** (conferido no dado); o cadastro tem uma linha por gestor, e 225 gestores são pessoa física (seção 10.8); no de FIAGRO, nomes conferidos na amostra (seção 9) |
| Administradora | `registro_fundo.Administrador` e `CNPJ_Administrador`; FIDC: `tab_I.ADMIN`, `CNPJ_ADMIN`; FIAGRO: `Nome_Administrador`, `CNPJ_Administrador` | conferido; no FIDC, `CNPJ_ADMIN` (com máscara) igual ao do cadastro em 4.423 das 4.444 classes (seção 10.8); no de FIAGRO, nomes conferidos na amostra (seção 9) |
| Custodiante | `registro_classe.Custodiante` e `CNPJ_Custodiante` | só no cadastro da classe; preenchido em 5.409 das 5.445 classes de FIDC (seção 10.8) |
| Cotas | FIDC: `tab_X_2` (valor e quantidade), `tab_X_3` (rentabilidade), `tab_X_1` e `tab_X_1_1` (cotistas), `tab_X_4`. FIAGRO: `Valor_Patrimonial_Cotas`, `Cotas_Emitidas`, `Rentabilidade_*`, `Dividend_Yield_Mes`, `Numero_Cotistas*`, subclasse | conferido |
| Subordinação | **não existe pronta**; calcular a partir de `tab_X_2` por classe/série | o rótulo `TAB_X_CLASSE_SERIE` não tem domínio, mas segue um molde que classifica todas as séries de 09/2026; quantidade × valor fecha com o PL em 4.154 das 4.444 classes (seção 10.6) |
| Carteira de recebíveis | `tab_I` (I.2.a e I.2.b), `tab_II` (segmento), `tab_V` e `tab_VI`, `tab_VII`, `tab_IX`, `tab_X`. FIAGRO: `A_Vencer_*`, `Vencidos_*`, `Direitos_Creditorios_Agronegocio` | conferido |
| Cedentes | `tab_I.TAB_I2A12_*` e `TAB_I2B12_*` (CPF/CNPJ e %), só os 9 maiores; `tab_VII.B` | **o CPF aparece** no dado (120 valores de 11 dígitos em 69 classes, seção 10.8); o CPF nunca é gravado, só o CNPJ, decidido pelo Gui em 27/10/2026 (decisão 3 de `docs/decisoes-em-aberto.md`); em aberto: como aparece o cedente pessoa física, sem identificador, e os 7 valores ambíguos (seção 10.8) |
| Cotas investidas (FIC-FIDC) | total em `tab_I.TAB_I2H_VL_COTA_FIDC` (`TAB_I2I_VL_COTA_FIDC_NP` vem vazio e `TAB_I2_COTA_FIDC` é provisão); posições no CDA, Bloco 2 | o detalhe de cada FIDC investido só existe no CDA |
| Spread, rating das cotas | não existem no informe | ficam "ausente" (regra de ausente com razão) |

## 5. Schema proposto

Mesmo esqueleto de `Eduardo/debenture-replica/migrations/001_initial_schema.sql` (sem numeração): `sources`, `collection_runs`, `raw_records`, `observations` (valor texto, numérico, data ou booleano; `observed_at`, `collected_at`, `confidence`, `checksum` único), `data_conflicts`, `audit_log` e a view `current_observations`. Muda o que identifica o assunto da observação:

- `funds` (no lugar de `issuers`): CNPJ de 14 dígitos único, denominação, `ID_Registro_Fundo`. Na origem o CNPJ não é único: o cadastro repete `CNPJ_Fundo` entre registros (8.165 CNPJs; por exemplo, o FI cancelado e o FIF que o sucedeu) e repete `ID_Registro_Fundo` quando o fundo tem mais de um gestor (seção 10.9). A unicidade vale para a entidade, não para a linha de origem; qual registro vale é regra do adaptador, a decidir.
- `fund_classes` (no lugar de `debentures`): fundo, CNPJ da classe (RCVM 175), `ID_Registro_Classe`. As observações apontam para a classe. O CNPJ da classe é o do fundo em 36.868 das 37.018 classes e se repete em 13 casos; `ID_Registro_Classe` se repete quando há mais de um custodiante ou controlador (seção 10.9).
- `quota_series`: classe/série/subclasse **com o rótulo exatamente como a fonte traz**, `ID_Subclasse` quando houver; `observations.quota_series_id` é anulável. O mesmo rótulo vem com espaços e `|` diferentes na `tab_X_1` e na `tab_X_2`: casar pela forma normalizada e guardar a original (seção 10.6).
- `party_observations`: papel (gestor, administrador, custodiante, controlador, auditor, cedente), CNPJ (nunca CPF, decidido pelo Gui em 27/10/2026: decisão 3 de `docs/decisoes-em-aberto.md`), nome, posição, % de participação, fonte, data, `raw_record_id`, `checksum`. Gestor, auditor e cedente podem ser pessoa física (seção 10.8): sem CPF, esses papéis ficam sem identificador, e como eles aparecem continua em aberto (decisão 3).
- `holdings`: fundo detentor, CNPJ e nome do fundo investido, data da posição, quantidade, valor de mercado, fonte, `raw_record_id`, `checksum`. É posição no tempo, não relação de identidade.
- `quota_class_map`: rótulo da série para sênior, mezanino ou subordinada, **curado e revisado** pela equipe a partir do padrão do rótulo, decidido pelo Gui em 27/10/2026 (decisão 8 de `docs/decisoes-em-aberto.md`); onde o rótulo não diz o subtipo, o subtipo sai "ausente", sem estimativa. Sem mapa, a subordinação sai "ausente (rótulo não mapeado)". Em 09/2026 o início do rótulo resolve todas as séries (seção 10.6); o mapa continua necessário para mudanças do molde, e a ordem entre duas subordinadas da mesma classe, que o rótulo não diz, continua em aberto.

`field_name` recebe `tabela.coluna` da CVM, sem renomear; a escolha do que exibir é F-03.

**Diferenças em relação às debêntures, a decidir:**

1. `raw_records` guarda um manifesto (nome, tamanho, SHA-256, linhas) e o arquivo fica em pasta fora do Git, porque o ZIP de FIDC tem cerca de 3 MB e muda toda semana, e o do cadastro tem 6,9 MB e muda de terça a sábado. O arquivo original da CVM traz CPF (seção 10.8). Se a regra do CPF (decisão 3 de `docs/decisoes-em-aberto.md`) vale também para ele continua **pendente**, a confirmar com o Gui; a proposta, ainda não aprovada, é guardar só o manifesto, nunca o conteúdo, com os arquivos originais em pasta de acesso restrito.
2. A escala de `priority` precisa de um ADR antes do uso. Nas debêntures a view ordena `priority DESC` e a ANBIMA (300) passaria à frente da CVM (200).
3. O informe de FIDC **não tem versão nem data de entrega**. Uma reapresentação aparece como mesma competência com valor diferente entre coletas semanais e deve ir para `data_conflicts`. Confirmado no dado de 09/2026: nenhum campo de versão ou entrega, uma só `DT_COMPTC` e nenhuma chave repetida nas 18 tabelas (seção 10.7). O informe do FIAGRO tem `Versao` e `Data_Entrega` (confirmado na amostra de 09/2026), mas, no arquivo da amostra, a única linha com `Versao` 2 não vem acompanhada da versão 1, e a chave (`CNPJ_Classe`, `Data_Referencia`) se repetiu em 2 casos que não são reapresentações (seção 9). O schema não deve pressupor histórico de versões dentro do arquivo nem unicidade dessa chave.
4. A camada compartilhada (`src/pense_alm/shared/entities/enums.py`) não tem tipo de entidade para administradora ou custodiante (`EntityType`, linhas 6-20) nem relação "investe em" (`RelationshipType`, linhas 85-102). Existem `MANAGES`, `ADMINISTERED_BY`, `PROVIDES_SERVICES_TO` e `ASSIGNS_RECEIVABLES_TO`. Proposta: gestora (`ASSET_MANAGER`) e fundo (`FIDC`, `FIAGRO` ou `FUND`) viram entidades; administradora e custodiante usam `FINANCIAL_INSTITUTION` ou `COMPANY` até um ADR decidir; as posições ficam em `holdings` (F-06).

## 6. FIC-FIDC e FIAGRO

**FIC-FIDC**

- **Como identificar (conferido em 09/2026, seção 10.4): nenhum campo marca um FIC-FIDC.** No cadastro ele é `Tipo_Fundo` FIDC, e `Classe_Cotas`, `Classificacao` e `Classificacao_Anbima` vêm vazios nas classes de FIDC. No informe, `TP_FUNDO_CLASSE` só separa fundo e classe. O sinal que resta é a parcela do ativo em cotas de FIDC (`TAB_I2H_VL_COTA_FIDC` sobre `TAB_I_VL_ATIVO`): 892 classes com 67% ou mais e 518 com 95% ou mais. Corte decidido pelo Gui em 27/10/2026: 95% ou mais classifica como FIC-FIDC, e de 67% a menos de 95% vai para revisão manual (decisão 6 de `docs/decisoes-em-aberto.md`). É uma regra de corte, não um dado da CVM; a regra da norma não foi verificada. Os cotistas "cotas de FIDC" da `tab_X_1_1` (538 classes) mostram o lado do fundo investido. Nunca identificar por "FIC" no nome.
- **Posições:** CDA, Bloco 2 (`CNPJ_FUNDO_CLASSE_COTA`, `NM_FUNDO_CLASSE_SUBCLASSE_COTA`). Para FIDC e FIAGRO as posições estão no `cda_fie` desde 08/11/2025, mas o dicionário dele não mostra a coluna do fundo investido (a conferir).
- **Exibição (F-04), proposta:** lista dos fundos investidos com valor e % do PL. Não somar métricas "por transparência" (dupla contagem), a menos que seja pedido e calculado à parte.

**FIAGRO**

- Mesmo cadastro dos demais fundos, mas informe próprio por classe (`CNPJ_Classe`), com `Codigo_ISIN`, `Mercado_Negociacao` e valores investidos em cotas de fundos: total em `Cotas_Fundos_Investimento` e abertura em `FIF`, `FIDC`, `FII`, `FIP`, `FIIM` e `FIAGRO` (o dicionário não descreve `FIIM`). São valores, sem identificar o fundo investido (isso vem do CDA), e não a variante do próprio fundo.
- **Variante: não sai do informe de FIAGRO nem do cadastro (confirmado nas amostras de 09/2026, seções 9 e 10.5).** `Regra_Anexo` é texto livre, preenchido em 25% das linhas, e cita Anexo Normativo I, II ou III; `Classificacao_Autorregulada` é texto livre preenchido em 9%, com conteúdo misto; `Classe_Unica` é S/N e não indica variante. No cadastro, `Tipo_Classe` só diz "Classes de Cotas de Fundos FIAGRO", e `Classificacao` e `Entidade_Investimento` vêm vazios. O histórico de registro do CNPJ (um registro anterior como FIDC, FII ou FIP) é pista para 166 das 310 classes, sem confirmar. Fontes que restam: o regulamento (Fundos.NET) e a ANBIMA, não consultados. A grade do Fundos.NET tem um só código para FIAGRO e não separa a variante (seção 11.3). Decidido pelo Gui em 27/10/2026: até haver uma segunda fonte confirmada, aparece "variante não informada", e a variante nunca é deduzida pelo nome (decisão 7 de `docs/decisoes-em-aberto.md`).
- O modelo aceita as duas escolhas de F-05 (variante como observação da classe). Páginas juntas ou separadas é decisão de exibição.
- **Subclasses:** o arquivo de subclasse traz `Nome_Subclasse`, `Numero_Cotas` e `Valor_Patrimonial_Cota`, mas o nome é ordinal (`Subclasse 1 (ou classe única)`, `Subclasse 2`, ...) e não diz sênior ou subordinada. A subordinação de um FIAGRO-FIDC não sai do informe, como no FIDC.
- **Risco:** o mesmo FIAGRO pode aparecer em dois informes. Em 09/2026, 1 das 310 classes do informe de FIAGRO aparece também no informe de FIDC (seção 10.5). Chavear por CNPJ da classe, sem máscara. A conferência com o informe de FII segue **pendente** (não lido).

## 7. FIDCs da casa

- "Fundo da casa" é definido por uma lista manual, por CNPJ da classe, mantida nesta tabela, decidido pelo Gui em 27/10/2026 (decisão 2 de `docs/decisoes-em-aberto.md`). A tabela é **privada**, fora do repositório e do banco versionados. Local: **pasta interna, fora dos dois clones Git, com acesso restrito à equipe**, decidido pelo Gui em 27/10/2026 (decisão 4 de `docs/decisoes-em-aberto.md`). A criação da pasta, que cabe ao Eduardo com a TI, está pendente.
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
| **F-01** Fonte e coleta | CVM dados abertos como fonte primária de cadastro e informes; Fundos.NET para documentos (seções 1 e 2); formato real dos CSV de FIAGRO, do cadastro e de FIDC conferido (seções 9 e 10); grade do Fundos.NET conferida pela sonda (seção 11); dono da frente decidido pelo Gui em 27/10/2026 (decisão 1 de `docs/decisoes-em-aberto.md`) | normalização do CNPJ (com máscara no informe de FIDC); ligação entre documento do Fundos.NET e classe, sem CNPJ na linha da grade (seção 11.5); nome da pasta do módulo, na FU2.1 (decisão 1) |
| **F-02** FIDCs da casa x mercado | Métricas disponíveis: rentabilidade (`tab_X_3`), PL, cotistas, inadimplência, segmento. Subordinação é derivada; o rótulo classifica todas as séries de 09/2026 (seção 10.6). **Spread não existe** no informe. Tabela da casa na seção 7; decidido pelo Gui em 27/10/2026: "da casa" é lista manual por CNPJ da classe, em tabela interna fora do Git (decisões 2 e 4), e o mapa de rótulos é curado e revisado pela equipe a partir do padrão (decisão 8) | métricas comparadas, grupos de comparação, valores de `relacao_com_a_casa` e forma de exibir (decisão 2); criação da pasta interna, pelo Eduardo com a TI (decisão 4); ordem entre duas subordinadas da mesma classe (decisão 8) |
| **F-03** Ficha | Campo a campo na seção 4; domínios dos campos de tipo conferidos (seção 10.3); decidido pelo Gui em 27/10/2026: o CPF nunca é gravado, só CNPJ, e `Diretor` e os campos de contato não são carregados (decisão 3); séries pelo padrão do rótulo, com o subtipo não dito como "ausente" (decisão 8) | alcance da regra do CPF para o arquivo original da CVM (**pendente**, a confirmar com o Gui); como aparece o gestor, auditor ou cedente pessoa física, sem identificador, e os 7 valores de cedente ambíguos (decisão 3, seção 10.8) |
| **F-04** FIC-FIDC | Total no informe, posições no CDA (seção 6); nenhum campo marca o FIC-FIDC, e o sinal é a parcela do ativo em cotas de FIDC (seção 10.4); corte decidido pelo Gui em 27/10/2026: 95% ou mais é FIC-FIDC, de 67% a menos de 95% vai para revisão manual (decisão 6) | forma de exibir as cotas de FIDC investidas (decisão 6); lista dos FIDCs investidos e coluna do fundo investido no `cda_fie` (CDA não lido) |
| **F-05** FIAGRO | Informe próprio; modelo aceita as duas escolhas (seção 6); a variante não sai do informe (seção 9) nem do cadastro (seção 10.5); 1 classe aparece também no informe de FIDC; decidido pelo Gui em 27/10/2026: "variante não informada" até haver segunda fonte confirmada, nunca pelo nome (decisão 7) | segunda fonte da variante (regulamento ou ANBIMA); mesma página ou páginas separadas (decisão 7); sobreposição com o informe de FII |
| **F-06** Relacionamentos | `holdings` e `party_observations` (seção 5) | ADR para administradora e custodiante e para a relação "investe em" |

### Divergências entre dicionário e Novidades

- O dicionário do FIDC não tem `ID_SUBCLASSE` na `tab_X_1`, embora as Novidades de 02/02/2026 digam que o campo entrou.
- O dicionário do FIDC lista `CNPJ_FUNDO` nas tabelas X.1 a X.4 e X.6, embora as Novidades de 06/01/2025 digam que `CNPJ_FUNDO_CLASSE` o substituiu.
- **Conferido no dado de 09/2026 (seção 10.2):** o dado segue as Novidades. A `tab_X_1` tem `ID_SUBCLASSE`, e as tabelas X.1 a X.4 e X.6 trazem `TP_FUNDO_CLASSE` e `CNPJ_FUNDO_CLASSE`, sem `CNPJ_FUNDO`. O dicionário baixado em 27/10/2026 continua desatualizado nesses cinco arquivos.

### Datas relevantes das Novidades

07/10/2024 (cadastro reorganizado em fundo, classe e subclasse); 06/01/2025 (`TP_FUNDO_CLASSE`); 14/10/2025 (FIAGRO); 08/11/2025 (CDA com FIDC e FIAGRO); 05/04/2026 (FIDC de 2019 a 2024 movido para `HIST/`); 13/08/2026 (`tab_VIII` incluída); 06/09/2026 (histórico de 2013 a 2024 atualizado).

### Não confirmado

- **(a)** A grade de FIDC e FIAGRO no Fundos.NET (página, `tipoFundo`, categorias de documento). **Confirmado em 27/10/2026 pela sonda** (seção 11): página `abrirGerenciadorDocumentosCVM`, `tipoFundo` `2` (FIDC) e `11` (FIAGRO), sem código para FIC-FIDC nem para variante de FIAGRO; 17 categorias para FIDC e 18 para FIAGRO; 37 campos por linha, sem CNPJ; link pelo `id` da linha.
- **(b)** O domínio dos campos `Tipo_Fundo`, `Tipo_Classe`, `Classificacao` e `Entidade_Investimento` (do cadastro). **Confirmado em 27/10/2026 no dado** (seção 10.3): o dicionário os deixa vazios, e o dado traz 19 valores de `Tipo_Fundo`, 10 de `Tipo_Classe` ("Classes de Cotas de Fundos" seguido do tipo), 5 de `Classificacao` (vazia em quase todas as classes de FIDC e FIAGRO) e S/N em `Entidade_Investimento` (vazio em FIDC). **Confirmado também para o informe de FIAGRO:** `Regra_Anexo`, `Classe_Unica` e `Classificacao_Autorregulada` (seção 9). `Regra_Anexo` e `Classificacao_Autorregulada` são texto livre, não domínios controlados.
- **(c)** Se o FIAGRO-FIDC aparece também no informe de FIDC e o FIAGRO-FII no de FII (a página do FII, <https://dados.cvm.gov.br/dataset/fii-doc-inf_mensal>, não cita FIAGRO). **Confirmado para o FIDC em 27/10/2026** (seção 10.5): 1 das 310 classes do informe de FIAGRO de 09/2026 aparece no informe de FIDC do mesmo mês. Para o FII segue **não confirmado**: o informe de FII não foi lido.
- **(d)** Cobertura de FIDC nos balancetes (`fie-doc-balancete`, `fi-doc-balancete`): a descrição das páginas está truncada.
- **(e)** Se o `cda_fie` identifica o fundo investido pelo CNPJ.
- **(f)** Codificação, separador e linhas dos CSV de FIDC (os de CRI/CRA eram latin-1 e `;`). **Confirmado em 27/10/2026 para o FIDC e o cadastro** (seção 10.2): `;`, cp1252, CRLF, cabeçalho na primeira linha; 18 tabelas de FIDC com 4.444 classes em 09/2026; cadastro com 90.859 linhas de fundo, 37.018 de classe e 11.518 de subclasse. **Confirmado para o FIAGRO:** `;`, cp1252, CRLF, cabeçalho na primeira linha, 312 linhas de classe e 697 de subclasse (seção 9).
- **(g)** Prazos regulatórios de entrega dos informes. A amostra de FIAGRO mostra entregas de 05/10 a 15/10/2026 para a competência 09/2026, com 226 das 312 linhas em 14 e 15/10; o prazo da norma segue **não confirmado**. O informe de FIDC não tem data de entrega (seção 10.7).
- **(h)** A ANBIMA como fonte.
- **(i)** A variante de cada FIAGRO (FIDC, FII, FIP): não está no informe de FIAGRO nem no cadastro (seção 10.5), nem no filtro da grade do Fundos.NET (seção 11.3). Fontes candidatas: o regulamento (Fundos.NET) e a ANBIMA, não consultados.

### Próximos passos, sem código

1. **Feito em 27/10/2026:** a sonda da grade do Fundos.NET (seção 11). Fica para o desenho do coletor de documentos: como ligar documento e classe sem CNPJ na linha, e o que a sonda não confirma (seção 11.8).
2. **Feito em 27/10/2026** para o FIAGRO (seção 9), o cadastro e o informe de FIDC (seção 10). Falta a mesma leitura de uma amostra do CDA (`cda_fie`) e do informe de FII, que precisa de nova autorização de rede.
3. **Feito em 27/10/2026:** o dono da frente (F-01), decidido pelo Gui (decisão 1 de `docs/decisoes-em-aberto.md`). Falta o nome da pasta do módulo, na FU2.1; em F-01 continua em aberto a normalização do CNPJ (seção 8).
4. Escrever o ADR de prioridade de fontes.
5. **Feito em 27/10/2026:** o tratamento do CPF e do nome do `Diretor`, decidido pelo Gui (decisão 3 de `docs/decisoes-em-aberto.md`). Continua **pendente** se a regra vale para o arquivo original da CVM, a confirmar com o Gui; continuam em aberto como aparece o papel de pessoa física, sem identificador, e os 7 valores de cedente ambíguos (seção 10.8).
6. **Feito em 27/10/2026:** o corte do sinal de FIC-FIDC (decisão 6) e o tratamento da variante do FIAGRO ("variante não informada", decisão 7), decididos pelo Gui (`docs/decisoes-em-aberto.md`). Falta a segunda fonte da variante (regulamento ou ANBIMA, não consultados).
7. Criar a pasta interna dos fundos da casa, pelo Eduardo com a TI (pendência da decisão 4 de `docs/decisoes-em-aberto.md`).

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
- **Dados de contato:** `Email_Administrador` (311 preenchidos, 29 distintos, 308 com padrão de e-mail), `Servico_Atendimento_Cotista` (texto livre, 311 preenchidos, 107 com e-mail e 158 com padrão de telefone), `Site` (296 preenchidos, 6 com e-mail) e `Entidade_Administradora` (8 linhas com telefone). São contatos da administradora ou da classe; a amostra não permite dizer se algum é de pessoa natural. Decidido pelo Gui em 27/10/2026: os campos de contato `Email_Administrador`, `Site` e `Servico_Atendimento_Cotista` não são carregados (decisão 3 de `docs/decisoes-em-aberto.md`). `Entidade_Administradora`, que traz telefone em 8 linhas, não é citada na decisão: para ela continua a proposta de não gravar nem exibir sem decisão.
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

Os itens acima que dependiam da FU1.2 estão respondidos na seção 10, menos a sobreposição com o informe de FII e a comparação com o CDA, que não foram lidos.

## 10. Amostra do cadastro e do informe de FIDC (27/10/2026)

Leitura do cadastro de fundos, classes e subclasses, de um mês do informe mensal de FIDC e dos dois dicionários, para fechar os pontos que as seções 6, 8 e 9 deixavam para a FU1.2. Só agregados: esta seção não traz linhas de fundos, CNPJs, ISINs nem nomes. Os arquivos ficam numa pasta local fora do repositório e foram lidos em memória, sem extrair nada em disco, com a biblioteca padrão do Python.

### 10.1 Origem e integridade

As URLs saíram das páginas dos conjuntos, lidas com um GET cada às 13:42:56 UTC de 27/10/2026. A página <https://dados.cvm.gov.br/dataset/fi-cad> lista seis recursos: dados e dicionário do cadastro, de `cad_fi.csv` e de `cad_fi_hist.zip`. Só os dois do cadastro foram baixados. A página <https://dados.cvm.gov.br/dataset/fidc-doc-inf_mensal> lista o dicionário e os informes de 10/2025 a 09/2026. Não havia arquivo de 10/2026, então 09/2026 é o último mês completo. Foi feita uma requisição GET a cada arquivo, por HTTPS, com verificação de TLS e sem redirecionamento. As quatro respostas foram 200 `application/zip`, abaixo do teto de 15 MB.

| Arquivo | Tamanho | SHA-256 | Baixado (UTC) | `Last-Modified` (GMT) |
|---|---|---|---|---|
| `registro_fundo_classe.zip` | 6.868.246 bytes | `b6cd4f1e456e5fa0303ff0c8a73b161450745a30f1dcd50944d15775c27298df` | 2026-10-27 13:50:38 | 2026-10-27 04:28:04 |
| `meta_registro_fundo_classe.zip` | 2.222 bytes | `ee821af85275d9f798c158c860b89ca7ef565c81eb88a22b213a4379a2d08783` | 2026-10-27 13:50:38 | 2026-10-27 04:28:04 |
| `inf_mensal_fidc_202609.zip` | 3.637.109 bytes | `365ef15fb1ba4e20a6a2adfefcd70c7f17cd9226135943739411e38f890d9ab0` | 2026-10-27 13:50:38 | 2026-10-24 11:46:15 |
| `meta_inf_mensal_fidc_txt.zip` | 15.942 bytes | `148ecadc9fc98991703873ed7ce98d528c92e51f88d3ad2724b57cd824a9edb1` | 2026-10-27 13:50:38 | 2026-10-24 14:32:26 |

URLs: `https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip`, `https://dados.cvm.gov.br/dados/FI/CAD/META/meta_registro_fundo_classe.zip`, `https://dados.cvm.gov.br/dados/FIDC/DOC/INF_MENSAL/DADOS/inf_mensal_fidc_202609.zip` e `https://dados.cvm.gov.br/dados/FIDC/DOC/INF_MENSAL/META/meta_inf_mensal_fidc_txt.zip`. O cadastro muda de terça a sábado e o informe de FIDC toda semana (seção 2). Os hashes vão mudar quando a CVM atualizar os arquivos; os da tabela identificam o que foi lido. Depois da análise, os quatro hashes foram conferidos de novo e não mudaram. Os dois arquivos do FIAGRO (seção 9.1) foram abertos só para leitura, no cruzamento, e mantiveram os hashes.

### 10.2 Estrutura dos arquivos (item a)

**Membros dos ZIPs.** O cadastro traz `registro_fundo.csv` (27.123.839 bytes descomprimidos), `registro_classe.csv` (16.339.683) e `registro_subclasse.csv` (1.808.084). O dicionário do cadastro traz um TXT por arquivo (`meta_registro_fundo.txt`, `meta_registro_classe.txt`, `meta_registro_subclasse.txt`; 11.163 bytes no total). O informe de FIDC traz 18 CSV `inf_mensal_fidc_tab_<tabela>_202609.csv` (36.115.195 bytes) e o dicionário, 18 TXT `meta_inf_mensal_fidc_tab_<tabela>.txt` (110.077 bytes). **As 18 tabelas (`tab_I` a `tab_X_7`) estão presentes**, e não há nenhuma a mais.

| CSV | Linhas de dados | Campos no CSV | Campos no dicionário |
|---|---|---|---|
| `registro_fundo` | 90.859 | 21 | 21 |
| `registro_classe` | 37.018 | 30 | 30 |
| `registro_subclasse` | 11.518 | 14 | 14 |
| `tab_I` | 4.444 | 109 | 109 |
| `tab_II` | 4.444 | 37 | 37 |
| `tab_III` | 4.444 | 13 | 13 |
| `tab_IV` | 4.444 | 6 | 6 |
| `tab_V` | 4.444 | 37 | 37 |
| `tab_VI` | 4.444 | 37 | 37 |
| `tab_VII` | 4.444 | 29 | 29 |
| `tab_VIII` | 44.701 | 6 | 6 |
| `tab_IX` | 4.444 | 76 | 76 |
| `tab_X` | 4.444 | 23 | 23 |
| `tab_X_1` | 12.231 | 7 | 5 |
| `tab_X_1_1` | 4.444 | 36 | 36 |
| `tab_X_2` | 12.735 | 7 | 6 |
| `tab_X_3` | 12.731 | 6 | 5 |
| `tab_X_4` | 48.687 | 8 | 7 |
| `tab_X_5` | 4.444 | 11 | 11 |
| `tab_X_6` | 12.469 | 7 | 6 |
| `tab_X_7` | 4.444 | 6 | 6 |

- **Formato dos 21 CSV:** separador `;`, cabeçalho na primeira linha (nomes únicos), fim de linha CRLF, sem BOM, uma quebra de linha no fim e todas as linhas com o número de campos do cabeçalho. Não há aspas como delimitador; o arquivo de subclasse tem 25 aspas dentro de valores, sem efeito na leitura.
- **Codificação:** não é UTF-8 (a leitura estrita falha). Decodifica sem erro como cp1252, sem bytes de 0x80 a 0x9F (então cp1252 e ISO-8859-1 não se distinguem) e sem sinal de dupla codificação, nos 21 CSV e nos 21 TXT dos dicionários, também em CRLF. É o mesmo formato do FIAGRO (seção 9.2).
- **Números e datas:** decimal com ponto, sem separador de milhar; datas `AAAA-MM-DD`; nenhum decimal com vírgula nem data `dd/mm/aaaa`.
- **Confere com o dicionário:** no cadastro, os nomes batem nos três arquivos. No FIDC, batem em 13 tabelas. Nas tabelas X.1, X.2, X.3, X.4 e X.6, o dicionário lista `CNPJ_FUNDO` e o dado traz `TP_FUNDO_CLASSE` e `CNPJ_FUNDO_CLASSE`; a `tab_X_1` traz ainda `ID_SUBCLASSE`, que o dicionário não tem. O dado segue as Novidades e fecha as divergências da seção 8.
- **Chave comum:** as 18 tabelas começam por `TP_FUNDO_CLASSE`, `CNPJ_FUNDO_CLASSE`, `DENOM_SOCIAL` e `DT_COMPTC`. As 12 tabelas por classe têm uma linha por classe (4.444). As de série têm uma linha por série (X.1, X.2, X.3 e X.6) ou por série e tipo de operação (X.4). A `tab_VIII` tem até 25 `SEQUENCIAL` por classe, em 3.141 classes. Todo CNPJ das outras 17 tabelas está na `tab_I`.
- **O dicionário do cadastro é pobre:** descreve 28 dos 65 campos e não dá domínio para nenhum campo de tipo, classe, classificação ou situação (10.3). O do FIDC descreve quase todos os campos (107 de 109 na `tab_I`), com domínio genérico (Numérico, Alfanumérico, `AAAA-MM-DD`, S/N, Aberto/Fechado). `SEQUENCIAL` e `VALOR` da `tab_VIII` seguem sem descrição.

### 10.3 Domínios do cadastro (item b)

Valores e contagens de linhas no arquivo inteiro, inclusive registros cancelados. "Vazio", na coluna do dicionário, quer dizer sem domínio e sem descrição.

| Campo | Arquivo | Dicionário | Valores (contagem de linhas) |
|---|---|---|---|
| `Tipo_Fundo` | fundo | vazio | 19 valores: FI (62.565), FIDC (8.205), FIF (5.229), FACFIF (5.211), FIP (4.499), FII (2.293), FITVM (842), FMIA-CL (775), FIAGRO (419), FIIM (340), FMIA (229), FMP-FGTS (118), FMIEE (49), FUNCINE (32), FAPI (32), FMP-FGTS CL (10), FICART (6), FMAI (4), FI-FGTS (1). Nenhum valor para FIC-FIDC |
| `Situacao` | fundo | vazio | Cancelado (52.977), Em Funcionamento Normal (34.492), Fase Pré-Operacional (2.457), Em Liquidação (918), Incorporação (9), Em Situação Especial (5), Em Análise (1) |
| `Tipo_Pessoa_Gestor` | fundo | vazio | PJ (64.177), PF (225), vazio (26.457) |
| `Tipo_Classe` | classe | vazio | 10 valores, todos "Classes de Cotas de Fundos" seguido do tipo: FIF (26.782), FIDC (5.445), FIP (2.546), FII (1.554), FIAGRO (395), FIIM (273), FIF (FAPI) (13), Funcine (8), FIP (FMIEE) (1), FICART (1). Nenhuma variante de FIAGRO |
| `Situacao` | classe | vazio | Em Funcionamento Normal (33.801), Fase Pré-Operacional (2.382), Em Liquidação (798), Cancelado (37) |
| `Classificacao` | classe | vazio | Multimercado (14.415), Renda Fixa (7.906), Ações (4.288), FMP-FGTS (93), Cambial (68), vazio (10.248). Vazia em 5.433 das 5.445 classes de FIDC e em 394 das 395 de FIAGRO |
| `Classificacao_Anbima` | classe | vazio | 65 categorias ANBIMA, vazio em 10.342. Vazia em 5.434 das 5.445 classes de FIDC e em 394 das 395 de FIAGRO |
| `Classe_Cotas` | classe | vazio | N (16.844), S (9.895), vazio (10.279). Vazio em todas as classes de FIDC e de FIAGRO |
| `Entidade_Investimento` | classe | vazio | N (8.331), S (1.715), vazio (26.972). Vazio em todas as classes de FIDC e em 391 das 395 de FIAGRO (4 N) |
| `Forma_Condominio` | classe | Aberto/Fechado | Aberto (23.282), Fechado (9.850), vazio (3.886) |
| `Exclusivo` | classe | vazio | N (15.208), S (13.518), vazio (8.292) |
| `Publico_Alvo` | classe | "Alfanumérico" | Profissional (16.907), Público Geral (5.585), Qualificado (3.711), vazio (10.815) |
| `Indicador_Desempenho` | classe | vazio | 32 índices ("DI de um dia" 10.740, "Não se aplica" 8.712, "OUTROS" 3.260, Ibovespa 1.303 e outros), vazio (11.284) |
| `Tributacao_Longo_Prazo` | classe | vazio | N/A (21.062), S (3.088), N (1.458), vazio (11.410) |
| `Permitido_Aplicacao_CemPorCento_Exterior` | classe | vazio | N (18.948), S (7.793), vazio (10.277) |
| `Classe_ESG` | classe | vazio | N (36.048), S (579), vazio (391) |
| `Situacao` | subclasse | vazio | Em Funcionamento Normal (6.346), Fase Pré-Operacional (4.734), Em Liquidação (250), Em Análise (187), Cancelado (1) |
| `Forma_Condominio` | subclasse | Aberto/Fechado | Fechado (8.765), Aberto (2.753) |
| `Exclusivo` | subclasse | vazio | N (10.542), S (974), vazio (2) |
| `Publico_Alvo` | subclasse | "Alfanumérico" | Profissional (7.248), Qualificado (3.189), Público Geral (607), vazio (474) |
| `Previdenciario`, `Exclusivo_INR`, `Exclusivo_Previdencia_Complementar` | subclasse | S/N | N quase sempre (S em 47, 31 e 5) |

- **`Fundo_Cotas` não existe** em nenhum dos três arquivos. O campo parecido é `Classe_Cotas` (classe), preenchido só fora de FIDC e FIAGRO.
- **Sem domínio no dicionário:** todos os campos acima, exceto `Forma_Condominio` (Aberto/Fechado), `Publico_Alvo` ("Alfanumérico", sem lista) e os três S/N da subclasse. Os valores do dado são poucos e estáveis, mas são o que a amostra mostra, não uma lista oficial.
- **Tipo do fundo e tipo da classe andam juntos:** fundo FIDC tem classe FIDC (5.444), fundo FIAGRO tem classe FIAGRO (395), e assim por diante. A única exceção é 1 classe de FIDC, cancelada, de um fundo FIF.
- **O arquivo de subclasse não tem campo de tipo nem de senioridade** (sênior, subordinada).
- **`FIIM`**, a aplicação do FIAGRO que o dicionário não descreve (seção 9.6), é um `Tipo_Fundo` do cadastro (340 fundos, 273 classes); o significado da sigla não está no dicionário.
- **No informe de FIDC:** `TP_FUNDO_CLASSE` Classe (4.413) e Fundo (31); `CLASSE_UNICA` S (3.390) e N (1.054), sem domínio no dicionário; `CONDOM` FECHADO (3.250) e ABERTO (1.194), em maiúsculas, embora o dicionário diga Aberto/Fechado; `FUNDO_EXCLUSIVO` e `COTST_INTERESSE` S/N; `TP_PRAZO_CONVERSAO_COTA` e `TP_PRAZO_PAGTO_RESGATE` DIAS CORRIDOS ou DIAS ÚTEIS (vazios em cerca de 3.250 linhas); `TAB_X_TP_OPER` Amortizações, Captações no Mês, Resgates no Mês e Resgates Solicitados. `CLASSE` é texto livre (2.069 preenchidos, 1.975 distintos), não domínio.

### 10.4 Como identificar FIDC, FIC-FIDC e FIAGRO (item c)

| Tipo | Sinal que serve | Não serve | Conferência com os informes de 09/2026 |
|---|---|---|---|
| FIDC | `registro_fundo.Tipo_Fundo` FIDC e `registro_classe.Tipo_Classe` "Classes de Cotas de Fundos FIDC" | `Classificacao`, `Classificacao_Anbima`, `Classe_Cotas` e `Entidade_Investimento` (vazios em FIDC); `TP_FUNDO_CLASSE` do informe (só separa fundo e classe); o nome | dos 4.444 CNPJs do informe, 4.400 são classes de FIDC no cadastro e 38 só aparecem como registro de fundo FIDC. Os outros 6 são 3 classes de FIF, 2 de FIAGRO e 1 com registros de FIDC e de FIF. Das 4.322 classes de FIDC em funcionamento normal, 4.201 (97%) estão no informe; das 381 em liquidação, 200; das 741 em fase pré-operacional, nenhuma |
| FIC-FIDC | **nenhum campo**. Sinal de comportamento: `TAB_I2H_VL_COTA_FIDC` sobre `TAB_I_VL_ATIVO`, na `tab_I` | `Tipo_Fundo` (o FIC-FIDC é FIDC), `Classe_Cotas` (vazio em FIDC; só é preenchido em FIF), `Classificacao`, `Classificacao_Anbima`, `TP_FUNDO_CLASSE`, `CLASSE` (texto livre), o nome | cotas de FIDC sobre o ativo: 0 em 2.905 classes, abaixo de 5% em 146, de 5% a 50% em 287, de 50% a 67% em 69, de 67% a 95% em 374 e 95% ou mais em 518; 145 sem ativo positivo. `TAB_I2I_VL_COTA_FIDC_NP` vem vazio, e `TAB_I2_COTA_FIDC` é provisão (5 linhas) |
| FIAGRO | `Tipo_Fundo` FIAGRO e `Tipo_Classe` "Classes de Cotas de Fundos FIAGRO" | para a variante, nenhum campo (10.5) | 309 das 310 classes do informe de FIAGRO são FIAGRO no cadastro; 1 está registrada como FIDC. Das 312 classes FIAGRO em funcionamento normal, 303 estão no informe de FIAGRO; das 12 em liquidação, 6; das 71 em fase pré-operacional, nenhuma |

**Conclusão:** FIDC e FIAGRO se identificam pelo par `Tipo_Fundo` e `Tipo_Classe`, conferido contra os dois informes. O FIC-FIDC não tem marca. O informe dá a parcela do ativo em cotas de FIDC, e o corte foi decidido pelo Gui em 27/10/2026: 95% ou mais classifica como FIC-FIDC, e de 67% a menos de 95% vai para revisão manual (decisão 6 de `docs/decisoes-em-aberto.md`). É uma regra de corte, não um dado da CVM; a regra da norma não foi verificada nesta etapa. A lista dos FIDCs investidos continua vindo do CDA (não lido). Os cotistas "cotas de FIDC" da `tab_X_1_1` (538 classes com algum) mostram o lado do fundo investido, não marcam o investidor.

### 10.5 Cruzamento com a amostra de FIAGRO (item d)

- **Encontradas:** as 312 linhas (310 `CNPJ_Classe`) do informe de FIAGRO de 09/2026 estão em `registro_classe`, com um só registro de classe por CNPJ. Nenhuma aparece só como fundo.
- **Distribuição das 310:** `Tipo_Classe` "Classes de Cotas de Fundos FIAGRO" em 309 e "Classes de Cotas de Fundos FIDC" em 1 (com `Tipo_Fundo` FIDC); `Classificacao`, `Classe_Cotas` e `Classificacao_Anbima` vazios nas 310; `Entidade_Investimento` vazio em 307 e N em 3; `Situacao` Em Funcionamento Normal (304) e Em Liquidação (6).
- **Conclusão: o cadastro não identifica a variante do FIAGRO (FII, FIDC, FIP).** O que existe é uma pista no histórico de registro: 166 das 310 classes têm o mesmo CNPJ em outro registro de `registro_fundo` (FIDC cancelado 88, FII cancelado 64, FIP cancelado 10, FIDC e FII cancelados 2, FII e FIP cancelados 1, FIDC em funcionamento 1); as outras 144 só têm o registro de FIAGRO. O tipo anterior não é a variante declarada: **não confirmado**.
- **As duas chaves repetidas da seção 9.4:** cada CNPJ tem um só registro de classe no cadastro (um `ID_Registro_Classe`, em funcionamento normal). As duas linhas do informe não são duas classes no cadastro; a causa segue **não confirmada**.
- **Sobreposição FIAGRO-FIDC:** 1 das 310 classes do informe de FIAGRO aparece no informe de FIDC de 09/2026, como `CNPJ_FUNDO_CLASSE` e como `CNPJ_CLASSE` da `tab_I`. No cadastro, ela é FIAGRO. No sentido inverso, 2 classes do informe de FIDC são FIAGRO no cadastro (uma é a da sobreposição), e mais 1 tem um registro de fundo FIAGRO. A classe que o cadastro registra como FIDC não está no informe de FIDC.

### 10.6 Séries e subordinação (item e)

- **Arquivo e campo:** a `tab_X_2` traz a quantidade e o valor da cota por série (`TAB_X_QT_COTA`, `TAB_X_VL_COTA`), com o rótulo em `TAB_X_CLASSE_SERIE`. O mesmo campo está na `tab_X_1` (cotistas, com `ID_SUBCLASSE`), na `tab_X_3` (rentabilidade), na `tab_X_4` (operações) e na `tab_X_6` (desempenho). O dicionário o descreve como "(X) Classe/Série", alfanumérico de até 49 caracteres, sem domínio.

**Padrões** (12.735 linhas, 220 rótulos distintos):

| Início do rótulo | Linhas | Rótulos distintos | Categoria |
|---|---|---|---|
| `Subclasse Senior` | 7.017 (55,1%) | 148 | sênior |
| `Subclasse Subordinada Subordinada` | 2.784 (21,9%) | 7 | subordinada |
| `Subclasse Subordinada Mezanino` | 2.335 (18,3%) | 63 | mezanino |
| `Subclasse Subordinada`, sem segunda palavra | 599 (4,7%) | 2 | subordinada |
| qualquer outro | 0 | 0 | sem classificação |

Pelos padrões pedidos: contém "sênior" 7.017; contém "subordinada" sem "mezanino" 3.383; contém "mezanino" 2.335 (o molde escreve "Subclasse Subordinada Mezanino"); só número ou letra 0; outro 0. Nenhum rótulo junta sênior com subordinada, e nenhum traz "júnior" ou "única".

- **Rótulos mais frequentes**, todos genéricos: `Subclasse Subordinada Subordinada 1 |` (2.749), `Subclasse Senior Série 1` (1.877), `Subclasse Senior Subclasse 1` (1.557), `Subclasse Senior` (994), `Subclasse Subordinada` seguido de `|` (598), `Subclasse Senior Série 2` a `Subclasse Senior Série 15` (de 583 a 32) e `Subclasse Subordinada Mezanino 1 |` (38). A parte que varia é, em quase todos, o número da série ou da subclasse.
- **Por classe (4.444):** 1.056 têm uma só série, sempre `Subclasse Senior` (então "sênior" sozinho não quer dizer que há subordinação). As outras 3.388 têm duas ou mais, todas classificadas: sênior e subordinada (2.331); sênior, mezanino e subordinada (1.018); sênior e mezanino (12); só sênior (27). Em 20 classes há duas ou mais subordinadas sem mezanino, e o rótulo não diz a ordem entre elas.
- **Conferência com o PL:** a soma de quantidade × valor da cota das séries fecha com `TAB_IV_A_VL_PL` (diferença de até 1%) em 4.154 das 4.444 classes. Não fecha em 113, e 177 têm PL vazio ou menor ou igual a zero. Nas 4.154, o PL se divide em 65,5% sênior, 26,6% subordinada e 7,9% mezanino. Nas 3.169 delas com duas ou mais séries, a parcela subordinada (subordinada mais mezanino) é 0 em 626, abaixo de 5% em 91, de 5% a 10% em 66, de 10% a 20% em 213, de 20% a 30% em 225, de 30% a 50% em 426 e de 50% ou mais em 1.522.
- **`tab_X_1` e `tab_X_2`:** o mesmo rótulo vem com espaços e `|` diferentes. Como vêm, só 5.086 dos 12.231 pares (CNPJ, série) da `tab_X_1` existem na `tab_X_2`; sem acento, caixa, espaços extras e `|`, existem 12.103. Na `tab_X_3` e na `tab_X_6`, 12.716 de 12.731 e 12.443 de 12.469 casam como vêm. `ID_SUBCLASSE` (só na `tab_X_1`) vem em 6.714 das 12.231 linhas, com 5.241 valores distintos de 15 caracteres, dos quais 3.537 existem em `registro_subclasse.ID_Subclasse`.
- **A `tab_X_1_1` não confere o rótulo:** em 1.743 classes, a contagem de cotistas sênior ou subordinados não acompanha as séries rotuladas (por exemplo, 999 classes com série sênior e nenhum cotista sênior).
- **Conclusão:** em 09/2026, o rótulo permite mapear sênior, mezanino e subordinada sem ambiguidade, pelo início do texto, e nenhuma série fica sem classificação (0%). Ressalvas: é um molde do sistema de entrega, não um domínio documentado, e pode mudar; 599 linhas dizem só "Subclasse Subordinada", sem o subtipo; e o rótulo não ordena duas subordinadas da mesma classe. O `quota_class_map` (seção 5) continua necessário, mas como regra por início do rótulo, revisada, e não como lista de rótulos.

### 10.7 Reapresentação (item f)

- Nenhuma das 18 tabelas tem campo de versão, de entrega ou de recebimento. O único campo de data é `DT_COMPTC`, com um só valor (2026-09-30) em todas as linhas.
- Nenhuma chave se repete. (`CNPJ_FUNDO_CLASSE`, `DT_COMPTC`) é única nas 12 tabelas por classe; nas de série, junto com o rótulo (mais `ID_SUBCLASSE` na X.1 e o tipo de operação na X.4); na `tab_VIII`, junto com `SEQUENCIAL`. Não há linha repetida, idêntica ou não.
- O arquivo traz, portanto, uma linha por classe e competência, sem histórico. Uma reapresentação só aparece comparando dois instantâneos do mesmo mês (o ZIP muda toda semana; não feito nesta etapa), o que confirma a proposta da seção 5 (`data_conflicts`). É diferente do FIAGRO, que traz `Versao` e `Data_Entrega` (seção 9.4).
- O cadastro também não tem versão. Cada linha tem `Situacao` e `Data_Inicio_Situacao`, e o histórico aparece como registros diferentes do mesmo CNPJ (10.9).

### 10.8 Papéis e dados pessoais (item g)

| Papel | Cadastro | Informe de FIDC |
|---|---|---|
| Gestora | `registro_fundo`: `Gestor`, `CPF_CNPJ_Gestor`, `Tipo_Pessoa_Gestor` | não tem |
| Administradora | `registro_fundo`: `Administrador`, `CNPJ_Administrador` | `tab_I`: `ADMIN`, `CNPJ_ADMIN` |
| Custodiante | `registro_classe`: `Custodiante`, `CNPJ_Custodiante` | não tem |
| Controlador | `registro_classe`: `Controlador`, `CNPJ_Controlador` | não tem |
| Auditor | `registro_classe`: `Auditor`, `CNPJ_Auditor` | não tem |
| Diretor responsável | `registro_fundo`: `Diretor` (só o nome) | não tem |
| Cedentes | não tem | `tab_I`: `TAB_I2A12_CPF_CNPJ_CEDENTE_1` a `_9` e `TAB_I2B12_CPF_CNPJ_CEDENTE_1` a `_9`, com os percentuais em `TAB_I2A12_PR_CEDENTE_n` e `TAB_I2B12_PR_CEDENTE_n`; `tab_VII`: `TAB_VII_B1_1_QT_CEDENTE`, `TAB_VII_B1_2_VL_CEDENTE` e `TAB_VII_B1_3_VL_CONTAB_CEDENTE` (quantidade e valores, sem identificação) |

O arquivo de subclasse não tem papéis. As 18 tabelas têm `DENOM_SOCIAL` (nome do fundo ou da classe). Nenhum arquivo tem campo de e-mail, site ou telefone.

- **Preenchimento nos FIDCs:** gestor em 8.107 das 8.205 linhas de fundo FIDC (702 identificadores distintos), administrador em 8.192 (100 CNPJs), custodiante em 5.409 das 5.445 classes de FIDC (48 CNPJs), auditor em 5.287 (35) e controlador em 278 (29).
- **Papéis com mais de um valor:** `ID_Registro_Fundo` se repete em 1.069 casos (2.224 linhas), e o que muda é o gestor (`Gestor` e `CPF_CNPJ_Gestor`); em 10 casos, as linhas são idênticas. `ID_Registro_Classe` se repete em 5 casos, por custodiante ou controlador. O cadastro tem uma linha por gestor, não uma por fundo.
- **Administradora no informe e no cadastro:** `CNPJ_ADMIN`, sem a máscara, é igual ao `CNPJ_Administrador` do fundo em 4.423 das 4.444 classes; 21 diferem.

**CPF e outros dados pessoais** (só o campo e a contagem):

| Campo | Valores com formato de CPF (11 dígitos) | Observação |
|---|---|---|
| `registro_fundo.CPF_CNPJ_Gestor` | 225, todos com dígito verificador de CPF válido | todos com `Tipo_Pessoa_Gestor` PF; 9 são fundos FIDC (6 em funcionamento). `Gestor` traz o nome da pessoa |
| `registro_classe.CNPJ_Auditor` | 8, com dígito de CPF válido | o campo se chama CNPJ, mas traz CPF |
| `tab_I.TAB_I2A12_CPF_CNPJ_CEDENTE_1` a `_8` e `tab_I.TAB_I2B12_CPF_CNPJ_CEDENTE_1` a `_3` | 120, em 69 das 4.444 classes; 117 com dígito de CPF válido | 7 também viram CNPJ válido com zeros à esquerda (ambíguos) |
| `registro_fundo.Diretor` | 0 | nome de pessoa natural em 63.273 linhas (374 nomes distintos) |

Nenhuma outra coluna dos 3 CSV do cadastro e das 18 tabelas tem valor com formato de CPF. Decidido pelo Gui em 27/10/2026 (decisão 3 de `docs/decisoes-em-aberto.md`): o CPF nunca é gravado, só CNPJ, com um teste automático que garante isso, e os campos de pessoa natural (por exemplo o `Diretor`) e os de contato não são carregados. Continuam em aberto como aparece o papel de gestor, auditor ou cedente pessoa física, que fica sem identificador, e o tratamento dos 7 valores de cedente ambíguos; continua **pendente** se a regra vale também para o arquivo original da CVM.

### 10.9 Formato de CNPJ e casamento entre os conjuntos (item h)

| Campo | Formato | Observação |
|---|---|---|
| cadastro: `CNPJ_Fundo`, `CNPJ_Classe`, `CNPJ_Administrador`, `CNPJ_Custodiante`, `CNPJ_Controlador` | 14 dígitos, sem máscara | dígitos verificadores válidos em todos, menos 1 `CNPJ_Fundo` |
| cadastro: `CPF_CNPJ_Gestor`, `CNPJ_Auditor` | 14 dígitos, ou 11 quando é CPF | ver 10.8 |
| informe: `CNPJ_FUNDO_CLASSE` (18 tabelas) | **com máscara** (`NN.NNN.NNN/NNNN-NN`) nas 196.882 células | dígitos válidos em todas; 4.444 distintos |
| informe: `CNPJ_ADMIN` (`tab_I`) | com máscara | 53 distintos |
| informe: `CNPJ_CLASSE` (`tab_I`) | sem máscara: 14 dígitos (4.435), 13 dígitos (8, zero à esquerda perdido) e 1 valor de 18 caracteres em outro formato | sem a máscara, igual a `CNPJ_FUNDO_CLASSE` em 4.427 das 4.444 linhas |
| informe: cedentes | sem máscara: 14 dígitos (3.585), 11 (120), 12 ou 13 (21, todos CNPJ válidos com zeros à esquerda) | ver 10.8 |

Nenhum arquivo tem CNPJ alfanumérico.

- **Casamento:** como vem, nenhum `CNPJ_FUNDO_CLASSE` do informe casa com o cadastro, porque a máscara não bate com os 14 dígitos. Sem a máscara, os 4.444 casam: 4.406 com `CNPJ_Classe` (4.397 deles também são `CNPJ_Fundo`) e 38 só com `CNPJ_Fundo`. Das 31 linhas com `TP_FUNDO_CLASSE` Fundo, 22 casam só como fundo e 9 também como classe. `CNPJ_CLASSE`, completado com zeros à esquerda, casa como classe em 4.397 dos 4.431 valores distintos, só como fundo em 33 e não casa em 1.
- **Unicidade no cadastro:** `CNPJ_Classe` se repete em 13 casos (26 linhas; 2 envolvem uma classe de FIDC). `CNPJ_Fundo` se repete em 8.165 casos (17.092 linhas), porque o mesmo CNPJ tem registros de tipos diferentes ao longo do tempo (FI e FIF em 2.376 casos, FACFIF e FI em 2.336, FI e FIDC em 571, FIAGRO e FIDC em 92) e porque há uma linha por gestor; 5.115 desses CNPJs só têm registros cancelados. A classe tem o mesmo CNPJ do fundo em 36.868 das 37.018 classes.
- **Consequência:** casar pelo CNPJ normalizado (14 dígitos, sem máscara, com zeros à esquerda) e não pressupor que o CNPJ seja único por linha do cadastro. Escolher o registro vigente é regra do adaptador.
- 14 CNPJs do informe só têm registros cancelados no cadastro (cancelados depois da competência? **não confirmado**).

### 10.10 O que a amostra não confirma (item i)

- A variante de cada FIAGRO: não está no informe nem no cadastro, e o histórico de registro é só pista. Candidatos: o regulamento (Fundos.NET) e a ANBIMA, não consultados. Até lá, aparece "variante não informada" (decidido pelo Gui em 27/10/2026, decisão 7 de `docs/decisoes-em-aberto.md`).
- A sobreposição FIAGRO-FII: o informe de FII não foi lido.
- O CDA: não foi lido. A lista dos FIDCs investidos por um FIC-FIDC e a coluna do fundo investido no `cda_fie` continuam pendentes.
- A regra da norma para o FIC-FIDC. O corte do sinal não depende dela: foi decidido pelo Gui em 27/10/2026 como regra de corte (decisão 6 de `docs/decisoes-em-aberto.md`).
- Reapresentações ao longo do tempo: há um só instantâneo, e o informe de FIDC não tem versão.
- Se o molde do rótulo de série vale para outros meses, e se "Subclasse Subordinada" sem subtipo é júnior ou mezanino. Enquanto o rótulo não disser, o subtipo aparece como "ausente" (decidido pelo Gui em 27/10/2026, decisão 8 de `docs/decisoes-em-aberto.md`).
- O significado da `tab_VIII` (`SEQUENCIAL`, `VALOR`), que o dicionário não descreve.
- Por que só 3.537 dos 5.241 `ID_SUBCLASSE` do informe existem no cadastro, por que 113 classes não fecham quantidade × valor com o PL e por que 14 CNPJs do informe só têm registros cancelados no cadastro.
- A causa das duas chaves repetidas do FIAGRO (seção 9.4).
- O significado da sigla `FIIM`.
- Se a codificação é cp1252 ou ISO-8859-1: a amostra não tem os bytes que distinguem as duas.

## 11. Sonda da grade do Fundos.NET (27/10/2026)

Consulta à grade pública de documentos do Fundos.NET para fechar o item (a) da seção 8: como a grade filtra FIDC, FIC-FIDC e FIAGRO, quais categorias de documento existem para fundos, que campos a grade traz por linha e como se chega ao link de um documento. Só agregados e nomes de campos: esta seção não traz nomes de fundos, gestoras, administradoras ou pessoas, CNPJs, identificadores de documento nem texto de documento. As respostas brutas ficam numa pasta local fora do repositório.

### 11.1 Requisições e integridade

Foram 10 requisições GET, aprovadas antes da execução, em duas fases: a lista da segunda fase foi preenchida com os códigos lidos na primeira e aprovada à parte. As condições da execução:

- um processo, em sequência, com 5 s entre requisições e sem retentativa;
- TLS verificado e nenhum redirecionamento seguido;
- sem login, credencial ou cabeçalho CSRF;
- User-Agent próprio (`pense-alm-fundos-sonda/0.1`), já que o coletor do Enrico usa o padrão do Edge;
- cookies de sessão do site guardados só em memória;
- nenhuma chamada de download, de visualização de documento ou das listas de administradores e de fundos.

Nenhuma resposta veio com 403, 429, redirecionamento ou captcha. O script ficou fora do repositório, usa só a biblioteca padrão do Python e importa do coletor do Enrico apenas funções de leitura (seção 11.7).

O host é `https://fnet.bmfbovespa.com.br`. As consultas à grade (R5, R6, R7 e R10) também levam `l=10`, `o[0][dataEntrega]=desc`, `idTipoDocumento=0`, `idEspecieDocumento=0`, `dataInicial=29/09/2026`, `dataFinal=27/10/2026` e `isSession=false`.

| # | Caminho | Parâmetros | Status e tipo | Bytes | SHA-256 | UTC |
|---|---|---|---|---|---|---|
| R1 | `/robots.txt` | nenhum | 404 `text/html` | 314 | `7dd7d1aea029157de8d8cdf2a4f5e855a44cb48dfa53fdfbd3e1897e2ad86b71` | 16:30:41 |
| R2 | `/fnet/publico/abrirGerenciadorDocumentosCVM` | nenhum | 200 `text/html` | 14.883 | `b1676ca8b50ddd303b1b8ecefaa3e82115dcef6891195c781217274be509994d` | 16:30:46 |
| R3 | `/fnet/resources/js/paginas/publico/gerenciador-documentos-cvm.js` | nenhum | 200 `application/javascript` | 21.888 | `770c567bef268bba2f5dab8705ed2169cf6592edb91148a799a8318231032490` | 16:30:51 |
| R4 | `/fnet/publico/abrirGerenciadorDocumentosCVM` (sessão da segunda fase) | nenhum | 200 `text/html` | 14.883 | `59930893a5c4ac06b54eaa5711f79068596ec296d4fe5a473b489ddea379a2d8` | 16:34:01 |
| R5 | `/fnet/publico/pesquisarGerenciadorDocumentosDados` | `d=1`, `s=0`, `tipoFundo=2`, `idCategoriaDocumento=0` | 200 `application/json` | 10.035 | `668e8d077d09373a0e091aeb778eb907adb09e89ee9e8b2e12831ca3ed02452f` | 16:34:06 |
| R6 | idem | `d=2`, `s=10`, `tipoFundo=2`, `idCategoriaDocumento=0` | 200 `application/json` | 9.929 | `d180a4aad61bf7fc21b35cf3f0e93e6ba826001beb6e402c8706feb888cb33b3` | 16:34:11 |
| R7 | idem | `d=3`, `s=0`, `tipoFundo=11`, `idCategoriaDocumento=0` | 200 `application/json` | 9.815 | `e9cdec9acb91d351af2540713b1136f5273a67da93744097b8a07ea250a29751` | 16:34:16 |
| R8 | `/fnet/publico/listarTodasCategoriaPorTipoFundo` | `idTipoFundo=2` | 200 `application/json` | 1.441 | `43b79190b753e7e04b41f3e1c91fda140fad5f3f1dd904c33ec6b3bbc8cfef94` | 16:34:21 |
| R9 | idem | `idTipoFundo=11` | 200 `application/json` | 1.533 | `9af5cc69f25dbc4cb2c36a86215def1d10caa8d113ae41da4a1565cc210226bc` | 16:34:26 |
| R10 | `/fnet/publico/pesquisarGerenciadorDocumentosDados` | `d=4`, `s=0`, `tipoFundo=2`, `idCategoriaDocumento=5` | 200 `application/json` | 9.678 | `257bd9d3b9d90e5d32de7b701a591e0ffd0634477c14831672155550cd45630b` | 16:34:31 |

Depois da análise, os 10 hashes foram conferidos de novo e não mudaram. A página muda a cada acesso: R2 e R4 diferem em duas linhas, o script de monitoramento e o parâmetro por requisição da Cloudflare. A grade muda a cada entrega. Os hashes identificam o que foi lido.

### 11.2 robots.txt, termos de uso e proteções

- **robots.txt e termos:** o host não publica `robots.txt` (R1 devolveu 404). A página não tem link para termos de uso nem para política de privacidade. Os termos gerais da B3, fora desse host, **não foram conferidos**.
- **Scripts e cookies:** a página carrega um script de detecção de robôs da Cloudflare (`/cdn-cgi/challenge-platform/.../jsd/main.js`) e um agente de monitoramento (Dynatrace); a sonda não executa JavaScript. O site grava cookies de balanceamento e de sessão (`F051234a800`, `JSESSIONID`, `ROUTEID_CAUF`, `ROUTEID_FNET`, `dtCookie`); só os nomes foram registrados.
- **Captcha:** existe na página, mas só para a exportação do "Anexo B" (`btnAnexoB`, `validarAnexoB`). A busca na grade não pede captcha.
- **CSRF:** o JS envia um cabeçalho CSRF lido de `<meta name="_csrf">`, mas a página não tem essa meta, e o navegador envia o valor vazio. A sonda não enviou o cabeçalho, e a grade respondeu JSON.
- **Limite:** com 5 s entre requisições, nenhuma resposta indicou limite.

### 11.3 Filtro por tipo de fundo (FIDC, FIC-FIDC, FIAGRO)

A página é `/fnet/publico/abrirGerenciadorDocumentosCVM`; a de certificados do CRI/CRA (`abrirGerenciadorDocumentosCertificadosCVM`) é outra. O `<select name="tipoFundo">` tem 7 tipos:

| Código | Rótulo |
|---|---|
| 1 | Fundo Imobiliário |
| 2 | **FIDC** |
| 3 | ETF |
| 4 | ETF RF |
| 7 | Fundo Setorial |
| 10 | FIP |
| 11 | **FIAGRO** |

- **FIC-FIDC não tem código próprio:** entra em `tipoFundo=2`, como no cadastro da CVM (seção 10.4). Nenhum campo da linha da grade o separa.
- **FIAGRO não é separado por variante** (FIDC, FII, FIP): há um só código, `11`. A variante continua sem fonte estruturada (seções 6 e 10.5).
- CRI (5) e CRA (6) não aparecem nesta página.
- **Volume na janela de 29/09 a 27/10/2026:** a grade informa 8.930 documentos com `tipoFundo=2` e 891 com `tipoFundo=11` (`recordsFiltered`, igual a `recordsTotal` nas quatro consultas).
- **Outros filtros da grade** (JS, linhas 69 a 92):
  - `administrador` e `idFundo`, com listas carregadas por `buscarAdministrador` e `listarFundos`, que não foram chamadas;
  - `idCategoriaDocumento`, `idTipoDocumento` e `idEspecieDocumento`;
  - `situacao`: A Ativo, I Inativo, C Cancelado;
  - `cnpj` e `cnpjFundo`, preenchidos pelo mesmo campo de texto;
  - `dataReferencia`, com `ultimaDataReferencia`;
  - `dataInicial` e `dataFinal`, em dd/mm/aaaa;
  - `idModalidade`: 1 Apresentação, 2 Reapresentação por Exigência, 3 Reapresentação Espontânea;
  - `palavraChave` e `isSession`.

  O JS remove os parâmetros vazios antes de enviar. O filtro por CNPJ **não foi testado**, porque exigiria um fundo específico.
- **Datas:** nas 40 linhas lidas, `dataEntrega` está sempre na janela, e `dataReferencia` às vezes não (a mais antiga é de 08/01/2026). Então o filtro `dataInicial`/`dataFinal` não se aplica à data de referência. É provável que se aplique à data de entrega, mas, com a ordem decrescente, as linhas lidas só mostram o fim da janela: o limite inicial **não foi confirmado**.

### 11.4 Categorias de documento

- O HTML lista 48 categorias, mais "Todos", que valem para todos os tipos de fundo e de certificado. A lista por tipo de fundo vem de `listarTodasCategoriaPorTipoFundo?idTipoFundo=<código>`, que devolve `id`, `descricao`, `sigla` e `situacao` por categoria. Ela traz também um item 0, "Categoria", que é só o rótulo do campo.
- **FIDC tem 17 categorias e FIAGRO, 18:** 16 são comuns; a 16 é só de FIDC; a 12 e a 13 são só de FIAGRO.

| Código | Categoria | FIDC | FIAGRO |
|---|---|---|---|
| 1 | Fato Relevante | sim | sim |
| 2 | Assembleia | sim | sim |
| 3 | Comunicado ao Mercado | sim | sim |
| 4 | Aviso aos Cotistas | sim | sim |
| 5 | Regulamento | sim | sim |
| 6 | Informes Periódicos | sim | sim |
| 7 | Relatórios | sim | sim |
| 8 | Oferta Pública de Distribuição de Cotas | sim | sim |
| 9 | Políticas de Governança Corporativa | sim | sim |
| 10 | Outras Informações | sim | sim |
| 11 | Atos de Deliberação do Administrador | sim | sim |
| 12 | Oferta Pública de Aquisição de Cotas | não | sim |
| 13 | Laudo de Avaliação (Conclusão de Negócio) | não | sim |
| 14 | Aviso aos Cotistas - Estruturado | sim | sim |
| 15 | Regulamento de Emissores B3 | sim | sim |
| 16 | Documentos de Oferta de Distribuição Pública | sim | não |
| 24 | Listagem e Admissão à Negociação de Cotas | sim | sim |
| 43 | Outras Demonstrações Financeiras | sim | sim |
| 48 | Anexo ao Regulamento | sim | sim |

- **Rótulos com espaços sobrando:** `Outras Demonstrações Financeiras ` tem espaço no fim, e `Listagem e  Admissão à  Negociação  de Cotas` tem espaços duplos. O tipo `Informe Mensal Estruturado ` também vem com espaço no fim. A comparação precisa normalizar, guardando o valor original.
- **Tipos e espécies:** vêm de `listarTodosTiposPorCategoriaETipoFundo` (`idTipoFundo`, `idCategoria`) e de `listarTodasEspeciePorTipoECategoriaETipoFundo` (`idTipoFundo`, `idCategoria`, `idTipo`), que **não foram consultados**. Nas 40 linhas lidas apareceram estes rótulos (contagem de linhas):
  - **Categoria:** Regulamento (12), Informes Periódicos (11), Assembleia (6), Relatórios (6), e uma linha de cada uma destas: Oferta Pública de Distribuição de Cotas, Outras Demonstrações Financeiras, Atos de Deliberação do Administrador, Aviso aos Cotistas e Fato Relevante.
  - **Tipo:** Informe Mensal Estruturado (10), AGE (5), Relatório Gerencial (4), Outros Relatórios (2), e uma linha de cada um destes: AGO, Demonstrações Financeiras, Demonstrações Financeiras - Substituição de administrador, Anúncio de Início e Instrumento Particular de Alteração do Regulamento. Vazio em 14.
  - **Espécie:** Ata da Assembleia (5) e Carta Consulta (1). Vazia em 34.
- **Filtro de categoria confirmado:** com `idCategoriaDocumento=5`, `recordsFiltered` cai de 8.930 para 610, e as 10 linhas são "Regulamento". Os regulamentos vêm sem tipo e sem espécie.

### 11.5 Campos da grade e paginação

- **Resposta:** é um objeto no formato DataTables, com `draw` (eco de `d`), `recordsTotal`, `recordsFiltered` e `data` (a lista de linhas). Na requisição, os nomes são curtos: `d` (draw), `s` (início) e `l` (tamanho), e a ordem vai em `o[0][<coluna>]=asc|desc`.
- **Paginação:** `s=10` traz a página seguinte. Entre as páginas 1 e 2 de FIDC não há `id` repetido, e `recordsFiltered` não mudou. A ordem `dataEntrega desc` foi respeitada nas quatro consultas.
- **Ordem padrão:** a página geral ordena pela coluna 5, que nela é `dataReferencia`; na página de certificados, a coluna 5 é `dataEntrega`. A sonda pediu `dataEntrega`.
- **Linha:** são 37 campos, os mesmos nas 40 linhas de FIDC e de FIAGRO. Preenchimento nas 40 linhas:

| Campo | Preenchido | Forma ou valores |
|---|---|---|
| `id` | 40 | inteiro de 7 dígitos, único; é o que entra no link (11.6) |
| `descricaoFundo` | 40 | texto livre de 20 a 100 caracteres, com o nome do fundo ou da classe; nenhum traz padrão de CNPJ |
| `fundoOuClasse` | 40 | `Classe` nas 40 |
| `categoriaDocumento` | 40 | rótulo da categoria (11.4) |
| `tipoDocumento` | 26 | rótulo do tipo; vazio em 14 |
| `especieDocumento` | 6 | rótulo da espécie; vazio em 34 |
| `dataEntrega` | 40 | `dd/mm/aaaa hh:mm` |
| `dataReferencia` | 40 | forma dada por `formatoDataReferencia`: 2 = `mm/aaaa` (10), 3 = `dd/mm/aaaa` (24), 4 = `dd/mm/aaaa hh:mm` (6); o JS prevê também 1 = `aaaa` |
| `versao` | 40 | 1 (29), 2 (10), 3 (1) |
| `modalidade`, `descricaoModalidade` | 40 | `AP` Apresentação (29), `RE` Reapresentação Espontânea (11) |
| `status`, `descricaoStatus`, `situacaoDocumento` | 40 | `AC`, "Ativo com visualização" e `A` nas 40 |
| `altaPrioridade` | 40 | booleano; verdadeiro em 1 |
| `indicadorFundoAtivoB3` | 40 | falso nas 40 |
| `analisado` | 40 | `N` nas 40 |
| `idTemplate`, `idSelectItemConvenio` | 40 | 0 nas 40 |
| `informacoesAdicionais` | 40 | `;` em 34; texto de 2 a 13 caracteres em 6 linhas de FIAGRO |
| `nomePregao` | 6 | texto de 11 a 12 caracteres, só em linhas de FIAGRO |
| `arquivoEstruturado`, `assuntos`, `cnpjAdministrador`, `cnpjFundo`, `codSegNegociacao`, `dda`, `formatoEstruturaDocumento`, `idEntidadeGerenciadora`, `idFundo`, `idSelectNotificacaoConvenio`, `nomeAdministrador`, `nomePrimeiraVisualizacao`, `numeroEmissao`, `ofertaPublica`, `tipoPedido` | 0 | vazios ou nulos nas 40 |

- **O que a linha não traz:** o CNPJ do fundo ou da classe (`cnpjFundo` e `idFundo` vêm vazios, e `descricaoFundo` é só texto), o administrador e a variante do FIAGRO. O cadastro da CVM é chaveado por CNPJ (seção 10.9). Para ligar um documento à classe, restam dois caminhos: consultar a grade com o filtro `cnpj` de cada fundo (não testado) ou casar pelo nome, o que manda o caso para revisão (regra de dados 6 do `CLAUDE.md`).
- **Fundo ou classe:** `fundoOuClasse` mostra que a grade separa documento do fundo e documento da classe. As 40 linhas lidas eram de classe.
- **Versão e reapresentação:** ao contrário do informe de FIDC (seção 10.7), a grade traz `versao` e `modalidade` por documento, e com elas se distingue apresentação de reapresentação.

### 11.6 Link do documento

O JS monta as duas ações de cada linha a partir do `id` (linhas 16 e 19):

- visualizar: `https://fnet.bmfbovespa.com.br/fnet/publico/visualizarDocumento?id=<id>&cvm=true`
- baixar: `https://fnet.bmfbovespa.com.br/fnet/publico/downloadDocumento?id=<id>`

A linha não tem campo de URL. O `downloadDocumento?id=<id>` é o mesmo endereço que o relatório do Enrico validou para CRA, devolvendo XML (seção 1). Nenhum dos dois foi chamado na sonda, e o formato do arquivo (PDF ou XML) por categoria de documento de fundo **não foi conferido**.

### 11.7 O que o coletor do CRI/CRA aproveita

A análise rodou no ambiente Python do coletor do CRI/CRA (Python 3.14, com o pacote playwright). Ela importou do coletor, sem alterá-lo, `_extract_rows`, `_classify_html` e `_to_document`, este com um ativo fictício. Assim mediu o mesmo que o `--dry-run` mostra, sem os exemplos de linhas. O `--dry-run` em si não foi usado, porque ele:

- exige um ativo de CRI/CRA;
- abre a página de certificados num navegador, o que dispara dezenas de requisições;
- retenta requisições que falham;
- grava amostras de linhas em `reports/`.

| Peça | Resultado com linhas de fundos |
|---|---|
| `_extract_rows` | lê as 40 linhas; o total vem de `recordsTotal`, igual a `recordsFiltered` aqui |
| `_to_document` | converte as 40 sem erro. Categoria, versão, descrição e as duas datas saem preenchidas nas 40, o tipo nas 26 linhas que o trazem e a espécie nas 6 |
| `source_url` | como a linha não tem campo de URL, cai no padrão `visualizarDocumento?id=<id>`, **sem** o `&cvm=true` |
| `document_name` | vem de `tipoDocumento`; nas 14 linhas sem tipo (12 regulamentos, 1 aviso aos cotistas e 1 fato relevante) vira "Documento" |
| `classify_document` | Informe Mensal 11, Ata/Edital 5, Fato Relevante 1 e **Outro 23**, incluindo os 12 regulamentos. As 9 categorias de CRI/CRA não servem para fundos; a categoria oficial da grade (`categoriaDocumento`) serve |
| `_fetch_documentos` | usa `draw`/`start`/`length`, mas a página envia `d`/`s`/`l`; não foi testado se o servidor aceita os nomes longos |
| `_classify_html` | classifica a página normal como "protecao", por causa do bloco de captcha escondido do "Anexo B" |

### 11.8 O que a sonda não confirma

- Se o filtro `dataInicial`/`dataFinal` vale para a data de entrega (o início da janela não foi testado), e se o filtro `cnpj` acha a classe pelo CNPJ com ou sem máscara.
- Os tipos e as espécies por categoria: os endpoints existem, mas não foram chamados. Também não se sabe quais categorias aparecem de fato na janela inteira, porque só 40 linhas foram lidas.
- O formato do arquivo de cada categoria (PDF ou XML) e se o `downloadDocumento` funciona fora do navegador para fundos: nenhum download foi feito.
- Como ligar documento e classe sem CNPJ na linha, e se `descricaoFundo` repete o nome do cadastro da CVM.
- Como aparecem na grade os documentos de fundo, e não de classe: as 40 linhas eram de classe.
- Se o servidor aceita os nomes longos (`draw`/`start`/`length`) que o coletor do Enrico usa.
- Os termos de uso gerais da B3.
- O limite de taxa: 10 requisições, uma a cada 5 s, não deram sinal de limite, mas isso não diz qual seria o limite de uma coleta.
