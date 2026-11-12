-- Migration 001 do modulo de Fundos: base do banco.
-- Mesmo esqueleto de proveniencia das debentures. Identidade so por CNPJ de
-- 14 caracteres sem mascara: 12 em [0-9A-Z] e 2 digitos verificadores
-- numericos (CNPJ alfanumerico, IN RFB 2.229/2024; decisao de implementacao
-- de 27/10/2026, registrada por Eduardo, a confirmar com o Gui).
-- Nenhuma coluna guarda CPF ou dado de pessoa natural.
-- Fundos da casa nao entram neste banco (docs/decisoes-em-aberto.md,
-- decisoes 2 e 4 de Fundos).
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
 version INTEGER PRIMARY KEY,
 name TEXT NOT NULL,
 applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sources (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 code TEXT NOT NULL UNIQUE CHECK(length(code)>0 AND code NOT GLOB '*[^A-Z0-9_]*'),
 name TEXT NOT NULL CHECK(length(trim(name))>0),
 source_type TEXT NOT NULL CHECK(source_type IN ('open_data','scraper','api','manual','document','internal')),
 priority INTEGER NOT NULL DEFAULT 0 CHECK(priority>=0),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS collection_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 started_at TEXT NOT NULL CHECK(datetime(started_at) IS NOT NULL),
 finished_at TEXT CHECK(finished_at IS NULL OR datetime(finished_at) IS NOT NULL),
 status TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running','success','partial','failed','cancelled')),
 requested_items INTEGER NOT NULL DEFAULT 0 CHECK(requested_items>=0),
 successful_items INTEGER NOT NULL DEFAULT 0 CHECK(successful_items>=0),
 failed_items INTEGER NOT NULL DEFAULT 0 CHECK(failed_items>=0),
 error_summary TEXT,
 CHECK(finished_at IS NULL OR finished_at>=started_at),
 CHECK((status='running')=(finished_at IS NULL))
);

