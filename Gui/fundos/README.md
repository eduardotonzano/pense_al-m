# Fundos (FIDC, FIC-FIDC, FIAGRO): base do módulo

Dono da frente: Gui (`docs/decisoes-em-aberto.md`, decisão 1 de Fundos). O nome da pasta (`Gui/fundos`) e o do pacote Python (`fundos`) são **provisórios**: o nome definitivo é do Gui. Veja "Como renomear".

## O que existe

- Banco SQLite próprio, criado pela migration `migrations/001_initial_schema.sql`, com o mesmo esqueleto de proveniência das debêntures: `sources`, `collection_runs`, `raw_records`, `observations`, `data_conflicts`, `audit_log`, a view `current_observations` e `schema_migrations`. Os assuntos são `funds`, `fund_classes` e `quota_series`.
- `src/fundos/`: conexão (`database.py`), utilitário de CNPJ (`cnpj.py`), guarda de dados pessoais (`personal_data.py`), backup (`backup.py`) e repositórios mínimos (`repositories/`).
- `scripts/apply_migration.py`: aplica as migrations numeradas, com backup e verificação.

## O que ainda não existe

Coletor, leitor dos arquivos da CVM, acesso à rede, banco real, dados reais e adaptador para a camada compartilhada. Ficam para etapas futuras do plano de Fundos:

- o ADR de prioridade das fontes;
- o leitor do cadastro;
- `party_observations` (gestor, administrador, custodiante, controlador, auditor, cedente);
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
  - Limitação conhecida: se o valor antigo volta depois de um conflito (A, depois B, depois A de novo), não há linha nova; o conflito A×B continua aberto e a view mostra B.
- **CPF nunca é gravado** (`docs/decisoes-em-aberto.md`, decisão 3 de Fundos).
  - Nenhuma coluna tem `cpf` no nome.
  - Não são carregados: `Diretor`, `Email_Administrador`, `Site`, `Servico_Atendimento_Cotista` e `Entidade_Administradora`.
  - Coluna de identificação (com `cpf` ou `cnpj` no nome) só aceita CNPJ válido já normalizado.
  - Quem garante isso: a guarda em `personal_data.py`, o trigger `trg_observations_personal_data` e os testes.
  - A guarda não reconhece o nome de gestor ou auditor pessoa física, que depende de outra coluna da mesma linha. Isso fica com o leitor do cadastro (etapa futura).
- **`raw_records` guarda só o manifesto do arquivo** (nome, tamanho, SHA-256, número de linhas), nunca o conteúdo.
  - **Proposta ainda não aprovada pelo Gui:** se a regra do CPF vale também para o arquivo original da CVM (`docs/decisoes-em-aberto.md`, decisão 3).
  - Foi implementada assim por ser o caminho conservador e reversível. Não trate como decidido.
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

## Como renomear

- **Só a pasta** (`git mv Gui/fundos Gui/<nome>`): nenhum import muda; atualize os comandos deste README.
- **O pacote** (`fundos` para `<pacote>`): `git mv src/fundos src/<pacote>`, troque `fundos.` nos imports de `src/`, `scripts/` e `tests/`, e a mensagem "Pacote fundos:" de `scripts/apply_migration.py` e o teste dela. Rode a suíte.

## Pontos para o Fábio

- A camada compartilhada não aceita CNPJ alfanumérico: `normalize_cnpj` em `src/pense_alm/shared/entities/identifiers.py` remove tudo que não é dígito, então um CNPJ com letras perde as letras e é recusado. Isso bloqueia o futuro adaptador de Fundos até a camada compartilhada ser ajustada.
- O CHECK de `issuers.cnpj` nas debêntures (`Eduardo/debenture-replica/migrations/001_initial_schema.sql`) só aceita dígitos e também recusaria CNPJ alfanumérico.
- Este módulo tem utilitário próprio de CNPJ (`src/fundos/cnpj.py`), com dígito verificador numérico e alfanumérico. Unificar com a camada compartilhada fica a seu critério.
