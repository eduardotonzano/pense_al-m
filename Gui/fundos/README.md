# Fundos (FIDC, FIC-FIDC, FIAGRO): base do módulo

Dono da frente: Gui (`docs/decisoes-em-aberto.md`, decisão 1 de Fundos). O nome da pasta (`Gui/fundos`) e o do pacote Python (`fundos`) são **provisórios**: o nome definitivo é do Gui. Veja "Como renomear".

## O que existe

- Banco SQLite próprio, criado pela migration `migrations/001_initial_schema.sql`, com o mesmo esqueleto de proveniência das debêntures: `sources`, `collection_runs`, `raw_records`, `observations`, `data_conflicts`, `audit_log`, a view `current_observations` e `schema_migrations`. Os assuntos são `funds`, `fund_classes` e `quota_series`.
- A migration `migrations/002_party_observations.sql` cria `party_observations` (papéis com vários valores: gestor, administrador, custodiante, controlador e auditor) e `party_conflicts`. Veja "Papéis".
- A migration `migrations/003_party_observation_shares.sql` cria `party_observation_shares`, com o percentual do cedente do informe de FIDC, 1:1 com a linha do cedente em `party_observations`. Veja "Papéis".
- A migration `migrations/004_holdings.sql` cria `holdings` e `confidential_holdings` (posições em cotas de fundos do CDA, identificadas e confidenciais), cada uma com a sua tabela de conflitos. Veja "Como carregar o CDA".
- A migration `migrations/006_quota_class_map.sql` cria o `quota_class_map`, o mapa das séries de FIDC para sênior, mezanino ou subordinada, com as 4 regras iniciais como `proposto`. A 005 continua reservada (veja "Como aplicar a migration"). Veja "Mapa das séries (`quota_class_map`)".
- `src/fundos/`: conexão (`database.py`), utilitário de CNPJ (`cnpj.py`), guarda de dados pessoais (`personal_data.py`), backup (`backup.py`) e repositórios mínimos (`repositories/`).
- `src/fundos/cvm_csv.py`: leitura comum dos CSV da CVM (cp1252 estrito, cabeçalho exato, largura das linhas, conversão por tipo, situação do identificador), usada pelo cadastro e pelo informe.
- `src/fundos/cadastro/`: leitor do cadastro de fundos da CVM (`registro_fundo_classe.zip`), sem banco (`reader.py`, com a lista fechada de colunas em `columns.py`); filtro de FIDC e FIAGRO e escolha do registro vigente (`selection.py`); gravação (`loader.py`); e relatório só com agregados (`report.py`).
- `src/fundos/informe_fidc/`: leitor do informe mensal de FIDC (`inf_mensal_fidc_AAAAMM.zip`, 18 tabelas), sem banco (`reader.py`, com a lista fechada das 461 colunas em `columns.py`); gravação (`loader.py`); e relatório só com agregados (`report.py`).
- `src/fundos/informe_fiagro/`: leitor do informe mensal de FIAGRO (`inf_mensal_fiagro_AAAAMM.zip`, 2 arquivos), sem banco (`reader.py`, com a lista fechada das 133 + 6 colunas em `columns.py`); gravação (`loader.py`), com a reapresentação (`compare.py`, FU5.3); e relatório só com agregados (`report.py`).
- `src/fundos/cda/`: leitor do CDA da CVM (`cda_fi_AAAAMM.zip`, 12 membros, dos quais só o `cda_fie` e o `cda_fie_CONFID` são lidos), sem banco (`reader.py`, com a lista fechada de colunas em `columns.py`); gravação das posições em cotas de fundos (`loader.py`, com `repositories/holding_repository.py`); e relatório só com agregados (`report.py`).
- `src/fundos/fic_fidc/`: a classificação de FIC-FIDC (decisão 6 de Fundos) e a conferência das posições do CDA em cotas de FIDC com a `tab_I`, calculadas na leitura, sem gravar nada, e a fila de revisão manual no `audit_log`. Veja "FIC-FIDC e conferência do CDA".
- `src/fundos/indicators/`: indicadores calculados na leitura a partir do informe de FIDC já carregado (vencidos na carteira, faixas de atraso, a distribuição "Por Prazo de Vencimento (R$)", os cedentes gravados, as alienações do mês a partes relacionadas e a "Provisão para Redução no Valor de Recuperação" com a cobertura dos vencidos), sem gravar nada. Veja "Indicadores de carteira vencida", "Cedentes e alienações a partes relacionadas" e "Provisão para Redução no Valor de Recuperação e cobertura".
- `src/fundos/indicators/subordinacao.py`: a subordinação das classes de FIDC pelas séries da `tab_X_2`, classificadas pelo `quota_class_map`, calculada na leitura. `scripts/report_subordinacao.py` mostra o relatório, só lendo o banco. Veja "Subordinação (FU6.3)".
- `scripts/apply_migration.py`: aplica as migrations numeradas, com backup e verificação.
- `scripts/load_cadastro.py`: carrega os FIDC e FIAGRO do cadastro. Veja "Como carregar o cadastro".
- `scripts/load_informe_fidc.py`: carrega o informe mensal de FIDC. Veja "Como carregar o informe de FIDC".
- `scripts/load_informe_fiagro.py`: carrega o informe mensal de FIAGRO. Veja "Como carregar o informe de FIAGRO".
- `scripts/load_cda.py`: carrega as posições em cotas de fundos do CDA. Veja "Como carregar o CDA" e, para o primeiro banco real, "Banco real".
- `scripts/classify_fic_fidc.py`: mostra a classificação de FIC-FIDC e a conferência do CDA, só com contagens, e grava a fila de revisão manual. Veja "FIC-FIDC e conferência do CDA".
- `src/fundos/quota_classes/`: as regras do `quota_class_map`, a classificação de um rótulo de série, o relatório de revisão e a revisão de uma regra. `scripts/report_quota_class_map.py` mostra o relatório, só lendo o banco, e `scripts/review_quota_class_map.py` grava a revisão de uma pessoa. Veja "Mapa das séries (`quota_class_map`)".

## O que ainda não existe

Coletor, acesso à rede e adaptador para a camada compartilhada. O banco real existe desde 25/11/2026, com o cadastro de 27/10/2026 e o CDA de 10/2026. O informe de FIDC ainda **não** está carregado nele; essa carga fica para outra etapa (veja "Banco real").

Ficam para etapas futuras do plano de Fundos:

- a migration de prioridade das fontes (ADR-010, proposta);
- o `registro_subclasse` como dado (hoje só entra no manifesto);
- na reapresentação do informe: registrar no banco a célula que sumiu, guardar o conjunto exato de cedentes de cada ZIP e unir a série que trocou de rótulo à antiga (hoje só são contados; cada um exigiria uma migration nova, com o próximo número livre na hora (a 004 é a das holdings, a 005 está reservada à prioridade de fontes do ADR-010, ainda proposta, e a 006 é a do `quota_class_map`), se o módulo de Fundos decidir);
- **dívida da reapresentação (FU5.3):** a regra de ordem do `--last-modified` (e a mensagem dela) está duplicada entre o informe de FIDC e o de FIAGRO (`reapresentation_problem` nos dois `loader.py`), e a comparação do FIAGRO (`informe_fiagro/compare.py`) repete a estrutura da do FIDC. Fica assim de propósito, para não mexer no FIDC; a extração para uma parte comum fica para quando houver um terceiro uso;
- as classes de chave repetida no arquivo de FIAGRO **com a mesma `Versao`** (ou empate na maior, ou `Versao` vazia) e as subclasses delas (2 classes e 9 linhas de subclasse em 09/2026, as duas com a mesma `Versao`): só contadas, até decisão do módulo de Fundos;
- a comparação, na leitura, entre o informe de FIAGRO e o de FIDC e entre o informe e o cadastro (gestor e administradora): a conferência foi feita na FU5.2 (seção 10.5 de `docs/fundos-descoberta.md`) e o Gui decidiu em 04/11/2026 que vale o informe que corresponde ao `Tipo_Classe` e, para gestor e administradora, o cadastro vigente (F-03 e F-05 de `docs/regras-de-exibicao-pendentes.md`). Nada disso está no código: o banco não compara os informes, a comparação fica na camada de leitura (FU9.2) e a view de valor atual dos papéis entra antes da FU9.1. O informe de FII foi amostrado (seção 13 de `docs/fundos-descoberta.md`) e não é carregado;
- a `tab_VIII` e a `tab_X_4` do informe, lidas e conferidas mas **não carregadas** (várias linhas para o mesmo assunto e campo). A `tab_X_4` (captações, resgates e amortizações por série) fica **indisponível** até uma tarefa própria, com ADR (uma dimensão a mais em `observations`);
- o uso do percentual do cedente em contas e as métricas de concentração: pela decisão de 24/11/2026 (FU11.2), o percentual é só mostrado como informado, com qualificador, até a base dele ser confirmada, e não há métrica de concentração. A forma de exibir continua em aberto;
- **pendência do FIAGRO nos indicadores de carteira vencida (FU11.1):** os campos `Vencidos_*`, `A_Vencer_*` e `Total_Ativos_Prazo_Vencimento` do informe de FIAGRO ficaram fora por falta de descrição oficial. O dicionário de FIAGRO descreve 13 dos 133 campos, e nenhum destes. A inclusão depende da leitura do Anexo Normativo VI da Resolução CVM 175 e do modelo do informe de FIAGRO, que exige aprovação de rede;
- a evolução das faixas de atraso conferida no dado real: o banco de teste tem uma competência só do informe de FIDC (09/2026). Uma segunda exige baixar outro mês (rede, com aprovação) e carregá-lo numa cópia;
- a política de volume: retenção e frequência das cargas (o cadastro grava o retrato inteiro a cada carga; o informe, cerca de 0,6 GB por competência);
- a revisão das 4 regras iniciais do mapa das séries por uma pessoa (hoje as 4 estão como `proposto`) e a 006 no banco real. A subordinação calculada já existe (veja "Subordinação (FU6.3)"); no banco real, ela espera a 006 e a carga do informe de FIDC;
- a resolução de conflitos com `audit_log`;
- a resolução da fila de revisão manual de FIC-FIDC: a decisão de uma pessoa, como entrada MANUAL, só vem depois da migration 005 (ADR-010). Hoje a fila só recebe os assuntos (veja "FIC-FIDC e conferência do CDA").

A tabela dos fundos da casa não entra neste módulo (veja "Regras").

## Regras do banco

- **Identidade só por CNPJ**, com 14 caracteres e sem máscara: os 12 primeiros em `[0-9A-Z]` (maiúsculas) e os 2 últimos, os dígitos verificadores, numéricos.
  - O CNPJ alfanumérico (IN RFB 2.229/2024) é aceito por decisão de implementação de 27/10/2026, registrada por Eduardo, a confirmar com o Gui.
  - A amostra de 09/2026 (`docs/fundos-descoberta.md`, seção 10) não tem nenhum CNPJ alfanumérico; esse caminho só é exercitado por dados fictícios.
  - O exemplo de referência dos testes, `12.ABC.345/01DE-35`, vem de material técnico de terceiros, não de norma conferida no repositório.
- **Normalização do CNPJ** (`cnpj.py`) é uma proposta, não uma decisão.
  - Aceita os 14 caracteres ou a máscara completa `NN.NNN.NNN/NNNN-NN`, converte para maiúsculas e exige dígito verificador válido.
  - Completar zeros à esquerda só acontece quando pedido, e só para entradas numéricas de 12 ou 13 dígitos. Nunca para 11 dígitos, que podem ser CPF.
- **`field_name` = `tabela.coluna` da CVM**, sem renomear e sem mudar maiúsculas (por exemplo `tab_IV.TAB_IV_A_VL_PL`).
- **Valor ausente não tem linha.** Nada é estimado.
- **Proveniência:** cada observação tem fonte, coleta (`collection_run_id`), manifesto do arquivo (`raw_record_id`), competência (`reference_date`) e data de coleta (`collected_at`). A fonte MANUAL também exige coleta e manifesto da evidência.
- **Valor atual** (`current_observations`): prioridade da fonte, depois competência mais recente, depois coleta mais recente; só fontes ativas.
  - Fontes semeadas: `CVM_DADOS_ABERTOS` (200) e `MANUAL` (1000). A escala é provisória até o ADR de prioridade das fontes.
  - Com a prioridade em primeiro lugar, um valor manual de competência antiga continua valendo sobre um valor mais novo da CVM.
- **Nunca sobrescreve.** Mesmo assunto, campo e competência com valor diferente (reapresentação na mesma fonte ou divergência entre fontes) gera uma linha nova e um conflito aberto em `data_conflicts`. Triggers bloqueiam UPDATE e DELETE em `observations`.
  - Limitação conhecida: se o valor antigo volta depois de um conflito (A, depois B, depois A de novo), não há linha nova; o conflito A×B continua aberto e a view mostra B. As cargas dos informes de FIDC e de FIAGRO tratam esse caso (veja "Reapresentação" em cada uma); o cadastro continua com a limitação.
- **CPF nunca é gravado** (`docs/decisoes-em-aberto.md`, decisão 3 de Fundos).
  - Nenhuma coluna tem `cpf` no nome.
  - Não são carregados: `Diretor`, `Email_Administrador`, `Site`, `Servico_Atendimento_Cotista` e `Entidade_Administradora`.
  - Coluna de identificação (com `cpf` ou `cnpj` no nome) só aceita CNPJ válido já normalizado.
  - Quem garante isso: a guarda em `personal_data.py`, o trigger `trg_observations_personal_data` e os testes.
  - A guarda não reconhece o nome de gestor ou auditor pessoa física, que depende de outra coluna da mesma linha. Isso fica com o leitor do cadastro (`src/fundos/cadastro/reader.py`), que descarta o CPF, o nome do gestor PF e todo nome de papel sem CNPJ válido antes de chegar aos repositórios. Do gestor PF só fica a observação `registro_fundo.Tipo_Pessoa_Gestor` = PF.
  - Antes do COMMIT, a carga procura texto inteiro com formato de CPF (11 dígitos ou a máscara) no que gravou e, se achar, desfaz tudo.
- **`raw_records` guarda só o manifesto do arquivo** (nome, tamanho, SHA-256, número de linhas), nunca o conteúdo.
  - **Decidido em 03/11/2026** (`docs/decisoes-em-aberto.md`, decisão 3): a regra do CPF vale também para o arquivo original da CVM. O banco e o `raw_records` guardam só o manifesto, nunca o conteúdo; os arquivos originais ficam fora do Git e fora de pasta de rede, em pasta local de acesso restrito; não há regra de apagar o original depois da leitura.
