# Coletor piloto de documentos CRA/CRI

Ferramenta independente para abrir o Fundos.NET em um Chromium real e registrar chamadas `fetch`/XHR relacionadas à pesquisa de documentos.

## Preparacao

Com Python instalado e disponivel no `PATH`:

```powershell
python -m pip install requests playwright
python -m playwright install chromium
```

No Windows, o launcher alternativo e `py`.

## Uso

```powershell
python capturar_fundosnet.py
```

O navegador sera aberto em uma pagina do Fundos.NET. Faça a pesquisa manualmente e pressione Enter no terminal quando a grade de documentos aparecer. Os arquivos sanitizados serao gravados em `logs/`:

- `fundosnet_requests_*.json`
- `fundosnet_responses_*.json`
- `fundosnet_*.har`

O HAR pode conter dados de sessao. Nao o publique sem revisar seu conteudo.

## Dados do piloto

Os valores de teste estao em `config/ativos_piloto.csv`:

- Tipo: CRA
- Securitizadora: Eco Securitizadora
- CNPJ: 10.753.164/0001-43
- Emissao: 190
- Codigo: CRA022009VM

O projeto original `debenture-replica` permanece separado em sua propria pasta.
