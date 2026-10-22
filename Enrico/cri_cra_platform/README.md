# Plataforma CRI/CRA

Fundação modular do projeto de coleta, histórico e monitoramento de CRIs e CRAs.

## O que existe

- SQLite com catálogo de documentos do Fundos.NET, versões de arquivo, execuções (`run_id`) e tentativas de coleta
- Cadastro de ativos a partir de `config/ativos_piloto.csv` (qualquer linha com `ativo=true` e ISIN)
- Coletor do Fundos.NET (Playwright) e download de amostra com validação e SHA-256
- Migrations numeradas, com backup e verificação antes de confirmar
- Classificador estrito de categoria, com prévia do que mudaria
- Testes unitários e de integração (sem rede e sem navegador: usam fakes)

O SQLite é a fonte principal do catálogo. `scripts/export_documents_csv.py` apenas
lê a tabela `documents` e gera `data/catalogo_documentos.csv`; ele não importa nem
sincroniza dados de volta.

## Regra de ouro

Nunca rode `--commit` (ou qualquer script que grave) contra o banco real sem aprovação
explícita, e rode sempre `--dry-run` antes. Nenhum arquivo baixado, banco ou backup vai
para o Git (`data/documents/`, `data/*.db` e `data/backups/` estão no `.gitignore`).

## Executar no Windows / VS Code

Crie o ambiente virtual **fora** de pastas de rede:

```powershell
py -m venv C:\Users\<voce>\cricra-venv
C:\Users\<voce>\cricra-venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt   # instala o pacote playwright; nenhum navegador é baixado
py -m pytest
```

Os testes importam o pacote `playwright` (não abrem navegador). O `pytest.ini` já define
`pythonpath = src`.

## Migrations

`src/credit_assets/database/schema.sql` é a linha de base e `migrations/` guarda as
mudanças numeradas (`NNN_nome.sql`; formato em `migrations/README.md`).

- Banco **novo** recebe a linha de base e todas as migrations.
- Banco **existente** só as recebe por `scripts/apply_migration.py`. Os scripts de coleta e
  exportação recusam rodar enquanto houver migration pendente e mostram o comando.

```powershell
py scripts/apply_migration.py --database data\cri_cra.db --dry-run   # aplica numa cópia
py scripts/apply_migration.py --database data\cri_cra.db --commit    # backup + transação única
```

O `--commit` imprime o caminho e o SHA-256 do backup e só confirma se `integrity_check`,
`foreign_key_check`, as versões, as colunas, os índices e as contagens anteriores passarem.

## Catálogo de documentos

```powershell
py scripts/run_document_catalog.py --dry-run     # lê o Fundos.NET e mostra o que mudaria; não grava
py scripts/run_document_catalog.py               # grava no banco
```

O catálogo guarda, por documento, os campos oficiais da grade (Categoria, Tipo, Espécie,
versão, descrição) e a linha original em JSON (`source_row_json`). Rodar de novo não volta o
`download_status` para `pending`: o estado só é reaberto se a versão na grade mudar. O
`--dry-run` lista as chaves JSON vistas, para confirmar os nomes de campo antes do primeiro
`--commit`.

## Categorias de documento

`scripts/reclassify_documents.py` reclassifica documentos hoje em "Outro". Troca só com
correspondência inequívoca (exatamente uma categoria candidata) e nunca altera uma
categoria já específica.

```powershell
py scripts/reclassify_documents.py --database data\cri_cra.db --dry-run
py scripts/reclassify_documents.py --database data\cri_cra.db --commit
```

A prévia tem duas seções: as regras **verificadas** (valem por padrão: Informe Mensal e
Ata/Edital pela Espécie, com veto de Demonstrações Financeiras) e as **não verificadas**
(Aditamento, Termo de Securitização, Fato Relevante, Relatório do Agente Fiduciário,
Relatório de Rating e Anúncio de Encerramento), que ficam desligadas e só gravam com
`--enable-unverified-rules`. O `--commit` faz backup, audita cada troca em
`document_category_changes` e verifica antes de confirmar.

## Pendências

- Download em lotes: fila, retomada, limite de taxa e critério de parada.
- Operações com várias séries (hoje cada série é uma linha de `assets`).
- Ligar o classificador estrito ao catálogo (hoje o catálogo ainda usa `classify_document`).
- Banco real: nenhum `cri_cra.db` está neste repositório; os números reais dependem dele.
