# Códigos de Saída

## Objetivo

Padronizar o comportamento dos scripts de automação.

---

# Código 0

```text
0
```

Significa:

```text
Sucesso
```

Inclui:

- sucesso total
- sucesso com alertas
- qualidade sem críticos

---

# Código 1

```text
1
```

Significa:

```text
Erro geral
```

Exemplos:

- erro inesperado
- erro de configuração
- falha operacional

---

# Código 2

```text
2
```

Significa:

```text
Falha em um ou mais ativos
```

Exemplos:

- falha de consulta
- falha de processamento
- falha de importação

---

# Código 3

```text
3
```

Significa:

```text
Lock ativo
```

Relacionamento:

```text
runtime/collection.lock
```

---

# Código 4

```text
4
```

Significa:

```text
Qualidade crítica
```

Exemplos:

- integridade SQLite inválida
- foreign key violation
- erro crítico de qualidade

---

# Código 130

```text
130
```

Significa:

```text
Interrupção manual
```

Exemplo:

```text
CTRL+C
```

---

# Consulta no PowerShell

```powershell
$LASTEXITCODE
```

---

# Consulta em Python

```python
raise SystemExit(0)
```

```python
raise SystemExit(1)
```

```python
raise SystemExit(2)
```

```python
raise SystemExit(3)
```

```python
raise SystemExit(4)
```

```python
raise SystemExit(130)
```

---

# Tabela Resumida

```text
0   sucesso
1   erro geral
2   falha operacional
3   lock ativo
4   qualidade crítica
130 interrupção manual
```