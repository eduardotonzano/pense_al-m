-- Migration 001 do modulo de Titulos bancarios (CDB, LCI, LCA, LF, DPGE).
-- Base do banco e do IFData (indicadores prudenciais, com o indice de Basileia
-- como principal). Plano aprovado pelo Enrico em 27/11/2026; ADR-013.
--
-- Mesmo esqueleto de proveniencia de Fundos (coletas, arquivo bruto com
-- SHA-256, observacoes imutaveis, conflitos), com estas diferencas:
--  * a identidade NAO mora aqui: subjects so guarda o entity_id da camada
--    compartilhada (ADR-001, regra 1). Linha de arquivo sem entidade conhecida
--    vai para unmatched_issuers e nunca cria sujeito (regra 6);
--  * sources tem a camada da regra 3 (BACEN > CVM > ANBIMA > especializadas >
--    institucionais) e o banco recusa prioridade fora da faixa da camada
--    (ADR-010, opcao A4, como reforco do teste de escala);
--  * observations exige o campo no field_catalog (rotulo, descricao e unidade
--    da fonte) e recusa competencia posterior a data da coleta (ADR-010,
--    condicao b.1);
--  * a view current_observations usa a ordem do ADR-010 b): competencia mais
--    recente primeiro, depois a prioridade da fonte.
-- As posicoes do CDA (migration 002) e as series do SGS e ofertas (003) nao
-- entram aqui. Nenhuma coluna guarda CPF ou dado de pessoa natural.
-- Todo CNPJ tem 14 caracteres sem mascara: 12 em [0-9A-Z] e 2 digitos
-- verificadores numericos (ADR-011). O digito verificador e conferido no
-- Python, nao no banco.

