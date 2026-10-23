-- Indicadores do Informe Mensal (S-09) e ratings (S-10). Toda linha aponta para o
-- documento de origem e para o arquivo exato que foi lido (document_versions).

-- Cada linha e uma folha (ou atributo) do XML do informe, com o campo e o valor
-- como estao no arquivo. Nenhum campo e escolhido aqui: o que a ficha exibe e
-- decisao da S-09.
CREATE TABLE IF NOT EXISTS informe_indicators (
    indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    version_id INTEGER NOT NULL,
    -- Mes de competencia lido do proprio XML, nunca do nome do arquivo.
    reference_period TEXT NOT NULL CHECK (
        date(reference_period) IS NOT NULL AND date(reference_period) = reference_period
    ),
    -- Caminho do elemento no XML, sem indices (estavel entre meses). A
    -- ocorrencia lista as posicoes maiores que 1 entre irmaos de mesmo nome,
    -- no formato profundidade:posicao separado por virgula, e fica vazia na
    -- primeira ocorrencia.
    field TEXT NOT NULL CHECK (TRIM(field) <> ''),
    occurrence TEXT NOT NULL DEFAULT '',
    -- Texto do XML sem os espacos das pontas. value_kind e a forma do texto:
    -- empty (value NULL), number (so digitos com ponto decimal), date (AAAA-MM-DD)
    -- ou text. Nunca vem do nome do campo.
    value TEXT,
    value_kind TEXT NOT NULL CHECK (value_kind IN ('empty', 'number', 'date', 'text')),
    -- So quando o proprio XML declara a unidade.
    unit TEXT CHECK (unit IS NULL OR TRIM(unit) <> ''),
    source TEXT NOT NULL CHECK (TRIM(source) <> ''),
    collected_at TEXT NOT NULL CHECK (datetime(collected_at) IS NOT NULL),
    parser_version TEXT NOT NULL CHECK (TRIM(parser_version) <> ''),
    run_id TEXT NOT NULL,
    CHECK ((value_kind = 'empty') = (value IS NULL)),
    CHECK (value IS NULL OR TRIM(value) <> ''),
    UNIQUE (version_id, field, occurrence),
    FOREIGN KEY(asset_id) REFERENCES assets(asset_id),
    FOREIGN KEY(document_id) REFERENCES documents(document_pk),
    FOREIGN KEY(version_id) REFERENCES document_versions(version_id),
    FOREIGN KEY(run_id) REFERENCES executions(run_id)
);

CREATE INDEX IF NOT EXISTS ix_informe_indicators_asset_period
    ON informe_indicators(asset_id, reference_period);

CREATE INDEX IF NOT EXISTS ix_informe_indicators_document
    ON informe_indicators(document_id);

-- A versao e o ativo precisam ser do documento informado.
CREATE TRIGGER IF NOT EXISTS trg_informe_indicators_origin_insert
BEFORE INSERT ON informe_indicators
WHEN (SELECT document_id FROM document_versions WHERE version_id = NEW.version_id)
         IS NOT NEW.document_id
     OR (SELECT asset_id FROM documents WHERE document_pk = NEW.document_id)
         IS NOT NEW.asset_id
BEGIN
    SELECT RAISE(ABORT, 'informe_indicators: a versao ou o ativo nao sao do documento informado');
END;

CREATE TRIGGER IF NOT EXISTS trg_informe_indicators_origin_update
BEFORE UPDATE OF asset_id, document_id, version_id ON informe_indicators
WHEN (SELECT document_id FROM document_versions WHERE version_id = NEW.version_id)
         IS NOT NEW.document_id
     OR (SELECT asset_id FROM documents WHERE document_pk = NEW.document_id)
         IS NOT NEW.asset_id
BEGIN
    SELECT RAISE(ABORT, 'informe_indicators: a versao ou o ativo nao sao do documento informado');
END;

-- Agencia e nota como estao no documento. A fonte e um PDF (page) ou o XML do
-- informe (source_ref, o caminho do campo): a linha sempre aponta para um lugar.
-- Nada vai para a ficha sem revisao humana: a ficha le ratings_verified.
CREATE TABLE IF NOT EXISTS ratings (
    rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    agency TEXT NOT NULL CHECK (TRIM(agency) <> ''),
    grade TEXT NOT NULL CHECK (TRIM(grade) <> ''),
    rating_date TEXT NOT NULL CHECK (
        date(rating_date) IS NOT NULL AND date(rating_date) = rating_date
    ),
    document_id INTEGER NOT NULL,
    version_id INTEGER NOT NULL,
    page INTEGER CHECK (page IS NULL OR page >= 1),
    source_ref TEXT CHECK (source_ref IS NULL OR TRIM(source_ref) <> ''),
    -- Trecho literal que sustenta a nota, para quem revisa.
    quoted_text TEXT NOT NULL CHECK (TRIM(quoted_text) <> ''),
    review_status TEXT NOT NULL DEFAULT 'pending_review' CHECK (
        review_status IN ('pending_review', 'verified', 'rejected')
    ),
    reviewed_at TEXT CHECK (reviewed_at IS NULL OR datetime(reviewed_at) IS NOT NULL),
    collected_at TEXT NOT NULL CHECK (datetime(collected_at) IS NOT NULL),
    parser_version TEXT NOT NULL CHECK (TRIM(parser_version) <> ''),
    run_id TEXT NOT NULL,
    CHECK (page IS NOT NULL OR source_ref IS NOT NULL),
    CHECK ((review_status = 'pending_review') = (reviewed_at IS NULL)),
    UNIQUE (version_id, agency, grade, rating_date),
    FOREIGN KEY(asset_id) REFERENCES assets(asset_id),
    FOREIGN KEY(document_id) REFERENCES documents(document_pk),
    FOREIGN KEY(version_id) REFERENCES document_versions(version_id),
    FOREIGN KEY(run_id) REFERENCES executions(run_id)
);

CREATE INDEX IF NOT EXISTS ix_ratings_asset_date
    ON ratings(asset_id, rating_date);

CREATE INDEX IF NOT EXISTS ix_ratings_document
    ON ratings(document_id);

CREATE TRIGGER IF NOT EXISTS trg_ratings_origin_insert
BEFORE INSERT ON ratings
WHEN (SELECT document_id FROM document_versions WHERE version_id = NEW.version_id)
         IS NOT NEW.document_id
     OR (SELECT asset_id FROM documents WHERE document_pk = NEW.document_id)
         IS NOT NEW.asset_id
BEGIN
    SELECT RAISE(ABORT, 'ratings: a versao ou o ativo nao sao do documento informado');
END;

CREATE TRIGGER IF NOT EXISTS trg_ratings_origin_update
BEFORE UPDATE OF asset_id, document_id, version_id ON ratings
WHEN (SELECT document_id FROM document_versions WHERE version_id = NEW.version_id)
         IS NOT NEW.document_id
     OR (SELECT asset_id FROM documents WHERE document_pk = NEW.document_id)
         IS NOT NEW.asset_id
BEGIN
    SELECT RAISE(ABORT, 'ratings: a versao ou o ativo nao sao do documento informado');
END;

CREATE VIEW IF NOT EXISTS ratings_verified AS
SELECT * FROM ratings WHERE review_status = 'verified';
