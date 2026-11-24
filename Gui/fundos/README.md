# Fundos (FIDC, FIC-FIDC, FIAGRO): base do módulo

Dono da frente: Gui (`docs/decisoes-em-aberto.md`, decisão 1 de Fundos). O nome da pasta (`Gui/fundos`) e o do pacote Python (`fundos`) são **provisórios**: o nome definitivo é do Gui. Veja "Como renomear".

## O que existe

- Banco SQLite próprio, criado pela migration `migrations/001_initial_schema.sql`, com o mesmo esqueleto de proveniência das debêntures: `sources`, `collection_runs`, `raw_records`, `observations`, `data_conflicts`, `audit_log`, a view `current_observations` e `schema_migrations`. Os assuntos são `funds`, `fund_classes` e `quota_series`.
- A migration `migrations/002_party_observations.sql` cria `party_observations` (papéis com vários valores: gestor, administrador, custodiante, controlador e auditor) e `party_conflicts`. Veja "Papéis".
- A migration `migrations/003_party_observation_shares.sql` cria `party_observation_shares`, com o percentual do cedente do informe de FIDC, 1:1 com a linha do cedente em `party_observations`. Veja "Papéis".
- `src/fundos/`: conexão (`database.py`), utilitário de CNPJ (`cnpj.py`), guarda de dados pessoais (`personal_data.py`), backup (`backup.py`) e repositórios mínimos (`repositories/`).
- `src/fundos/cvm_csv.py`: leitura comum dos CSV da CVM (cp1252 estrito, cabeçalho exato, largura das linhas, conversão por tipo, situação do identificador), usada pelo cadastro e pelo informe.
- `src/fundos/cadastro/`: leitor do cadastro de fundos da CVM (`registro_fundo_classe.zip`), sem banco (`reader.py`, com a lista fechada de colunas em `columns.py`); filtro de FIDC e FIAGRO e escolha do registro vigente (`selection.py`); gravação (`loader.py`); e relatório só com agregados (`report.py`).
- `src/fundos/informe_fidc/`: leitor do informe mensal de FIDC (`inf_mensal_fidc_AAAAMM.zip`, 18 tabelas), sem banco (`reader.py`, com a lista fechada das 461 colunas em `columns.py`); gravação (`loader.py`); e relatório só com agregados (`report.py`).
- `src/fundos/informe_fiagro/`: leitor do informe mensal de FIAGRO (`inf_mensal_fiagro_AAAAMM.zip`, 2 arquivos), sem banco (`reader.py`, com a lista fechada das 133 + 6 colunas em `columns.py`); gravação (`loader.py`); e relatório só com agregados (`report.py`).
- `src/fundos/indicators/`: indicadores calculados na leitura a partir do informe de FIDC já carregado (vencidos na carteira, faixas de atraso, a distribuição "Por Prazo de Vencimento (R$)", os cedentes gravados e as alienações do mês a partes relacionadas), sem gravar nada. Veja "Indicadores de carteira vencida" e "Cedentes e alienações a partes relacionadas".
- `scripts/apply_migration.py`: aplica as migrations numeradas, com backup e verificação.
- `scripts/load_cadastro.py`: carrega os FIDC e FIAGRO do cadastro. Veja "Como carregar o cadastro".
- `scripts/load_informe_fidc.py`: carrega o informe mensal de FIDC. Veja "Como carregar o informe de FIDC".
- `scripts/load_informe_fiagro.py`: carrega o informe mensal de FIAGRO. Veja "Como carregar o informe de FIAGRO".

## O que ainda não existe

Coletor, acesso à rede, banco real, dados reais e adaptador para a camada compartilhada. Ficam para etapas futuras do plano de Fundos:

