CREATE TABLE IF NOT EXISTS executions (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    duration_seconds REAL,
    assets_processed INTEGER NOT NULL DEFAULT 0,
    documents_found INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_cetip TEXT NOT NULL UNIQUE,
    tipo_ativo TEXT NOT NULL CHECK (tipo_ativo IN ('CRI','CRA')),
    securitizadora TEXT NOT NULL,
    cnpj_securitizadora TEXT NOT NULL,
    emissao TEXT NOT NULL,
    serie TEXT NOT NULL,
    devedor TEXT,
    cnpj_devedor TEXT,
    isin TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    document_pk INTEGER PRIMARY KEY AUTOINCREMENT,
    source_document_id TEXT NOT NULL,
    asset_id INTEGER NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'Termo de Securitização',
        'Aditamento',
        'Informe Mensal',
        'Ata/Edital',
        'Fato Relevante',
        'Relatório Agente Fiduciário',
        'Relatório de Rating',
        'Anúncio de Encerramento',
        'Outro'
    )),
    document_name TEXT NOT NULL,
    reference_date TEXT,
    publication_date TEXT,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    download_status TEXT NOT NULL DEFAULT 'pending',
    file_hash TEXT,
    collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id TEXT,
    UNIQUE(source_document_id, source),
    FOREIGN KEY(asset_id) REFERENCES assets(asset_id),
    FOREIGN KEY(run_id) REFERENCES executions(run_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_file_hash_nonempty
    ON documents(file_hash)
    WHERE file_hash IS NOT NULL AND file_hash <> '';

CREATE TABLE IF NOT EXISTS collection_attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    asset_id INTEGER,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    http_status INTEGER,
    error_message TEXT,
    FOREIGN KEY(run_id) REFERENCES executions(run_id),
    FOREIGN KEY(asset_id) REFERENCES assets(asset_id)
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    asset_id INTEGER,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES executions(run_id),
    FOREIGN KEY(asset_id) REFERENCES assets(asset_id)
);
