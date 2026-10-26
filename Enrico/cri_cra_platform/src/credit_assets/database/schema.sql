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

-- Fase E: extração reprocessável. Cada execução é imutável; reprocessar cria
-- nova extraction_run sem apagar as anteriores.
CREATE TABLE IF NOT EXISTS extraction_runs (
    extraction_run_id TEXT PRIMARY KEY,
    document_version_id INTEGER NOT NULL REFERENCES document_versions(version_id),
    extractor_version TEXT NOT NULL,
    mapping_version TEXT NOT NULL,
    layout_version TEXT,
    layout_validation_status TEXT NOT NULL
        CHECK (layout_validation_status IN ('formal', 'structural_only')),
    semantic_normalizer_version TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    error_message TEXT,
    raw_file_hash TEXT NOT NULL,
    semantic_hash TEXT,
    unmapped_fields_count INTEGER
);

CREATE INDEX IF NOT EXISTS ix_extraction_runs_document_version
    ON extraction_runs(document_version_id);

CREATE TABLE IF NOT EXISTS extracted_reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    extraction_run_id TEXT NOT NULL UNIQUE REFERENCES extraction_runs(extraction_run_id),
    asset_id INTEGER NOT NULL REFERENCES assets(asset_id),
    document_id INTEGER NOT NULL REFERENCES documents(document_pk),
    document_version_id INTEGER NOT NULL REFERENCES document_versions(version_id),
    reference_date TEXT,
    publication_date TEXT,
    source_version TEXT,
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0, 1)),
    automatic_validation_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (automatic_validation_status IN ('valid', 'warning', 'invalid', 'pending')),
    human_review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (human_review_status IN ('not_required', 'pending', 'approved', 'rejected', 'corrected'))
);

CREATE TABLE IF NOT EXISTS extracted_values (
    extracted_value_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES extracted_reports(report_id),
    field_name TEXT NOT NULL,
    original_value TEXT,
    normalized_value TEXT,
    data_type TEXT,
    field_state TEXT NOT NULL CHECK (field_state IN (
        'present_value', 'present_empty', 'absent', 'zero', 'not_applicable', 'invalid'
    )),
    xsi_nil INTEGER NOT NULL DEFAULT 0 CHECK (xsi_nil IN (0, 1)),
    unit TEXT,
    currency TEXT,
    scale TEXT,
    xml_path TEXT NOT NULL,
    instance_index INTEGER NOT NULL DEFAULT 0,
    instance_key TEXT,
    parent_instance_key TEXT,
    mapping_status TEXT NOT NULL
        CHECK (mapping_status IN ('mapped', 'ignored', 'pending_decision')),
    automatic_validation_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (automatic_validation_status IN ('valid', 'warning', 'invalid', 'pending')),
    UNIQUE(report_id, xml_path, instance_index)
);

CREATE INDEX IF NOT EXISTS ix_extracted_values_report ON extracted_values(report_id);

CREATE TABLE IF NOT EXISTS evidences (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    extracted_value_id INTEGER NOT NULL UNIQUE REFERENCES extracted_values(extracted_value_id),
    document_version_id INTEGER NOT NULL REFERENCES document_versions(version_id),
    xml_path TEXT NOT NULL,
    line_number INTEGER,
    evidence_excerpt TEXT,
    evidence_excerpt_truncated INTEGER NOT NULL DEFAULT 0 CHECK (evidence_excerpt_truncated IN (0, 1)),
    evidence_full_hash TEXT NOT NULL,
    contains_personal_data INTEGER NOT NULL DEFAULT 0 CHECK (contains_personal_data IN (0, 1)),
    masking_applied INTEGER NOT NULL DEFAULT 0 CHECK (masking_applied IN (0, 1)),
    retention_policy TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS value_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    extracted_value_id INTEGER NOT NULL REFERENCES extracted_values(extracted_value_id),
    source_value_hash TEXT NOT NULL,
    review_status TEXT NOT NULL
        CHECK (review_status IN ('pending', 'approved', 'rejected', 'corrected')),
    corrected_value TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    justification TEXT
);

CREATE TABLE IF NOT EXISTS extraction_findings (
    finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES extracted_reports(report_id),
    rule TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('warning', 'invalid')),
    xml_path TEXT,
    instance_index INTEGER,
    message TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_extraction_findings_report ON extraction_findings(report_id);

