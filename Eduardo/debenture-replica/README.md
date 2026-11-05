# Motor de Busca de Debentures

Replica funcional independente do projeto publico `eduardotonzano/debenture-`, mantendo os conceitos observados: modelos com proveniencia, providers segregados, agregador resiliente, cache SQLite TTL, rate limiting, provider manual, estrutura para SND e CLI.

## Testes

```bash
python -m pytest -q
```

## Migrations

As migrations ficam em `migrations/NNN_nome.sql`. O `scripts/apply_migration.py` aplica todas as pendentes numa unica transacao:

```bash
python scripts/apply_migration.py --database <banco> --dry-run
python scripts/apply_migration.py --database <banco> --commit
```

- `--dry-run` aplica e verifica numa copia; o banco informado nao muda.
- `--commit` faz o backup antes e so confirma se a verificacao passar: `integrity_check`, `foreign_key_check`, versao registrada em `schema_migrations` e, sem `--allow-existing-changes`, o DDL e as contagens do que ja existia.
- Um banco com erro de chave estrangeira e recusado antes do backup.

### Recriar uma tabela

O SQLite nao altera CHECK: mudar um CHECK exige recriar a tabela. Se a tabela tem filhas, o `DROP` so passa com as chaves estrangeiras desligadas, e o `PRAGMA foreign_keys` so tem efeito fora de transacao. A migration declara isso no proprio arquivo:

```sql
-- apply_migration: foreign_keys=off
-- apply_migration: recria=issuers
```

- `foreign_keys=off`: o script desliga as chaves antes do `BEGIN`, roda o `foreign_key_check` antes do `COMMIT` (qualquer linha encontrada desfaz tudo) e religa as chaves no fim, tambem em caso de erro. Se uma pendente tiver a marca, o lote inteiro roda assim, numa transacao so.
- `recria=<tabela>`: aceita a mudanca do DDL so dessa tabela. As contagens de linhas e o resto do esquema continuam conferidos.
- Marca desconhecida e erro, antes do backup. Migrations sem marca rodam com as chaves ligadas.

### 003_issuers_cnpj_alfanumerico

O CHECK de `issuers.cnpj` passa a aceitar o CNPJ alfanumerico (ADR-011, em `docs/architecture/` na raiz do repositorio): 12 caracteres em `[0-9A-Z]` e 2 digitos. O digito verificador nao e conferido no banco.

- E um superconjunto do CHECK antigo (14 digitos): nenhuma linha existente e recusada. Ids, debentures filhas e o AUTOINCREMENT sao preservados.
- Aplicar so pelo `apply_migration.py`, primeiro com `--dry-run`. Nunca com `executescript` nem com o `sqlite3` de linha de comando: fora do script as marcas nao valem.
- Por enquanto o codigo continua gravando so CNPJ numerico. `IssuerRepository.normalize_cnpj` e `SndParser.normalize_cnpj` mudam em outro PR.
