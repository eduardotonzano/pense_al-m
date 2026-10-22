-- Campos oficiais da grade do Fundos.NET (todos opcionais). Permitem classificar
-- e reprocessar o catalogo sem nova coleta. A linha original da grade fica em
-- source_row_json; as colunas tipadas so existem para o que o coletor ja le.
ALTER TABLE documents ADD COLUMN source_category TEXT;
ALTER TABLE documents ADD COLUMN source_type TEXT;
ALTER TABLE documents ADD COLUMN source_species TEXT;
ALTER TABLE documents ADD COLUMN grid_version TEXT;
ALTER TABLE documents ADD COLUMN source_description TEXT;
ALTER TABLE documents ADD COLUMN source_row_json TEXT;

-- Primeira vez que o documento apareceu no catalogo (collected_at e a ultima).
ALTER TABLE documents ADD COLUMN first_seen_at TEXT;
UPDATE documents SET first_seen_at = collected_at WHERE first_seen_at IS NULL;

-- Auditoria das trocas de categoria feitas por scripts/reclassify_documents.py.
CREATE TABLE IF NOT EXISTS document_category_changes (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    old_category TEXT NOT NULL,
    new_category TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    rule_group TEXT NOT NULL CHECK (rule_group IN ('verified', 'unverified')),
    matched_field TEXT,
    matched_value TEXT,
    classifier_version TEXT NOT NULL,
    run_id TEXT,
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (old_category <> new_category),
    FOREIGN KEY(document_id) REFERENCES documents(document_pk),
    FOREIGN KEY(run_id) REFERENCES executions(run_id)
);

CREATE INDEX IF NOT EXISTS ix_document_category_changes_document_id
    ON document_category_changes(document_id);