- **Papéis** (`party_observations`, migration 002): uma linha por papel, com assunto (fundo ou classe), papel, campo do identificador (`tabela.coluna` da CVM), CNPJ da parte e, quando houver, o nome e o campo do nome, mais a mesma proveniência de `observations`. Imutável; só CNPJ (CHECK no banco e guarda no repositório).
  - A chave é assunto + papel + campo + CNPJ + competência; o valor é o nome. Nome diferente na mesma chave gera linha nova e conflito aberto em `party_conflicts`.
  - Limitação conhecida: uma parte que some numa reapresentação **da mesma competência** não gera conflito, porque as linhas se somam. Entre competências diferentes, o conjunto de cada data é exato.
  - **Percentual do cedente** (`party_observation_shares`, migration 003): tabela nova, e não coluna nova, porque `apply_migration.py` recusa DDL alterado em objeto existente. Uma linha por cedente com percentual, presa à linha do papel (chave primária = `party_observation_id`), imutável.
    - Só o papel `cedente` tem percentual, e o cedente não tem nome (triggers no banco e guarda no repositório).
    - O percentual entra no checksum da linha **só quando existe**: o checksum dos outros papéis é o mesmo de antes da 003. E só entra logo depois da linha do cedente (trigger `trg_party_observation_shares_with_parent`), então uma linha gravada sem percentual não ganha percentual depois.
    - Percentual diferente (ou um com e outro sem) na mesma chave gera linha nova e conflito aberto em `party_conflicts`, como o nome nos outros papéis.
    - Limitação conhecida: cedente que muda de posição ou some numa reapresentação da mesma competência não gera conflito (a posição está no campo).
    - **O conjunto de cedentes de uma competência no banco é a soma dos ZIPs carregados dela**, não o do ZIP mais novo: o cedente que saiu continua lá, e a linha igual fica presa ao ZIP que a gravou primeiro, então o conjunto do ZIP mais novo não pode ser reconstruído. Isso importa para as métricas de concentração (Gui).
    - Banco só com 001 e 002 continua servindo ao cadastro: o repositório percebe que a tabela não existe e só recusa gravar percentual.
- **Fundos da casa ficam fora** deste banco e de qualquer arquivo versionado (`docs/decisoes-em-aberto.md`, decisões 2 e 4 de Fundos). O caminho da pasta interna vai só na variável de ambiente `PENSE_INTERNAL_DIR`; este módulo ainda não a lê.
- **O banco real fica fora do Git e em disco local**, não no compartilhamento de rede (veja "Banco real"). Não versionar `*.db`, `*.sqlite*`, ZIPs, CSVs da CVM, backups nem `.env` (veja `.gitignore`).

## Como testar

Sem instalação: o `pyproject.toml` põe `src` no caminho do pytest, e o módulo usa só a biblioteca padrão.

```powershell
cd Gui\fundos
& C:\Users\eduardo.tonzano\debenture-venv\Scripts\python.exe -m pytest -q
```

Não instale este módulo no `debenture-venv` e não reinstale pacote nenhum nele. Se um dia for preciso instalar, use um venv próprio fora do compartilhamento de rede (`py -m venv C:\Users\<voce>\fundos-venv` e depois `pip install -e "Gui\fundos[dev]"`).

Os testes usam só bancos sintéticos em pasta temporária e CNPJs fictícios. Nenhum teste abre banco real ou acessa a rede.

## Como aplicar a migration

Não existe banco padrão: `--database` é obrigatório, e `--dry-run` ou `--commit` também. Rode sempre o `--dry-run` antes. O `--commit` só com aprovação explícita.

```powershell
cd Gui\fundos
# banco novo: primeiro verifica numa pasta temporária, sem criar nada
python scripts\apply_migration.py --database C:\<pasta-local>\fundos.db --create --dry-run
python scripts\apply_migration.py --database C:\<pasta-local>\fundos.db --create --commit
# banco existente
python scripts\apply_migration.py --database C:\<pasta-local>\fundos.db --dry-run
python scripts\apply_migration.py --database C:\<pasta-local>\fundos.db --commit
```

- `--dry-run` aplica e verifica numa cópia temporária; o banco informado não muda.
- `--commit` faz o backup antes (`backups\fundos_<UTC>.sqlite3` ao lado do banco, ou a pasta de `--backup-dir`) e aplica tudo numa transação.
- Antes do COMMIT, confere `integrity_check`, `foreign_key_check`, a versão registrada, que nada do que existia mudou (a não ser com `--allow-existing-changes`) e que nenhuma coluna tem `cpf` no nome. Se algo falhar, desfaz e mantém o backup.
- **Caminho de rede e caminho longo:** o script recusa antes de tocar no banco, no `--dry-run` também (saída 1):
  - `--database` ou o destino do backup (`--backup-dir` ou `backups` ao lado do banco) em caminho de rede: `\\servidor\...`, um caminho relativo rodado de dentro do compartilhamento ou uma unidade mapeada remota;
  - o caminho do banco ou do backup que, com `-journal`, chega a 260 caracteres.

  O `--dry-run` também recusa a pasta temporária em rede, porque a cópia de teste vai para ela. A mensagem traz só o parâmetro e o motivo, nunca o caminho. Use pasta local curta, também no `--backup-dir` (por exemplo `C:\pense\bk\fundos`).
- Nova migration: novo arquivo `migrations/NNN_nome.sql` que termina com `INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(NNN,'nome');`. Nunca edite uma migration já aplicada.
- **Lacuna na numeração:**
  - **A 005 está reservada** para a prioridade de fontes (ADR-010), e a 006 (`quota_class_map`) é aplicada sem ela.
  - **O runner** aplica, em ordem de número, toda migration que o banco ainda não registrou. Quando a 005 existir, ela entra depois da 006; as duas são independentes (a 005 mexe na prioridade da fonte e na view `current_observations`, a 006 só cria o mapa).
  - **Testes ajustados:** os testes das migrations que já existiam passaram a esperar a 006.
    - A lista de versões `[1, 2, 3, 4]` virou `[1, 2, 3, 4, 6]` em 5 asserções.
    - A lista das migrations da pasta ganhou a 006.
    - O teste da 004 com dados passou a usar uma pasta só com 001 a 004, como o da 003 já fazia.

## Como carregar o cadastro

O `scripts/load_cadastro.py` lê o `registro_fundo_classe.zip` da CVM (baixado à mão, fora do Git), escolhe os FIDC e FIAGRO vigentes e grava fundos, classes, observações e papéis. `--database`, `--zip` e `--reference-date` são obrigatórios, e `--dry-run` ou `--commit` também. Rode sempre o `--dry-run` antes. O `--commit` só com aprovação explícita.

```powershell
cd Gui\fundos
# prévia: lê o ZIP e imprime só agregados; não escreve em banco nenhum
python scripts\load_cadastro.py --database C:\<pasta-local>\fundos.db --zip C:\<pasta-local>\cvm-amostras\cadastro-fidc\registro_fundo_classe.zip --reference-date 2026-10-27 --dry-run
# carga (banco já criado e migrado com scripts\apply_migration.py)
python scripts\load_cadastro.py --database C:\<pasta-local>\fundos.db --zip C:\<pasta-local>\cvm-amostras\cadastro-fidc\registro_fundo_classe.zip --reference-date 2026-10-27 --commit
```

- **Banco em disco local.** SQLite em compartilhamento de rede não é seguro (trava e journal). O script recusa antes de ler o ZIP, no `--dry-run` também (saída 1):
  - `--database` ou o destino do backup (`--backup-dir` ou `backups` ao lado do banco) em caminho de rede: `\\servidor\...`, um caminho relativo rodado de dentro do compartilhamento ou uma unidade mapeada remota;
  - caminho longo.

  A mensagem traz só o parâmetro e o motivo, nunca o caminho. Use uma pasta local, como nos exemplos.
- **`--reference-date`** é a competência do retrato: a data do `Last-Modified` do ZIP na CVM (para o arquivo de 27/10/2026, `2026-10-27`), nunca a data da coleta (ADR-010).
  - É recusada se for posterior a hoje (UTC) ou anterior ao maior `Data_Registro` do arquivo.
  - Se a data dos membros dentro do ZIP for diferente, o script avisa e segue.
- **`--dry-run`:**
  - lê o ZIP em memória e escolhe os vigentes;
  - se o banco existir, só o lê (`PRAGMA query_only`) para dizer se o `--commit` seria aceito;
  - se não existir, não cria nada.
- **`--commit`:**
  - recusa banco inexistente ou sem as migrations 001 e 002;
  - se o ZIP (mesmo SHA-256) já foi carregado, diz "Nada a carregar" e não faz backup; se foi carregado com outra competência, recusa;
  - senão, faz o backup (`backups\fundos_<UTC>.sqlite3` ao lado do banco, ou `--backup-dir`) e grava tudo numa transação;
  - antes do COMMIT, confere `integrity_check`, `foreign_key_check`, nenhuma coluna com `cpf` e nenhum texto com formato de CPF no que gravou;
  - se algo falhar, desfaz e mantém o backup.
- **Saída:** 0 (sucesso ou nada a fazer), 1 (erro, com "Erro ao carregar o cadastro: ..." no stderr), 2 (argumentos).
- **O relatório tem só agregados**, nunca CNPJ, nome ou valor:
  - linhas por CSV;
  - linhas por `Tipo_Fundo` e `Tipo_Classe`;
  - identificadores por coluna (vazio, CNPJ válido, CPF descartado, inválido), no arquivo inteiro e por FIDC e FIAGRO;
  - gestor PF e nomes descartados;
  - valores fora do formato em linhas fora do escopo;
  - vigentes por tipo, o que ficou fora e por quê;
  - os candidatos a gravar por tabela e tipo de valor;
  - no `--commit`, o que foi criado ou já existia e os conflitos abertos.
- **Regras da carga:**
  - **Escopo:** pelo par `Tipo_Fundo` e `Tipo_Classe`, nunca pelo nome.
  - **Registro vigente, por CNPJ:** prefere `Situacao` diferente de `Cancelado`; depois, o `Data_Inicio_Situacao` mais recente. Empate não entra.
  - **Classe:** só entra com o fundo vigente dela na carga.
  - **Formato:** valor fora do formato (data, número, S/N) aborta numa linha FIDC ou FIAGRO; fora do escopo, é contado e descartado. O cabeçalho tem de ser exato.
  - **Subclasse:** o `registro_subclasse.csv` entra só no manifesto (`processing_status` `ignored`).
  - **Volume:** cada carga grava o retrato inteiro na sua competência. A política de recarga (frequência, ou gravar só o que muda) fica para antes de automatizar.

## Como carregar o informe de FIDC

O `scripts/load_informe_fidc.py` lê o `inf_mensal_fidc_AAAAMM.zip` da CVM (baixado à mão, fora do Git) e grava as observações do mês, a administradora e os cedentes das classes e fundos que **já estão no banco**: o cadastro tem de ser carregado antes. `--database` e `--zip` são obrigatórios, e `--dry-run` ou `--commit` também. Não há `--reference-date`. `--last-modified` é o `Last-Modified` do ZIP na CVM: opcional na primeira carga da competência e obrigatório na reapresentação (veja "Reapresentação"); passe sempre. Rode sempre o `--dry-run` antes. O `--commit` só com aprovação explícita.

```powershell
cd Gui\fundos
# prévia: lê e confere o ZIP; com o banco, mostra o casamento com o cadastro (ou a comparação, se a competência já tiver ZIP); não escreve nada
python scripts\load_informe_fidc.py --database C:\<pasta-local>\fundos.db --zip C:\<pasta-local>\cvm-amostras\cadastro-fidc\inf_mensal_fidc_202609.zip --last-modified 2026-10-24T11:46:15Z --dry-run
# carga (banco migrado e com o cadastro carregado)
python scripts\load_informe_fidc.py --database C:\<pasta-local>\fundos.db --zip C:\<pasta-local>\cvm-amostras\cadastro-fidc\inf_mensal_fidc_202609.zip --last-modified 2026-10-24T11:46:15Z --commit
```

- **Banco em disco local**, como no cadastro: banco ou backup em caminho de rede ou longo é recusado antes de ler o ZIP, no `--dry-run` também.
- **Competência = `DT_COMPTC`.** O arquivo tem de ter um só valor, do mês do `AAAAMM` dos 18 membros (e do nome do ZIP), não posterior a hoje (UTC). `collected_at` é o início da coleta.
- **Formato:** os 18 membros e só eles; o cabeçalho de cada tabela tem de ser exatamente o da lista fechada (`src/fundos/informe_fidc/columns.py`, montada do cabeçalho do dado de 09/2026, não do dicionário). Qualquer diferença aborta sem gravar nada.
- **Identidade:** `TP_FUNDO_CLASSE` Classe precisa do CNPJ em `fund_classes`; Fundo, em `funds`. O resto não carrega e é contado por tabela e por assunto, em 6 motivos (Classe com CNPJ só como fundo, Classe fora do cadastro, Fundo com CNPJ só como classe, Fundo fora do cadastro, tipo desconhecido, CNPJ inválido). Nenhum fundo nem classe é criado.
- **O que vira observação:** `tab_<tabela>.<COLUNA>`, sem renomear. `TP_FUNDO_CLASSE`, `CNPJ_FUNDO_CLASSE` e `DT_COMPTC` são chave. `DENOM_SOCIAL` só da `tab_I` (nas outras 17 ela é conferida e a divergência é contada).
- **Zeros são gravados:** zero é valor informado (cerca de 80% das células do mês). Valor vazio não tem linha.
- **Notação científica** (`e` ou `E` seguido de expoente inteiro, como `1.5e+10`) é convertida de forma exata, sem arredondar e sem expoente, e contada por coluna no relatório. Qualquer outro formato fora do decimal com ponto aborta.
- **Cedentes** (as 36 colunas `TAB_I2A12_CPF_CNPJ_CEDENTE_1..9` e `TAB_I2A12_PR_CEDENTE_1..9`, com risco, e as mesmas `TAB_I2B12_*`, sem risco): o identificador da posição n vai com o percentual da posição n do mesmo grupo.
  - Só o cedente com **CNPJ válido** é gravado: uma linha em `party_observations` com papel `cedente`, campo = coluna real do identificador com a posição (por exemplo `tab_I.TAB_I2A12_CPF_CNPJ_CEDENTE_3`), sem nome, no mesmo assunto e com a mesma proveniência da administradora. O percentual vai em `party_observation_shares` (migration 003).
  - Regra de implementação: **11 dígitos ou máscara de CPF são tratados como CPF e descartados, mesmo que fechem como CNPJ com zeros** (7 casos em 09/2026). 12 ou 13 dígitos com DV válido ganham os zeros à esquerda. Vazio ou inválido não tem linha.
  - Percentual: decimal exato, como veio (notação científica convertida, como nas outras colunas numéricas); **formato inválido aborta a carga**, como em qualquer coluna numérica. Negativo ou acima de 100 é gravado como veio e contado no relatório.
  - Identificador gravável sem percentual: a linha é gravada sem percentual. Percentual sem identificador gravável (vazio, CPF ou inválido): só contado, nada é gravado.
  - O mesmo CNPJ em duas posições, ou nos dois grupos, vira linhas separadas (o campo é outro) e é contado.
  - O relatório mostra, por grupo, só contagens: identificador CNPJ (com os zeros restaurados), CPF descartado, inválido, percentual com e sem identificador, identificador sem percentual, percentual negativo e acima de 100, CNPJ repetido; e o total de células preenchidas, que fecha com essas contagens.
  - **Achado de 09/2026** (medição só de leitura, em memória): 7.452 células preenchidas; 3.605 cedentes com CNPJ válido (2.476 com risco e 1.129 sem risco), todos com percentual; 120 valores de 11 dígitos. Nos percentuais preenchidos: mínimo 0, **máximo de cerca de 17,5 milhões**, **385 acima de 100** (306 com risco e 79 sem risco), zeros 75 e 67, nenhum negativo. Em parte das linhas a coluna não traz um percentual. **A regra para usar o percentual em métricas de concentração é do Gui**; esta carga não decide nada sobre isso.
