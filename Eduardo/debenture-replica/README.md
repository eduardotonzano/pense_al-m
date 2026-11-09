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
- O codigo grava o CNPJ alfanumerico (secao CNPJ, abaixo). Por isso a 003 tem de estar aplicada antes de usar o codigo.

## CNPJ

**Ordem de implantacao:** aplique a migration 003 no banco antes de usar este codigo: `python scripts/apply_migration.py --database <banco> --dry-run` e depois `--commit`. Sem ela, o CHECK antigo de `issuers.cnpj` recusa o CNPJ alfanumerico. O repositorio transforma o `IntegrityError` em "Nao foi possivel cadastrar o emissor." e o documento falha.

A regra (ADR-011, IN RFB 2.229/2024) mora em `src/debenture_search/cnpj.py`. E uma copia da regra da camada compartilhada (`pense_alm.shared.entities.identifiers.normalize_cnpj`), porque este pacote nao importa `pense_alm`. A paridade vem dos mesmos vetores de teste.

- `normalize_cnpj`: tira os espacos das pontas, remove so ponto, barra e hifen e poe em maiusculas. Exige 12 caracteres em `[0-9A-Z]` e 2 digitos, recusa caracteres todos iguais e valida os 2 digitos verificadores (cada caractere vale `ord(c) - 48`). Nunca completa zeros a esquerda. O erro e `ValueError`, e a mensagem nunca repete o valor recebido.
- `clean_cnpj`: so o formato, sem o DV. Devolve `None` fora dele.
- `IssuerRepository`: `None` continua `None` (emissor sem CNPJ); o resto passa por `normalize_cnpj`. `create`, `get_or_create` e `get_by_cnpj` levantam `ValueError` com formato errado, caracteres iguais ou DV invalido.
- `SndParser.normalize_cnpj`, tambem usado pelo `SndTabularParser`: so aceita o valor inteiro no formato 12 + 2, depois de tirar os espacos das pontas e remover ponto, barra e hifen. Devolve o CNPJ sem mascara e em maiusculas, sem conferir o DV; qualquer outro texto vira `None` ("sem CNPJ"). A regra antiga era diferente: extraia 14 digitos de dentro de qualquer texto. Valores como `CNPJ: 99.999.991/9999-04`, `99 999 991 9999 04` (espacos entre os grupos) ou `99.999.991/9999-04 (matriz)` viravam `99999991999904` e agora viram `None`.
- CNPJ com DV errado ou caracteres iguais chega ao repositorio, e aquele documento falha de forma visivel: a coleta termina `failed` com a mensagem, o payload fica em `raw_records` e, no lote, o item vira `failed` e os outros seguem. A regra antiga gravava esse CNPJ sem conferir.
- Testes: use os CNPJs ficticios de `tests/cnpj_amostras.py` (raizes `9999999n9999` e `ZZZZZZZnZZZZ`, DV valido calculado de forma independente do codigo de producao), nunca CNPJ real.