- a migration de prioridade das fontes (ADR-010, proposta);
- o `registro_subclasse` como dado (hoje só entra no manifesto);
- na reapresentação do informe: registrar no banco a célula que sumiu, guardar o conjunto exato de cedentes de cada ZIP e unir a série que trocou de rótulo à antiga (hoje só são contados; cada um exigiria uma migration nova, com o próximo número livre na hora (a 004 é a das holdings, no ramo do Gui, e a 005 está reservada à prioridade de fontes do ADR-010, ainda proposta), se o Gui quiser);
- a reapresentação do informe de FIAGRO: hoje uma competência = um ZIP (outro ZIP do mesmo mês é recusado), e `Versao` e `Data_Entrega` só são gravadas, sem ordenar nada;
- as classes de chave repetida no arquivo de FIAGRO e as subclasses delas (2 classes e 9 linhas de subclasse em 09/2026): só contadas, até o Gui decidir;
- a comparação, na leitura, entre o informe de FIAGRO e o de FIDC e entre o informe e o cadastro (gestor e administradora): a conferência foi feita na FU5.2 (seção 10.5 de `docs/fundos-descoberta.md`) e o Gui decidiu em 04/11/2026 que vale o informe que corresponde ao `Tipo_Classe` e, para gestor e administradora, o cadastro vigente (F-03 e F-05 de `docs/regras-de-exibicao-pendentes.md`). Nada disso está no código: o banco não compara os informes, a comparação fica na camada de leitura (FU9.2) e a view de valor atual dos papéis entra antes da FU9.1. O informe de FII foi amostrado (seção 13 de `docs/fundos-descoberta.md`) e não é carregado;
- a `tab_VIII` e a `tab_X_4` do informe, lidas e conferidas mas **não carregadas** (várias linhas para o mesmo assunto e campo). A `tab_X_4` (captações, resgates e amortizações por série) fica **indisponível** até uma tarefa própria, com ADR (uma dimensão a mais em `observations`);
- o uso do percentual do cedente em contas e as métricas de concentração: pela decisão de 24/11/2026 (FU11.2), o percentual é só mostrado como informado, com qualificador, até a base dele ser confirmada, e não há métrica de concentração. A forma de exibir continua em aberto;
- **pendência do FIAGRO nos indicadores de carteira vencida (FU11.1):** os campos `Vencidos_*`, `A_Vencer_*` e `Total_Ativos_Prazo_Vencimento` do informe de FIAGRO ficaram fora por falta de descrição oficial. O dicionário de FIAGRO descreve 13 dos 133 campos, e nenhum destes. A inclusão depende da leitura do Anexo Normativo VI da Resolução CVM 175 e do modelo do informe de FIAGRO, que exige aprovação de rede;
- a evolução das faixas de atraso conferida no dado real: o banco de teste tem uma competência só do informe de FIDC (09/2026). Uma segunda exige baixar outro mês (rede, com aprovação) e carregá-lo numa cópia;
- a política de volume: retenção e frequência das cargas (o cadastro grava o retrato inteiro a cada carga; o informe, cerca de 0,6 GB por competência);
- a carteira de cotas de fundos;
- o mapa de séries sênior, mezanino e subordinada;
- a resolução de conflitos com `audit_log`.

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
  - Limitação conhecida: se o valor antigo volta depois de um conflito (A, depois B, depois A de novo), não há linha nova; o conflito A×B continua aberto e a view mostra B. A carga do informe de FIDC trata esse caso (veja "Reapresentação"); o cadastro continua com a limitação.
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
- **O banco real fica fora do Git e em disco local**, não no compartilhamento de rede. Não versionar `*.db`, `*.sqlite*`, ZIPs, CSVs da CVM, backups nem `.env` (veja `.gitignore`).

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
- **Caminho longo:** se o caminho do backup ou do banco, com `-journal`, chegar a 260 caracteres, o script recusa antes de tocar no banco. Use `--backup-dir` com uma pasta curta (por exemplo `C:\bk\fundos`).
- Nova migration: novo arquivo `migrations/NNN_nome.sql` que termina com `INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(NNN,'nome');`. Nunca edite uma migration já aplicada.

## Como carregar o cadastro

O `scripts/load_cadastro.py` lê o `registro_fundo_classe.zip` da CVM (baixado à mão, fora do Git), escolhe os FIDC e FIAGRO vigentes e grava fundos, classes, observações e papéis. `--database`, `--zip` e `--reference-date` são obrigatórios, e `--dry-run` ou `--commit` também. Rode sempre o `--dry-run` antes. O `--commit` só com aprovação explícita.