- **Administradora:** `tab_I.CNPJ_ADMIN` e `tab_I.ADMIN` vão para `party_observations` (papel `administrador`), só com CNPJ válido. `tab_I.CNPJ_CLASSE` vira observação só com CNPJ válido (espaços nas pontas tirados; zero à esquerda só para 12 ou 13 dígitos); senão a célula é contada e não carregada.
- **Séries** (`tab_X_1`, `tab_X_2`, `tab_X_3` e `tab_X_6`): a chave é o rótulo normalizado (sem acento, minúsculo, sem `|`, espaços colapsados); o rótulo original de cada tabela fica como observação da série. Regra do `ID_SUBCLASSE` (só na `tab_X_1`):
  - vira `cvm_subclass_id` só quando aparece num único assunto e rótulo do arquivo (em 09/2026, 63 IDs aparecem em mais de uma classe e não viram chave);
  - se o banco o recusar (por exemplo, o mesmo ID já é de outra série), a série fica só com o rótulo, as linhas são carregadas, o relatório conta "recusado pelo banco" e a coleta fica `partial`, com `failed_items` igual ao número de IDs recusados;
  - em todos os casos, `tab_X_1.ID_SUBCLASSE` é gravado como observação.
- **Não carregadas:** `tab_VIII` e `tab_X_4` são lidas e conferidas, entram no manifesto como `ignored` e ficam fora do banco (veja "O que ainda não existe").
- **Mesmo ZIP:** o mesmo ZIP (mesmo SHA-256) diz "Nada a carregar" e não faz backup. Uma competência nova é carga normal (série mensal).
- **Reapresentação (FU4.2; proposta, o Gui precisa confirmar):** a CVM troca o ZIP toda semana no mesmo endereço, e um fundo pode corrigir o informe do mês. Outro ZIP de uma competência já carregada é aceito, assim:
  - **`--last-modified` obrigatório:** o `Last-Modified` do ZIP na CVM, com fuso, em ISO (`2026-10-29T11:46:15Z`) ou no texto do cabeçalho HTTP (`Thu, 29 Oct 2026 11:46:15 GMT`). Sem fuso, ou posterior a agora, é recusado. O dry-run e o commit mostram a data que será gravada, em UTC, e ela vai para `raw_records.last_modified` do ZIP.
  - **Ordem:** tem de ser estritamente posterior ao maior `Last-Modified` dos ZIPs já carregados da competência; senão a carga é recusada, com as duas datas na mensagem. Carregar um ZIP mais antigo depois de um mais novo faria o valor antigo virar o atual (a view escolhe a coleta mais recente).
  - **ZIP carregado antes da FU4.2** (sem `last_modified`): o novo tem de ser posterior ao início da carga dele. Ele foi baixado antes de ser carregado, então o `Last-Modified` dele é anterior a essa hora; se o novo não for posterior, não dá para provar a ordem e a carga é recusada.
  - **Aviso:** se a data dos membros do ZIP passar da do `--last-modified` em mais de 1 dia, o script avisa no stderr e segue.
  - **Comparação** (`src/fundos/informe_fidc/compare.py`): cada célula, papel, assunto e série do ZIP novo é comparado com o último valor carregado desta fonte na competência. O banco é lido tabela por tabela, pelos manifestos dos ZIPs já carregados.
  - **O que é gravado:** a célula igual não é gravada de novo (continua presa ao ZIP que a gravou primeiro); a alterada vira linha nova e conflito aberto em `data_conflicts`; a nova é gravada; a que **volta** a um valor anterior (A, depois B, depois A) vira linha reapresentada, com a coleta no checksum, e passa a ser o valor atual, sem abrir de novo o conflito A×B. O mesmo vale para administradora e cedente, por posição. ZIP igual em valores grava só a coleta, os 19 manifestos e o `last_modified`.
  - **O que só é contado** (nada é apagado): a célula que tinha valor e vem vazia ou sem a linha (o valor atual continua o último informado), o assunto que some (as observações dele continuam como valor atual da competência), a série nova e a que sumiu no mesmo assunto (possível troca de rótulo: a série nova fica duplicada até alguém tratar), o ID_SUBCLASSE que aparece numa série existente (a chave da série é preenchida) ou que some (a chave fica), e o papel que entrou, saiu, trocou de CNPJ na posição ou mudou de nome ou percentual.
  - **Relatório:** a seção "Reapresentacao" do dry-run e do commit mostra só contagens, por tabela e no total.
  - **Volume:** só crescem as células alteradas, novas e que voltam (cerca de 360 bytes por observação, com índices), mais os conflitos e 19 manifestos. O backup continua copiando o banco inteiro a cada `--commit`.
  - **Medido com dados fictícios, em disco local** (1,54 milhão de células já carregadas; segundo ZIP com 4.312 células alteradas, 17.550 novas e 88 assuntos a menos): o dry-run leu o ZIP em 6,6 s e comparou em 19,2 s, com pico de 203 MiB no processo; a segunda carga levou 54 s (a primeira, 375 s), criou 21.862 observações e o banco cresceu 8,1 MiB, com pico de 412 MiB (inclui o cache de 200 MB da carga).
- **Versão do leitor:** o manifesto guarda `fundos.informe_fidc.v2`. Competência carregada por versão anterior (a v1, sem cedentes), com o mesmo ZIP ou com outro, é recusada: esta versão não atualiza esse carregamento; use um banco novo e carregue de novo.
- **Migrations:** o informe exige 001, 002 e 003 (o cadastro continua exigindo só 001 e 002). Banco sem a 003: aplique antes com `scripts/apply_migration.py`.
- **Antes do COMMIT:** `integrity_check`, `foreign_key_check`, nenhuma coluna com `cpf` e nenhum texto inteiro com formato de CPF no que a coleta gravou (inclusive percentual de cedente de 11 dígitos). Se algo falhar, desfaz tudo e mantém o backup. A mensagem cita só as contagens.
- **Andamento:** uma linha por tabela lida (`lido tab_IX: ... linha(s)`) e, no `--commit`, uma por tabela gravada (`gravado tab_IX: ... observacao(oes), ... s`).
- **Tamanho e tempo:** cerca de 0,6 GB por competência (1,57 milhão de observações em 09/2026). Medido com dados fictícios do volume real (1,56 milhão de observações), em disco local: o banco cresceu 0,56 GB, o `--commit` completo (backup, carga e verificação) levou 7,3 min e o `--dry-run`, 15 s. Sem inserção em lote.

## Como carregar o informe de FIAGRO

O `scripts/load_informe_fiagro.py` lê o `inf_mensal_fiagro_AAAAMM.zip` da CVM (baixado à mão, fora do Git) e grava as observações do mês, as subclasses, a administradora e a gestora das classes que **já estão no banco**: o cadastro tem de ser carregado antes. `--database` e `--zip` são obrigatórios, e `--dry-run` ou `--commit` também. Não há `--reference-date`. `--last-modified` é o `Last-Modified` do ZIP na CVM: opcional na primeira carga da competência e obrigatório na reapresentação (veja "Reapresentação (FU5.3)"); passe sempre. Rode sempre o `--dry-run` antes. O `--commit` só com aprovação explícita. As regras abaixo (as da FU5.1 e, para a reapresentação e a `Versao`, as da FU5.3) valem como **proposta, a confirmar pelo módulo de Fundos**.

```powershell
cd Gui\fundos
# prévia: lê e confere o ZIP; com o banco, mostra o casamento com o cadastro (ou a comparação, se a competência já tiver ZIP); não escreve nada
python scripts\load_informe_fiagro.py --database C:\<pasta-local>\fundos.db --zip C:\<pasta-local>\cvm-amostras\fiagro\inf_mensal_fiagro_202609.zip --last-modified 2026-10-24T11:46:15Z --dry-run
# carga (banco migrado e com o cadastro carregado)
python scripts\load_informe_fiagro.py --database C:\<pasta-local>\fundos.db --zip C:\<pasta-local>\cvm-amostras\fiagro\inf_mensal_fiagro_202609.zip --last-modified 2026-10-24T11:46:15Z --commit
```

- **Banco em disco local**, como no cadastro: banco ou backup em caminho de rede ou longo é recusado antes de ler o ZIP, no `--dry-run` também.
- **Competência:**
  - é o `AAAAMM` dos dois membros (e do nome do ZIP, quando segue o padrão `inf_mensal_fiagro_AAAAMM.zip`);
  - `Data_Referencia` tem de ter um só valor nos dois arquivos, **o dia 1 desse mês**; senão o arquivo é recusado e nada é lido;
  - a competência gravada (`reference_date`) é o **último dia do mês** (`2026-09-30`), a mesma convenção do `DT_COMPTC` do FIDC, para que os dois informes do mesmo mês empatem na data;
  - **a data gravada não é a literal do arquivo** (`2026-09-01`): a literal é reconstruível, porque o leitor só aceita o dia 1;
  - não pode ser posterior a hoje (UTC); `collected_at` é o início da coleta.
- **Formato:** os 2 membros e só eles (`inf_mensal_fiagro_AAAAMM.csv`, 133 colunas, e `inf_mensal_fiagro_subclasse_AAAAMM.csv`, 6 colunas), cp1252 estrito, com o cabeçalho exatamente o da lista fechada (`src/fundos/informe_fiagro/columns.py`, montada do cabeçalho do dado de 09/2026, não do dicionário, que descreve só 13 dos 133 campos). Qualquer diferença aborta sem gravar nada.
- **Identidade:** o `CNPJ_Classe` tem de estar em `fund_classes`. Nenhum fundo nem classe é criado, e nunca se casa por nome. O resto não carrega e é contado por arquivo e por classe: `CNPJ_Classe` vazio, CPF ou inválido; chave repetida no arquivo; CNPJ só como fundo; CNPJ fora do cadastro carregado; e, na subclasse, sem linha no arquivo de classe, rótulo vazio e par (classe, rótulo) repetido.
- **Chave repetida (FU5.1, com a regra de `Versao` da FU5.3):** um `CNPJ_Classe` em mais de uma linha do arquivo de classe só entra quando todas as linhas têm `Versao` e a maior `Versao` (comparada como número) está numa linha só.
  - Entra essa linha. As outras ficam fora como "versao anterior no mesmo arquivo", e as subclasses da classe ficam fora como "subclasse de classe com mais de uma Versao no arquivo": o arquivo de subclasse não tem `Versao`, então não dá para ligar a subclasse a uma versão. As duas são contadas, e o `error_summary` da coleta traz `linhas_de_versao_anterior_nao_carregadas` e `subclasses_de_classe_com_mais_de_uma_versao`.
  - Com a mesma `Versao` nas linhas, empate na maior ou `Versao` vazia, continua a regra da FU5.1: nenhuma das linhas nem as subclasses entram, e a coleta fica `success`, com `chaves_repetidas_nao_carregadas` no `error_summary`. São os 2 casos de 09/2026.
  - `Data_Entrega` e nome não escolhem nada. O relatório conta as chaves, as linhas, as chaves com `Versao` diferente e as escolhidas pela `Versao`.
  - Na amostra de 09/2026 não há `Versao` 1 e 2 da mesma classe no mesmo ZIP: a regra só foi provada com dado fictício e com ZIP fabricado.
- **O que vira observação:** `inf_mensal_fiagro.<Coluna>` (da classe) e `inf_mensal_fiagro_subclasse.<Coluna>` (da série), sem renomear: 123 das 133 colunas e 3 das 6.
  - `CNPJ_Classe` e `Data_Referencia` são chave.
  - `Nome_Classe` é observação da classe, como vem; o do arquivo de subclasse só é conferido, e a divergência é contada.
  - Os `field_name` não coincidem com os do FIDC (`tab_*`) nem com os do cadastro (`registro_*`): a classe que está nos dois informes (1 em 09/2026) fica com os dois conjuntos, sem conflito falso.
- **Não carregadas:** `Email_Administrador`, `Site` e `Servico_Atendimento_Cotista` (contato, decisão 3 de Fundos) e `Entidade_Administradora` (traz telefone em parte das linhas). São exigidas no cabeçalho e descartadas sem serem guardadas nem contadas.
- **Valores:**
  - decimal exato, com a notação científica convertida e contada por coluna, como no FIDC; zero é valor informado e vazio não tem linha; número, data e S/N fora do formato abortam;
  - texto livre (`Regra_Anexo`, `Classificacao_Autorregulada`, `Prazo_Duracao`, `Encerramento_Exercicio_Social`) é gravado como vem, sem interpretar; nenhuma variante é derivada (decisão 7);
  - `Versao` (numérica) e `Data_Entrega` (data) são gravadas como observações comuns. A `Versao` escolhe a linha da chave repetida no mesmo ZIP e barra a classe de `Versao` menor numa reapresentação (veja "Reapresentação (FU5.3)"); `Data_Entrega` não ordena nada;
  - `Codigo_ISIN` é texto e não é chave nem identidade (em 09/2026, 3 ISIN aparecem em duas classes cada).
- **Papéis:** `CNPJ_Administrador` e `Nome_Administrador` (papel `administrador`) e `CNPJ_Gestor` e `Nome_Gestor` (papel `gestor`) vão para `party_observations` da classe, só com CNPJ válido.
  - CPF (11 dígitos ou máscara), vazio ou inválido é descartado junto com o nome e contado; a máscara do CNPJ é tirada; 12 ou 13 dígitos com DV válido ganham os zeros.
  - O gestor e a administradora do cadastro ficam no fundo (`registro_fundo.*`), com a data do retrato. Os do informe convivem com eles, cada um com a sua proveniência, sem conflito; a divergência foi medida na FU5.2 (seção 10.5 de `docs/fundos-descoberta.md`) e, pela decisão de 04/11/2026 (F-03 de `docs/regras-de-exibicao-pendentes.md`), o valor atual é o do cadastro vigente; o banco não compara os dois.
- **Subclasses:** cada linha vira uma série da classe (`quota_series`) pelo rótulo normalizado, com a regra do FIDC e sem ID da CVM (o arquivo não tem); o rótulo original fica como observação da série. Nada diz sênior ou subordinada: o mapa das séries (FU6.2, "Mapa das séries (`quota_class_map`)") cobre só o FIDC, e as subclasses de FIAGRO ficam sem mapa.
  - As duas grafias de "Subclasse 1" (`Subclasse 1 (ou classe única)` e `Subclasse 1(ou classe única)`) viram **chaves diferentes**. Em 09/2026 nenhuma classe tem as duas.
  - O par (classe, rótulo normalizado) repetido não entra (3 em 09/2026, todos nas chaves repetidas).
