## CRI/CRA: pipeline de auditoria dos três pilotos (Café Brasil, Alibem, CRI Almeida Junior)

Branch `enricosuman27-e1-auditoria-informes` → `main`. Escopo restrito a `Enrico/cri_cra_platform/`
(os demais arquivos do diff vieram dos merges da `main`).

### O que entra

**Coleta e documentos**
- Download por `source_document_id` explícito, com categorias extras só nesse modo (Relatório do AF, Fato Relevante,
  Anúncio de Encerramento) e limite de tamanho configurável (`--max-megabytes`, padrão 25).
- Texto por página dos PDFs (`extract_document_text.py`) e OCR opcional para PDF em imagem (`ocr_document_pages.py`;
  dependências fora do `requirements.txt`). Os carregadores preferem o texto nativo e só usam OCR quando ele vem vazio.

**Extração e validação dos Informes Mensais**
- Extração guiada por mapeamento versionado: CRA `0.1.1` e CRI `cri-0.1.1` (a raiz do leiaute vem do mapeamento).
- Golden sets (Café Brasil, Alibem, CRI), revisão de relatórios com versão vigente, comparação entre períodos por
  leiaute e alertas de qualidade de dado (regras CRA e CRI aprovadas; o executor recusa regra não aprovada).

**Termos, fatos e alertas contratuais**
- Parâmetros contratuais com âncora literal e vigência (`valid_from`/`valid_to`/`supersedes`); fatos reportados com
  trecho literal conferido na página; página HTML de revisão com nota da proposta e conferência visual.
- Alertas contratuais só com parâmetros **e fatos aprovados** (correção: antes entravam fatos pendentes), tipos
  `fact_minimum`, `fact_flag`, prazo cumprido por fato e modo `--preview`.
- Série histórica das DFs com confronto com o Informe (`export_df_history.py`, nomes equivalentes em
  `config/fact_aliases.json`).

**Esquema**
- Migration `002_asset_series.sql` (séries por emissão, com classe do Informe e do Termo, evidência e revisão humana),
  `load_asset_series.py` e `review_asset_series.py`. Aplicada no banco local em 28/10 com backup e verificação.

### Como verificar
```powershell
cd Enrico\cri_cra_platform
python -m pytest            # 276 testes
python scripts/apply_migration.py --database data\cri_cra.db --dry-run
```
Num banco novo, `initialize_database` aplica a linha de base e as migrations 001 e 002. Testado: esquema de um banco
criado do zero igual ao do banco real, exceto `assets.codigo_cetip` (NOT NULL no legado) e
`documents.source_document_id` (opcional no legado), diferenças anteriores a esta branch.

### Riscos e pontos de atenção
- **Tamanho do diff:** a maior parte são relatórios gerados em `reports/` (CSV e HTML de revisão). Nenhum banco,
  documento baixado ou backup está versionado.
- **Dados interpretados:** valores tirados de tabelas desalinhadas ou de OCR têm nota e conferência visual; os que
  continuam incertos estão pendentes de revisão humana e não alimentam alertas.
- **Regras contratuais do Alibem e do CRI** estão como rascunho (`approval_status: pending`); só rodam com `--preview`.
- **Migrations antigas:** as tabelas criadas antes da numeração ainda usam `ALTER` no `initialize_database`.

### Fora do escopo
Interface e layout, até o levantamento de requisitos da equipe (ADR-001). A fila de download em lotes e a
expansão para o mercado inteiro seguem em plano separado (`reports/plano_fila_download.md`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