-- Manifesto do arquivo: nome, tamanho, SHA-256 e linhas. Nunca o conteudo.
-- Proposta ainda nao aprovada pelo Gui: se a regra do CPF vale tambem para o
-- arquivo original da CVM (docs/decisoes-em-aberto.md, decisao 3).
-- O ZIP e uma linha; cada CSV lido de dentro dele e uma linha filha
-- (parent_raw_record_id), com o tamanho descomprimido, o hash do CSV e o
-- numero de linhas de dados (sem cabecalho).
CREATE TABLE IF NOT EXISTS raw_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 collection_run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 parent_raw_record_id INTEGER REFERENCES raw_records(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 file_name TEXT NOT NULL CHECK(length(file_name)>0 AND file_name=trim(file_name) AND file_name NOT GLOB '*[/\:]*'),
 size_bytes INTEGER NOT NULL CHECK(size_bytes>0),
 sha256 TEXT NOT NULL CHECK(length(sha256)=64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
 line_count INTEGER CHECK(line_count IS NULL OR line_count>=0),
 request_url TEXT CHECK(request_url IS NULL OR request_url GLOB 'https://*'),
 content_type TEXT,
 http_status INTEGER CHECK(http_status IS NULL OR http_status BETWEEN 100 AND 599),
 last_modified TEXT,
 collected_at TEXT NOT NULL CHECK(datetime(collected_at) IS NOT NULL),
 parser_version TEXT,
 processing_status TEXT NOT NULL DEFAULT 'pending' CHECK(processing_status IN ('pending','processed','failed','ignored')),
 processing_error TEXT,
 CHECK(processing_status<>'failed' OR processing_error IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS funds (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 cnpj TEXT NOT NULL UNIQUE CHECK(length(cnpj)=14
   AND substr(cnpj,1,12) NOT GLOB '*[^0-9A-Z]*'
   AND substr(cnpj,13,2) NOT GLOB '*[^0-9]*'),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fund_classes (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 fund_id INTEGER NOT NULL REFERENCES funds(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 cnpj TEXT NOT NULL UNIQUE CHECK(length(cnpj)=14
   AND substr(cnpj,1,12) NOT GLOB '*[^0-9A-Z]*'
   AND substr(cnpj,13,2) NOT GLOB '*[^0-9]*'),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Serie de cotas: o pai e a classe ou, quando o CNPJ do informe so casa como
-- fundo, o proprio fundo. Chaves: rotulo normalizado (sem acento, minusculo,
-- sem '|', espacos colapsados) e/ou o ID_Subclasse da CVM. O rotulo original
-- fica nas observacoes, com proveniencia.
CREATE TABLE IF NOT EXISTS quota_series (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 fund_class_id INTEGER REFERENCES fund_classes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 fund_id INTEGER REFERENCES funds(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 series_label_key TEXT CHECK(series_label_key IS NULL OR (length(series_label_key)>0
   AND series_label_key=trim(series_label_key) AND series_label_key=lower(series_label_key)
   AND series_label_key NOT GLOB '*|*' AND series_label_key NOT GLOB '*  *')),
 cvm_subclass_id TEXT CHECK(cvm_subclass_id IS NULL OR (length(cvm_subclass_id)>0 AND cvm_subclass_id=trim(cvm_subclass_id))),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK((fund_class_id IS NOT NULL)+(fund_id IS NOT NULL)=1),
 CHECK(series_label_key IS NOT NULL OR cvm_subclass_id IS NOT NULL)
);

-- EAV: field_name = tabela.coluna da CVM, sem renomear. Valor ausente nao tem
-- linha. value_numeric e TEXT com o decimal exato (NUMERIC guardaria so 15
-- digitos significativos).
CREATE TABLE IF NOT EXISTS observations (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 fund_id INTEGER REFERENCES funds(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 fund_class_id INTEGER REFERENCES fund_classes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 quota_series_id INTEGER REFERENCES quota_series(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 collection_run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 raw_record_id INTEGER NOT NULL REFERENCES raw_records(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 field_name TEXT NOT NULL CHECK(field_name NOT GLOB '*[^A-Za-z0-9_.]*' AND field_name NOT GLOB '.*'
   AND field_name NOT GLOB '*.' AND length(field_name)-length(replace(field_name,'.',''))=1),
 value_type TEXT NOT NULL CHECK(value_type IN ('text','numeric','date','boolean')),
 value_text TEXT CHECK(value_text IS NULL OR length(trim(value_text))>0),
 value_numeric TEXT CHECK(value_numeric IS NULL OR (value_numeric NOT GLOB '*[^0-9.-]*'
   AND value_numeric GLOB '*[0-9]' AND value_numeric NOT GLOB '?*-*' AND value_numeric NOT GLOB '.*'
   AND value_numeric NOT GLOB '-.*' AND length(value_numeric)-length(replace(value_numeric,'.',''))<=1)),
 value_date TEXT CHECK(value_date IS NULL OR (date(value_date) IS NOT NULL AND date(value_date)=value_date)),
 value_boolean INTEGER CHECK(value_boolean IS NULL OR value_boolean IN (0,1)),
 unit TEXT CHECK(unit IS NULL OR (length(unit)>0 AND unit=trim(unit))),
 reference_date TEXT NOT NULL CHECK(date(reference_date) IS NOT NULL AND date(reference_date)=reference_date),
 collected_at TEXT NOT NULL CHECK(datetime(collected_at) IS NOT NULL),
 confidence TEXT NOT NULL DEFAULT 'reported' CHECK(confidence IN ('reported','verified','manual','conflicting','suspect')),
 checksum TEXT NOT NULL UNIQUE CHECK(length(checksum)=64 AND checksum NOT GLOB '*[^0-9a-f]*'),
 CHECK((fund_id IS NOT NULL)+(fund_class_id IS NOT NULL)+(quota_series_id IS NOT NULL)=1),
 CHECK((value_type='text' AND value_text IS NOT NULL AND value_numeric IS NULL AND value_date IS NULL AND value_boolean IS NULL)
  OR (value_type='numeric' AND value_text IS NULL AND value_numeric IS NOT NULL AND value_date IS NULL AND value_boolean IS NULL)
  OR (value_type='date' AND value_text IS NULL AND value_numeric IS NULL AND value_date IS NOT NULL AND value_boolean IS NULL)
  OR (value_type='boolean' AND value_text IS NULL AND value_numeric IS NULL AND value_date IS NULL AND value_boolean IS NOT NULL))
);

-- Mesmo assunto, campo e competencia com valores diferentes (reapresentacao na
-- mesma fonte ou divergencia entre fontes). Nenhuma observacao e sobrescrita.
CREATE TABLE IF NOT EXISTS data_conflicts (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 field_name TEXT NOT NULL,
 reference_date TEXT NOT NULL CHECK(date(reference_date) IS NOT NULL AND date(reference_date)=reference_date),
 observation_a_id INTEGER NOT NULL REFERENCES observations(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 observation_b_id INTEGER NOT NULL REFERENCES observations(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','ignored')),
 resolution_note TEXT,
 resolved_at TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(observation_a_id<observation_b_id),
 CHECK(status<>'resolved' OR (resolved_at IS NOT NULL AND resolution_note IS NOT NULL)),
 UNIQUE(observation_a_id, observation_b_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 actor TEXT NOT NULL CHECK(length(trim(actor))>0),
 action TEXT NOT NULL CHECK(length(trim(action))>0),
 entity_type TEXT NOT NULL CHECK(length(trim(entity_type))>0),
 entity_id INTEGER NOT NULL,
 before_data TEXT, after_data TEXT, reason TEXT,
 occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_raw_records_manifest ON raw_records(source_id, COALESCE(parent_raw_record_id,0), file_name, sha256);
CREATE UNIQUE INDEX IF NOT EXISTS ux_quota_series_class_label ON quota_series(fund_class_id, series_label_key) WHERE fund_class_id IS NOT NULL AND series_label_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_quota_series_fund_label ON quota_series(fund_id, series_label_key) WHERE fund_id IS NOT NULL AND series_label_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_quota_series_subclass ON quota_series(cvm_subclass_id) WHERE cvm_subclass_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_collection_runs_source ON collection_runs(source_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_records_run ON raw_records(collection_run_id);
CREATE INDEX IF NOT EXISTS idx_raw_records_parent ON raw_records(parent_raw_record_id);
CREATE INDEX IF NOT EXISTS idx_fund_classes_fund ON fund_classes(fund_id);
CREATE INDEX IF NOT EXISTS idx_quota_series_class ON quota_series(fund_class_id);
CREATE INDEX IF NOT EXISTS idx_quota_series_fund ON quota_series(fund_id);
CREATE INDEX IF NOT EXISTS idx_observations_fund ON observations(fund_id, field_name, reference_date DESC) WHERE fund_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_observations_class ON observations(fund_class_id, field_name, reference_date DESC) WHERE fund_class_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_observations_series ON observations(quota_series_id, field_name, reference_date DESC) WHERE quota_series_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_observations_raw_record ON observations(raw_record_id);
CREATE INDEX IF NOT EXISTS idx_observations_run ON observations(collection_run_id);
CREATE INDEX IF NOT EXISTS idx_conflicts_status ON data_conflicts(status);
CREATE INDEX IF NOT EXISTS idx_conflicts_b ON data_conflicts(observation_b_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);

CREATE TRIGGER IF NOT EXISTS trg_observations_no_update BEFORE UPDATE ON observations
BEGIN SELECT RAISE(ABORT, 'observations e imutavel: registre uma nova observacao'); END;

CREATE TRIGGER IF NOT EXISTS trg_observations_no_delete BEFORE DELETE ON observations
BEGIN SELECT RAISE(ABORT, 'observations e imutavel: o historico nao e apagado'); END;

-- Reforco no banco da guarda de dados pessoais (src/fundos/personal_data.py).
-- Recusa os campos de pessoa natural e de contato e, em coluna de
-- identificacao (cpf ou cnpj no nome), qualquer valor fora do formato de CNPJ
-- de 14 caracteres (12 em [0-9A-Z] e 2 digitos). 11 digitos e CPF com mascara
-- (14 caracteres com '.' e '-') caem aqui pelo formato; o digito verificador e
-- conferido no Python.
CREATE TRIGGER IF NOT EXISTS trg_observations_personal_data BEFORE INSERT ON observations
WHEN lower(substr(NEW.field_name, instr(NEW.field_name,'.')+1)) IN
     ('diretor','email_administrador','site','servico_atendimento_cotista','entidade_administradora')
  OR ((lower(substr(NEW.field_name, instr(NEW.field_name,'.')+1)) GLOB '*cpf*'
       OR lower(substr(NEW.field_name, instr(NEW.field_name,'.')+1)) GLOB '*cnpj*')
      AND NOT (NEW.value_type='text' AND length(NEW.value_text)=14
               AND substr(NEW.value_text,1,12) NOT GLOB '*[^0-9A-Z]*'
               AND substr(NEW.value_text,13,2) NOT GLOB '*[^0-9]*'))
BEGIN SELECT RAISE(ABORT, 'campo de dado pessoal ou valor fora do formato de CNPJ em campo de identificacao'); END;

-- Valor atual: prioridade da fonte, depois competencia mais recente, depois
-- coleta mais recente. So fontes ativas. O historico continua inteiro em
-- observations. A escala de prioridade e provisoria ate o ADR de prioridade
-- das fontes (etapa futura do plano de Fundos).
CREATE VIEW IF NOT EXISTS current_observations AS
SELECT id, fund_id, fund_class_id, quota_series_id, field_name, value_type,
       value_text, value_numeric, value_date, value_boolean, unit,
       reference_date, collected_at, confidence,
       source_id, source_code, source_priority, collection_run_id, raw_record_id
FROM (
  SELECT o.*, s.code AS source_code, s.priority AS source_priority,
         ROW_NUMBER() OVER (
           PARTITION BY o.fund_id, o.fund_class_id, o.quota_series_id, o.field_name
           ORDER BY s.priority DESC, o.reference_date DESC, o.collected_at DESC, o.id DESC
         ) AS rn
  FROM observations o
  JOIN sources s ON s.id = o.source_id
  WHERE s.active = 1
)
WHERE rn = 1;

-- So estas duas fontes. ANBIMA e Fundos.NET nao sao semeadas: entram depois do
-- ADR de prioridade das fontes (etapa futura do plano de Fundos).
INSERT OR IGNORE INTO sources(code,name,source_type,priority,active) VALUES
('CVM_DADOS_ABERTOS','CVM - Portal de Dados Abertos','open_data',200,1),
('MANUAL','Entrada manual validada','manual',1000,1);

INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(1,'initial_schema');