- **`--last-modified`:** a mesma normalização do FIDC (ISO com fuso, como `2026-10-24T11:46:15Z`, ou o texto do cabeçalho HTTP; sem fuso ou no futuro, recusado), gravado em `raw_records.last_modified` do ZIP e mostrado em UTC, com o aviso quando a data dos membros passa dela em mais de 1 dia. Na primeira carga da competência é opcional: sem ele, `raw_records.last_modified` fica vazio e o relatório diz "Last-Modified do ZIP: nao informado". Na reapresentação é obrigatório.
- **Mesmo ZIP:** o mesmo ZIP (mesmo SHA-256) diz "Nada a carregar" e não faz backup. Uma competência nova é carga normal, e as séries que já existem são reaproveitadas.
- **Reapresentação (FU5.3; proposta, a confirmar pelo módulo de Fundos):** a CVM troca o conjunto toda semana, e uma classe pode reenviar o informe do mês com outra `Versao`. Outro ZIP de uma competência já carregada é aceito com o mesmo mecanismo da reapresentação do FIDC (FU4.2), assim:
  - **`--last-modified` obrigatório e em ordem:** estritamente posterior ao maior `Last-Modified` dos ZIPs já carregados da competência; senão a carga é recusada antes do backup, com as duas datas na mensagem. O dry-run mostra as datas dos ZIPs já carregados.
  - **Competência carregada pela v1 (FU5.1) sem `last_modified`:** serve de base para a comparação, porque a v1 grava os mesmos `field_name`, séries e papéis. O ZIP novo tem de ser posterior ao início da carga dela (foi baixado antes de ser carregado). O manifesto passa a dizer `fundos.informe_fiagro.v2`; competência carregada por versão desconhecida do leitor é recusada.
  - **Comparação** (`src/fundos/informe_fiagro/compare.py`): cada célula, classe, série e papel do ZIP novo é comparado com o último valor carregado desta fonte na competência, lido pelos manifestos dos 2 arquivos dos ZIPs já carregados. Não lê `party_observation_shares`: o banco do FIAGRO continua precisando só das migrations 001 e 002.
  - **O que é gravado:** a célula igual não é gravada de novo; a alterada vira linha nova e conflito aberto em `data_conflicts`; a nova é gravada; a que volta a um valor anterior (A, depois B, depois A) vira linha reapresentada e passa a ser o valor atual, sem abrir de novo o conflito A×B. O mesmo vale para administrador e gestor, por posição. ZIP com outro SHA-256 e valores idênticos grava só a coleta, os 3 manifestos e o `last_modified`.
  - **`Versao` entre ZIPs:** a classe cuja `Versao` no ZIP novo é **menor** que a `Versao` atual dela na competência não entra (nem a linha, nem os papéis, nem as subclasses) e é contada como "Versao menor que a carregada"; o valor carregado continua o atual. `Versao` igual com célula alterada entra pela regra acima e é contada à parte, como a `Versao` que sobe.
  - **`Data_Entrega`:** é célula comum (se muda, abre conflito) e não ordena nada. A entrega que anda para trás com `Versao` igual ou maior é só contada.
  - **O que só é contado** (nada é apagado): a célula que tinha valor e vem vazia ou sem a linha, a classe que some (as observações dela continuam como valor atual), a série nova e a que sumiu na mesma classe (possível troca de rótulo) e o papel que entrou, saiu, trocou de CNPJ na posição ou mudou de nome. Na mesma competência, os papéis se somam (limitação já conhecida).
  - **Retidas:** as subclasses de uma classe com mais de uma `Versao` no ZIP e a classe barrada pela `Versao` menor não são comparadas. O que o banco tem delas é contado como "retidas", com o motivo, e **nunca** como célula ou série sumida nem como possível troca de rótulo.
  - **Relatório:** a seção "Reapresentacao" do dry-run e do commit mostra só contagens, por arquivo e no total.
  - **Dívida:** a regra de ordem do `--last-modified` está duplicada entre o loader do FIDC e o do FIAGRO, e a comparação do FIAGRO repete a estrutura da do FIDC (do FIDC só são importados as constantes e o `LatestValues`). A extração para uma parte comum fica para quando houver um terceiro uso.
  - **Não confirmado:** se a CVM tira a `Versao` 1 do conjunto quando chega a `Versao` 2; se a `Versao` de uma classe pode diminuir entre duas atualizações; se `Data_Entrega` muda sem mudar a `Versao`. A amostra tem um só instantâneo (27/10/2026), com 1 classe de `Versao` 2 sem a `Versao` 1 e nenhuma classe com as duas.
  - **Nenhuma reapresentação real da CVM foi testada.** As regras foram provadas só com dados fictícios (testes) e com ZIPs fabricados a partir do ZIP real de 09/2026, numa cópia do banco de teste (medição abaixo).
  - **Medido em 25/11/2026** numa cópia do banco de teste (o FIAGRO de 09/2026 carregado pela v1, sem `last_modified`; o original ficou com o SHA-256 igual antes e depois), com 4 ZIPs fabricados fora do Git a partir do ZIP real e `--last-modified` fictícios. Só contagens:
    - **Z1** (os mesmos CSV, outro SHA-256): 39.316 células iguais e nenhuma observação; só a coleta e os 3 manifestos.
    - **Z2** (100 células numéricas alteradas, 50 esvaziadas, 2 classes removidas, 1 série nova e 1 removida, `Versao` 2 sobre a 1, a mesma `Versao` com `Data_Entrega` nova, `Versao` 1 e 2 da mesma classe no arquivo, 1 nome e 1 CNPJ de gestor trocados): 105 células alteradas, 3 novas, 50 vazias, 2 classes sumidas (248 células), 3 séries sumidas e 2 retidas (as da classe com 2 `Versao`, nenhuma contada como sumida). Gravou 108 observações, 105 conflitos, 2 papéis e 1 conflito de papel.
    - **Z3** (o conteúdo real de volta): 101 células voltam, reapresentadas e sem conflito novo; 2 classes retidas pela `Versao` menor (241 células da classe e 18 de subclasse); 2 papéis de gestor voltam.
    - **Z4** (o real com a classe de `Versao` 2 baixada para 1): 3 classes retidas pela `Versao` menor, nenhuma observação.
    - **Recusas**, sem mudar o banco e sem backup: o mesmo ZIP ("Nada a carregar"), e outro ZIP com `--last-modified` anterior ao mais novo, sem `--last-modified`, sem fuso e no futuro.
    - **Verificador independente** (fora do Git, sem o código do módulo): recalculou dos CSV as contagens de cada carga e o crescimento do banco, e conferiu o valor atual da view em 39.319 chaves. Deu 0 divergências.
    - **Tempo:** o dry-run levou cerca de 3 s. O `--commit` levou de 3,5 a 4 min, quase todo no backup e na verificação do banco inteiro (664 MB). O banco cresceu no máximo 53 KB por carga.
- **Riscos conhecidos:**
  - se a grafia de "Subclasse 1" mudar de um mês para outro, nasce outra série para a mesma subclasse; unir as grafias seria uma regra nova, do Gui;
  - se o rótulo de uma série do FIDC e o de uma subclasse do FIAGRO da mesma classe normalizarem igual, os dois usam a mesma série (sem conflito, porque os campos são outros).
- **Migrations:** 001 e 002, como o cadastro (sem cedente, não precisa da 003).
- **Antes do COMMIT:** `integrity_check`, `foreign_key_check`, nenhuma coluna com `cpf` e nenhum texto inteiro com formato de CPF no que a coleta gravou (texto, nome e CNPJ). Se algo falhar, desfaz tudo e mantém o backup.
- **Saída:** 0 (sucesso ou nada a fazer), 1 (erro, com "Erro ao carregar o informe de FIAGRO: ..." no stderr), 2 (argumentos).
- **O relatório tem só agregados**, nunca CNPJ, nome, ISIN ou valor: linhas e colunas por arquivo, CNPJ por situação, chaves repetidas, `Versao` igual ou diferente de 1, datas de entrega distintas, ISIN, notação científica, papéis, subclasses, o casamento por arquivo e por classe e os candidatos (dry-run) ou o que foi gravado (commit).
- **Esperado em 09/2026** (contagem em memória, só agregados, do arquivo de SHA-256 `a9700ab7...0948` da seção 9.1 de `docs/fundos-descoberta.md`): 312 linhas de classe (310 `CNPJ_Classe`), 308 carregáveis; 697 linhas de subclasse, 688 carregáveis (688 séries); 39.316 observações (37.252 da classe e 2.064 das séries); 616 papéis (308 administradores e 308 gestores). Com o cadastro de 27/10/2026, as 308 classes carregáveis estão em `fund_classes`.

## Como carregar o CDA

O `scripts/load_cda.py` lê o `cda_fi_AAAAMM.zip` da CVM (baixado à mão, fora do Git) e grava as posições em cotas de fundos das classes e fundos que **já estão no banco**: o cadastro tem de ser carregado antes. `--database` e `--zip` são obrigatórios, e `--dry-run` ou `--commit` também. `--last-modified` é o `Last-Modified` do ZIP na CVM: opcional na primeira carga da competência e obrigatório na reapresentação; passe sempre. Rode sempre o `--dry-run` antes. O `--commit` só com aprovação explícita.

```powershell
cd Gui\fundos
# prévia: lê e confere o ZIP; com o banco, mostra o casamento do detentor, o tipo do investido e a comparação com o banco; não escreve nada
python scripts\load_cda.py --database C:\<pasta-local>\fundos.db --zip C:\<pasta-local>\originais\cda\cda_fi_202610.zip --last-modified "Tue, 24 Nov 2026 04:05:23 GMT" --dry-run
# carga (banco com as migrations 001 a 004 e o cadastro carregado)
python scripts\load_cda.py --database C:\<pasta-local>\fundos.db --zip C:\<pasta-local>\originais\cda\cda_fi_202610.zip --last-modified "Tue, 24 Nov 2026 04:05:23 GMT" --commit --backup-dir C:\<pasta-local>\bk\fundos
```

- **Banco em disco local**, como no cadastro: banco ou backup em caminho de rede ou longo é recusado antes de ler o ZIP, no `--dry-run` também (veja "Banco real").
- **Formato:** os 12 membros e só eles, com o mesmo `AAAAMM` (e o do nome do ZIP). Só o `cda_fie` e o `cda_fie_CONFID` são lidos, em cp1252 estrito e com o cabeçalho exato de `src/fundos/cda/columns.py`. Os 10 `cda_fi_*` entram só no manifesto, sem ser decodificados.
- **Competência = `DT_COMPTC`** das linhas de "Cotas de Fundos": um só valor, do mês do `AAAAMM`, não posterior a hoje (UTC). As outras linhas são só contadas por `TP_APLIC`.
- **Detentor:** `CNPJ_FUNDO_CLASSE`, sem completar zeros. `CLASSES - FIDC` e `CLASSES - FIAGRO` casam com a classe; `FIDC` e `FIAGRO`, com o fundo. O detentor fora do cadastro carregado, de outro tipo (`CLASSES FIIM`) ou de classe que só existe como fundo é só contado, por motivo. Nenhum fundo nem classe é criado.
- **Dados pessoais** (guardas aprovadas em 25/11/2026; seção 12.6 de `docs/fundos-descoberta.md` e decisão 3 de `docs/decisoes-em-aberto.md`):
  - **(a)** `CPF_CNPJ_EMISSOR` só vale como CNPJ do investido se `PF_PJ_EMISSOR` for PJ, se tiver 14 caracteres ou a máscara completa (sem completar zeros) e se o DV de CNPJ fechar. Fora disso, o identificador não é gravado e a linha é contada por motivo: PF, vazio, `PF_PJ_EMISSOR` fora de PJ, formato ou DV;
  - **(b)** `EMISSOR` só entra com o identificador aceito, nunca de linha PF nem de linha recusada;
  - **(c)** os testes cobrem o CPF completado com zeros até 14 dígitos, em linha PF e em linha PJ. A varredura antes do COMMIT procura só 11 dígitos ou a máscara de CPF e não o acha: a barreira é a guarda (a);
  - **(d)** o descarte aparece só como contagem no relatório; as mensagens de erro citam arquivo, linha e coluna, nunca o valor.
  - **Regra 4 do CLAUDE.md:** o identificador PJ com DV inválido não vai para o banco e é contado. O valor original continua íntegro no arquivo da CVM, identificado pelo manifesto (nome, tamanho e SHA-256).
  - **Risco residual da guarda (a):** todo CPF que começa com `00`, completado com zeros até 14 dígitos, é também um CNPJ válido (começa com `00000`, e os dois DVs coincidem), e numa linha PJ de cotas ele seria aceito. Os outros CPFs completados com zeros só passam se o DV de CNPJ fechar por acaso. Em 10/2026, nenhum investido de linha de cotas começa com 000.
- **O que é gravado:** uma coleta, o manifesto do ZIP e dos 12 CSV (os 10 `cda_fi_*` como `ignored`), as posições identificadas em `holdings` e as confidenciais em `confidential_holdings`, com a competência = `DT_COMPTC`.
  - Chave das identificadas: detentor, investido, `DT_COMPTC` e a ordem da linha na chave. Cada linha repetida é uma posição própria, e nenhuma soma é gravada.
  - O investido é só o CNPJ, sem FK.
  - O arquivo com mais de uma linha confidencial de cotas do mesmo detentor é recusado.
- **Mesmo ZIP:** o mesmo ZIP (mesmo SHA-256) diz "Nada a carregar" e não faz backup.
- **Reapresentação:** outro ZIP da competência exige `--last-modified` estritamente posterior ao do ZIP mais novo já carregado (ou ao início da carga dele, se não tiver a data). Valor igual não grava; valor diferente grava linha nova e conflito aberto; a posição que sumiu só é contada.
- **Migrations:** 001 a 004.
- **Antes do COMMIT:** o `verify()` do cadastro (`integrity_check`, `foreign_key_check`, nenhuma coluna com `cpf` e nenhum texto com formato de CPF) e a varredura das posições desta coleta (todo investido com DV válido; nenhum nome nem CNPJ com formato de CPF). Se algo falhar, desfaz tudo e mantém o backup.
- **Saída:** 0 (sucesso ou nada a fazer), 1 (erro, com "Erro ao carregar o CDA: ..." no stderr), 2 (argumentos).
- **Esperado em 10/2026** (ZIP de SHA-256 `25e71555...0bca01`, carga em banco em memória com o cadastro de 27/10/2026, em 25/11/2026, só agregados):
  - 5.846 linhas de cotas, das quais 8 recusadas por DV: são 5.838 posições lidas;
  - 5.746 gravadas em `holdings`, com 92 de detentor fora (1 classe fora do cadastro e 91 `CLASSES FIIM`);
  - 183 confidenciais, das quais 136 gravadas e 47 `CLASSES FIIM` fora;
  - 0 conflitos.

