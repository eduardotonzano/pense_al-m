# Checklist Operacional

## Objetivo

Checklist obrigatório antes de considerar uma versão pronta para uso operacional.

---

# Pré-Execução

## Ambiente

- [ ] Ambiente virtual disponível
- [ ] Configuração carregada
- [ ] Arquivo collection.production.json válido
- [ ] Espaço em disco disponível

---

# Validação de Código

## Compilação

- [ ] run_collection.py compilado
- [ ] run_scheduled_collection.py compilado

Comandos:

```powershell
python -m py_compile .\scripts\run_collection.py
```

```powershell
python -m py_compile .\scripts\run_scheduled_collection.py
```

Resultado esperado:

```text
$LASTEXITCODE = 0
```

---

# Testes

## Suite Completa

```powershell
python -m pytest
```

Validação:

```text
417 passed
```

Checklist:

- [ ] Testes executados
- [ ] Nenhuma falha
- [ ] Nenhum teste ignorado inesperadamente

---

# DryRun

## Coleta

```powershell
python .\scripts\run_collection.py `
    .\config\collection.production.json `
    --dry-run
```

Verificar:

- [ ] ExitCode = 0
- [ ] Nenhum erro inesperado
- [ ] Integridade SQLite ok

---

# Agendamento

## Script Python

```powershell
python .\scripts\run_scheduled_collection.py `
    --config .\config\collection.production.json `
    --dry-run
```

---

## Script PowerShell

```powershell
.\scripts\run_scheduled_collection.ps1
```

Verificar:

- [ ] ExitCode = 0
- [ ] scheduled_collection.log atualizado

---

# Logs

## Operação

- [ ] collection_last.json atualizado
- [ ] debenture_collection.log atualizado
- [ ] debenture_collection.jsonl atualizado

---

## Qualidade

- [ ] quality_last.json atualizado
- [ ] quality_history.jsonl atualizado

---

## Monitoramento

- [ ] health_last.json atualizado
- [ ] health_history.jsonl atualizado

---

# Lock

Arquivo:

```text
runtime/collection.lock
```

Verificar:

```powershell
Test-Path .\runtime\collection.lock
```

Resultado esperado:

```text
False
```

Checklist:

- [ ] Lock removido após execução

---

# Relatório Principal

Arquivo:

```text
logs/collection_last.json
```

Verificar:

- [ ] quality presente
- [ ] health presente
- [ ] ativos processados
- [ ] sucessos
- [ ] falhas

---

# Estado Congelado

Versão validada:

```text
417 testes aprovados
```

Etapas concluídas:

```text
1 - Logs estruturados
2 - Lock operacional
3 - Retry seguro
4 - Retenção automática
5 - Qualidade integrada
6 - Agendamento Windows
7 - Alertas e monitoramento
```

---

# Aprovação

- [ ] Validação técnica concluída
- [ ] Checklist concluído
- [ ] Versão aprovada para operação
``