CREATE TABLE IF NOT EXISTS schema_migrations (
 version INTEGER PRIMARY KEY,
 name TEXT NOT NULL,
 applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sources (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 code TEXT NOT NULL UNIQUE CHECK(length(code)>0 AND code NOT GLOB '*[^A-Z0-9_]*'),
 name TEXT NOT NULL CHECK(length(trim(name))>0),
 source_type TEXT NOT NULL CHECK(source_type IN ('open_data','scraper','api','manual','document')),
 layer TEXT NOT NULL CHECK(layer IN ('bacen','cvm','anbima','specialized','institutional','manual')),
 priority INTEGER NOT NULL CHECK(priority>=100),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK((layer='bacen' AND priority BETWEEN 500 AND 599)
    OR (layer='cvm' AND priority BETWEEN 400 AND 499)
    OR (layer='anbima' AND priority BETWEEN 300 AND 399)
    OR (layer='specialized' AND priority BETWEEN 200 AND 299)
    OR (layer='institutional' AND priority BETWEEN 100 AND 199)
    OR (layer='manual' AND priority=1000))
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

-- Manifesto do arquivo ou da resposta: nome, tamanho, SHA-256 e linhas. Nunca
-- o conteudo. O ZIP e uma linha; cada CSV lido de dentro dele e uma linha
-- filha (parent_raw_record_id). A CVM republica arquivos antigos, entao o
-- hash e o que distingue a versao lida.
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

-- Sujeito das observacoes: so a chave de juncao com a camada compartilhada.
-- institution: CNPJ completo de 14 caracteres (a raiz de 8 do CodInst do
--   IFData nao e CNPJ e nunca cria sujeito; so resolve para um sujeito que ja
--   exista, e so se houver exatamente um com aquela raiz).
-- conglomerate: codigo BACEN 'C' + 7 digitos (ex.: C0080312).
-- A linha so e criada pelo adaptador, a partir de uma entidade que ja existe
-- na camada compartilhada (entity_id).
CREATE TABLE IF NOT EXISTS subjects (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 entity_id TEXT NOT NULL UNIQUE CHECK(length(trim(entity_id))>0 AND entity_id=trim(entity_id)),
 subject_kind TEXT NOT NULL CHECK(subject_kind IN ('institution','conglomerate')),
 subject_key TEXT NOT NULL,
 first_seen_run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(subject_kind, subject_key),
 CHECK((subject_kind='institution'
        AND length(subject_key)=14
        AND substr(subject_key,1,12) NOT GLOB '*[^0-9A-Z]*'
        AND substr(subject_key,13,2) NOT GLOB '*[^0-9]*')
    OR (subject_kind='conglomerate'
        AND length(subject_key)=8
        AND substr(subject_key,1,1)='C'
        AND substr(subject_key,2,7) NOT GLOB '*[^0-9]*'))
);

-- Catalogo de campos da fonte: rotulo e descricao como a fonte publica.
-- unit fica NULL ate ser conferida (unit_confirmed = 0): os rotulos do IFData
-- trazem letras como "(k)" que nao indicam a unidade.
CREATE TABLE IF NOT EXISTS field_catalog (
 source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 field_name TEXT NOT NULL CHECK(field_name NOT GLOB '*[^A-Za-z0-9_.]*' AND field_name NOT GLOB '.*'
   AND field_name NOT GLOB '*.' AND length(field_name)-length(replace(field_name,'.',''))=1),
 label TEXT NOT NULL CHECK(length(trim(label))>0),
 description TEXT,
 unit TEXT CHECK(unit IS NULL OR (length(unit)>0 AND unit=trim(unit))),
 unit_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(unit_confirmed IN (0,1)),
 first_seen_run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(source_id, field_name),
 CHECK(unit_confirmed=0 OR unit IS NOT NULL)
);

-- EAV: field_name = <relatorio>.<conta> do IFData (ex.: r5.c79664 = indice de
-- Basileia), sem renomear. Valor ausente nao tem linha. value_numeric e TEXT
-- com o decimal exato (NUMERIC guardaria so 15 digitos significativos).
-- reference_date e a competencia informada pela fonte (fim do trimestre no
-- IFData), nunca a data da coleta.
CREATE TABLE IF NOT EXISTS observations (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 subject_id INTEGER NOT NULL REFERENCES subjects(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 collection_run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 raw_record_id INTEGER NOT NULL REFERENCES raw_records(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 field_name TEXT NOT NULL,
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
 FOREIGN KEY(source_id, field_name) REFERENCES field_catalog(source_id, field_name) ON UPDATE CASCADE ON DELETE RESTRICT,
 CHECK((value_type='text' AND value_text IS NOT NULL AND value_numeric IS NULL AND value_date IS NULL AND value_boolean IS NULL)
  OR (value_type='numeric' AND value_text IS NULL AND value_numeric IS NOT NULL AND value_date IS NULL AND value_boolean IS NULL)
  OR (value_type='date' AND value_text IS NULL AND value_numeric IS NULL AND value_date IS NOT NULL AND value_boolean IS NULL)
  OR (value_type='boolean' AND value_text IS NULL AND value_numeric IS NULL AND value_date IS NULL AND value_boolean IS NOT NULL))
);

-- Fila de revisao: chave vista na fonte que nao casou com entidade da camada
-- compartilhada (ou casou com mais de uma). Nunca vira sujeito sozinha.
-- A linha e uma fila de trabalho, nao historico: status e as datas de
-- resolucao mudam. Resolver ou ignorar deve registrar audit_log.
CREATE TABLE IF NOT EXISTS unmatched_issuers (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 key_kind TEXT NOT NULL CHECK(key_kind IN ('cnpj','cnpj_root','conglomerate_code')),
 key_value TEXT NOT NULL,
 name_seen TEXT CHECK(name_seen IS NULL OR length(trim(name_seen))>0),
 reason TEXT NOT NULL CHECK(reason IN ('no_entity','ambiguous_root','name_only','identifier_conflict')),
 first_run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 last_run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','ignored')),
 resolution_note TEXT,
 resolved_at TEXT CHECK(resolved_at IS NULL OR datetime(resolved_at) IS NOT NULL),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(source_id, key_kind, key_value),
 CHECK((key_kind='cnpj'
        AND length(key_value)=14
        AND substr(key_value,1,12) NOT GLOB '*[^0-9A-Z]*'
        AND substr(key_value,13,2) NOT GLOB '*[^0-9]*')
    OR (key_kind='cnpj_root'
        AND length(key_value)=8
        AND key_value NOT GLOB '*[^0-9A-Z]*')
    OR (key_kind='conglomerate_code'
        AND length(key_value)=8
        AND substr(key_value,1,1)='C'
        AND substr(key_value,2,7) NOT GLOB '*[^0-9]*')),
 CHECK((status='open')=(resolved_at IS NULL))
);

-- Mesmo sujeito, campo e competencia com valores diferentes (reapresentacao na
-- mesma fonte ou divergencia entre fontes). Nenhuma observacao e sobrescrita.
CREATE TABLE IF NOT EXISTS data_conflicts (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 subject_id INTEGER NOT NULL REFERENCES subjects(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 field_name TEXT NOT NULL,
 reference_date TEXT NOT NULL CHECK(date(reference_date) IS NOT NULL AND date(reference_date)=reference_date),
 observation_a_id INTEGER NOT NULL REFERENCES observations(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 observation_b_id INTEGER NOT NULL REFERENCES observations(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','ignored')),
 resolution_note TEXT,
 resolved_at TEXT CHECK(resolved_at IS NULL OR datetime(resolved_at) IS NOT NULL),
 detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(observation_a_id<>observation_b_id),
 CHECK((status='open')=(resolved_at IS NULL)),
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
-- Uma raiz de CNPJ, um sujeito de instituicao: duas entidades com a mesma raiz
-- nao podem ser resolvidas sozinhas e vao para revisao (regra 6).
CREATE UNIQUE INDEX IF NOT EXISTS ux_subjects_institution_root ON subjects(substr(subject_key,1,8)) WHERE subject_kind='institution';
CREATE INDEX IF NOT EXISTS idx_collection_runs_source ON collection_runs(source_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_records_run ON raw_records(collection_run_id);
CREATE INDEX IF NOT EXISTS idx_raw_records_parent ON raw_records(parent_raw_record_id);
CREATE INDEX IF NOT EXISTS idx_subjects_first_run ON subjects(first_seen_run_id);
CREATE INDEX IF NOT EXISTS idx_observations_subject ON observations(subject_id, field_name, reference_date DESC);
CREATE INDEX IF NOT EXISTS idx_observations_field ON observations(source_id, field_name, reference_date DESC);
CREATE INDEX IF NOT EXISTS idx_observations_raw_record ON observations(raw_record_id);
CREATE INDEX IF NOT EXISTS idx_observations_run ON observations(collection_run_id);
CREATE INDEX IF NOT EXISTS idx_unmatched_status ON unmatched_issuers(status);
CREATE INDEX IF NOT EXISTS idx_conflicts_status ON data_conflicts(status);
CREATE INDEX IF NOT EXISTS idx_conflicts_b ON data_conflicts(observation_b_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);

CREATE TRIGGER IF NOT EXISTS trg_observations_no_update BEFORE UPDATE ON observations
BEGIN SELECT RAISE(ABORT, 'observations e imutavel: registre uma nova observacao'); END;

CREATE TRIGGER IF NOT EXISTS trg_observations_no_delete BEFORE DELETE ON observations
BEGIN SELECT RAISE(ABORT, 'observations e imutavel: o historico nao e apagado'); END;

-- Competencia posterior a data da coleta dominaria o valor atual (ADR-010,
-- condicao b.1): o banco recusa.
CREATE TRIGGER IF NOT EXISTS trg_observations_reference_not_future BEFORE INSERT ON observations
WHEN NEW.reference_date > date(NEW.collected_at)
BEGIN SELECT RAISE(ABORT, 'competencia posterior a data da coleta'); END;

-- Valor atual (ADR-010 b): a competencia mais recente vence; dentro da mesma
-- competencia, a prioridade da fonte; depois a coleta mais recente. So fontes
-- ativas. O historico continua inteiro em observations. A view nao le
-- data_conflicts: quem le mostra o valor atual junto das observacoes em
-- disputa.
CREATE VIEW IF NOT EXISTS current_observations AS
SELECT id, subject_id, field_name, value_type,
       value_text, value_numeric, value_date, value_boolean, unit,
       reference_date, collected_at, confidence,
       source_id, source_code, source_layer, source_priority,
       collection_run_id, raw_record_id
FROM (
  SELECT o.*, s.code AS source_code, s.layer AS source_layer, s.priority AS source_priority,
         ROW_NUMBER() OVER (
           PARTITION BY o.subject_id, o.field_name
           ORDER BY o.reference_date DESC, s.priority DESC, o.collected_at DESC, o.id DESC
         ) AS rn
  FROM observations o
  JOIN sources s ON s.id = o.source_id
  WHERE s.active = 1
)
WHERE rn = 1;

-- Fontes semeadas (ADR-013 D3, escala do ADR-010; o codigo da fonte e o nome
-- da camada, nunca o numero, e o que a integracao usa). ANBIMA, B3 e FGC nao
-- sao semeadas: entram em migration propria, depois de amostra e de
-- conferencia de acesso e termos de uso. Nenhuma fonte 'internal'.
INSERT OR IGNORE INTO sources(code,name,source_type,layer,priority,active) VALUES
('BACEN_IFDATA','BACEN - IFData (Olinda)','api','bacen',550,1),
('BACEN_SGS','BACEN - Sistema Gerenciador de Series (SGS)','api','bacen',540,1),
('CVM_OFERTAS','CVM - Ofertas de distribuicao','open_data','cvm',450,1),
('CVM_CDA','CVM - Composicao e diversificacao das aplicacoes (CDA)','open_data','cvm',440,1);

INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(1,'initial_schema');
