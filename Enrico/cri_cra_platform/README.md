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

## Pipeline de análise dos pilotos

Ordem de execução para um ativo (exemplo: `--cetip CRA022009VM --isin BRECOACRABX0`). Tudo grava no
SQLite; scripts que gravam têm `--dry-run` ou `--preview` e só aplicam regras aprovadas.

| Etapa | Comando | Observação |
|---|---|---|
| 1. Catálogo | `run_document_catalog.py --only <CETIP> --dry-run`, depois sem `--dry-run` | mostra `documentos_novos` |
| 2. Download | `run_sample_download.py --cetip … --isin … --source-id <ids> [--allow-other] [--max-megabytes N] --dry-run`, depois sem | confere o ISIN na grade; falha nunca vira versão |
| 3. Texto dos PDFs | `extract_document_text.py --cetip …` | pdftotext; lista os PDFs em imagem |
| 3b. OCR (opcional) | `ocr_document_pages.py --cetip … --source-id <id> --dry-run`, depois sem | exige `pip install pymupdf rapidocr-onnxruntime`; texto `ocr: …` convive com o nativo |
| 4. Extração do XML | `run_raw_extraction.py --cetip … --isin … --mapping config/xml_mappings/<cra\|cri>.json` | mapeamento aprovado |
| 5. Revisão dos informes | `build_report_review.py --mapping-version …` e `apply_report_review.py --sheet … --reviewer … --decision-source …` | define a versão vigente |
| 6. Golden set | `build_golden_set.py --golden …` e `check_extraction_against_golden.py` | extração × XML bruto |
| 7. Comparação | `run_period_comparison.py --cetip … --isin …` | indicadores por leiaute CRA/CRI |
| 8. Qualidade de dado | `run_data_quality_alerts.py --cetip … --isin … --rules config/alert_rules/data_quality_*.json` | recusa regra não aprovada |
| 9. Parâmetros e fatos | `load_contract_parameters.py --proposal …`, `load_reported_facts.py --facts …` | entram `pending`; trecho literal conferido na página |
| 10. Revisão humana | `export_pending_review.py --cetip …` (página HTML), `review_contract_parameters.py`, `review_reported_facts.py [--ids-file]`, `review_asset_series.py` | aprovação registra o revisor |
| 11. Alertas contratuais | `run_contract_alerts.py --rules config/alert_rules/contractual_<cetip>.json [--preview]` | só fatos e parâmetros aprovados; `--preview` não grava |
| 12. Série das DFs | `export_df_history.py --cetip … [--include-pending]` | confronta DF × Informe da mesma competência |
| 13. Séries da emissão | `load_asset_series.py --cetip … --dry-run`, depois `--commit` | código, ISIN e classes (Informe e Termo) |
| 14. Fila de download | `run_download_queue.py --enqueue --dry-run`, `--run --dry-run`, depois `--commit`; `--status` | migration 003; 1 worker, limite de taxa, parada automática (ver `reports/plano_fila_download.md`) |
| 15. Cobertura contratual | `report_contract_coverage.py` | campos padrão (`config/contract_terms/standard_fields.json`) por ativo; só leitura (ver `reports/plano_extrator_contratual.md`) |
| 16. Comparação entre documentos | `report_cross_document_checks.py` | mesmo dado em Termo, oferta, AF e DFs (`config/contract_terms/cross_checks.json`); só leitura, lista divergências |
| 17. Fila de revisão priorizada | `build_review_queue.py` | ordena o que aguarda aprovação em 5 níveis; gera ids do nível 4 para aprovação em bloco; só leitura |
| 18. Localizador de campos | `evaluate_finder_recall.py` | `config/contract_terms/field_topics.json` localiza a cláusula de cada campo padrão; mede o recall contra os parâmetros aprovados (só leitura) |
| 19. Mercado inteiro (CVM) | `ingest_cvm_open_data.py --dry-run`, depois `--commit` | Informe Mensal de todos os CRA/CRI dos dados abertos da CVM em `data/cvm_open.db` (ver `reports/plano_escala_mercado.md`) |
| 20. Triagem e universo | `run_market_checks.py`, `build_market_universe.py`, `validate_cvm_vs_xml.py` | ranking de emissões, universo por ISIN, candidatos a lote, validação CVM × XML |
| 21. Prévia de campos em Termos novos | `preview_field_coverage.py` | localizador de campos sobre os Termos baixados, sem gravar no banco |
| 22. Rotina mensal do mercado | `run_monthly_market.py --dry-run`, depois `--commit` | ingestão CVM, triagem, eventos de crédito, devedores, securitizadoras e painel `reports/painel_mercado.html` |
| 23. Histórico de uma emissão | `market_asset_history.py --isin <ISIN>` | mês a mês por série, com eventos |
| 24. Termo × Informe da CVM | `run_termo_vs_cvm.py` | extrator determinístico de valores do Termo (emissão, vencimentos, valor, quantidade, VNU) comparado com a CVM |
| 25. Assuntos de assembleias e fatos | `run_assembly_topics.py` | classificação por palavras-chave das atas, editais, fatos relevantes e comunicados baixados |
| 26. Fichas por ativo | `build_asset_dossiers.py` | tudo o que a plataforma sabe de cada ativo do catálogo (`reports/fichas/`) |
| 27. Sinais das DFs | `ingest_cvm_dfin.py --dry-run`, depois `--commit`; `run_dfin_checks.py` | opinião do auditor (ressalva, abstenção, piora), prazo e emissões sem DF (`data/cvm_dfin.db`) |
| 28. Fichas contratuais | `build_contract_sheets.py [--only <cetip>…]` | trecho literal de cada um dos 36 campos padrão nos Termos e aditamentos, com página, parâmetro aprovado e Termo × CVM (`reports/fichas_contratuais/`); rodar depois de `run_termo_vs_cvm.py`; só leitura |
| 29. OCR de PDFs em imagem | `ocr_document_pages.py --source-id … --cetip … --dry-run` | opcional (pymupdf + rapidocr); o texto de OCR fica em `document_text_pages` e os relatórios o usam quando a página nativa vem vazia |

Relatórios gerados ficam em `reports/`; o resumo do trabalho está em
`reports/resumo_do_projeto_2026-10-28.md`.

## Pendências

- Download em lotes: fila, retomada, limite de taxa e critério de parada.
- Séries: `asset_series` (migration 002) guarda as séries de cada emissão; os informes ainda ligam valores
  por série só pelo `instance_key` (NumeroSerie).
- Ligar o classificador estrito ao catálogo (hoje o catálogo ainda usa `classify_document`).
- Banco real: nenhum `cri_cra.db` está neste repositório; os números reais dependem dele.
