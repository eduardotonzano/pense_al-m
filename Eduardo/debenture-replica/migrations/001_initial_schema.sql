PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS issuers (
 id INTEGER PRIMARY KEY AUTOINCREMENT, cnpj TEXT UNIQUE, legal_name TEXT NOT NULL CHECK(length(trim(legal_name))>0), trade_name TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(cnpj IS NULL OR (length(cnpj)=14 AND cnpj NOT GLOB '*[^0-9]*'))
);
CREATE TABLE IF NOT EXISTS debentures (
 id INTEGER PRIMARY KEY AUTOINCREMENT, issuer_id INTEGER REFERENCES issuers(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 asset_code TEXT UNIQUE, isin TEXT UNIQUE, issue_number TEXT, series TEXT,
 status TEXT NOT NULL DEFAULT 'unknown' CHECK(status IN ('unknown','active','inactive','matured','cancelled')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, inactive_at TEXT,
 CHECK(asset_code IS NOT NULL OR isin IS NOT NULL),
 CHECK(asset_code IS NULL OR (length(trim(asset_code))>0 AND asset_code=upper(asset_code))),
 CHECK(isin IS NULL OR (length(isin)=12 AND isin=upper(isin)))
);
CREATE TABLE IF NOT EXISTS sources (
 id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE CHECK(length(trim(code))>0 AND code=upper(code)),
 name TEXT NOT NULL CHECK(length(trim(name))>0), source_type TEXT NOT NULL CHECK(source_type IN ('scraper','api','manual','document','internal')),
 priority INTEGER NOT NULL DEFAULT 0 CHECK(priority>=0), active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS collection_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT,
 status TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running','success','partial','failed','cancelled')),
 requested_items INTEGER NOT NULL DEFAULT 0 CHECK(requested_items>=0), successful_items INTEGER NOT NULL DEFAULT 0 CHECK(successful_items>=0),
 failed_items INTEGER NOT NULL DEFAULT 0 CHECK(failed_items>=0), error_summary TEXT,
 CHECK(finished_at IS NULL OR finished_at>=started_at)
);
CREATE TABLE IF NOT EXISTS raw_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 collection_run_id INTEGER REFERENCES collection_runs(id) ON UPDATE CASCADE ON DELETE SET NULL,
 request_url TEXT, request_parameters TEXT, content_type TEXT, payload BLOB NOT NULL CHECK(length(payload)>0),
 payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64), http_status INTEGER CHECK(http_status IS NULL OR http_status BETWEEN 100 AND 599),
 collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, parser_version TEXT,
 processing_status TEXT NOT NULL DEFAULT 'pending' CHECK(processing_status IN ('pending','processed','failed','ignored')), processing_error TEXT,
 UNIQUE(source_id,payload_sha256)
);
CREATE TABLE IF NOT EXISTS observations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, debenture_id INTEGER NOT NULL REFERENCES debentures(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 raw_record_id INTEGER REFERENCES raw_records(id) ON UPDATE CASCADE ON DELETE SET NULL,
 field_name TEXT NOT NULL CHECK(length(trim(field_name))>0), value_type TEXT NOT NULL CHECK(value_type IN ('text','numeric','date','boolean')),
 value_text TEXT, value_numeric NUMERIC, value_date TEXT, value_boolean INTEGER CHECK(value_boolean IS NULL OR value_boolean IN (0,1)), unit TEXT,
 observed_at TEXT NOT NULL, collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, valid_from TEXT, valid_until TEXT,
 confidence TEXT NOT NULL DEFAULT 'reported' CHECK(confidence IN ('reported','verified','manual','conflicting','suspect')),
 checksum TEXT NOT NULL UNIQUE CHECK(length(checksum)=64), CHECK(valid_until IS NULL OR valid_from IS NULL OR valid_until>=valid_from),
 CHECK((value_type='text' AND value_text IS NOT NULL AND value_numeric IS NULL AND value_date IS NULL AND value_boolean IS NULL)
 OR (value_type='numeric' AND value_text IS NULL AND value_numeric IS NOT NULL AND value_date IS NULL AND value_boolean IS NULL)
 OR (value_type='date' AND value_text IS NULL AND value_numeric IS NULL AND value_date IS NOT NULL AND value_boolean IS NULL)
 OR (value_type='boolean' AND value_text IS NULL AND value_numeric IS NULL AND value_date IS NULL AND value_boolean IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS data_conflicts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, debenture_id INTEGER NOT NULL REFERENCES debentures(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 field_name TEXT NOT NULL CHECK(length(trim(field_name))>0), observation_a_id INTEGER NOT NULL REFERENCES observations(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 observation_b_id INTEGER NOT NULL REFERENCES observations(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','ignored')), resolution_note TEXT, resolved_at TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, CHECK(observation_a_id<>observation_b_id),
 CHECK(status<>'resolved' OR resolved_at IS NOT NULL), UNIQUE(debenture_id,field_name,observation_a_id,observation_b_id)
);
CREATE TABLE IF NOT EXISTS audit_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL CHECK(length(trim(actor))>0), action TEXT NOT NULL CHECK(length(trim(action))>0),
 entity_type TEXT NOT NULL CHECK(length(trim(entity_type))>0), entity_id INTEGER NOT NULL, before_data TEXT, after_data TEXT, reason TEXT,
 occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_issuers_legal_name ON issuers(legal_name);
CREATE INDEX IF NOT EXISTS idx_debentures_issuer ON debentures(issuer_id);
CREATE INDEX IF NOT EXISTS idx_collection_runs_source ON collection_runs(source_id,started_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_records_source ON raw_records(source_id,collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_observations_lookup ON observations(debenture_id,field_name,observed_at DESC,collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_conflicts_status ON data_conflicts(status);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type,entity_id);
CREATE VIEW IF NOT EXISTS current_observations AS
SELECT id,debenture_id,field_name,value_type,value_text,value_numeric,value_date,value_boolean,unit,observed_at,collected_at,source_code,source_name,source_priority,confidence
FROM (SELECT o.*,s.code source_code,s.name source_name,s.priority source_priority,
ROW_NUMBER() OVER(PARTITION BY o.debenture_id,o.field_name ORDER BY s.priority DESC,o.observed_at DESC,o.collected_at DESC,o.id DESC) rn
FROM observations o JOIN sources s ON s.id=o.source_id WHERE s.active=1) WHERE rn=1;
INSERT OR IGNORE INTO sources(code,name,source_type,priority,active) VALUES
('SND','Sistema Nacional de Debentures','scraper',100,1),
('CVM','Comissao de Valores Mobiliarios','document',200,1),
('ANBIMA_API','ANBIMA API Oficial','api',300,0),
('MANUAL','Entrada manual validada','manual',1000,1);
INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(1,'initial_schema');