## Banco real

Decidido em 25/11/2026 (decisão 9 de Fundos em `docs/decisoes-em-aberto.md`). O primeiro banco real foi criado e carregado com o cadastro de 27/10/2026 e o CDA de 10/2026; os informes de FIDC e de FIAGRO ainda não estão nele. Cada `--commit` da sequência abaixo roda com aprovação explícita.

- **Onde:** numa pasta local de caminho curto (por exemplo `C:\pense\fundos\fundos.db`), fora do Git e fora de pasta de rede.
  - O `--backup-dir` também é local (por exemplo `C:\pense\bk\fundos`), porque a `fundos_cli` da camada compartilhada não confere esse parâmetro.
  - O caminho do banco e o do backup, contando o `-journal`, ficam abaixo de 260 caracteres. No exemplo, são 33 e 65.
- **Backup:** todo `--commit` faz o backup antes e só roda com aprovação explícita. A exceção é o `--create --commit` da migration: o banco ainda não existe e não há o que copiar. O backup da carga do cadastro cobre esse estado.
- **Originais:** os ZIPs da CVM ficam numa pasta local de acesso restrito, fora do Git e de rede, sem regra de apagar (decisão 3 de Fundos).
  - Por exemplo `C:\pense\originais`, sem herança de permissão, com acesso só para o usuário, SYSTEM e Administradores.
  - O carregador lê a cópia, nunca a amostra original. O SHA-256 é conferido antes e depois da cópia, e a cópia fica somente leitura.
- **No banco, só o manifesto:** `raw_records` guarda nome, tamanho, SHA-256 e número de linhas de cada arquivo, nunca o conteúdo.
- **Dados pessoais:** o CPF nunca é gravado. O que as guardas descartam aparece só como contagem no relatório (veja "Como carregar o CDA").
  - O original pode ter CPF. O CDA de 10/2026 tem 5 CPFs com máscara no `cda_fi_BLC_6`, que o carregador não decodifica, e 1 CPF completado com zeros numa linha PF do `cda_fie` que não é de cotas.
