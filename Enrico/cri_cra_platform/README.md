# Plataforma CRI/CRA

Fundação modular do projeto de coleta, histórico e monitoramento de CRIs e CRAs.

## Primeiro marco

- SQLite inicializado
- Cadastro do ativo piloto CRA022009VM
- Registro de execução por run_id
- Relatório de saúde em JSON
- Testes unitários e de integração
- Conector Fundos.NET preparado para receber o endpoint real
- Catálogo de documentos em SQLite com exportação CSV

O SQLite é a fonte principal do catálogo. `scripts/export_documents_csv.py` apenas
lê a tabela `documents` e gera `data/catalogo_documentos.csv`; ele não importa nem
sincroniza dados de volta. A inicialização adiciona somente o índice único parcial
de `file_hash` (valores não vazios), sem apagar ou reescrever dados existentes.

## Executar no Windows / VS Code

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py scripts/run_foundation.py
py -m pytest
```

## Próximo marco

Integrar o endpoint real de listagem do Fundos.NET no arquivo `src/credit_assets/collectors/fundosnet_collector.py`.