```powershell
cd Gui\fundos
# prévia: lê o ZIP e imprime só agregados; não escreve em banco nenhum
python scripts\load_cadastro.py --database C:\<pasta-local>\fundos.db --zip C:\<pasta-local>\cvm-amostras\cadastro-fidc\registro_fundo_classe.zip --reference-date 2026-10-27 --dry-run
# carga (banco já criado e migrado com scripts\apply_migration.py)
python scripts\load_cadastro.py --database C:\<pasta-local>\fundos.db --zip C:\<pasta-local>\cvm-amostras\cadastro-fidc\registro_fundo_classe.zip --reference-date 2026-10-27 --commit
```

- **Banco em disco local.** SQLite em compartilhamento de rede não é seguro. Se `--database` apontar para um caminho de rede (`\\servidor\...`, inclusive um caminho relativo rodado de dentro do compartilhamento), o script avisa no stderr e segue. Use uma pasta local, como nos exemplos.
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

- **Banco em disco local**, como no cadastro: caminho de rede só gera aviso no stderr.
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

O `scripts/load_informe_fiagro.py` lê o `inf_mensal_fiagro_AAAAMM.zip` da CVM (baixado à mão, fora do Git) e grava as observações do mês, as subclasses, a administradora e a gestora das classes que **já estão no banco**: o cadastro tem de ser carregado antes. `--database` e `--zip` são obrigatórios, e `--dry-run` ou `--commit` também. Não há `--reference-date`. `--last-modified` é opcional. Rode sempre o `--dry-run` antes. O `--commit` só com aprovação explícita. As regras abaixo são da FU5.1 e valem como **proposta: o Gui precisa confirmar**.

```powershell
cd Gui\fundos
# prévia: lê e confere o ZIP; com o banco, mostra o casamento com o cadastro; não escreve nada
python scripts\load_informe_fiagro.py --database C:\<pasta-local>\fundos.db --zip C:\<pasta-local>\cvm-amostras\fiagro\inf_mensal_fiagro_202609.zip --dry-run
# carga (banco migrado e com o cadastro carregado)
python scripts\load_informe_fiagro.py --database C:\<pasta-local>\fundos.db --zip C:\<pasta-local>\cvm-amostras\fiagro\inf_mensal_fiagro_202609.zip --commit
```

- **Banco em disco local**, como no cadastro: caminho de rede só gera aviso no stderr.
- **Competência:**
  - é o `AAAAMM` dos dois membros (e do nome do ZIP, quando segue o padrão `inf_mensal_fiagro_AAAAMM.zip`);
  - `Data_Referencia` tem de ter um só valor nos dois arquivos, **o dia 1 desse mês**; senão o arquivo é recusado e nada é lido;
  - a competência gravada (`reference_date`) é o **último dia do mês** (`2026-09-30`), a mesma convenção do `DT_COMPTC` do FIDC, para que os dois informes do mesmo mês empatem na data;
  - **a data gravada não é a literal do arquivo** (`2026-09-01`): a literal é reconstruível, porque o leitor só aceita o dia 1;
  - não pode ser posterior a hoje (UTC); `collected_at` é o início da coleta.