- **Caminho de rede:** os 5 scripts (`apply_migration.py` e os 4 carregadores) recusam, antes de ler o ZIP e de abrir o banco, no `--dry-run` também (saída 1):
  - `--database` e o destino do backup em caminho de rede (UNC, relativo dentro de pasta de rede ou unidade mapeada remota);
  - caminho longo.

  Mais regras:
  - a mensagem traz só o parâmetro e o motivo, nunca o caminho;
  - o caminho de rede é recusado antes de ser tocado, e o link ou a junção local para a rede é recusado pelo caminho resolvido;
  - o `\\?\` conta como rede, um falso positivo seguro;
  - a unidade criada com SUBST sobre pasta local é aceita;
  - o `--zip` não é conferido: ler o ZIP pela rede não tem o risco de trava do SQLite.
- **Sequência:** cada passo com `--dry-run` antes e `--commit` depois.
  1. Pasta local restrita e cópia dos originais (o cadastro de 27/10/2026 e o CDA de 10/2026), com o SHA-256 antes e depois.
  2. `scripts\apply_migration.py --create`: as migrations 001 a 004, em 25/11/2026. A 005 fica reservada à prioridade de fontes (ADR-010). A 006 (`quota_class_map`) veio depois e ainda não foi aplicada no banco real.
  3. `scripts\load_cadastro.py --reference-date 2026-10-27`.
  4. `scripts\load_cda.py --last-modified "Tue, 24 Nov 2026 04:05:23 GMT"`: o `Last-Modified` do ZIP na CVM, do manifesto do download. Ele grava a data da fonte e evita recusar uma reapresentação publicada entre essa data e a carga.
  5. Verificação só de leitura:
     - `integrity_check`, `foreign_key_check` e a varredura de CPF em todas as colunas;
     - as contagens contra o ensaio em memória: 8.044 fundos, 5.839 classes, 5.746 posições, 136 confidenciais e 0 conflitos.

     A segunda execução de cada passo diz que já foi carregado e não duplica.

### Fora desta etapa

- a carga dos informes de FIDC e de FIAGRO no banco real;
- a classificação de FIC-FIDC e a conferência do CDA com a `tab_I` no banco real: o código existe (veja "FIC-FIDC e conferência do CDA"), mas o banco real ainda não tem o informe de FIDC de 10/2026, a mesma competência do CDA carregado. O informe foi baixado em 26/11/2026, está na pasta local de originais e foi carregado só numa cópia do banco real;
- a fase 4 da camada compartilhada (`fundos_cli`) sobre o banco real;
- o segundo consumidor do banco (com ele, revisita-se o local: disco local de servidor);
- a mesma guarda de caminho na `fundos_cli` da camada compartilhada (o `--backup-dir`, o `--target-db` no dry-run e a unidade remota no `--fundos-db`) e na leitura dos indicadores (`indicators/reading.py`, que já recusa UNC, mas não unidade remota), em PR próprio;
- um cadastro mais novo que o de 27/10/2026 (outra competência, com download aprovado).

## FIC-FIDC e conferência do CDA

O `src/fundos/fic_fidc/` calcula na leitura duas coisas, por assunto (a classe ou o fundo) e por competência (FU6.1, partes 3 e 4):
- a classificação de FIC-FIDC (decisão 6 de `docs/decisoes-em-aberto.md`);
- a conferência das posições do CDA em cotas de FIDC com a `tab_I` do informe.

Nenhuma das duas é gravada. A única escrita é a fila de revisão manual no `audit_log`, feita só pelo `--commit` do script.

### A classificação (`classification.classify(conexao, competencia, assuntos=None)`)

- **Regra (`fic_fidc.v1`):** `tab_I.TAB_I2H_VL_COTA_FIDC` sobre `tab_I.TAB_I_VL_ATIVO`, na mesma competência.
  - 95% ou mais: FIC-FIDC.
  - De 67% a menos de 95%: em revisão manual.
  - Abaixo de 67%: não classificado.

  É uma regra de corte, não um dado da CVM. Nunca classifica pelo nome.
- **Exatidão:** a faixa sai da multiplicação cruzada em `Decimal` (100 x cotas contra 95 x ativo e contra 67 x ativo), num contexto que recusa arredondamento. A divisão nunca decide a faixa; o percentual sai só para exibição, com 28 dígitos e sem arredondar.
- **Os dois números** saem com o campo, a competência, a fonte, a observação de origem e a coleta, pelo `read_competence` dos indicadores. Valem as fontes ativas, depois a prioridade e depois a coleta mais recente, dentro da competência.
- **Sem dado, com o motivo** (nunca zero, nunca estimado):
  - `sem_informe_na_competencia`: o assunto pedido não tem a `tab_I` na competência;
  - `campo_ausente` e `tipo_inesperado`;
  - `denominador_zero` e `denominador_negativo`: o ativo é 0 ou negativo;
  - `numerador_negativo`: as cotas de FIDC são negativas.

  Zero informado é zero: cotas 0 com ativo positivo dão "não classificado".
- **Marcas:**
  - `acima_de_100`: as cotas passam o ativo; o assunto é classificado, sem cortar;
  - `conflito_aberto`: um dos dois campos tem conflito aberto no banco;
  - `tipo_no_cadastro_fiagro`: a classe é FIAGRO no cadastro e tem o informe de FIDC. É classificada pela regra e marcada.

### A conferência (`cda_check.cda_vs_informe(conexao, competencia, assuntos=None)`)

- **O que compara:** a soma de `cda_fie.VL_MERC_POS_FINAL` das posições identificadas (`holdings`) cujo investido é FIDC no cadastro, como classe ou só como registro de fundo, contra `tab_I.TAB_I2H_VL_COTA_FIDC`.
  - Investido FIAGRO, misto ou fora do cadastro carregado fica fora da soma, à parte e com marca. O banco só tem FIDC e FIAGRO, então FIF, FII e FIP caem em "fora do cadastro carregado".
  - O consolidado confidencial não separa o tipo do investido e nunca entra na soma.
  - O tipo do investido é o do cadastro atual (`cda.loader.cadastro_types`). O CNPJ do investido é lido só para buscar o tipo, e nenhum resultado o traz.
- **Tolerância (decidida em 26/11/2026):** dentro é `|CDA - informe| <= max(R$ 1; 1% do informe)`, conferido por multiplicação cruzada.
  - **O 1%:** vem da seção 12.5 de `docs/fundos-descoberta.md`. Em 09/2026, só com os investidos FIDC, 266 de 292 e 134 de 173 classes ficaram a até 1% do informe; a faixa seguinte (de 1% a 5%) tinha 8 e 16.
  - **O R$ 1:** absorve centavo quando o informe é pequeno ou zero.
- **A divergência é nota de qualidade** (decidido em 26/11/2026), calculada na leitura:
  - não vai para `data_conflicts`, que liga duas observações do mesmo campo; a posição do CDA não é observação, e as duas fontes não são reapresentação uma da outra;
  - nada é gravado nem sobrescrito.
- **Competência:** nunca se compara um mês com outro. Se um dos lados não tem a competência, o resultado é `sem_dado`, com `sem_informe_na_competencia` ou `cda_nao_carregado_na_competencia`, e traz as duas datas.
- **Os outros motivos de `sem_dado`:**
  - `holdings_nao_existe`: o banco não tem a migration 004;
  - `campo_ausente`, `tipo_inesperado` e `valor_negativo`;
  - `sem_posicao_em_cotas_no_cda` e `so_posicao_confidencial`.
- **Marcas:**
  - `conflito_aberto` (no informe) e `conflito_de_posicao` (posição com conflito aberto: vale a mais recente);
  - `investido_misto`, `investido_fora_do_cadastro` e `tem_posicao_confidencial`;
  - `sem_cotas_nos_dois_lados`: o informe é 0 e não há posição. É só contado.
- **FIAGRO detentor:** sem o informe de FIDC, o resultado é `sem_informe_na_competencia`. O CDA não é comparado com o informe de FIAGRO. O relatório conta os detentores por tipo no cadastro e mostra 0 quando não há nenhum, sem concluir a causa.

### A fila de revisão manual (`review_queue`)

**Uma linha no `audit_log`** por assunto em revisão manual, por competência e por evidência:

| Coluna | Valor |
|---|---|
| `actor` | `fundos.fic_fidc.v1`, o processo, nunca nome de pessoa |
| `action` | `fic_fidc_revisao_manual_pendente` |
| `entity_type` e `entity_id` | `fund_classes` ou `funds`, e o id do assunto |
| `after_data` | JSON canônico, com a competência, a regra, `fonte_da_decisao` MANUAL (o `audit_log` não tem coluna de fonte) e, de cada campo, o nome e a observação de origem. Nenhum valor, CNPJ nem nome |
| `reason` | a regra que mandou o assunto para a fila |

**Sem duplicar:**
- Classificar e ler a fila nunca escrevem.
- O `--commit` grava só dentro de uma transação e só faz INSERT.
- A entrada com o mesmo `after_data` não é gravada de novo.

**Reapresentação:** um valor reapresentado muda a observação de origem e gera uma linha nova; a antiga fica. A leitura da fila mostra a mais recente por assunto, com a marca `classificacao_atual_diferente` quando o assunto saiu da faixa de revisão ou a evidência mudou.

**A decisão de uma pessoa não é gravada aqui.** A entrada MANUAL em `observations` só vem depois da migration 005 (ADR-010).

**Limitação:** o `audit_log` não tem trigger de imutabilidade. Este código só faz INSERT, e o teste confere.

### O script (`scripts/classify_fic_fidc.py`)

```powershell
# na pasta do módulo de Fundos
python scripts\classify_fic_fidc.py --database C:\<pasta-local>\fundos.db --reference-date 2026-09-30 --dry-run
python scripts\classify_fic_fidc.py --database C:\<pasta-local>\fundos.db --reference-date 2026-09-30 --commit --backup-dir C:\<pasta-local>\bk\fundos
```

- **Argumentos:** `--reference-date` é a competência, o último dia do mês; outro dia dá saída 2. `--dry-run` ou `--commit` é obrigatório.
- **Banco em disco local**, como nos carregadores: banco ou backup em caminho de rede ou longo é recusado antes de abrir o banco, no `--dry-run` também (saída 1).
- **`--dry-run`:**
  - abre o banco só para leitura (`mode=ro` e `query_only`), e banco em WAL é recusado;
  - mostra a regra e as competências de cada lado;
  - mostra as faixas, os estados da conferência e o cruzamento das faixas com os estados;
  - diz quantos assuntos já estão na fila e quantos entrariam.

  Não escreve nada.
- **`--commit`:** só grava a fila.
  - **Sem entrada nova:** diz "Nada a enfileirar" e não faz backup.
  - **Com entrada nova:** faz o backup antes e grava numa transação. Confere o que gravou antes do COMMIT e roda `integrity_check` e `foreign_key_check` depois.
  - **Migrations:** exige as 001 a 003.
- **Saída:** 0 (sucesso ou nada a fazer), 1 (erro, com "Erro na classificacao de FIC-FIDC: ..." no stderr; o erro inesperado mostra só o tipo do erro) e 2 (argumentos).
- **O relatório tem só contagens,** nunca CNPJ, nome nem valor de linha.

### Medição em 26/11/2026 (cópias; só contagens)

**09/2026, cópia do banco de teste.** O banco tem o cadastro de 27/10/2026 e o informe de FIDC de 09/2026, sem `holdings`. O SHA-256 da cópia era igual ao do original, e o do original ficou igual depois.
- **Classificação:** 4.425 assuntos.
  - FIC-FIDC: 517;
  - em revisão manual: 374;
  - não classificado: 3.404;
  - sem dado: 130, todos `denominador_zero`.

  Marcas: `acima_de_100` em 1 e `tipo_no_cadastro_fiagro` em 2. Os números vêm todos da `CVM_DADOS_ABERTOS`.
- **Sanidade:** a seção 10.4 de `docs/fundos-descoberta.md` contou 518, 374, 3.407 e 145 sem ativo positivo nas 4.444 linhas do ZIP. A diferença (1, 0, 3 e 15) soma 19, o mesmo número de linhas do ZIP que não viraram assunto carregado (4.444 - 4.425). Não foi conferido se são as mesmas linhas.
- **Conferência:** os 4.425 assuntos saem `holdings_nao_existe`, porque o banco não tem a 004.
- **Fila:** o `--commit` gravou 374 linhas, de 370 classes e 4 fundos, com 1 backup, `integrity_check` ok e 0 problemas de chave estrangeira. O segundo `--commit` disse "Nada a enfileirar", sem backup e sem mudar o banco. O `--dry-run` seguinte mostrou 0 a entrar e 374 na fila.

**10/2026, cópia do banco real.** O SHA-256 era igual antes e depois, e não houve backup novo.
- **O CDA:** tem só a competência 2026-10-31, com 5.746 posições e 136 confidenciais.
- **O informe:** esta cópia é de antes do download do informe de 10/2026 e não o tinha, então não houve classificação. A medição com o informe está no bloco seguinte.
- **A conferência:** 635 detentores, todos `sem_informe_na_competencia`. Por tipo no cadastro, 635 são FIDC (5.882 linhas) e 0 são FIAGRO. A marca `investido_fora_do_cadastro` aparece em 435 e `tem_posicao_confidencial` em 136.

**10/2026 contra 10/2026, cópia nova do banco real com o informe de FIDC de 10/2026.** O banco real ficou com o SHA-256 igual antes e depois, e não houve backup novo.
- **O informe:** `inf_mensal_fidc_202610.zip`, com 3.681.356 bytes, SHA-256 `7f8ca7d7...403817` e `Last-Modified` de 21/11/2026 11:50:03 GMT. Foi baixado em 26/11/2026 com um único GET e guardado na pasta local de originais, somente leitura.
- **A carga, só na cópia:**
  - a `tab_I` tem 4.523 linhas (4.492 classes e 31 fundos), das quais 4.506 assuntos estão no cadastro carregado (4.476 classes e 30 fundos) e 17 ficaram fora;
  - foram 1.592.309 observações, com 0 conflitos;
  - `integrity_check` ok, 0 problemas de chave estrangeira e a varredura de CPF com 0.
- **Classificação:** 4.506 assuntos.
  - FIC-FIDC: 532;
  - em revisão manual: 365;
  - não classificado: 3.467;
  - sem dado: 142, todos `denominador_zero`.

  Marcas: `acima_de_100` em 1 e `tipo_no_cadastro_fiagro` em 1.
- **Conferência:** 4.508 assuntos, que são os 4.506 do informe e 2 detentores só no CDA.
  - Dentro da tolerância: 424; fora: 71.
  - `sem_dado`: 4.013, dos quais `sem_posicao_em_cotas_no_cda` 3.873, `so_posicao_confidencial` 136, `sem_informe_na_competencia` 2 e `valor_negativo` 2.
  - Marcas: `investido_fora_do_cadastro` em 435, `tem_posicao_confidencial` em 136 e `sem_cotas_nos_dois_lados` em 3.067.
  - Detentores por tipo no cadastro: 635 FIDC (5.882 linhas) e 0 FIAGRO.
- **Cruzamento** (dentro, fora e os `sem_dado`):

  | Faixa | Dentro | Fora | Sem posição | Só confidencial | Valor negativo |
  |---|---|---|---|---|---|
  | FIC-FIDC | 264 | 29 | 144 | 95 | 0 |
  | Em revisão manual | 134 | 34 | 161 | 36 | 0 |
  | Não classificado | 26 | 8 | 3.428 | 5 | 0 |
  | Sem dado | 0 | 0 | 140 | 0 | 2 |
- **Sanidade contra a seção 12.5,** sem teste fixo. Com 1% puro, sem o piso de R$ 1 e só nas classes, ficaram dentro 263 de 290 (95% ou mais) e 133 de 167 (de 67% a menos de 95%). Em 09/2026 tinham sido 266 de 292 e 134 de 173. Com classes e fundos, o piso de R$ 1 não mudou nenhuma contagem: 264 de 293 e 134 de 168.
- **Fila:** o `--commit` gravou 365 linhas, de 363 classes e 2 fundos, com 1 backup, `integrity_check` ok e 0 problemas de chave estrangeira. O segundo `--commit` disse "Nada a enfileirar", e o `--dry-run` seguinte mostrou 0 a entrar e 365 na fila.

### Não confirmado

1. **O critério de valor:** não se sabe se `cda_fie.VL_MERC_POS_FINAL` e `TAB_I2H_VL_COTA_FIDC` seguem o mesmo (seção 12.8 de `docs/fundos-descoberta.md`).
2. **As classes fora de 1% em 09/2026:** 26 e 39, sem causa explicada.
3. **O valor confidencial:** não se sabe quanto dele é FIDC.
4. **FIAGRO no CDA de 10/2026:** há 0 detentores FIAGRO no CDA carregado, contra 272 linhas em 09/2026, e a causa não foi verificada.
5. **A conferência no banco real:** com dado real, só rodou numa cópia (10/2026 contra 10/2026). O banco real continua sem o informe.
6. **As classes fora de 1% em 10/2026:** 27 e 34, sem causa explicada, como em 09/2026.
7. **A norma:** não se sabe se ela define FIC-FIDC. A decisão 6 é regra de corte.

## Mapa das séries (`quota_class_map`)

O `quota_class_map` (migration 006, decisão 8 de `docs/decisoes-em-aberto.md`, FU6.2) diz se uma série de FIDC é sênior, mezanino ou subordinada, pelo rótulo dela.

**O rótulo original nunca é alterado.**
- O rótulo de cada tabela continua como observação da série (`tab_X_2.TAB_X_CLASSE_SERIE` e as outras).
- A regra casa com o rótulo **normalizado**, na mesma forma de `quota_series.series_label_key`, que o carregador já preenche: sem acento, minúsculo, sem `|` e com os espaços colapsados.
- É essa forma que já junta a `tab_X_1` e a `tab_X_2` na mesma série.
- Nenhuma coluna nova foi criada para a forma normalizada.

### As regras

| Coluna | O que guarda |
|---|---|
| `pattern` | o padrão, já normalizado |
| `match_type` | `inicio` (a chave é igual ao padrão ou começa com ele seguido de espaço) ou `igual` (só a chave igual) |
| `level` e `subtype` | `senior` com `nao_se_aplica`, ou `nao_senior` com `mezanino`, `subordinada` ou `ausente` (o rótulo não diz o subtipo; nada é estimado) |
| `origin_note` | de onde veio a regra; imutável |
| `review_status`, `reviewer`, `reviewed_at` e `review_note` | a revisão: `proposto`, `revisado` ou `rejeitado`, o papel de quem revisou, a data e a nota |
| `valid_from` e `valid_to` | a vigência, por competência; vazia é aberta |

**As 4 regras iniciais,** todas `proposto` e com a vigência aberta, derivadas da seção 10.6 de `docs/fundos-descoberta.md`:

| Padrão | Casamento | Classificação |
|---|---|---|
| `subclasse senior` | `inicio` | sênior |
| `subclasse subordinada mezanino` | `inicio` | não sênior, mezanino |
| `subclasse subordinada subordinada` | `inicio` | não sênior, subordinada |
| `subclasse subordinada` | `igual` | não sênior, subtipo ausente |

**Classificação** (`quota_classes.mapping.classify_label`):
- Valem só as regras não rejeitadas e vigentes na competência.
- Entre as que casam, vence a mais específica, que é o padrão mais longo. Por isso "Subclasse Subordinada Mezanino 1" cai em mezanino, e não na regra genérica.
- Duas regras do mesmo comprimento que casam ficam `regras_em_conflito`, e nenhuma vale.
- Rótulo sem regra fica "ausente (rótulo não mapeado)", nunca um palpite. "Subclasse Subordinada Junior 1", por exemplo, não é classificada.
- A situação da revisão vai junto de cada classificação.

**Proteções no banco** (triggers da 006):
- nenhuma regra é apagada;
- padrão, casamento, nível, subtipo, origem e início da vigência são imutáveis;
- o fim da vigência só é preenchido uma vez;
- a revisão só vai de `proposto` para `revisado` ou `rejeitado`, ou de `revisado` para `rejeitado`;
- `revisado` e `rejeitado` exigem o papel e a data;
- há uma regra ativa por padrão, casamento e início da vigência.

### Revisão por uma pessoa (`scripts/review_quota_class_map.py`)

Nada vira `revisado` sem uma pessoa. Quem roda o `--commit` é a pessoa que revisou.

- **O revisor:** é identificado por um papel da lista fechada do código, `papel:dono_da_frente_fundos` ou `papel:revisor_fundos`, nunca pelo nome. O banco confere o formato `papel:<id>`.
- **A nota é conferida antes de tudo:**
  - só ASCII imprimível, até 200 caracteres;
  - sem quebra de linha;
  - sem sequência de 11 dígitos ou mais e sem máscara de CPF ou CNPJ.

  O erro diz só o motivo, nunca o texto, e a saída mostra só o tamanho da nota.
- **`--dry-run`:** confere a regra e a transição, só lendo o banco.
- **`--commit`:**
  - faz o backup e grava a revisão e uma linha no `audit_log` numa transação. A linha leva `actor` = o papel, `action` = `quota_class_map_revisao` e o antes e o depois em JSON;
  - roda `integrity_check` e `foreign_key_check`;
  - a mesma revisão de novo diz "Nada a revisar", sem backup.
- **Caminho:** banco ou backup em caminho de rede ou longo é recusado antes de abrir o banco, no `--dry-run` também. Exige as migrations 001 e 006.

```powershell
# na pasta do módulo de Fundos
python scripts\review_quota_class_map.py --database C:\<pasta-local>\fundos.db --rule-id 1 --status revisado --reviewer papel:revisor_fundos --note "<nota>" --dry-run
```

### Relatório de revisão (`scripts/report_quota_class_map.py`)

Só lendo o banco (`mode=ro` e `query_only`; banco em WAL é recusado), com a mesma guarda de caminho. Sem `--reference-date`, cobre todas as competências com `tab_X_2`. Mostra:
- as regras, com a situação, o papel, a data e a vigência;
- por competência:
  - as séries de FIDC e os rótulos normalizados;
  - quantas séries e rótulos cada regra classifica;
  - os rótulos sem regra, com as séries, as variantes originais (só a contagem) e o motivo;
  - a **ordem entre subordinadas não informada:** os assuntos com 2 ou mais séries de subtipo subordinada ou ausente, com ou sem mezanino. O rótulo não ordena duas subordinadas da mesma classe, e nada é inferido;
  - os assuntos com 2 ou mais séries não seniores e nenhum mezanino, só como contagem;
  - as séries com subtipo ausente;
- os rótulos novos desde a última revisão (a primeira coleta do rótulo depois da maior data de revisão; sem revisão nenhuma, só a contagem);
- as séries de FIAGRO sem mapa: o FIAGRO fica fora desta etapa, porque as subclasses dele não dizem sênior ou subordinada.

Só contagens e rótulos normalizados de série. O rótulo só aparece onde a revisão precisa dele, sem regra ou novo. Nunca traz CNPJ, nome, valor de linha nem o rótulo original.

### Medição em 26 e 27/11/2026 (cópias; só contagens)

Cópias novas da pasta da sessão, cada uma com o SHA-256 igual ao da origem; as origens ficaram com o hash igual depois. Em cada cópia, `apply_migration.py --dry-run` e depois `--commit`, com `integrity_check` ok, 0 problemas de chave estrangeira e 0 colunas com `cpf`. O banco real ficou com o SHA-256 igual, sem backup novo, e **não tem a 006**.

| | 09/2026 (cópia do banco de teste) | 10/2026 (cópia do banco real com o informe de 10/2026) |
|---|---|---|
| Migrations pendentes | 004 e 006 | 006 |
| Séries de FIDC com `tab_X_2` (rótulos normalizados) | 12.700 (216) | 12.430 (205) |
| `subclasse senior` | 6.998 | 7.092 |
| `subclasse subordinada mezanino` | 2.331 | 2.375 |
| `subclasse subordinada subordinada` | 2.775 | 2.447 |
| `subclasse subordinada` (subtipo ausente) | 596 | 516 |
| Sem regra | 0 | 0 |
| Ordem entre subordinadas não informada (2 ou mais de subtipo subordinada ou ausente, com ou sem mezanino) | 20 | 21 |
| Assuntos com 2 ou mais não seniores e nenhum mezanino | 15 | 16 |
| Séries de FIAGRO sem mapa | 688 | 0 (a cópia não tem o informe de FIAGRO) |

- **Revisão,** só na cópia de 09/2026:
  - o `--dry-run` não mudou o banco;
  - o `--commit` gravou a regra 1 como `revisado`, com `papel:revisor_fundos`, e uma linha no `audit_log`;
  - o segundo `--commit` disse "Nada a revisar";
  - o relatório depois mostrou a regra revisada, com a data, e 0 rótulos novos.
- **Rótulos no relatório:** a contagem de rótulos sem revisão (217 e 206) inclui os rótulos de todas as tabelas `tab_X`, e por isso passa um pouco dos rótulos da `tab_X_2` (216 e 205).

### Não confirmado

1. **O molde:** é do sistema de entrega da CVM, não um domínio documentado, e pode mudar. Em 09 e 10/2026, nenhum rótulo ficou sem regra.
2. **Os 20 da seção 10.6 contra os 15:** a diferença é de definição, e não de base. Medido em 27/11/2026, só lendo a cópia de 09/2026 e o ZIP de 09/2026 (o SHA-256 dos dois ficou igual), com a mesma normalização e as mesmas 4 regras:

   | Definição | Banco | ZIP |
   |---|---|---|
   | (a) 2 ou mais não seniores e nenhum mezanino | 15 | 15 |
   | (b) 2 ou mais séries de subtipo subordinada ou ausente, com ou sem mezanino | **20** | **20** |
   | (c) 2 ou mais não seniores, com ou sem mezanino | 1.034 | 1.038 |

   Os 20 da seção 10.6 são a definição (b), porque a ordem entre as subordinadas também fica sem informação quando há mezanino acima delas. Desde 27/11/2026, o relatório conta a (b) como "ordem entre subordinadas não informada" e mantém a (a) com o nome neutro. A subordinação (FU6.3) usa a mesma definição (b) para a marca.
3. **A regra genérica:** a seção 10.6 contou 599 linhas genéricas no ZIP, e o banco tem 596 séries. A hipótese são os assuntos fora do cadastro carregado, e não foi conferida.
4. **A ordem** entre duas subordinadas (ou dois mezaninos) da mesma classe não é informada, e nunca é inferida.
5. **As regras iniciais** são proposta do módulo de Fundos: falta a revisão de uma pessoa no banco real, que ainda não tem a 006.

## Subordinação (FU6.3)

`indicators.subordinacao.subordinacao(conexao, competencia, assuntos=None)` calcula a subordinação de cada assunto (a classe ou o fundo) numa competência (decisão 8 de `docs/decisoes-em-aberto.md`). **Nada é gravado:** o resultado é calculado por cima das observações, que continuam sendo o dado da CVM.

### A fórmula

**Subordinação total** = soma de `TAB_X_QT_COTA x TAB_X_VL_COTA` das séries não seniores / soma de todas as séries, na `tab_X_2` da mesma competência.
- **Valor de cada série:** o produto é exato, em `Decimal`, sem arredondar.
- **O percentual:** tem 28 dígitos e não é arredondado; arredondar é decisão de exibição.
- **Classificação:** cada série é classificada pelo `quota_class_map`, pelo rótulo normalizado, com as regras não rejeitadas e vigentes na competência, `proposto` ou `revisado`.
- **O resultado traz:**
  - a fórmula e o estado `calculado`;
  - cada série, com a regra e a situação dela;
  - cada insumo, com o campo, a competência, a fonte, a observação e a coleta;
  - a situação do mapa (`revisado` só quando todas as regras usadas foram revisadas).
- **A leitura** é `indicators.reading.read_series_competence`: a mesma regra de ordem do `read_competence` (fontes ativas, prioridade, coleta mais recente e id), por série.

### Partes e camadas

- **Partes:** sênior, mezanino, subordinada e subtipo ausente, cada uma com as séries de origem e a parcela no total, quando existem.
- **Colchão do sênior:** é a subordinação total.
- **Colchão do mezanino:** subordinada / total, só com mezanino e nenhum subtipo ausente. Vários mezaninos somam como uma camada, com a marca `mais_de_uma_serie_mezanino`, e a ordem entre eles não é inferida.

### Estados, motivos e marcas

**`sem_dado`, com o motivo, nesta ordem:**
1. `mapa_nao_existe`: o banco não tem a 006;
2. `sem_tab_X_2_na_competencia`;
3. `rotulo_nao_mapeado` ou `regras_em_conflito`: nada parcial, "ausente (rótulo não mapeado)";
4. `campo_ausente`, `tipo_inesperado` ou `valor_negativo`, na quantidade ou no valor da cota de alguma série;
5. `soma_das_series_zero`.

**Marcas:**

| Marca | Quando |
|---|---|
| `sem_serie_subordinada` | só há série sênior. A subordinação é 0, e a exibição diz "sem série subordinada", nunca 0% sem explicação |
| `ordem_entre_subordinadas_nao_informada` | 2 ou mais séries de subtipo subordinada ou ausente, com ou sem mezanino. **Só avisa:** não muda a subordinação total nem o colchão do mezanino, e a ordem nunca é inferida |
| `subtipo_ausente` e `mais_de_uma_serie_mezanino` | a classe tem série de subtipo ausente, ou mais de um mezanino |
| `pl_ausente`, `pl_nao_positivo` e `soma_fora_de_1pct_do_pl` | a conferência da soma das séries com `tab_IV.TAB_IV_A_VL_PL`, com 1% puro e multiplicação cruzada. **A fórmula não usa o PL:** o resultado continua calculado, com a marca |
| `mapa_proposto` | alguma regra usada ainda não foi revisada por uma pessoa |
| `conflito_aberto` | algum insumo tem conflito aberto no banco |

### O relatório (`scripts/report_subordinacao.py`)

```powershell
# na pasta do módulo de Fundos
python scripts\report_subordinacao.py --database C:\<pasta-local>\fundos.db --reference-date 2026-09-30
```

- **Leitura:** só lendo o banco (`mode=ro` e `query_only`; banco em WAL é recusado), com a guarda de caminho de rede e longo. Exige as migrations 001 e 006.
- **O que mostra:** só contagens.
  - **Estados, motivos e marcas:** as marcas contam todos os assuntos, calculados ou sem dado.
  - **Só nos calculados:** a conferência com o PL e os assuntos com uma série sênior.
  - **Faixas e divisão:** só os calculados que fecham com o PL a até 1%, como na seção 10.6 de `docs/fundos-descoberta.md`. As faixas contam só os assuntos com 2 ou mais séries, e a divisão do valor das séries sai em %, com 1 casa só na exibição.
- **Nunca traz** CNPJ, nome nem valor de linha. Um erro inesperado mostra só o tipo do erro.

### Medição em 27/11/2026 (cópias, só leitura; só contagens)

As cópias da etapa 12, que já têm a 006, foram abertas só para leitura. O SHA-256 de cada uma ficou igual. O banco real ficou com o SHA-256 igual, sem backup novo, e **não tem a 006**.

| | 09/2026 (cópia do banco de teste) | 10/2026 (cópia do banco real com o informe) |
|---|---|---|
| Assuntos | 4.425 | 4.506 |
| `calculado` / `sem_dado` | 4.246 / 179 | 4.306 / 200 |
| `sem_dado`: `soma_das_series_zero` / `valor_negativo` | 144 / 35 | 159 / 41 |
| `sem_serie_subordinada` (todos) | 1.076 | 1.571 |
| `ordem_entre_subordinadas_nao_informada` | 20 | 21 |
| Séries com subtipo ausente | 596 | 516 |
| `mais_de_uma_serie_mezanino` | 435 | 454 |
| Conferência com o PL (calculados): dentro / fora / PL menor ou igual a 0 | 4.142 / 97 / 7 | 4.194 / 108 / 4 |
| Calculados com uma série, sênior | 987 | 1.453 |
| Divisão (sênior / mezanino / subordinada / subtipo ausente) | 65,4% / 7,9% / 26,6% / 0,1% | 71,1% / 7,6% / 21,2% / 0,1% |

Em 09/2026, uma das 4 regras da cópia estava revisada (a revisão de teste da etapa 12); em 10/2026, todas eram `proposto`.

**Sanidade contra a seção 10.6** (09/2026, sem teste fixo):

| Medida | Seção 10.6 | Medido |
|---|---|---|
| Ordem entre subordinadas não informada | 20 | 20 |
| Linhas ou séries com subtipo ausente | 599 linhas | 596 séries |
| Faixas: 0 / abaixo de 5% / 5 a 10% / 10 a 20% / 20 a 30% / 30 a 50% / 50% ou mais | 626 / 91 / 66 / 213 / 225 / 426 / 1.522 | 618 / 91 / 66 / 212 / 225 / 425 / 1.522 |
| Divisão (sênior / mezanino / subordinada) | 65,5% / 7,9% / 26,6% | 65,4% / 7,9% / 26,7%, contando o subtipo ausente |

As medidas que parecem diferentes são diferença de base, e não de cálculo. Medido só lendo a cópia e o ZIP:
- **Uma série sênior:** a seção conta 1.056 no ZIP. Com séries no banco, são 1.049 com uma série e 27 com 2 ou mais, todas sênior: os 1.076 da marca. Os 987 do relatório são só os calculados; 62 das séries únicas têm soma zero.
- **PL:** contando todos os assuntos com séries, e não só os calculados, há 4.150 dentro de 1%, **113 fora** (como na seção) e 162 com PL menor ou igual a 0, contra os 177 com PL "vazio ou menor ou igual a 0" da seção.
- **Os assuntos fora do cadastro:** a seção conta as 4.444 classes do ZIP; o banco tem 4.425 assuntos.

### Não confirmado

1. **QT x VL:** não se sabe se é a parcela da série no PL. O texto da CVM não diz; só a aritmética fecha, a até 1% em 4.150 dos assuntos com séries em 09/2026.
2. **A ordem** entre subordinadas e entre mezaninos não é informada, e nunca é inferida.
3. **Os 15 PL "vazios" da seção 10.6** (177 contra 162): sem PL e com série, o banco não tem nenhum assunto. Não foi conferido se são os assuntos fora do cadastro.
4. **Revisão do mapa:** a subordinação usa regras ainda `proposto`. Falta a revisão de uma pessoa, e o banco real não tem a 006.
5. **De 09/2026 para 10/2026** (observação de dado; a causa não foi confirmada): os assuntos só com série sênior passam de 1.076 para 1.571, e as séries `subclasse subordinada subordinada` caem de 2.775 para 2.447.

   Foi medido em 27/11/2026, só lendo as duas cópias (o SHA-256 das duas ficou igual). Os assuntos foram casados pelo CNPJ só em memória, sem imprimir CNPJ, id nem nome:
   - 4.388 assuntos estão nos dois meses; 37 aparecem só em 09/2026 e 118 só em 10/2026;
   - dos 3.349 com série não sênior em 09/2026 (subordinada, mezanino ou de subtipo ausente), 489 estão em 10/2026 sem nenhuma série não sênior, e 29 não estão em 10/2026;
   - dos 489, 298 mantêm as mesmas séries seniores, com os mesmos rótulos normalizados.

   As duas cópias vêm de bancos diferentes, com o mesmo cadastro de 27/10/2026: o de teste, para 09/2026, e o real, para 10/2026.

## Indicadores de carteira vencida

O `src/fundos/indicators/` calcula, na leitura, três indicadores do informe mensal de FIDC já carregado (FU11.1), por assunto (a classe ou o fundo do informe) e por competência.

**Nada é gravado:** não há tabela nova nem migration. Cada valor sai com:
- a fonte (`tabela.coluna`);
- a competência;
- a observação de origem;
- o estado.

**Conexão.**
- `reading.open_read_only(caminho)` abre o banco com URI `mode=ro` e confere o `PRAGMA query_only`.
- Recusa caminho de rede e banco em WAL.
- As consultas rodam numa transação fechada com `ROLLBACK`.
- Quem já tem uma conexão pode passá-la direto às funções.

**Leitura por competência, e não pela view.**
- **O problema da view:** `current_observations` guarda só a competência mais recente de cada assunto e campo. Não serve para a série mensal, e misturaria competências num mesmo indicador: um campo que viesse vazio no mês novo continuaria com o valor do mês anterior.
- **O que `reading.read_competence` faz:** aplica a regra de ordem da view dentro de cada competência. Valem só as fontes ativas, depois a prioridade da fonte, depois a coleta mais recente e depois o `id`.
- **Diferença conhecida:** um valor `MANUAL` de competência antiga continua sendo o atual na view. Aqui, cada competência fica com o que foi informado nela.

**Estados e motivos.**
- Cada valor é `presente` ou `sem_dado`. O `sem_dado` traz um motivo: `campo_ausente`, `tipo_inesperado`, `competencia_anterior_nao_carregada`, `denominador_zero` ou `denominador_negativo`.
- **Ausente nunca vira zero,** e zero informado é zero.
- **Precisão:** os valores são `Decimal` exatos. O percentual tem 28 dígitos significativos e não é arredondado, porque arredondar é decisão de exibição.
- **Percentual acima de 100 não é cortado.**

**Campos lidos.** Cada indicador lê uma lista fechada de campos:
- campo de identificação (CPF ou CNPJ no nome) e coluna da lista de cedentes da `tab_I` (`TAB_I2A12_*` e `TAB_I2B12_*`) são recusados;
- nenhuma provisão é lida (`TAB_I2A11` e `TAB_I2B11` ficam para a FU11.3);
- nenhum campo de FIAGRO é lido.

**Blocos.**
- **`a`:** direitos creditórios com aquisição substancial dos riscos e benefícios (I.2.a e `tab_V`).
- **`b`:** sem aquisição substancial (I.2.b e `tab_VI`).
- **`a+b`:** soma a mesma medida dos dois blocos, que não se sobrepõem, e só existe com os dois presentes.

### Os indicadores

| Indicador | Função | Campos |
|---|---|---|
| Vencidos na carteira | `overdue.overdue_in_portfolio(conexao, competencia, denominador)` | R$: `tab_V.TAB_V_B_VL_DIRCRED_INAD` e `tab_VI.TAB_VI_B_VL_DIRCRED_INAD` ("Inadimplentes (Valor das Parcelas Inadimplentes, em R$)"). Ao lado, separados: a.2, a.2.1 e a.3 da `tab_I`, e os equivalentes do bloco b |
| Faixas de atraso | `overdue.delinquency_buckets(conexao, competencia)` | as 10 faixas de `tab_V.b` e `tab_VI.b`, de "Vencidos e não Pagos entre 1 e 30 dias" a "acima de 1080 dias", com o % de cada uma no total informado |
| Evolução das faixas | `overdue.bucket_evolution(conexao, competencia)` | cada faixa na competência M e em M-1 (último dia do mês anterior): os dois valores, a diferença em R$ e a diferença da participação em pontos percentuais |
| Indicador 10: "Por Prazo de Vencimento (R$)" | `prazo_de_vencimento.por_prazo_de_vencimento(conexao, competencia)` | a distribuição informada: `tab_V.TAB_V_A_VL_DIRCRED_PRAZO` e `tab_VI.TAB_VI_A_VL_DIRCRED_PRAZO`, cada um com as 10 faixas, de "Até 30 dias" a "Acima de 1080 dias", e o % de cada faixa no total |

**Denominador do % de vencidos** (decidido em 24/11/2026): é um parâmetro obrigatório, sem padrão.
- **`Denominator.PORTFOLIO` (D1):** `tab_I.TAB_I2_VL_CARTEIRA`, o mesmo para o bloco a, o bloco b e o total. Inclui títulos, cotas, compromissadas e CDB.
- **`Denominator.CREDIT_RIGHTS` (D2):** I.2.a para o bloco a, I.2.b para o b e a soma dos dois para o total. Os totais I.2.a e I.2.b vêm líquidos da provisão (seção 2.2 de `docs/fundos-sonda-pdd-cedente.md`).
- **O PL não é uma opção.**

**Regras de cálculo.**
- **Parcela e crédito não se somam.** a.2.1 (parcelas inadimplentes de créditos a vencer) e a.3 (créditos inadimplentes) são medidas diferentes e voltam separadas. O R$ de vencidos é o total `V.b` (ou `VI.b`) que a CVM informa.
- **O total nunca é recalculado pelas faixas,** nem nas faixas de atraso nem em "Por Prazo de Vencimento (R$)".
- **Evolução:** sem M-1 carregada para o assunto, o resultado é `sem_dado` (`competencia_anterior_nao_carregada`), e nenhum buraco é pulado.
  - A passagem de crédito de uma faixa para outra não é observável no informe, que é agregado, e não é calculada.
- **"Por Prazo de Vencimento (R$)"** é a distribuição como o informe a traz. O que o total cobre não está confirmado.

Exemplo, com o banco em disco local:

```python
from fundos.indicators.overdue import Denominator, overdue_in_portfolio
from fundos.indicators.reading import open_read_only

