## CRI/CRA: pipeline dos pilotos e base para o mercado inteiro

Branch `enricosuman27-e1-auditoria-informes` → `main`. Escopo restrito a `Enrico/cri_cra_platform/`
(os demais arquivos do diff vieram dos merges da `main`).

### O que entra

**Mercado inteiro (dados abertos da CVM)**
- `ingest_cvm_open_data.py`: Informe Mensal de todos os CRA e CRI (2019 a 2026) num banco separado `data/cvm_open.db`, com valor
  original preservado, SHA-256 por arquivo, recarga idempotente e todas as versões guardadas. Universo: 1.195 emissões de CRA e 3.690 de CRI.
- `run_market_checks.py` e `build_market_universe.py`: triagem do mercado (atraso, vencimento passado com saldo, informe defasado,
  vencimento fora do mês-base, ISIN repetido ou inválido) e ranking de emissões; une a mesma emissão publicada com dois códigos.
- `validate_cvm_vs_xml.py`: a base da CVM bate com a nossa extração do XML em 96,4% dos valores dos pilotos; a diferença é a rentabilidade
  do CRI, que a CVM publica arredondada.

**Coleta e documentos**
- Fila de download em lotes (migration `003_download_queue.sql`): retomada, limite de taxa, parada automática (403, falhas seguidas,
  taxa de falha, disco), erros temporários × permanentes e grupos de documentos do mesmo ativo por sessão de navegador.
- Coletor: localiza a securitizadora com nomes parecidos (desempate pelo nome exato) e trata "S/A" como "S.A".
- Download por `source_document_id`, texto por página dos PDFs e OCR opcional para PDF em imagem.

**Informes Mensais (pilotos)**
- Extração por mapeamento versionado (CRA `0.1.1`, CRI `cri-0.1.1`), golden sets, versão vigente, comparação entre períodos e
  alertas de qualidade de dado.

**Termos, fatos e alertas contratuais**
- Parâmetros com âncora literal e vigência; fatos com trecho literal conferido; página HTML de revisão.
- Catálogo de 36 campos contratuais padrão, cobertura por ativo, localizador de cláusulas (recall de 89% nos parâmetros aprovados) e
  comparação do mesmo dado entre documentos (Termo, oferta, AF, DFs e Informe), inclusive texto curto.
- Alertas contratuais só com parâmetros e fatos aprovados; regra pendente "cadastro do Informe × Termo".
- Fila de revisão priorizada em 5 níveis.

**Esquema**
- Migrations `002_asset_series.sql` e `003_download_queue.sql`, aplicadas no banco local com backup e verificação.

### Como verificar
```powershell
cd Enrico\cri_cra_platform
python -m pytest                                                     # 369 testes
python scripts/apply_migration.py --database data\cri_cra.db --dry-run
python scripts/ingest_cvm_open_data.py --dry-run                     # lista os 16 arquivos da CVM, não grava
```

### Riscos e pontos de atenção
- **Tamanho do diff:** a maior parte são relatórios gerados em `reports/`. Nenhum banco, documento baixado ou backup está versionado.
- **Dado da CVM = dado do Informe:** erros de preenchimento vêm junto (ex.: vencimentos do Alibem). A triagem aponta candidatos, não conclusões.
- **Dados interpretados:** valores de tabelas desalinhadas ou OCR têm nota e conferência visual; os incertos estão pendentes e não alimentam alertas.
- **Regras pendentes** (contratuais do Alibem e do CRI, cadastro do Informe × Termo) só rodam com `--preview`.

### Fora do escopo
Interface e layout, até o levantamento de requisitos da equipe (ADR-001).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
