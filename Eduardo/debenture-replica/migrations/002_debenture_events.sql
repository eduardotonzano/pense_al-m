PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS debenture_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 debenture_id INTEGER NOT NULL REFERENCES debentures(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 event_type TEXT NOT NULL CHECK(event_type IN ('amortizacao','atualizacao','juros','opcao_venda','participacao','premio','premio_permanencia','repactuacao','resgate_total_antecipado','vencimento')),
 event_date TEXT NOT NULL CHECK(date(event_date) IS NOT NULL AND date(event_date)=event_date),
 value_numeric NUMERIC, unit TEXT CHECK(unit IS NULL OR length(trim(unit))>0),
 source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 raw_record_id INTEGER REFERENCES raw_records(id) ON UPDATE CASCADE ON DELETE SET NULL,
 observed_at TEXT NOT NULL, collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 confidence TEXT NOT NULL DEFAULT 'reported' CHECK(confidence IN ('reported','verified','manual','conflicting','suspect')),
 checksum TEXT NOT NULL UNIQUE CHECK(length(checksum)=64),
 CHECK(unit IS NULL OR value_numeric IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_debenture_events_lookup ON debenture_events(debenture_id,event_date,event_type);
INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(2,'debenture_events');