conexao = open_read_only(r"C:\<pasta-local>\fundos.db")
try:
    resultados = overdue_in_portfolio(conexao, "2026-09-30", Denominator.CREDIT_RIGHTS)
finally:
    conexao.close()
```

### Medição em 09/2026 (só leitura, só contagens)

Feita em 24/11/2026 numa cópia idêntica do banco de teste: o SHA-256 do original e o da cópia eram iguais, antes e depois. A cópia foi aberta com `mode=ro&immutable=1` e `query_only`.

**O dado:**
- uma competência carregada (2026-09-30), com 4.425 assuntos (4.394 classes e 31 fundos);
- nenhum campo dos indicadores ausente, porque o zero é gravado;
- nenhuma chave com mais de uma linha e nenhum conflito aberto.

**Vencidos, D1:**
- % presente em 4.276 assuntos; `denominador_zero` em 147 e `denominador_negativo` em 2;
- acima de 100% em 147 assuntos (bloco a), 32 (bloco b) e 175 (a+b).

**Vencidos, D2:**

| | Bloco a | Bloco b | a+b |
|---|---|---|---|
| % presente | 2.874 | 1.103 | 3.259 |
| `denominador_zero` | 1.550 | 3.322 | 1.165 |
| `denominador_negativo` | 1 | 0 | 1 |
| acima de 100% | 203 | 62 | 191 |

**Faixas de atraso:** `V.b` > 0 em 1.655 assuntos e `VI.b` > 0 em 846 (1.984 com algum dos dois).

**Evolução:** os 4.425 assuntos não têm 08/2026, então todos dão `competencia_anterior_nao_carregada`.

**"Por Prazo de Vencimento (R$)":** `V.a` > 0 em 2.844 assuntos, zero em 1.579 e negativo em 2; `VI.a` > 0 em 1.099.

**Tempo:** de 1,5 s a 6,6 s por indicador, para todos os assuntos.

**Aritmética informativa** (tolerância de R$ 1; descreve o dado e não define nenhum campo):
- o total `V.b` fecha com a soma das 10 faixas em 1.655 de 1.655 assuntos com `V.b` > 0, e com a.2.1 + a.3 em 4.425 de 4.425;
- o `VI.b` fecha com b.2.1 + b.3 em 4.425 de 4.425;
- o `V.a` fecha com a.1 em 2.422 de 2.844 assuntos com `V.a` > 0.

### Não confirmado

1. **`V.b` = a.2.1 + a.3 como regra:** o dado fecha em todos os assuntos de 09/2026, mas o texto da CVM não diz isso.
2. **O que o total "Por Prazo de Vencimento (R$)" cobre** (`V.a` e `VI.a`): a descrição oficial não diz.
3. **Prazo médio:** o informe de FIDC não tem esse campo, e nada é estimado.
4. **Os itens a.5 a a.10 da `tab_I`:** não se sabe se são recortes de a.1 a a.4, nem se as parcelas deles entram em `V.b`.
5. **A evolução no dado real:** há uma competência só carregada. Ela foi testada com dado sintético.
6. **O sentido dos valores negativos:** carteira (2 assuntos), direitos creditórios a + b (1) e `V.a` (2).

## Cedentes e alienações a partes relacionadas

Dois indicadores do informe de FIDC já carregado, por assunto (classe ou fundo) e competência (FU11.2). Como os da seção anterior, são calculados na leitura, com a conexão só de leitura e os mesmos estados. Nada é gravado.

### Cedentes gravados (`cedentes.stored_cedentes(conexao, competencia)`)

**O que o informe traz.** Em cada bloco da `tab_I` há até 9 posições de cedente, com CPF ou CNPJ e percentual:
- **bloco a:** com aquisição substancial dos riscos e benefícios, `TAB_I2A12_*`;
- **bloco b:** sem aquisição substancial, `TAB_I2B12_*`.

O modelo pede o cedente "quando representar mais de 10% do PL do fundo" (seção 3 de `docs/fundos-sonda-pdd-cedente.md`).

**O que está no banco.** A carga grava só o cedente com CNPJ válido, sem nome. O percentual vai como veio.
- **O cedente com CPF não é gravado.** O informe pode ter cedente pessoa física que não aparece aqui.
- A lista é a dos cedentes **gravados**, com a posição e o percentual como informado.
- O CNPJ não aparece em `repr`, log, erro nem relatório.

**Regras de leitura.**
- **Bloco sem cedente gravado** sai com o estado e o motivo `sem_cedente_gravado`, nunca zero nem "sem concentração". Não se sabe se não há cedente acima do corte, se o cedente tem CPF ou se o informe não o trouxe.
- **A quantidade é um mínimo, nunca o total.** Conta os CNPJs distintos gravados no bloco.
- **O maior percentual** é o maior valor informado entre os gravados, sem conta nenhuma.
  - Leva o qualificador do próprio valor, que pode ser `acima_de_100`.
  - Não é medida de concentração.
- **O percentual** (decisão de 24/11/2026) é mostrado como informado e não entra em conta nenhuma enquanto a base não for confirmada. O qualificador nunca muda o valor: `acima_de_100`, `zero`, `ate_10` (acima de 0 e até 10) ou `negativo`.
- **Marcas do bloco:**
  - `lista_cheia`: a posição 9 está ocupada, e a lista do informe pode estar cortada;
  - `posicao_sem_cnpj_gravado`: há posição sem CNPJ gravado abaixo da maior. No arquivo ela estava vazia, era CPF ou era inválida, e não se distingue qual;
  - `cnpj_repetido_no_bloco`: o mesmo CNPJ em duas posições;
  - `posicao_com_mais_de_um_cnpj`: só acontece com reapresentação. Os dois CNPJs são listados e nenhum é escolhido.
- **Cedente nos dois blocos:** cada bloco o mostra separado, com a marca `in_other_block`. Os blocos nunca são juntados.
- **Limitação da carga** (veja "Papéis"): com reapresentação, o conjunto de cedentes de uma competência é a soma dos ZIPs carregados e pode incluir cedente que saiu.

### Alienações do mês a partes relacionadas (`partes_relacionadas.alienacoes_partes_relacionadas(conexao, competencia)`)

São **alienações** de direitos creditórios **realizadas no mês**, e não aquisições nem uma medida geral de parte relacionada. Vêm do item VII do modelo ("Negócios com Direitos Creditórios Realizados no Mês"), letra b), e só dos dois grupos cuja descrição oficial cita parte relacionada:
- **VII.b.1:** "Para o Cedente e Partes Relacionadas aos Cedentes";
- **VII.b.2:** "Para os Prestadores de Serviços e Partes Relacionadas aos Prestadores de Serviços".

Cada grupo traz Quantidade, Valor e Valor Contábil, como informados.
- **Nada é calculado entre Valor e Valor Contábil,** porque o dicionário não define a diferença.
- **Ficam fora:** VII.a (aquisições), VII.b.3 (alienações para terceiros), VII.c (substituições) e VII.d (recompras), cuja descrição não cita parte relacionada.

### Medição em 09/2026 (só leitura, só contagens)

Feita em 24/11/2026 na mesma cópia idêntica do banco de teste, aberta com `mode=ro&immutable=1` e `query_only`. O SHA-256 ficou igual antes e depois.

**Os totais:** 4.425 assuntos, 1.989 deles com algum cedente gravado; 3.587 cedentes e 3.587 percentuais.

| Bloco | Com cedente gravado | Total do bloco > 0 | Total do bloco = 0 | `sem_cedente_gravado` | `lista_cheia` | `cnpj_repetido_no_bloco` | `posicao_sem_cnpj_gravado` |
|---|---|---|---|---|---|---|---|
| a | 1.622 | 1.530 | 92 | 2.803 | 0 | 3 | 25 |
| b | 665 | 533 | 132 | 3.760 | 5 | 0 | 3 |

**O resto:**
- `posicao_com_mais_de_um_cnpj`: 0; conflito aberto: 0.
- Cedente nos dois blocos: 208 pares (assunto, CNPJ).

**Qualificadores do percentual:**

| Bloco | `acima_de_100` | `zero` | `ate_10` | Sem qualificador (acima de 10 e até 100) | `negativo` |
|---|---|---|---|---|---|
| a | 301 | 66 | 125 | 1.975 | 0 |
| b | 79 | 58 | 44 | 939 | 0 |

**Alienações a partes relacionadas,** nos 4.425 assuntos:
- VII.b.1 é positivo em 6 assuntos (Quantidade e Valor) e em 5 (Valor Contábil);
- VII.b.2 é positivo em 3, nos três campos;
- o resto é zero.

**Tempo:** cerca de 1 s por função, para todos os assuntos.

### Não confirmado

1. **A base do percentual do cedente.** Há valores iguais a 0, de 0 a 10 e acima de 100.
2. **O bloco sem cedente gravado:** não se sabe se não há cedente acima de 10% do PL, se o cedente tem CPF ou se o informe não o trouxe.
3. **A lista cortada:** não se sabe se as 9 posições cortam a lista do informe. Se a posição 9 for CPF, a lista cheia nem é detectada.
4. **A posição sem CNPJ gravado:** vazia, CPF ou inválida, e não se distingue qual.
5. **A diferença entre Valor e Valor Contábil** em VII.b.
6. **Partes relacionadas além das alienações de VII.b.1 e VII.b.2:** o informe não traz outra medida.

## Provisão para Redução no Valor de Recuperação e cobertura

A função é `reducao_valor_recuperacao.provisao_reducao_valor_recuperacao(conexao, competencia)` (FU11.3). Por assunto (classe ou fundo), competência e bloco, ela dá a provisão da carteira de direitos creditórios e a cobertura dos vencidos por ela. É calculada na leitura, com a conexão só de leitura e os estados das seções anteriores. Nada é gravado.

### A provisão

- **Campos:** `tab_I.TAB_I2A11_VL_REDUCAO_RECUP` (bloco a) e `tab_I.TAB_I2B11_VL_REDUCAO_RECUP` (bloco b).
- **Nome oficial:** "Provisão para Redução no Valor de Recuperação". São os itens a.10 e b.10 do Suplemento G, e a.11 e b.11 no dicionário.
- **PDD (equivalência não confirmada):** nenhuma fonte oficial usa essa sigla.
- **Sinal:** o valor vem positivo e é subtraído do total do bloco, então os totais I.2.a e I.2.b já vêm líquidos (seção 2 de `docs/fundos-sonda-pdd-cedente.md`).
- **Como sai:** como informada, por bloco. O a+b só existe com os dois blocos presentes e sem valor negativo.
- **Nunca são lidas:** `TAB_I2_COTA_FIDC`, `TAB_I2_DEBENTURE_CRI` e `TAB_I2_VL_OUTRO_ATIVO`. São provisões sobre cotas de FIDC, sobre debêntures e CRI e sobre outros ativos, e não sobre a carteira de direitos creditórios.
- **FIAGRO:** nenhum campo de provisão foi confirmado, e fica de fora.

### A cobertura

A cobertura é a provisão dividida pelos vencidos, vezes 100, por bloco e no a+b. Os vencidos são o total `V.b` (ou `VI.b`), "Inadimplentes (Valor das Parcelas Inadimplentes, em R$)", o mesmo da FU11.1 (decisão de 24/11/2026).

- **A provisão cobre o bloco todo, e não só o vencido.** A cobertura compara a provisão do bloco com o vencido do bloco. Ela não diz quanto do vencido está provisionado.
- **Cobertura acima de 100% não é erro.** A provisão é do bloco todo, e o vencido (`V.b` ou `VI.b`) é só uma parte dele, por isso o valor não é cortado.
  - Em 09/2026, a cobertura passa de 100% em 634 de 1.655 assuntos no bloco a, 191 de 846 no bloco b e 681 de 1.984 no a+b.
- **Estados, nesta ordem:**
  1. falta um dos lados: `sem_dado` com o motivo da parte (`campo_ausente` ou `tipo_inesperado`);
  2. provisão negativa: `sem_dado/provisao_negativa`, sem conta, e o R$ continua como informado;
  3. vencidos negativos: `sem_dado/vencidos_negativos`;
  4. vencidos iguais a 0: `sem_dado/denominador_zero`, com a provisão em R$ presente;
  5. fora disso, presente. Provisão 0 com vencidos > 0 é 0%: zero informado é zero.
- **No a+b,** um bloco com valor negativo impede a soma, com o mesmo motivo.
- **Marca `provisao_sem_vencidos`:** a provisão é maior que 0 e os vencidos são 0, para não parecer que não há o que cobrir.
- **Fica de fora** (decisão de 24/11/2026): nada é somado nem comparado com a.2.1, a.3 ou o total do bloco. Não há "bruto" (total do bloco + provisão) nem provisão como % da carteira.

### Medição em 09/2026 (só leitura, só contagens)

Feita em 24/11/2026 na mesma cópia idêntica do banco de teste, aberta com `mode=ro&immutable=1` e `query_only`. O SHA-256 ficou igual antes e depois. São 4.425 assuntos: 4.394 classes e 31 fundos.

| Medida | Bloco a | Bloco b | a+b |
|---|---|---|---|
| Provisão positiva | 1.550 | 791 | 1.862 |
| Provisão zero | 2.875 | 3.634 | 2.563 |
| Provisão ou vencidos negativos, ou ausentes | 0 | 0 | 0 |
| Vencidos > 0 | 1.655 | 846 | 1.984 |
| Cobertura acima de 0 e até 100% | 789 | 575 | 1.058 |
| Cobertura acima de 100% | 634 | 191 | 681 |
| Cobertura igual a 0% | 232 | 80 | 245 |
| `denominador_zero` | 2.770 | 3.579 | 2.441 |
| `provisao_sem_vencidos` | 127 | 25 | 123 |

**Diferença para a contagem no ZIP** (FU11.0: no bloco a, 1.551 positivas e 2.893 zeros; no b, 791 e 3.653):
- os dois blocos têm 19 linhas a menos, que é a diferença entre as 4.444 linhas do ZIP e os 4.425 assuntos carregados;
- são as linhas cujo assunto não está no cadastro;
- uma delas tinha provisão positiva no bloco a, e as outras eram zero.

**Teste de vazamento:** em `repr()` e `str()` dos 4.425 resultados, 0 CNPJ de assunto, 0 sequência de 14 dígitos e 0 máscara de CNPJ ou de CPF.

**Tempo:** cerca de 1 s para todos os assuntos.

### Não confirmado

1. **A equivalência entre a "Provisão para Redução no Valor de Recuperação" e a PDD.**
2. **Quanto do vencido está provisionado:** a provisão é do bloco todo.
3. **O "bruto" do bloco (total + provisão):** só a aritmética de 09/2026 o sugere, e o texto da CVM não.
4. **Por que há provisão maior que 0 com vencidos iguais a 0:** são 127 assuntos no bloco a e 25 no b.
5. **A provisão no FIAGRO:** não há campo descrito no dicionário.

## Como renomear

- **Só a pasta** (`git mv Gui/fundos Gui/<nome>`): nenhum import muda; atualize os comandos deste README.
- **O pacote** (`fundos` para `<pacote>`): `git mv src/fundos src/<pacote>`, troque `fundos.` nos imports de `src/`, `scripts/` e `tests/`, e a mensagem "Pacote fundos:" de `scripts/apply_migration.py`, de `scripts/load_cadastro.py`, de `scripts/load_informe_fidc.py` e de `scripts/load_informe_fiagro.py` e o teste dela. Rode a suíte.

## Pontos para o Fábio

- A camada compartilhada aceita CNPJ alfanumérico (ADR-011, `docs/architecture/ADR-011-cnpj-alfanumerico.md`): `normalize_cnpj` em `src/pense_alm/shared/entities/identifiers.py` valida o formato e o dígito verificador com a mesma regra de `src/fundos/cnpj.py`. A única diferença é a máscara parcial (por exemplo, `12.ABC.34501DE-35`), que a camada aceita e este módulo recusa. O futuro adaptador de Fundos deixa de estar bloqueado por isso.
- O CHECK de `issuers.cnpj` nas debêntures (`Eduardo/debenture-replica/migrations/001_initial_schema.sql`) só aceita dígitos e também recusaria CNPJ alfanumérico.
- Este módulo tem utilitário próprio de CNPJ (`src/fundos/cnpj.py`), com dígito verificador numérico e alfanumérico. Unificar com a camada compartilhada fica a seu critério.
