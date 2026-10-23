# Migrations do CRI/CRA

`src/credit_assets/database/schema.sql` e a linha de base. Toda mudanca de
schema a partir dela vira um arquivo numerado nesta pasta.

## Migrations existentes

| Nº | Arquivo | O que faz |
|---|---|---|
| 001 | `001_document_catalog.sql` | Campos da grade do Fundos.NET em `documents` e auditoria de troca de categoria |
| 002 | `002_asset_cnpj_observations.sql` | Fonte e data de cada CNPJ da securitizadora e do devedor (tabela e view) |

Os números seguem a ordem em que os ramos são mesclados; se dois ramos criarem o mesmo
número, o que entrar depois renumera a sua migration antes do merge.

## Formato

- Nome: `NNN_nome_em_minusculas.sql` (tres digitos, `a-z`, `0-9` e `_`).
  Exemplo: `001_document_catalog.sql`.
- Conteudo: so DDL/DML, uma instrucao por `;`. O executor cria a tabela
  `schema_migrations` e registra a versao; o arquivo nao precisa faze-lo.
- Nunca edite uma migration ja aplicada: crie a seguinte.
- Prefira mudancas aditivas (`ADD COLUMN`, `CREATE TABLE`, `CREATE INDEX`).
  A verificacao antes do COMMIT recusa remover coluna, indice ou linha.

## Como aplicar

Banco novo recebe a linha de base e todas as migrations em
`initialize_database`. Banco existente so as recebe por:

```
python scripts/apply_migration.py --database <banco> --dry-run
python scripts/apply_migration.py --database <banco> --commit
```

`--dry-run` aplica numa copia. `--commit` faz o backup (caminho e SHA-256
impressos), aplica numa transacao e so confirma se `integrity_check`,
`foreign_key_check`, as versoes registradas, as colunas, os indices e as
contagens anteriores passarem. Os scripts de coleta recusam rodar enquanto
houver migration pendente.