-- Revisão humana de relatórios; extracted_reports.human_review_status e
-- is_current refletem a revisão mais recente.
CREATE TABLE IF NOT EXISTS report_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES extracted_reports(report_id),
    review_status TEXT NOT NULL
        CHECK (review_status IN ('approved', 'rejected', 'pending', 'corrected')),
    reviewed_by TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    decision_source TEXT NOT NULL,
    justification TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_report_reviews_report ON report_reviews(report_id);

-- Comparação entre competências vigentes consecutivas (sem limites/alertas).
CREATE TABLE IF NOT EXISTS period_comparisons (
    comparison_id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_run_id TEXT NOT NULL,
    comparator_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    asset_id INTEGER NOT NULL REFERENCES assets(asset_id),
    xml_path TEXT NOT NULL,
    instance_key TEXT,
    data_type TEXT,
    previous_report_id INTEGER NOT NULL REFERENCES extracted_reports(report_id),
    current_report_id INTEGER NOT NULL REFERENCES extracted_reports(report_id),
    previous_month TEXT NOT NULL,
    current_month TEXT NOT NULL,
    months_between INTEGER NOT NULL,
    previous_value TEXT,
    current_value TEXT,
    previous_state TEXT,
    current_state TEXT,
    absolute_change TEXT,
    relative_change TEXT,
    comparison_status TEXT NOT NULL CHECK (comparison_status IN (
        'unchanged', 'changed', 'state_changed', 'excluded_scale_unknown', 'only_one_side'
    ))
);

CREATE INDEX IF NOT EXISTS ix_period_comparisons_run ON period_comparisons(comparison_run_id);

-- Alertas de qualidade de dado (sem limites contratuais). fingerprint evita
-- duplicar o mesmo alerta entre execuções; descartes são preservados.
CREATE TABLE IF NOT EXISTS data_quality_alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    rule_id TEXT NOT NULL,
    rules_version TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    asset_id INTEGER NOT NULL REFERENCES assets(asset_id),
    report_id INTEGER REFERENCES extracted_reports(report_id),
    competencia_mes TEXT NOT NULL,
    instance_key TEXT,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning')),
    message TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    alert_status TEXT NOT NULL DEFAULT 'open'
        CHECK (alert_status IN ('open', 'acknowledged', 'resolved', 'dismissed')),
    dismiss_reason TEXT,
    status_changed_by TEXT,
    status_changed_at TEXT,
    first_seen_run_id TEXT NOT NULL,
    last_seen_run_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK (alert_status <> 'dismissed' OR dismiss_reason IS NOT NULL)
);

-- Texto de PDFs por página (evidência para parâmetros contratuais).
CREATE TABLE IF NOT EXISTS document_text_pages (
    document_version_id INTEGER NOT NULL REFERENCES document_versions(version_id),
    page_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    extractor TEXT NOT NULL,
    extracted_at TEXT NOT NULL,
    PRIMARY KEY (document_version_id, page_number, extractor)
);

-- Trechos candidatos a parâmetros contratuais: literal + revisão humana.
CREATE TABLE IF NOT EXISTS contract_parameter_candidates (
    candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_version_id INTEGER NOT NULL REFERENCES document_versions(version_id),
    finder_version TEXT NOT NULL,
    topic TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    excerpt TEXT NOT NULL,
    excerpt_sha256 TEXT NOT NULL,
    page_text_sha256 TEXT NOT NULL,
    values_found_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (document_version_id, topic, excerpt_sha256)
);

-- Parâmetros contratuais estruturados; só os aprovados podem alimentar alertas.
CREATE TABLE IF NOT EXISTS contract_parameters (
    parameter_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL REFERENCES assets(asset_id),
    candidate_id INTEGER NOT NULL REFERENCES contract_parameter_candidates(candidate_id),
    parameter_name TEXT NOT NULL,
    parameter_value TEXT,
    unit TEXT,
    applies_when TEXT,
    source_reference TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'approved', 'rejected', 'corrected')),
    proposed_by TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    justification TEXT,
    UNIQUE (asset_id, parameter_name, candidate_id)
);

-- Fatos numéricos lidos de documentos textuais (AF, comunicados), com trecho
-- literal conferido contra o texto da página.
CREATE TABLE IF NOT EXISTS reported_facts (
    fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL REFERENCES assets(asset_id),
    document_version_id INTEGER NOT NULL REFERENCES document_versions(version_id),
    page_number INTEGER NOT NULL,
    page_text_sha256 TEXT NOT NULL,
    fact_name TEXT NOT NULL,
    reference_date TEXT NOT NULL,
    value TEXT NOT NULL,
    unit TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'approved', 'rejected', 'corrected')),
    proposed_by TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    UNIQUE (asset_id, fact_name, reference_date, document_version_id)
);
