# Plano: fila de download em lotes (aprovado para implementação e teste em ambiente descartável)

Status: plano aprovado por Enrico (revisão incorporada abaixo) para implementar e testar em cópia descartável.
**A migration 003 NÃO foi aplicada no banco real**: isso exige nova validação (backup, dry-run, verificação).

## Objetivo
Baixar documentos de centenas de CRI/CRA sem travar, sem repetir trabalho e sem sobrecarregar o Fundos.NET,
mantendo as regras do projeto: SHA-256, falha nunca vira versão de documento, nada é sobrescrito.

## Situação atual
- `documents.download_status` guarda só o último estado do documento; `collection_attempts` guarda tentativas.
- `run_sample_download.py` baixa por ativo (`--cetip --isin`), com `--source-id` e `--max-megabytes`. Não há fila,
  retomada, limite de taxa nem critério de parada.

## Proposta

### 1. Migration `003_download_queue.sql` (tabela nova, sem alterar as existentes)
`download_queue`:
- `id`, `document_id` (FK, único por documento enquanto ativo), `priority` (menor = primeiro),
- `status` ∈ `pending | running | done | failed | skipped`,
- `attempts`, `last_error`, `next_attempt_at`, `enqueued_at`, `started_at`, `finished_at`, `batch_id`.

`download_batches`: `batch_id`, parâmetros usados (limite de taxa, limite de erro, tamanho máximo), início, fim, motivo da parada.

### 2. Comportamento
- **Enfileirar** a partir do catálogo: só documentos com `download_status = pending` e categoria permitida.
  Prévia (`--dry-run`) mostra quantos, de quais ativos e o tamanho estimado quando conhecido.
- **Retomada:** item `running` abandonado volta para `pending` ao iniciar um novo lote. Nada é rebaixado se já está `done`.
- **Limite de taxa:** pausa mínima entre requisições (padrão 2 s) e teto por minuto, configuráveis.
- **Nova tentativa:** até 3 vezes, com espera crescente (1, 5, 30 min). Depois vira `failed` e fica para revisão.
- **Parada automática:** interrompe o lote se a taxa de falha passar de 20% nas últimas 20 tentativas, ou em 5
  falhas seguidas, ou ao sinal de bloqueio (HTTP 429/403). Registra o motivo em `download_batches`.
- **Segurança:** reaproveita a validação existente (ISIN conferido na grade, tamanho máximo, SHA-256). Falha não cria versão.
- **Idempotência:** rodar duas vezes não baixa de novo o que já tem versão válida com o mesmo hash.
- **Disco:** o lote para se o espaço livre ficar abaixo de um mínimo configurável.

### 3. Script
`scripts/run_download_queue.py` com `--enqueue`, `--run`, `--status`, `--limit`, `--only <CETIP>`, `--dry-run`
obrigatório antes de `--commit`. Sem nenhuma das flags, não faz nada.

### 4. Testes (sem rede, com fakes)
Migration e idempotência; retomada após queda; limite de taxa; parada por falhas; falha não cria versão;
segunda execução sem duplicar.

### 5. Ordem de aplicação (regras do CLAUDE.md)
1. Você aprova este plano. 2. Código e testes. 3. Migration numa cópia descartável (`--dry-run`).
4. Backup do banco real. 5. Aplicação, com sua aprovação. 6. `integrity_check`, `foreign_key_check`, contagens.
7. Lote-piloto de 20 a 30 ativos antes de abrir o universo.

## Decisões que estavam em aberto (respondidas na revisão aprovada, ver o fim do documento)
- Limites padrão (2 s entre requisições, 20% de falha, mínimo de disco).
- Categorias baixadas em massa: sugiro Informe Mensal, Termo, Relatório do AF, DFs, Ata/Edital e Comunicado/Fato
  Relevante; prospectos (grandes) só depois, por prioridade.
- Se a fila já entra com a lista de ativos da amostra (8 a 10) ou só com os três pilotos no primeiro teste.

## Ajustes aprovados e incorporados (implementação)
- Unicidade de `document_id` só enquanto `pending` ou `running` (índice parcial): documento pode ser enfileirado de novo depois.
- `running` não volta a `pending` só porque outro lote começou: o lote anterior precisa estar sem batimento há mais de
  30 min (`abandon_after_seconds`). Com batimento recente o novo worker **recusa iniciar**. Índice único garante 1 lote `running`.
- Concorrência 1; `claim` atômico (`BEGIN IMMEDIATE` + `UPDATE ... WHERE status='pending'`).
- Erros: **temporário** (timeout, rede, HTTP 429, 5xx, desconhecido: até 3 tentativas) × **permanente** (404 e demais 4xx,
  documento indisponível) × **validação** (ISIN divergente, acima do limite, vazio, HTML, formato inválido) × **bloqueio** (403: para o lote na hora).
- HTTP 429 respeita `Retry-After` quando o executor o informa (o downloader atual não expõe o cabeçalho: hoje vale a espera padrão).
- Parada: taxa de falha >= 20% após pelo menos 20 tentativas; 5 falhas consecutivas; limites de itens, duração e bytes totais.
- Registro por item: worker, código HTTP, classe e tipo do erro; por lote: parâmetros, batimento e motivo da parada.
- Padrões do piloto: intervalo 2 s, 20 req/min, esperas 1/5/30 min, espaço livre mínimo = maior entre 10 GB e 10% do disco,
  sem prospectos nem suplementos (excluídos pelo nome), primeiro teste com 3 ativos.
- Arquivos: `migrations/003_download_queue.sql`, `services/download_queue_service.py`, `scripts/run_download_queue.py`,
  `tests/unit/test_download_queue_service.py`.
- Verificação feita: dry-run da migration sobre o banco real (hash do banco igual antes e depois); aplicação só numa cópia
  descartável; os 3 pilotos já estão baixados, então a fila deles nasce vazia (esperado).
