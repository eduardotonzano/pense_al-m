# Divergências entre a documentação e o repositório

Insumo para a tarefa separada de revisão do `CLAUDE.md`. Cada item cita o que o documento
diz e o que o repositório mostra. Conferido em 22/10/2026 sobre a branch
`feat/cri-cra-catalogo` (base `654f2c8`), com leitura dos arquivos e comandos somente de
leitura. Onde algo **não foi verificado**, está dito. Itens marcados *(corrigido na branch)*
têm correção em branch ainda não mesclada na `main`.

## 1. `CLAUDE.md`

| # | Onde | O documento diz | O repositório mostra |
|---|---|---|---|
| 1 | L25 | "Não existe README na raiz nem `Fábio/README.md`" | Os dois existem (`README.md` e `Fábio/README.md`). |
| 2 | L24 | A automação congelada importa `debenture_search`, "que só existe em `Eduardo/debenture-replica/src`" | O pacote está partido em duas árvores. `Eduardo/debenture-replica/src/debenture_search/` **não** tem `config.py` nem `logging_config.py`; a cópia congelada (`debenture-replica/src/debenture_search/`) tem os dois, e 8 arquivos dela os importam. Já `database.py` e os repositórios só existem em `Eduardo/...`. A suíte congelada depende das duas árvores. |
| 3 | L44 | `tests/integration/test_fundosnet_collector.py` "importa `pense_alm` e falha na coleta sem `PYTHONPATH=..\..\src`" | Nenhum arquivo de `Enrico/` importa `pense_alm`. O que faz esses testes falharem é a falta do pacote `playwright` (3 arquivos de teste o importam). |
| 4 | L40 | Testes rodam no venv `C:\Users\eduardo.tonzano\debenture-venv` | Esse venv não tem `playwright` nem `requests`, então não roda a suíte do CRI/CRA. O venv `C:\Users\eduardo.tonzano\cricra-venv` foi criado para isso (`pip install -r Enrico/cri_cra_platform/requirements.txt`; nenhum navegador é baixado). |
| 5 | L41-45 | 285 (compartilhada), 312 (debêntures de trabalho), 105 (congelada), baseline 417 | Debêntures de trabalho: **324** testes em `feat/debentures-cadastro` e **416** em `feat/debentures-eventos`. CRI/CRA: **91** coletados no início de `feat/cri-cra-catalogo` (o "67" de relatórios e do `docs/regras-de-exibicao-pendentes.md` estava defasado). Compartilhada (285) e congelada (105) **não foram rodadas nesta sessão**; a contagem estática de `def test_` na congelada encontrou 93, e a diferença pode ser parametrização (não verificado). |
| 6 | L62 | CRI/CRA: "hoje só `schema.sql` (sem numeração); combinar o formato comigo antes" | Formato definido em `feat/cri-cra-catalogo`: `Enrico/cri_cra_platform/migrations/NNN_nome.sql`, tabela `schema_migrations` e `scripts/apply_migration.py`. *(corrigido na branch)* |
| 7 | L67 | `Eduardo/debenture-replica/scripts/apply_migration.py` tem caminho fixo, só a `001` e não faz backup | Generalizado em `feat/debentures-eventos` (`dce3ea2`): `--database` obrigatório, `--dry-run`/`--commit`, backup pelo `BackupService`, verificação antes do COMMIT. *(corrigido na branch)* |
| 8 | L52 | Backup pelo `BackupService.create_backup()` (debêntures) | O CRI/CRA ganhou o equivalente `credit_assets.database.backup.create_backup` (SQLite online backup, SHA-256). *(nesta branch)* |
| 9 | L30 | Hierarquia BACEN > CVM > ANBIMA > especializadas > institucionais | A migration 001 das debêntures semeia prioridades SND 100, CVM 200, ANBIMA_API 300 (inativa), MANUAL 1000. Numericamente a ANBIMA supera a CVM; sem efeito enquanto a fonte estiver inativa. |
| 10 | L53 | "Há arquivos assim já versionados" | Confirmado e medido: 14 arquivos em `Eduardo/debenture-replica/data/backups/` (`.sqlite3`, `-shm`, `-wal`), 1 `.bak`, 3 `.tar.gz`, 2 `debenture_db_base64.txt` e 5 arquivos em `Eduardo/debenture-replica/exports/`. `Eduardo/debenture-replica/` não tem `.gitignore` próprio, e o `.gitignore` da raiz não cobre `data/documents/` (só o do Enrico cobre). |

## 2. `README.md` da raiz

