# Plataforma CRI/CRA

Fundação modular do projeto de coleta, histórico e monitoramento de CRIs e CRAs.

## Primeiro marco

- SQLite inicializado
- Cadastro do ativo piloto CRA022009VM
- Registro de execução por run_id
- Relatório de saúde em JSON
- Testes unitários e de integração
- Conector Fundos.NET preparado para receber o endpoint real

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
