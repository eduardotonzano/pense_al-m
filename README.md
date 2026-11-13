# Pense Além

Plataforma de acompanhamento de ativos de crédito e renda fixa, construída pela equipe de research da Multiplica Capital.

> **Status (13/11/2026):** em desenvolvimento. Coletores de debêntures e de CRI/CRA funcionando de forma independente; o módulo de Fundos (`Gui/fundos`) tem banco próprio e leitores da CVM, ainda sem adaptador para a camada compartilhada. A camada compartilhada de entidades está construída e integra os emissores de debêntures e, desde o #11, a própria debênture (instrumento). Veja [Estado atual](#estado-atual).

---

## Sumário

1. [Problema e solução](#problema-e-solução)
2. [Escopo e frentes](#escopo-e-frentes)
3. [Arquitetura](#arquitetura)
4. [Estrutura do repositório](#estrutura-do-repositório)
5. [Módulos](#módulos)
6. [Como rodar](#como-rodar)
7. [Testes](#testes)
8. [Estado atual](#estado-atual)
9. [Roadmap](#roadmap)
10. [Princípios de dados](#princípios-de-dados)
11. [Convenções e contribuição](#convenções-e-contribuição)
12. [Equipe](#equipe)

---

## Problema e solução

**Dor:** a equipe não consegue acompanhar os ativos da forma desejada porque não existe uma base de dados sólida e consolidada. A dor foi validada pelo padrinho do projeto, Gustavo Vilela.

**Solução:** uma plataforma de fácil acesso para todos os membros da equipe, com:

- base de dados consolidada de ativos, emissores, documentos e preços;
- notificações de variações anormais de preço;
- notificações de notícias relevantes.

## Escopo e frentes

O plano original tem três passos:

1. **Listagem dos ativos**, com cada pessoa cobrindo uma classe.
2. **Confecção das APIs/coletores** de cada classe.
3. **Junção dos códigos** em um sistema único.

| Classe de ativo | Responsável | Maior dor a resolver |
|---|---|---|
| Securitizados (CRI/CRA) | Enrico | Análise de garantias, covenants e histórico de documentos; agente que leia rapidamente os documentos da empresa |
| Debêntures / Bonds | Eduardo | Buscar informações por empresa; PU real x PU par |
| Produtos bancários / Renda fixa | A definir (em aberto, ver R-01) | Acompanhar taxas; calculadora de precificação a mercado; indicadores dos bancos |
| Fundos (FIDC / FIAGRO) | Gui | Acompanhar o mercado de FIDCs; FIDCs da casa x mercado |
| Integração (T.I.) | Fábio | Juntar as frentes na camada compartilhada |

O documento original de escopo está em `Escopo - Projeto Pense Além.docx`.

## Arquitetura

Cada frente constrói seu próprio banco SQLite e seus coletores de forma independente. Uma **Shared Entity Layer** (o "galpão") é a fonte única de identificação dos participantes do mercado, para que nenhuma frente crie cadastros paralelos da mesma empresa, banco, gestora ou fundo.

```
 Debêntures (SND)      CRI/CRA (Fundos.NET)      Fundos (CVM)           Renda fixa (a iniciar)
        |                       |                        |                       |
   SQLite próprio          SQLite próprio           SQLite próprio          SQLite próprio
        \                       |                        |                       /
         \______ adaptadores de integração (somente leitura) _____________________/
                                      |
                        Shared Entity Layer (src/pense_alm/shared)
              entidades · identificadores · proveniência · matching · relacionamentos
                                      |
                              SQLite compartilhado
```

Decisões de arquitetura registradas em `docs/architecture/`:

| ADR | Tema |
|---|---|
| ADR-001 | Shared Entity Layer |
| ADR-002 | Relacionamentos entre entidades |
| ADR-003 | Repositórios de entidades |
| ADR-004 | Persistência em SQLite |
| ADR-005 | Integração gradual de emissores de debêntures |
| ADR-006 | Contrato de leitura para o site (proposta) |
| ADR-007 | Instrumento (debênture) como entidade |
| ADR-008 | Importação de debêntures como instrumento |
| ADR-009 | Execução segura da importação de instrumentos |
| ADR-010 | Prioridade de fontes em Fundos (proposta) |
| ADR-011 | CNPJ alfanumérico |
| ADR-012 | Prestadores de fundos e relação "investe em" |
| ADR-013 | Decisões de Fundos na camada compartilhada |

A integração é gradual: os módulos legados são lidos em modo somente leitura por adaptadores, sem reescrita imediata e sem que a camada compartilhada dependa das classes internas deles.

## Estrutura do repositório

```
pense_al-m/
├── Escopo - Projeto Pense Além.docx   # escopo original do projeto
├── docs/architecture/                 # ADRs da camada compartilhada
├── src/pense_alm/shared/              # Shared Entity Layer
│   ├── entities/                      # modelos, identificadores, matching, relacionamentos
│   ├── persistence/                   # SQLite, migrations, repositórios
│   ├── collection/                    # contratos de coleta (requests, runs, results, raw records)
│   └── integration/                   # adaptadores e CLIs de importação de emissores e de instrumentos
├── tests/shared/                      # testes da camada compartilhada
├── debenture-replica/                 # módulo de debêntures, versão congelada (etapas 1 a 8)
├── Eduardo/                           # módulo de debêntures, versão de trabalho (SND, observações, auditoria)
├── Enrico/cri_cra_platform/           # plataforma CRI/CRA (Fundos.NET, catálogo, download de documentos)
├── coletor_cri_cra/                   # primeiro coletor CRI/CRA (precursor da plataforma do Enrico)
└── Fábio/                             # README de integração do T.I.
```

## Módulos

### Shared Entity Layer (`src/pense_alm/shared`)

Fonte única de identificação dos participantes do mercado: bancos, empresas, holdings, instituições financeiras, cooperativas, gestoras, fundos (FIDC, FIAGRO), securitizadoras e entidades governamentais.

Responsabilidades:

- identidade única de cada entidade;
- razão social e nome comercial;
- identificadores (CNPJ, código BACEN, código CVM, código ANBIMA, LEI);
- classificação por tipo e situação cadastral;
- proveniência de cada dado, com prioridade de fontes (BACEN, CVM, ANBIMA, especializadas, institucionais, manual);
- relacionamentos entre entidades (controla, administra, emite, securitiza, garante etc.);
- identificação conservadora de possíveis duplicidades.

Veja `src/pense_alm/shared/entities/README.md` e os ADRs.

### Debêntures (`Eduardo/debenture-replica` e `debenture-replica`)

Motor de busca e agregação de dados de debêntures brasileiras, por código do ativo, ISIN ou emissor/CNPJ, montando uma ficha única com a origem de cada informação.

- Banco SQLite com histórico completo de observações por campo, controle de conflitos entre fontes, log de auditoria e visão `current_observations` com o valor consolidado respeitando a prioridade da fonte.
- Fonte principal: SND (Sistema Nacional de Debêntures). Fontes previstas: CVM e ANBIMA.
- A versão em `debenture-replica/` (raiz) é a versão **congelada** após as etapas 1 a 8: logs estruturados, lock operacional, retry seguro, retenção automática, qualidade integrada, agendamento no Windows, alertas e monitoramento, e documentação. No congelamento, a suite completa tinha 417 testes aprovados (`FREEZE.md`); a da versão congelada tem hoje 105.
- Documentação operacional em `debenture-replica/docs/`: `ARCHITECTURE.md`, `RUNBOOK.md`, `CHECKLIST.md`, `LOGS.md`, `EXIT_CODES.md` e `FREEZE.md`.
- A etapa 9 (layout/interface) está **pausada** até o levantamento de requisitos com a equipe.

### CRI/CRA (`Enrico/cri_cra_platform`)

Plataforma de coleta, histórico e monitoramento de CRIs e CRAs a partir do Fundos.NET.

- Acesso automatizado ao Fundos.NET com Playwright.
- Catálogo de documentos em SQLite (fonte principal), com exportação para CSV.
- Download de documentos pela ação oficial da grade, com hash SHA-256, versionamento e diagnóstico de tentativas.
- Classificação de documentos por categoria (Termo de Securitização, Aditamento, Informe Mensal, Ata/Edital, Fato Relevante, Relatório Agente Fiduciário, Relatório de Rating, Anúncio de Encerramento, Outro).
- Ativo piloto: CRA022009VM (Café Brasil).
- Relatórios de validação e diagnóstico em `Enrico/cri_cra_platform/reports/`.

`coletor_cri_cra/` é o coletor inicial que deu origem à plataforma.

### Fundos (`Gui/fundos`)

Base do módulo de FIDC, FIC-FIDC e FIAGRO, no repositório desde 27/10/2026, com banco SQLite próprio e leitores do cadastro e dos informes mensais da CVM. O dono da frente é o Gui; o nome da pasta e o do pacote (`fundos`) são provisórios. Ainda não existem, nas palavras do `Gui/fundos/README.md`: "coletor, acesso à rede, banco real, dados reais e adaptador para a camada compartilhada". O que existe e o que falta está em `Gui/fundos/README.md`. Como os fundos vão entrar na camada compartilhada está decidido no ADR-012 e no ADR-013 (aceitos, ainda não implementados).

### Renda fixa

Ainda não iniciada no repositório (responsável em aberto, ver R-01 em `docs/decisoes-em-aberto.md`).

## Como rodar

Requisitos gerais: Python 3.11 ou superior (o módulo de debêntures declara `>=3.11`). O desenvolvimento tem sido feito em Windows com VS Code.

Crie um ambiente virtual **fora** de pastas de rede e instale as dependências de cada módulo conforme abaixo.

### Shared Entity Layer: importar emissores de debêntures

A CLI lê um banco SQLite legado de debêntures (somente leitura) e grava as entidades no banco de destino. Os dois caminhos precisam ser diferentes.

```powershell
$env:PYTHONPATH = "src"

# simulação, sem gravar
python -m pense_alm.shared.integration.cli `
    --legacy-db .\caminho\debenture.db `
    --target-db .\caminho\shared.db `
    --dry-run

# importação real, em lotes
python -m pense_alm.shared.integration.cli `
    --legacy-db .\caminho\debenture.db `
    --target-db .\caminho\shared.db `
    --batch-size 100
```

A importação é idempotente. Arquivos `*.db` e `*.sqlite` estão no `.gitignore` e não são versionados.

### Debêntures

```powershell
cd Eduardo\debenture-replica
py -m venv C:\Users\<voce>\debenture-venv
C:\Users\<voce>\debenture-venv\Scripts\Activate.ps1
py -m pip install -e ".[dev]"
python -m pytest -q
```

Para a versão congelada (operação agendada), siga `debenture-replica/docs/RUNBOOK.md` e `debenture-replica/docs/CHECKLIST.md`. Regra importante: não executar `--commit` em validações técnicas sem aprovação.

Códigos de saída oficiais da coleta:

| Código | Significado |
|---|---|
| 0 | sucesso |
| 1 | erro geral |
| 2 | falha operacional |
| 3 | lock ativo |
| 4 | qualidade crítica |
| 130 | interrupção manual |

### CRI/CRA

```powershell
cd Enrico\cri_cra_platform
py -m venv C:\Users\<voce>\cricra-venv
C:\Users\<voce>\cricra-venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
playwright install chromium
py scripts/run_foundation.py
py -m pytest
```

Scripts úteis em `Enrico/cri_cra_platform/scripts/`: `run_document_catalog.py`, `run_document_inventory.py`, `run_sample_download.py`, `export_documents_csv.py` e scripts de diagnóstico do Fundos.NET.

## Testes

| Módulo | Como rodar |
|---|---|
| Shared Entity Layer | na raiz: `python -m pytest tests` com `PYTHONPATH=src` |
| Debêntures (trabalho) | `cd Eduardo\debenture-replica` e `python -m pytest -q` |
| Debêntures (congelada) | `cd debenture-replica` e `python -m pytest` (105 testes; os 417 de `FREEZE.md` são da suíte completa na época do congelamento) |
| CRI/CRA | `cd Enrico\cri_cra_platform` e `py -m pytest` |

## Estado atual

Mapa por passo do escopo, conforme o repositório em 20/10/2026:

| Passo | Situação |
|---|---|
| 1. Listagem dos ativos | Concluído |
| 2. Coletores/APIs | Em andamento: debêntures madura; CRI/CRA avançando com ativo piloto; fundos com a base do módulo em `Gui/fundos`, ainda sem coletor, acesso à rede, banco real, dados reais e adaptador para a camada compartilhada (correção de 09/11/2026); renda fixa não iniciada |
| 3. Junção dos códigos | Iniciado: a camada compartilhada existe e integra os emissores de debêntures (3 emissores reais importados) e, desde o #11, a debênture como instrumento (ADR-007 a 009; correção de 13/11/2026) |

Pontos em aberto:

- integrar os ativos CRI/CRA à camada compartilhada, com adaptador próprio (securitizadora e devedor, ambos com CNPJ); a debênture (o instrumento) já foi integrada no #11;
- rodar o download em escala dos documentos CRI/CRA e o catálogo completo no banco principal (o código que persiste o catálogo já está na `main`: migration 001 e `run_document_catalog.py`);
- ligar fontes oficiais adicionais (CVM e ANBIMA) às debêntures;
- iniciar a frente de Renda fixa (a de Fundos começou em `Gui/fundos`);
- definir os requisitos de interface e destravar a etapa 9;
- alertas de preço e de notícias, que ainda não têm código.

## Roadmap

1. Adaptador de debêntures (instrumento) para a camada compartilhada: feito no #11 (merge 9ac5032, 12/11/2026). A debênture virou entidade (ADR-007 a 009), e a CLI `python -m pense_alm.shared.integration.instrument_cli` simula por padrão e só grava com `--commit` e backup.
2. Adaptador CRI/CRA para a camada compartilhada. O ISIN duplicado do Café Brasil, segundo `Enrico/cri_cra_platform/reports/duplicate_assets_diagnostic.md`, foi resolvido no banco local do Enrico em 08/10/2026 (não verificável neste repositório). As séries por ativo têm tabela própria desde a migration `002_asset_series.sql` do CRI/CRA (PR #21); como exibi-las segue em aberto (S-07 em `docs/regras-de-exibicao-pendentes.md`).
3. Frente de Fundos (FIDC/FIAGRO), iniciada em `Gui/fundos`, e definição do responsável por Renda fixa (em aberto, ver R-01).
4. Levantamento de requisitos de interface com a equipe e retomada da etapa 9.
5. Motor de alertas: variações anormais de preço e notícias relevantes.
6. Plataforma única de acesso para a equipe.

## Princípios de dados

- Não inventar nem estimar dados ausentes.
- Todo dado carrega fonte e data (proveniência).
- Preservar o histórico; não sobrescrever silenciosamente valores válidos.
- Fontes oficiais têm prioridade sobre fontes complementares.
- Divergências entre fontes são registradas como conflito, sem apagar nenhuma observação.
- Alterações manuais passam por log de auditoria.
- O sistema deve continuar funcionando quando uma fonte estiver indisponível.
- Rejeitar duplicidades e dados inconsistentes.
- Nenhum domínio cria cadastro paralelo de entidades.

## Convenções e contribuição

- Trabalhe em branches de feature e abra pull request para a `main`.
- Mensagens de commit seguem o padrão `feat:`, `fix:`, `test:`, `chore:` nos módulos da camada compartilhada.
- Não versione bancos (`*.db`, `*.sqlite`), arquivos `.env`, ambientes virtuais nem documentos baixados.
- Código muda mais rápido que documentação: confirme caminhos, classes e comandos no código atual antes de agir.
- O `Fábio/README.md` traz o contrato técnico detalhado de cada fonte de dados e da camada compartilhada (retrato de 28/09/2026).

## Equipe

| Pessoa | Papel |
|---|---|
| Eduardo Tonzano | Debêntures (Renda fixa: em aberto, ver R-01 em `docs/decisoes-em-aberto.md`) |
| Enrico Suman Marques | Securitizados (CRI/CRA) |
| Gui | Fundos (FIDC, FIC-FIDC, FIAGRO) |
| Fábio Junior | T.I. e integração |
| Gustavo Vilela | Padrinho do projeto |
