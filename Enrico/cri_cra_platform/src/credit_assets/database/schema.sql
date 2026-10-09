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
    codigo_cetip TEXT,
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

CREATE UNIQUE INDEX IF NOT EXISTS uq_assets_isin_normalized_nonempty
    ON assets(UPPER(REPLACE(TRIM(isin), ' ', '')))
    WHERE isin IS NOT NULL AND TRIM(isin) <> '';

CREATE UNIQUE INDEX IF NOT EXISTS uq_assets_codigo_cetip_normalized_nonempty
    ON assets(UPPER(REPLACE(TRIM(codigo_cetip), ' ', '')))
    WHERE codigo_cetip IS NOT NULL AND TRIM(codigo_cetip) <> '';

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
    run_id TEXT NOT NULL,
    UNIQUE(source_document_id, source),
    FOREIGN KEY(asset_id) REFERENCES assets(asset_id),
    FOREIGN KEY(run_id) REFERENCES executions(run_id)
);

CREATE INDEX IF NOT EXISTS ix_documents_file_hash
    ON documents(file_hash)
    WHERE file_hash IS NOT NULL AND file_hash <> '';

CREATE TABLE IF NOT EXISTS document_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    file_name TEXT,
    local_file_path TEXT,
    file_format TEXT,
    file_size_bytes INTEGER,
    file_hash TEXT,
    downloaded_at TEXT,
    source_url TEXT,
    source_version TEXT,
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0, 1)),
    validation_status TEXT NOT NULL CHECK (validation_status = 'valid'),
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(document_pk),
    UNIQUE(document_id, file_hash),
    CHECK (file_hash IS NULL OR (
        length(file_hash) = 64 AND file_hash NOT GLOB '*[^0-9a-f]*'
    ))
);

CREATE INDEX IF NOT EXISTS ix_document_versions_document_id
    ON document_versions(document_id);

CREATE INDEX IF NOT EXISTS ix_document_versions_file_hash
    ON document_versions(file_hash)
    WHERE file_hash IS NOT NULL AND file_hash <> '';

CREATE UNIQUE INDEX IF NOT EXISTS uq_document_versions_current_per_document
    ON document_versions(document_id)
    WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS collection_attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    asset_id INTEGER,
    document_id INTEGER,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    http_status INTEGER,
    error_message TEXT,
    attempt_number INTEGER,
    response_content_type TEXT,
    final_url TEXT,
    FOREIGN KEY(run_id) REFERENCES executions(run_id),
    FOREIGN KEY(asset_id) REFERENCES assets(asset_id),
    FOREIGN KEY(document_id) REFERENCES documents(document_pk)
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
