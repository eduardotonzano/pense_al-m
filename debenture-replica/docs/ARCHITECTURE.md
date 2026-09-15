# Arquitetura Técnica

## Objetivo

Automatizar a coleta, validação, monitoramento, armazenamento e exportação de informações de debêntures, garantindo segurança operacional, rastreabilidade, qualidade de dados e execução agendada.

---

# Visão Geral

Fluxo principal:

```text
run_scheduled_collection.ps1
            │
            ▼
run_scheduled_collection.py
            │
            ▼
run_collection.py
            │
            ▼
CollectionAutomationService
            │
            ├── Lock Operacional
            ├── Retry Seguro
            ├── Logs Estruturados
            ├── Qualidade Integrada
            ├── Monitoramento
            └── Exportações
```

---

# Estrutura do Projeto

```text
config/
docs/
logs/
runtime/
scripts/
src/
tests/
```

---

# Scripts Principais

## run_collection.py

Responsável por:

- carregar configuração
- executar coleta
- gerar relatório operacional
- executar validações de qualidade
- executar monitoramento
- definir código de saída

---

## run_scheduled_collection.py

Responsável por:

- localizar raiz do projeto
- localizar configuração
- localizar Python
- preservar ExitCode
- permitir execução agendada

---

## run_scheduled_collection.ps1

Responsável por:

- localizar ambiente virtual
- localizar configuração
- gerar log do agendamento
- encaminhar ExitCode

---

# Serviços

## CollectionAutomationService

Responsável pela coleta dos ativos.

Funções:

- processamento
- observações
- conflitos
- exportações
- integração com banco

---

## ExecutionLockService

Responsável pela prevenção de execução simultânea.

Arquivo:

```text
runtime/collection.lock
```

---

## RetryPolicy

Responsável pelas tentativas controladas.

Permite:

```text
Timeout
ConnectionError
HTTP 429
HTTP 502
HTTP 503
HTTP 504
```

---

## QualityReportService

Responsável por:

- integridade SQLite
- foreign keys
- qualidade dos dados
- geração de relatórios

Arquivos:

```text
logs/quality_last.json
logs/quality_history.jsonl
```

---

## HealthMonitorService

Responsável por:

- monitoramento operacional
- saúde da automação
- alertas
- histórico operacional

Arquivos:

```text
logs/health_last.json
logs/health_history.jsonl
```

Estados:

```text
healthy
warning
critical
```

---

# Banco de Dados

Tecnologia:

```text
SQLite
```

Validações:

```text
integrity_check()
foreign_key_check()
```

---

# Logs

Arquivos:

```text
logs/debenture_collection.log
logs/debenture_collection.jsonl
logs/collection_last.json
logs/quality_last.json
logs/quality_history.jsonl
logs/health_last.json
logs/health_history.jsonl
logs/scheduled_collection.log
```

---

# Códigos de Saída

```text
0   sucesso
1   erro geral
2   falha operacional
3   lock ativo
4   qualidade crítica
130 interrupção manual
```

---

# Qualidade Atual

Estado validado:

```text
417 testes aprovados
```

---

# Etapas Concluídas

```text
Etapa 1 - Logs estruturados
Etapa 2 - Lock operacional
Etapa 3 - Retry seguro
Etapa 4 - Retenção automática
Etapa 5 - Qualidade integrada
Etapa 6 - Agendamento Windows
Etapa 7 - Alertas e monitoramento
```

---

# Próximas Etapas

## Etapa 8

Documentação e congelamento técnico.

Status: Concluída.


## Etapa 9

Layout.

ATENÇÃO:

O desenvolvimento do layout permanece pausado até que todos os requisitos da equipe sejam levantados e organizados.