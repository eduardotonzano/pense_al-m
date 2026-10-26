# ADR-009: Execução segura da importação de instrumentos

## Status

Proposta. Implementada no ramo `feat/shared-adapter-debentures`; passa a aceita com a revisão do pull request.

## Contexto

A importação de emissores (ADR-005) tem uma CLI que **grava por padrão**: só existe `--dry-run`, e sem a flag o comando escreve no banco de destino (CLAUDE.md, seção de segurança). Além disso, o "dry-run" dela não é livre de efeitos:

- `SQLiteEntityRepository.__init__` e `SQLiteRelationshipRepository.__init__` executam `MigrationRunner.apply_all()` e o `SQLiteConnectionManager` cria o arquivo e a pasta do banco. Abrir o destino real para simular já o cria ou o migra.
- A simulação do lote copia as entidades para um repositório em memória, mas não os relacionamentos, que o instrumento precisa consultar.

O projeto exige que qualquer gravação seja precedida de dry-run, aconteça só com `--commit` e tenha backup antes. A importação do instrumento é a primeira a gravar entidades e relações juntas.

## Decisão

Criar uma CLI própria, `python -m pense_alm.shared.integration.instrument_cli`, com estas regras:

1. **Simular é o padrão.** Sem `--commit`, a execução é um dry-run (`--dry-run` existe e tem o mesmo efeito; as duas flags são mutuamente exclusivas).
2. **O dry-run roda em cópia descartável.** O destino é copiado para uma pasta temporária com a API de backup do SQLite; o serviço roda com os repositórios SQLite reais sobre a cópia; a cópia é apagada no fim. O destino real **nunca é aberto por um repositório** (que o migraria). Se o destino não existe, a simulação roda sobre um banco vazio e o destino não é criado. Como a cópia contém entidades e relações, a simulação enxerga o mesmo estado que a gravação.
3. **Gravar exige `--commit` e `--backup-dir`.** O backup é feito antes de qualquer gravação e a CLI imprime caminho, tamanho e SHA-256. Se o backup falhar, a execução termina com código 2 e nada é gravado.
4. **Destino novo exige `--create`** junto com `--commit`. Evita criar um banco vazio por engano de caminho. Sem banco anterior, não há o que copiar e a CLI avisa.
5. **Caminhos explícitos.** `--legacy-db` e `--target-db` são obrigatórios; a CLI recusa legado inexistente, lote menor ou igual a zero e origem igual ao destino. `--backup-dir` só vale com `--commit`, e `--create` também.
6. **Legado só para leitura.** O leitor abre o banco sob `PRAGMA query_only`. Os testes comparam o SHA-256 do legado antes e depois.
7. **Códigos de saída da ADR-005:** 0 sem pendências, 2 para erro (inclui falha de backup), 3 para registros bloqueados, 4 para registros em revisão. Cada pendência é impressa com `legacy_id`, código, ISIN, ação e motivo, porque a fila de revisão não é persistente.

O backup fica em `pense_alm.shared.persistence.create_sqlite_backup`: usa `sqlite3.Connection.backup` a partir de uma conexão `query_only`, roda `PRAGMA integrity_check` na cópia, nomeia o arquivo `<banco>_<UTC>.sqlite3` e remove a cópia parcial em caso de falha. Tem o mesmo comportamento do `BackupService.create_backup` do módulo de debêntures, sem depender dele (a camada compartilhada não importa módulos de produto).

A CLI de emissores **não é alterada** nesta etapa.

## Alternativas consideradas

1. **Reaproveitar `cli.py` acrescentando `--commit`.** Descartada: mudaria o comportamento de um comando já documentado e validado (ADR-005), cujos testes assumem que ele grava sem a flag.
2. **Dry-run em memória, como o lote de emissores.** Descartada: não cobre os relacionamentos e não exercita as restrições do SQLite (identificador único, chaves estrangeiras).
3. **Abrir o destino real em dry-run e reverter a transação.** Descartada: o repositório migra o banco ao ser aberto e cria o arquivo antes da primeira consulta.
4. **Backup opcional.** Descartada: o requisito do projeto é backup antes de qualquer gravação.

## Consequências positivas

- por padrão, nada é gravado, nem no destino nem em arquivos novos fora da pasta temporária;
- a simulação usa o mesmo código e o mesmo schema da gravação;
- cada gravação tem um ponto de retorno verificado;
- um caminho errado não cria banco novo sem `--create`.

## Riscos e limitações

- a cópia para o dry-run lê o banco inteiro; para bancos grandes o custo cresce com o tamanho;
- o backup é uma cópia de arquivo no mesmo disco ou compartilhamento que o destino, não um backup remoto;
- a CLI não restaura backups; a restauração é manual;
- entidade e relação são gravadas em transações separadas (ADR-008); a reexecução repara, mas uma interrupção deixa o estado intermediário até a próxima execução;
- **divergência com a CLI de emissores:** ela continua gravando por padrão e seu dry-run continua criando e migrando o destino. Alinhá-la é uma mudança de comportamento e fica como pendência.

## Fora do escopo

- alterar a CLI de emissores;
- restauração de backup e política de retenção;
- registrar a CLI como comando instalável;
- fila persistente de revisão.
