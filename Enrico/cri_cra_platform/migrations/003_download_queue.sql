-- Fila de download em lotes. Tabelas novas, sem alterar nenhuma existente.
-- download_batches: cada execucao do worker (parametros, batimento e motivo da parada).
-- download_queue: um item por documento a baixar. A unicidade de document_id vale so
-- enquanto o item esta ativo (pending ou running), entao um documento pode ser
-- enfileirado de novo depois de concluido, falho ou ignorado.
CREATE TABLE IF NOT EXISTS download_batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'finished', 'stopped', 'abandoned')),
    params_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    finished_at TEXT,
    stop_reason TEXT,
    items_processed INTEGER NOT NULL DEFAULT 0 CHECK (items_processed >= 0),
    items_failed INTEGER NOT NULL DEFAULT 0 CHECK (items_failed >= 0),
    bytes_downloaded INTEGER NOT NULL DEFAULT 0 CHECK (bytes_downloaded >= 0),
    CHECK (status = 'running' OR finished_at IS NOT NULL)
);

-- No maximo um lote em andamento por banco (um worker por vez).
CREATE UNIQUE INDEX IF NOT EXISTS ux_download_batches_single_running
    ON download_batches((1)) WHERE status = 'running';

CREATE TABLE IF NOT EXISTS download_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'done', 'failed', 'skipped')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),
    next_attempt_at TEXT,
    last_error TEXT,
    last_error_type TEXT,
    error_class TEXT
        CHECK (error_class IS NULL
               OR error_class IN ('temporary', 'permanent', 'validation', 'blocked')),
    last_http_status INTEGER,
    worker_id TEXT,
    batch_id INTEGER,
    enqueued_at TEXT NOT NULL,
    started_at TEXT,
    heartbeat_at TEXT,
    finished_at TEXT,
    bytes_downloaded INTEGER CHECK (bytes_downloaded IS NULL OR bytes_downloaded >= 0),
    FOREIGN KEY(document_id) REFERENCES documents(document_pk),
    FOREIGN KEY(batch_id) REFERENCES download_batches(batch_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_download_queue_active_document
    ON download_queue(document_id) WHERE status IN ('pending', 'running');

CREATE INDEX IF NOT EXISTS ix_download_queue_next
    ON download_queue(status, priority, next_attempt_at);

CREATE INDEX IF NOT EXISTS ix_download_queue_batch ON download_queue(batch_id);
