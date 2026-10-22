# PENSE_AL-M

## Visão
- Plataforma de dados de crédito privado brasileiro (debêntures, CRI/CRA e, depois, FIDC/FIAGRO).
- Frentes: **Debêntures** (Eduardo), **CRI/CRA** (Enrico; coletor Fundos.NET), **automação/coletor piloto** (Fábio, branch `fabio`).
- **Shared Entity Layer** em `src/pense_alm/shared/`: fonte única de identidade (entidades, relacionamentos, proveniência, coleta, persistência SQLite, integração com legados).
- Nenhum domínio cria cadastro paralelo de entidades; os legados são integrados por adaptadores (ADR-001 a 005).
- Layout/interface está fora do escopo até o levantamento de requisitos da equipe (ADR-001, `debenture-replica/docs/FREEZE.md`).
- Donos por frente: confirmar com Eduardo antes de assumir.

## Mapa de pastas
| Caminho | Papel |
|---|---|
| `src/pense_alm/shared/{entities,collection,persistence,integration}` | camada compartilhada |
| `src/pense_alm/shared/persistence/migrations/` | migrations da camada compartilhada (`vNNN_*.py`, registradas em `MIGRATIONS` de `migration_runner.py`) |
| `tests/shared/{entities,collection,persistence,integration}` | testes da camada compartilhada |
| `docs/architecture/ADR-00x-*.md` | decisões de arquitetura |
| `Eduardo/debenture-replica/` | **versão de trabalho** de debêntures: `src/debenture_search`, `migrations/`, `scripts/`, `tests/`, `data/` |
| `debenture-replica/` (raiz) | **congelada** (`docs/FREEZE.md`): só automação (config, coleta, retenção, lock, retry, agendamento, monitoramento) |
| `Enrico/cri_cra_platform/` | CRI/CRA (schema em `src/credit_assets/database/schema.sql`) |
| `coletor_cri_cra/` | coletor piloto Fundos.NET |
| `Eduardo/*.py`, `Eduardo/*.tar.gz`, `Eduardo/correcao-banco/` | rascunhos/legado: não editar nem usar como referência |

Atenção: a automação congelada da raiz importa `debenture_search`, que só existe em `Eduardo/debenture-replica/src`. Não duplicar código entre as duas cópias.
Não existe README na raiz nem `Fábio/README.md`; os contratos estão nos ADRs e em `src/pense_alm/shared/entities/README.md`.

## Regras de dados (não quebrar)
1. Nenhum domínio cria cadastro paralelo de entidades.
2. Todo dado e todo relacionamento tem proveniência.
3. Hierarquia de fontes: BACEN > CVM > ANBIMA > plataformas especializadas > sites institucionais. Fonte de menor prioridade complementa, nunca sobrescreve a oficial automaticamente.
4. Preservar o valor original de cada fonte antes de reconciliar.
5. Código legado continua funcionando; migração incremental, reversível e sem alteração destrutiva do módulo legado.
6. CNPJ é o identificador forte. Match só por nome vai para revisão e nunca une automaticamente. Conflito de identificador bloqueia.
7. Gravação idempotente: salvar de novo não duplica. Chave canônica de relacionamento = origem + tipo + destino (a direção faz parte da identidade). Sem autorrelacionamento, relação inversa automática nem inferência.
8. Modelos de domínio imutáveis; datas com timezone (UTC); `confidence_score` entre 0 e 100.
9. SQLite: `foreign_keys=ON`, escrita em transação com rollback, e `PRAGMA integrity_check` = `ok` e `foreign_key_check` vazio.
10. Banco legado é lido com `PRAGMA query_only`.

## Testes
Python 3.14, venv `C:\Users\eduardo.tonzano\debenture-venv`. Rode sempre no diretório indicado.
- Camada compartilhada (raiz do repo): `$env:PYTHONPATH='src'; python -m pytest tests` (285 testes; sem o PYTHONPATH a coleta falha)
- Debêntures, versão de trabalho: `cd Eduardo\debenture-replica; python -m pytest -q` (312; o `pyproject.toml` já define `pythonpath=src`)
- Debêntures, automação congelada: `cd debenture-replica; python -m pytest -q` (105)
- CRI/CRA: `cd Enrico\cri_cra_platform; python -m pytest` (`pytest.ini` define `pythonpath=src`; `tests/integration/test_fundosnet_collector.py` importa `pense_alm` e falha na coleta sem `PYTHONPATH=..\..\src`)
- Baseline histórico de 417 testes (ADR-001, FREEZE) = 312 + 105. Não deve cair.

## Regras operacionais
- **Nunca** rodar coleta, importação ou CLI com `--commit` sem minha aprovação explícita na conversa. Sempre `--dry-run` antes.
  - `debenture-replica/scripts/run_collection.py <config> --dry-run|--commit` e `run_scheduled_collection.py` exigem uma das duas flags.
  - `Eduardo/debenture-replica/scripts/snd_import_one.py` e `snd_import_batch.py` fazem só a prévia sem `--commit`.
  - `python -m pense_alm.shared.integration.cli --legacy-db ... --target-db ... --dry-run` só tem `--dry-run`: **sem a flag ele grava**. Sempre passá-la primeiro.
- Backup antes de qualquer migration (`BackupService.create_backup()` em `Eduardo/debenture-replica/src/debenture_search/services/backup_service.py`).
- Não versionar bancos (`*.db`, `*.sqlite*`), `.env`, ambientes virtuais, documentos baixados (`data/documents/`), backups, exports gerados, `*.bak`, `.vscode/`. Há arquivos assim já versionados (ex.: `Eduardo/debenture-replica/data/backups/`, `debenture_db_base64.txt`, `*.tar.gz`); não remover sem pedido, pois a limpeza é um `chore:` à parte.
- Commits: `feat:`, `fix:`, `test:`, `chore:`, em português, no estilo do histórico. Trabalhar em branch de feature e abrir pull request para `main`; nunca commitar direto na `main`.
- Códigos de saída: coleta de debêntures 0/1/2/3 (lock)/4 (qualidade)/130; CLI compartilhada 0/2/3 (bloqueados)/4 (revisão). Não reutilizar um significado no outro.

## Mudança de schema
1. Plano aprovado por mim antes de escrever código.
2. Migration numerada, nunca editar uma já aplicada:
   - camada compartilhada: novo `vNNN_*.py` em `persistence/migrations/` + entrada em `MIGRATIONS`;
   - debêntures: novo `migrations/NNN_*.sql` em `Eduardo/debenture-replica/`;
   - CRI/CRA: hoje só `schema.sql` (sem numeração); combinar o formato comigo antes.
3. Teste que cubra a migration e a idempotência.
4. `--dry-run` / cópia do banco descartável.
5. Backup do banco real e só então aplicação, com minha aprovação.
6. Verificação: `integrity_check`, `foreign_key_check`, contagens e segunda execução sem duplicar.
- Limitação conhecida: `Eduardo/debenture-replica/scripts/apply_migration.py` tem caminho fixo `data/debenture.db`, aplica só a `001` e **não faz backup**: fazer o backup manualmente antes.
