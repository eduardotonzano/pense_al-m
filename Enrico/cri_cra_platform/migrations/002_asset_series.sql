-- Séries de um ativo (emissão). O ativo continua sendo a emissão; cada série
-- guarda seu código, ISIN e classe com a evidência de onde vieram. A classe
-- do Termo (parâmetro contratual aprovado) e a do Informe Mensal ficam
-- separadas, porque podem divergir (ex.: 4ª série do CRA02500C1D).
CREATE TABLE IF NOT EXISTS asset_series (
    series_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    numero_serie INTEGER NOT NULL CHECK (numero_serie > 0),
    codigo_negociacao TEXT,
    isin TEXT,
    classe_informe TEXT,
    classe_termo TEXT,
    classe_termo_parameter_id INTEGER,
    source_report_id INTEGER,
    source_document_id TEXT,
    evidence_json TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'approved', 'rejected')),
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (asset_id, numero_serie),
    CHECK (review_status = 'pending' OR reviewed_by IS NOT NULL),
    FOREIGN KEY(asset_id) REFERENCES assets(asset_id),
    FOREIGN KEY(classe_termo_parameter_id) REFERENCES contract_parameters(parameter_id),
    FOREIGN KEY(source_report_id) REFERENCES extracted_reports(report_id)
);

CREATE INDEX IF NOT EXISTS ix_asset_series_isin ON asset_series(isin);
CREATE INDEX IF NOT EXISTS ix_asset_series_codigo ON asset_series(codigo_negociacao);
