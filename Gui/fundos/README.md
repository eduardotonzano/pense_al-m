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
- `scripts/apply_migration.py`: aplica as migrations numeradas, com backup e verificação.
- `scripts/load_cadastro.py`: carrega os FIDC e FIAGRO do cadastro. Veja "Como carregar o cadastro".
- `scripts/load_informe_fidc.py`: carrega o informe mensal de FIDC. Veja "Como carregar o informe de FIDC".

## O que ainda não existe

Coletor, acesso à rede, banco real, dados reais e adaptador para a camada compartilhada. Ficam para etapas futuras do plano de Fundos:

- a migration de prioridade das fontes (ADR-010, proposta);
- o `registro_subclasse` como dado (hoje só entra no manifesto);
- na reapresentação do informe: registrar no banco a célula que sumiu, guardar o conjunto exato de cedentes de cada ZIP e unir a série que trocou de rótulo à antiga (hoje só são contados; cada um exigiria uma migration nova, a 005, se o Gui quiser);
- a `tab_VIII` e a `tab_X_4` do informe, lidas e conferidas mas **não carregadas** (várias linhas para o mesmo assunto e campo). A `tab_X_4` (captações, resgates e amortizações por série) fica **indisponível** até uma tarefa própria, com ADR (uma dimensão a mais em `observations`);
- o uso dos cedentes: a regra para o percentual (em 09/2026, 385 valores acima de 100), as métricas de concentração e a forma de exibir são do Gui (Fases 6 a 10). Hoje os cedentes só são gravados;
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
  - **Proposta ainda não aprovada pelo Gui:** se a regra do CPF vale também para o arquivo original da CVM (`docs/decisoes-em-aberto.md`, decisão 3).
  - Foi implementada assim por ser o caminho conservador e reversível. Não trate como decidido.
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

## Como renomear

- **Só a pasta** (`git mv Gui/fundos Gui/<nome>`): nenhum import muda; atualize os comandos deste README.
- **O pacote** (`fundos` para `<pacote>`): `git mv src/fundos src/<pacote>`, troque `fundos.` nos imports de `src/`, `scripts/` e `tests/`, e a mensagem "Pacote fundos:" de `scripts/apply_migration.py`, de `scripts/load_cadastro.py` e de `scripts/load_informe_fidc.py` e o teste dela. Rode a suíte.

## Pontos para o Fábio

- A camada compartilhada não aceita CNPJ alfanumérico: `normalize_cnpj` em `src/pense_alm/shared/entities/identifiers.py` remove tudo que não é dígito, então um CNPJ com letras perde as letras e é recusado. Isso bloqueia o futuro adaptador de Fundos até a camada compartilhada ser ajustada.
- O CHECK de `issuers.cnpj` nas debêntures (`Eduardo/debenture-replica/migrations/001_initial_schema.sql`) só aceita dígitos e também recusaria CNPJ alfanumérico.
- Este módulo tem utilitário próprio de CNPJ (`src/fundos/cnpj.py`), com dígito verificador numérico e alfanumérico. Unificar com a camada compartilhada fica a seu critério.