| # | Onde | O documento diz | O repositório mostra |
|---|---|---|---|
| 1 | L75-79 | Tabela de ADRs com ADR-001 a ADR-005 | Existe `docs/architecture/ADR-006-contrato-de-leitura.md`, ausente da tabela. |
| 2 | L48, L59, L245, L274 | Renda fixa "A definir" / "(a iniciar)" / "definição do responsável"; e na equipe, "Eduardo Tonzano: Debêntures (e agora renda fixa)" | O documento se contradiz sobre quem cuida de Renda fixa (o ponto está em aberto como R-01). |
| 3 | L219 | A suíte congelada tem "417 testes registrados em `FREEZE.md`" | O `CLAUDE.md` (L45) diz que 417 = 312 + 105. O número é de duas suítes somadas, não da congelada. |
| 4 | L151 e L179-180, L202-203 | Criar o venv "**fora** de pastas de rede" | Os trechos de instalação mandam `py -m venv .venv` dentro das pastas dos módulos, que estão no compartilhamento de rede. |
| 5 | L235, L244 | Persistir o catálogo CRI/CRA e rodar o download em escala; adaptador CRI/CRA "resolvendo o ISIN duplicado" | A persistência do catálogo está feita em `feat/cri-cra-catalogo`; o download em escala continua pendente. O duplicado do Café Brasil foi resolvido em 08/10/2026 (`Enrico/cri_cra_platform/reports/duplicate_assets_diagnostic.md`); o que falta é modelar multissérie (S-07). |
| 6 | L137 | Categoria "Relatório de Agente Fiduciário" | O código e o schema usam "Relatório Agente Fiduciário" (`models/document.py`, `schema.sql`). |

## 3. `Fábio/README.md`

Retrato de 28/09/2026 (357 arquivos versionados à época).

- L50-52, L141, L308 e L323 dizem que os 124 documentos do Café Brasil não estão persistidos
  no "banco de produção". O relatório de 08/10/2026 registra 168 documentos num banco local do
  Enrico. Nenhum `cri_cra.db` existe neste repositório nem no compartilhamento, então **não há
  como saber hoje qual é o "banco principal"**.
- L50: o período do inventário (01/08/2025 a 31/12/2025) sai de `min`/`max` sobre textos
  `dd/mm/aaaa` (`Enrico/cri_cra_platform/src/credit_assets/download_diagnostics.py`, bloco de
  `period`), então não é um intervalo cronológico.

## 4. CRI/CRA (`Enrico/cri_cra_platform`)

| # | Onde | Problema |
|---|---|---|
| 1 | `README.md` (versão anterior) L17-18 | Dizia que a inicialização só adiciona o índice único parcial de `file_hash`. Hoje `ix_documents_file_hash` é não único e `initialize_database` também adiciona coluna `isin`, índices únicos de ISIN e CETIP e colunas de tentativas. *(corrigido na branch)* |
| 2 | `README.md` L12, L30-32; `RELATORIO_ATIVIDADES_2026-09-16.md` L99-107 | "Preparado para receber o endpoint real" / "o endpoint real ainda não foi integrado": o coletor já lista documentos ao vivo (há catálogos reais nos relatórios). |
| 3 | `.env.example` | Define `DATABASE_PATH`, mas nada lê variável de ambiente; todos os scripts usam `ROOT/data/cri_cra.db` fixo. |
| 4 | `scripts/diagnose_document_action.py` L33 | Procura `codigo_cetip == "BRECOACRABX0"`, que hoje é o ISIN; o script falha desde a separação de CETIP e ISIN. |
| 5 | `scripts/run_document_inventory.py` L59, L77 | ISIN e a contagem esperada de 124 documentos fixos no código. |
| 6 | `DOCUMENT_CATEGORIES` / `SAMPLE_CATEGORIES` | Lista de categorias em `models/document.py` e no CHECK de `schema.sql`; `SAMPLE_CATEGORIES` aparece em `download_diagnostics.py` (8 valores) e em `document_download_service.py` (4 valores), com conteúdos diferentes. |
| 7 | `scripts/run_sample_download.py` L100-101, L116-120 | O `--dry-run` ainda chama `initialize_database` (pode criar/alterar o banco) e regrava os relatórios `reports/cafe_brasil_sample_download_latest.*`, que são versionados. |
| 8 | `scripts/run_document_catalog.py` | `--offline-fixtures` grava documentos fictícios no banco (não é um dry-run), e o código de saída era sempre 0. O `--dry-run` real e o código de saída 1 em erro entraram em `feat/cri-cra-catalogo`. *(corrigido na branch)* |
| 9 | `reports/test_fundosnet_capture_all.py` | Ferramenta interativa de captura dentro de `reports/` (não é teste); rodada no lugar, grava em `reports/reports/`. |
| 10 | `src/credit_assets/services/document_download_service.py` | Download limitado a 4 categorias e a 4 documentos por execução, com texto "Café Brasil" fixo na mensagem de erro de certificado não localizado. |

## 5. Ambiente

- A instalação editável do pacote `debenture-search` no `debenture-venv` aponta para a pasta
  `...\00.1.Pense Além\debenture-replica\src`, **fora do repositório** (a pasta pai). Scripts de
  debêntures rodados por esse venv sem `PYTHONPATH=src` usam o código e o banco `data/debenture.db`
  dessa pasta antiga; este checkout não tem `Eduardo/debenture-replica/data/debenture.db`.
- Reinstalar o pacote apontando para `Eduardo/debenture-replica` pode quebrar a suíte congelada,
  que depende de `config.py` e `logging_config.py` só presentes na pasta antiga e na cópia
  congelada *(inferência a partir dos imports; não foi executado)*. O `apply_migration.py` das
  debêntures contorna isso inserindo o próprio `src` no `sys.path` e imprimindo o pacote usado.
- Caminhos longos: no compartilhamento, `pasta\backups\<nome>.sqlite3` pode passar de 260
  caracteres e o SQLite falha com "unable to open database file" (o `LongPathsEnabled` está
  desligado nesta máquina). Os scripts de migration recusam sem alterar o banco e mostram o erro
  do backup.
