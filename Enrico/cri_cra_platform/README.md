# Plataforma CRI/CRA

Fundação modular do projeto de coleta, histórico e monitoramento de CRIs e CRAs.

## O que existe

- SQLite com catálogo de documentos do Fundos.NET, versões de arquivo, execuções (`run_id`) e tentativas de coleta
- Cadastro de ativos a partir de `config/ativos_piloto.csv` (qualquer linha com `ativo=true` e ISIN)
- Coletor do Fundos.NET (Playwright) e download de amostra com validação e SHA-256
- Migrations numeradas, com backup e verificação antes de confirmar
- Classificador estrito de categoria, com prévia do que mudaria
- CNPJ da securitizadora e do devedor obtido no Informe Mensal da CVM, ligado ao ativo só por ISIN e CETIP, com fonte e data
- Testes unitários e de integração (sem rede e sem navegador: usam fakes)

O SQLite é a fonte principal do catálogo. `scripts/export_documents_csv.py` apenas
lê a tabela `documents` e gera `data/catalogo_documentos.csv`; ele não importa nem
sincroniza dados de volta.

## Regra de ouro

Nunca rode `--commit` (ou qualquer script que grave) contra o banco real sem aprovação
explícita, e rode sempre `--dry-run` antes. Nenhum arquivo baixado, banco ou backup vai
para o Git (`data/documents/`, `data/raw/cvm/`, `data/*.db` e `data/backups/` estão no `.gitignore`).

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

## CNPJ da securitizadora e do devedor (S-08)

`scripts/resolve_cnpj.py` obtém o CNPJ no Informe Mensal de CRI e CRA que a CVM publica como
dado aberto (`dados.cvm.gov.br/dataset/securit-doc-inf_mensal_cri` e `..._cra`). O ativo é
ligado ao informe **só por ISIN e CETIP**: o nome da securitizadora ou do devedor nunca é
usado, nem como chave nem como veto.

```powershell
py scripts/resolve_cnpj.py --database data\cri_cra.db --cvm-dir data\raw\cvm --dry-run
py scripts/resolve_cnpj.py --database data\cri_cra.db --cvm-dir data\raw\cvm --commit
```

Os ZIPs anuais (`inf_mensal_cri_<ano>.zip` e `inf_mensal_cra_<ano>.zip`) ficam em
`data/raw/cvm/`, fora do Git. `--download --years 2025,2026` baixa os do ano de
`dados.cvm.gov.br` (usa a rede; só com aprovação). Sem `--download`, o script só lê arquivos
locais.

- **Securitizadora**: vale o `CNPJ_Emissora` quando é único, com dígito verificador válido, em
  todos os informes que citam o ativo. Mais de um valor é conflito e o campo continua ausente.
- **Devedor**: vale quando há um único CNPJ válido e 100% no informe mais recente. O marcador
  `0`, CPF e texto livre nunca viram valor. Por padrão o devedor é só **candidato**: fica em
  `asset_cnpj_observations` e `assets.cnpj_devedor` continua vazio; `--apply-devedor` grava.
- **Nunca sobrescreve**: `assets` só recebe CNPJ em campo vazio. Valor diferente vira
  `conflict` na tabela e é listado na prévia.
- **Fonte e data**: cada decisão (`applied`, `confirmed`, `candidate`, `conflict`) vai para
  `asset_cnpj_observations` (migration 002) com o período dos informes, a data de entrega, o
  arquivo da CVM (URL oficial e SHA-256) e a hora da leitura. A view `asset_cnpj_provenance`
  dá a fonte e a data do CNPJ que está hoje em `assets`; CNPJ digitado à mão não aparece nela.
- Sem valor único e válido da CVM, o campo continua ausente e a prévia diz o motivo
  (`sem_fonte`, `conflito`, `cnpj_invalido_na_fonte`, `varios_devedores`...).
- CNPJ alfanumérico (formato novo da Receita) é rejeitado como inválido, nunca gravado; nenhum
  apareceu nos arquivos de 2026 da CVM lidos em 23/10/2026.

O `--commit` exige a migration 002, faz backup (caminho e SHA-256 impressos), grava numa
transação e só confirma se a verificação passar. O `AssetRepository.upsert` não apaga mais o
CNPJ gravado quando o CSV do piloto vem em branco.

## Pendências

- Download em lotes: fila, retomada, limite de taxa e critério de parada.
- Operações com várias séries (hoje cada série é uma linha de `assets`).
- Ligar o classificador estrito ao catálogo (hoje o catálogo ainda usa `classify_document`).
- Banco real: nenhum `cri_cra.db` está neste repositório; os números reais dependem dele. A
  migration 002 e o `resolve_cnpj.py` ainda não rodaram em banco real.
- CNPJ do devedor do CRI Almeida Junior: a CVM informa 82.120.676/0001-83, mas ele só vira
  valor com uma segunda fonte (Termo de Securitização da emissão 301 ou cadastro da Receita,
  lido por uma pessoa). No Café Brasil o devedor da CVM difere do CSV, que não tem fonte.
- Fundos.NET: confirmar se a grade traz alguma chave de CNPJ (`run_document_catalog.py --dry-run`
  imprime as chaves vistas; usa a rede).
