# Catálogo de Logs

## Objetivo

Documentar todos os arquivos de log gerados pelo projeto e sua finalidade operacional.

---

# Logs Operacionais

## debenture_collection.log

Arquivo:

```text
logs/debenture_collection.log
```

Formato:

```text
texto
```

Objetivo:

- rastreabilidade operacional;
- auditoria;
- diagnóstico de falhas.

---

## debenture_collection.jsonl

Arquivo:

```text
logs/debenture_collection.jsonl
```

Formato:

```text
JSON Lines
```

Objetivo:

- processamento automatizado;
- integração futura;
- histórico de eventos.

Eventos registrados:

```text
automation_started
asset_started
asset_succeeded
retry_scheduled
automation_finished
quality_check_completed
```

---

# Relatório Operacional

## collection_last.json

Arquivo:

```text
logs/collection_last.json
```

Objetivo:

Registrar o resultado da última execução.

Conteúdo:

```text
ativos processados
sucessos
falhas
qualidade
saúde operacional
exportações
backup
```

---

# Qualidade

## quality_last.json

Arquivo:

```text
logs/quality_last.json
```

Objetivo:

Último relatório de qualidade.

Estados:

```text
success
success_with_warnings
failed
```

---

## quality_history.jsonl

Arquivo:

```text
logs/quality_history.jsonl
```

Objetivo:

Histórico completo da qualidade.

---

# Monitoramento

## health_last.json

Arquivo:

```text
logs/health_last.json
```

Objetivo:

Estado atual da saúde operacional.

Estados possíveis:

```text
healthy
warning
critical
```

Campos principais:

```text
health
critical_count
warning_count
open_alerts
```

---

## health_history.jsonl

Arquivo:

```text
logs/health_history.jsonl
```

Objetivo:

Histórico permanente da saúde do sistema.

---

# Agendamento

## scheduled_collection.log

Arquivo:

```text
logs/scheduled_collection.log
```

Objetivo:

Registrar execuções disparadas pelo agendador.

Informações registradas:

```text
hora de início
hora de término
saída do Python
ExitCode
```

---

# Retenção

Logs relacionados:

```text
logs/collection_last.json
logs/quality_last.json
logs/health_last.json
```

Protegidos pelas regras de retenção.

---

# Uso Operacional

## Última coleta

```powershell
Get-Content .\logs\collection_last.json
```

---

## Última qualidade

```powershell
Get-Content .\logs\quality_last.json
```

---

## Última saúde

```powershell
Get-Content .\logs\health_last.json
```

---

## Histórico de saúde

```powershell
Get-Content .\logs\health_history.jsonl -Tail 20
```

---

# Estado Congelado

Validação da Etapa 8:

```text
417 testes aprovados
logs operacionais ativos
qualidade ativa
monitoramento ativo
agendamento validado
```