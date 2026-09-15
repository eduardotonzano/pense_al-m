# Runbook Operacional

## Objetivo

Descrever os procedimentos operacionais necessários para execução e suporte do sistema.

---

# Ambiente

Projeto:

```text
debenture-replica
```

Ambiente virtual:

```text
C:\Users\eduardo.tonzano\debenture-venv
```

---

# Execução Manual

## DryRun

```powershell
python .\scripts\run_collection.py `
    .\config\collection.production.json `
    --dry-run
```

Objetivo:

- validar execução
- não gravar dados
- não alterar banco

---

## Commit

```powershell
python .\scripts\run_collection.py `
    .\config\collection.production.json `
    --commit
```

Objetivo:

- execução completa
- gravações autorizadas
- exportações

---

# Execução Agendada

## PowerShell

```powershell
.\scripts\run_scheduled_collection.ps1
```

---

## Python

```powershell
python .\scripts\run_scheduled_collection.py `
    --config .\config\collection.production.json `
    --dry-run
```

---

# Verificação Pós Execução

## Relatório principal

```powershell
Get-Content .\logs\collection_last.json
```

---

## Qualidade

```powershell
Get-Content .\logs\quality_last.json
```

---

## Saúde

```powershell
Get-Content .\logs\health_last.json
```

---

## Histórico de saúde

```powershell
Get-Content .\logs\health_history.jsonl -Tail 10
```

---

# Verificação de Lock

```powershell
Test-Path .\runtime\collection.lock
```

Resultado esperado:

```text
False
```

---

# Validação de Código

```powershell
python -m py_compile .\scripts\run_collection.py
```

```powershell
python -m py_compile .\scripts\run_scheduled_collection.py
```

---

# Validação dos Testes

```powershell
python -m pytest
```

Resultado esperado:

```text
417 passed
```

---

# Verificação de Saúde

Validar:

```text
health_last.json atualizado
health_history.jsonl atualizado
```

---

# Verificação de Qualidade

Validar:

```text
quality_last.json atualizado
quality_history.jsonl atualizado
```

---

# Recuperação

Em caso de falha:

1. verificar scheduled_collection.log
2. verificar collection_last.json
3. verificar quality_last.json
4. verificar health_last.json
5. verificar collection.lock
6. executar DryRun manual

---

# Estado Atual

Situação validada:

```text
417 testes aprovados
agendamento validado
monitoramento validado
qualidade validada
```