- **Formato:** os 2 membros e só eles (`inf_mensal_fiagro_AAAAMM.csv`, 133 colunas, e `inf_mensal_fiagro_subclasse_AAAAMM.csv`, 6 colunas), cp1252 estrito, com o cabeçalho exatamente o da lista fechada (`src/fundos/informe_fiagro/columns.py`, montada do cabeçalho do dado de 09/2026, não do dicionário, que descreve só 13 dos 133 campos). Qualquer diferença aborta sem gravar nada.
- **Identidade:** o `CNPJ_Classe` tem de estar em `fund_classes`. Nenhum fundo nem classe é criado, e nunca se casa por nome. O resto não carrega e é contado por arquivo e por classe: `CNPJ_Classe` vazio, CPF ou inválido; chave repetida no arquivo; CNPJ só como fundo; CNPJ fora do cadastro carregado; e, na subclasse, sem linha no arquivo de classe, rótulo vazio e par (classe, rótulo) repetido.
- **Chave repetida:** um `CNPJ_Classe` em mais de uma linha do arquivo de classe não entra (nenhuma das linhas, nem as subclasses dele). Nada é escolhido por `Versao`, `Data_Entrega` ou nome; o relatório conta as chaves, as linhas e as chaves com `Versao` diferente. A coleta fica `success`, com `chaves_repetidas_nao_carregadas` no `error_summary`.
- **O que vira observação:** `inf_mensal_fiagro.<Coluna>` (da classe) e `inf_mensal_fiagro_subclasse.<Coluna>` (da série), sem renomear: 123 das 133 colunas e 3 das 6.
  - `CNPJ_Classe` e `Data_Referencia` são chave.
  - `Nome_Classe` é observação da classe, como vem; o do arquivo de subclasse só é conferido, e a divergência é contada.
  - Os `field_name` não coincidem com os do FIDC (`tab_*`) nem com os do cadastro (`registro_*`): a classe que está nos dois informes (1 em 09/2026) fica com os dois conjuntos, sem conflito falso.
- **Não carregadas:** `Email_Administrador`, `Site` e `Servico_Atendimento_Cotista` (contato, decisão 3 de Fundos) e `Entidade_Administradora` (traz telefone em parte das linhas). São exigidas no cabeçalho e descartadas sem serem guardadas nem contadas.
- **Valores:**
  - decimal exato, com a notação científica convertida e contada por coluna, como no FIDC; zero é valor informado e vazio não tem linha; número, data e S/N fora do formato abortam;
  - texto livre (`Regra_Anexo`, `Classificacao_Autorregulada`, `Prazo_Duracao`, `Encerramento_Exercicio_Social`) é gravado como vem, sem interpretar; nenhuma variante é derivada (decisão 7);
  - `Versao` (numérica) e `Data_Entrega` (data) são observações comuns e não ordenam nada;
  - `Codigo_ISIN` é texto e não é chave nem identidade (em 09/2026, 3 ISIN aparecem em duas classes cada).
- **Papéis:** `CNPJ_Administrador` e `Nome_Administrador` (papel `administrador`) e `CNPJ_Gestor` e `Nome_Gestor` (papel `gestor`) vão para `party_observations` da classe, só com CNPJ válido.
  - CPF (11 dígitos ou máscara), vazio ou inválido é descartado junto com o nome e contado; a máscara do CNPJ é tirada; 12 ou 13 dígitos com DV válido ganham os zeros.
  - O gestor e a administradora do cadastro ficam no fundo (`registro_fundo.*`), com a data do retrato. Os do informe convivem com eles, cada um com a sua proveniência, sem conflito; a divergência foi medida na FU5.2 (seção 10.5 de `docs/fundos-descoberta.md`) e, pela decisão de 04/11/2026 (F-03 de `docs/regras-de-exibicao-pendentes.md`), o valor atual é o do cadastro vigente; o banco não compara os dois.
- **Subclasses:** cada linha vira uma série da classe (`quota_series`) pelo rótulo normalizado, com a regra do FIDC e sem ID da CVM (o arquivo não tem); o rótulo original fica como observação da série. Nada diz sênior ou subordinada (FU6.2).
  - As duas grafias de "Subclasse 1" (`Subclasse 1 (ou classe única)` e `Subclasse 1(ou classe única)`) viram **chaves diferentes**. Em 09/2026 nenhuma classe tem as duas.
  - O par (classe, rótulo normalizado) repetido não entra (3 em 09/2026, todos nas chaves repetidas).
- **`--last-modified`:** opcional, só como registro (a reapresentação do FIAGRO ainda não existe).
  - Se informado: a mesma normalização do FIDC (ISO com fuso, como `2026-10-24T11:46:15Z`, ou o texto do cabeçalho HTTP; sem fuso ou no futuro, recusado), gravado em `raw_records.last_modified` do ZIP e mostrado em UTC, com o aviso quando a data dos membros passa dela em mais de 1 dia.
  - Se não: `raw_records.last_modified` fica vazio e o relatório diz "Last-Modified do ZIP: nao informado".
- **Uma competência = um ZIP:** o mesmo ZIP (mesmo SHA-256) diz "Nada a carregar" e não faz backup. Outro ZIP de uma competência já carregada é recusado no dry-run e no commit, sem backup. Carregue o ZIP mais recente do mês. Uma competência nova é carga normal, e as séries que já existem são reaproveitadas.
- **Riscos conhecidos:**
  - a CVM atualiza o conjunto toda semana: até a reapresentação existir, a atualização de um mês já carregado não entra;
  - se uma atualização semanal trouxer `Versao` 1 e `Versao` 2 da mesma classe no mesmo ZIP, as duas linhas caem na regra de chave repetida e a classe fica sem dado até a tarefa de reapresentação;
  - se a grafia de "Subclasse 1" mudar de um mês para outro, nasce outra série para a mesma subclasse; unir as grafias seria uma regra nova, do Gui;
  - se o rótulo de uma série do FIDC e o de uma subclasse do FIAGRO da mesma classe normalizarem igual, os dois usam a mesma série (sem conflito, porque os campos são outros).
- **Migrations:** 001 e 002, como o cadastro (sem cedente, não precisa da 003).
- **Antes do COMMIT:** `integrity_check`, `foreign_key_check`, nenhuma coluna com `cpf` e nenhum texto inteiro com formato de CPF no que a coleta gravou (texto, nome e CNPJ). Se algo falhar, desfaz tudo e mantém o backup.
- **Saída:** 0 (sucesso ou nada a fazer), 1 (erro, com "Erro ao carregar o informe de FIAGRO: ..." no stderr), 2 (argumentos).
- **O relatório tem só agregados**, nunca CNPJ, nome, ISIN ou valor: linhas e colunas por arquivo, CNPJ por situação, chaves repetidas, `Versao` igual ou diferente de 1, datas de entrega distintas, ISIN, notação científica, papéis, subclasses, o casamento por arquivo e por classe e os candidatos (dry-run) ou o que foi gravado (commit).
- **Esperado em 09/2026** (contagem em memória, só agregados, do arquivo de SHA-256 `a9700ab7...0948` da seção 9.1 de `docs/fundos-descoberta.md`): 312 linhas de classe (310 `CNPJ_Classe`), 308 carregáveis; 697 linhas de subclasse, 688 carregáveis (688 séries); 39.316 observações (37.252 da classe e 2.064 das séries); 616 papéis (308 administradores e 308 gestores). Com o cadastro de 27/10/2026, as 308 classes carregáveis estão em `fund_classes`.

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

## Como renomear

- **Só a pasta** (`git mv Gui/fundos Gui/<nome>`): nenhum import muda; atualize os comandos deste README.
- **O pacote** (`fundos` para `<pacote>`): `git mv src/fundos src/<pacote>`, troque `fundos.` nos imports de `src/`, `scripts/` e `tests/`, e a mensagem "Pacote fundos:" de `scripts/apply_migration.py`, de `scripts/load_cadastro.py`, de `scripts/load_informe_fidc.py` e de `scripts/load_informe_fiagro.py` e o teste dela. Rode a suíte.

## Pontos para o Fábio

- A camada compartilhada aceita CNPJ alfanumérico (ADR-011, `docs/architecture/ADR-011-cnpj-alfanumerico.md`): `normalize_cnpj` em `src/pense_alm/shared/entities/identifiers.py` valida o formato e o dígito verificador com a mesma regra de `src/fundos/cnpj.py`. A única diferença é a máscara parcial (por exemplo, `12.ABC.34501DE-35`), que a camada aceita e este módulo recusa. O futuro adaptador de Fundos deixa de estar bloqueado por isso.
- O CHECK de `issuers.cnpj` nas debêntures (`Eduardo/debenture-replica/migrations/001_initial_schema.sql`) só aceita dígitos e também recusaria CNPJ alfanumérico.
- Este módulo tem utilitário próprio de CNPJ (`src/fundos/cnpj.py`), com dígito verificador numérico e alfanumérico. Unificar com a camada compartilhada fica a seu critério.
