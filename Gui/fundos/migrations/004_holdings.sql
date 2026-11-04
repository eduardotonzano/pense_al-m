-- Migration 004 do modulo de Fundos: posicoes em cotas de fundos do CDA.
-- O CDA da CVM traz, por fundo ou classe detentor e por competencia
-- (DT_COMPTC), as aplicacoes em cotas de fundos: identificadas no cda_fie e
-- consolidadas no cda_fie_CONFID. Posicao e um valor no tempo, nao relacao
-- de identidade: nada aqui cria fundo, classe nem relacionamento.
-- holdings: posicao identificada. O detentor e uma classe ou um fundo (FK,
-- exatamente um, como em observations). O investido e so o CNPJ, sem FK: ele
-- pode ser FIF, FII, FIP ou estar fora do cadastro carregado. O nome
-- (EMISSOR) e so o texto de origem, nunca usado para casar, e so entra junto
-- de um CNPJ aceito (guardas a e b, decisao 3 de Fundos). Nenhuma coluna
-- guarda CPF; CPF_CNPJ_EMISSOR aparece so como valor de investee_field_name.
-- confidential_holdings: o consolidado confidencial da linha de cotas de
-- fundos, sem investido e sem quantidade; confidential_until e o
-- DT_CONFID_APLIC (confidencial ate essa data).
-- Valores em TEXT com o decimal exato, como value_numeric de observations.
-- Chave natural das identificadas (FU6.1, decisao 2, depois do dry-run do
-- CDA real): detentor, investido, competencia e line_order, a ordem da linha
-- (1, 2, 3...) entre as linhas da mesma (detentor, investido, competencia)
-- no arquivo. Cada linha de cotas e uma posicao propria, com os valores como
-- vieram; nenhuma soma e gravada. A chave nao e UNIQUE: mesma chave com
-- valor diferente numa reapresentacao gera linha nova e conflito aberto;
-- nenhuma linha e
-- sobrescrita. Limitacao: a posicao que some numa reapresentacao da mesma
-- competencia nao gera conflito (as linhas se somam), como na 002.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS holdings (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 fund_id INTEGER REFERENCES funds(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 fund_class_id INTEGER REFERENCES fund_classes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 investee_field_name TEXT NOT NULL CHECK(investee_field_name NOT GLOB '*[^A-Za-z0-9_.]*'
   AND investee_field_name NOT GLOB '.*' AND investee_field_name NOT GLOB '*.'
   AND length(investee_field_name)-length(replace(investee_field_name,'.',''))=1
   AND lower(substr(investee_field_name, instr(investee_field_name,'.')+1)) GLOB '*cnpj*'),
 investee_cnpj TEXT NOT NULL CHECK(length(investee_cnpj)=14
   AND substr(investee_cnpj,1,12) NOT GLOB '*[^0-9A-Z]*'
   AND substr(investee_cnpj,13,2) NOT GLOB '*[^0-9]*'),
 name_field_name TEXT CHECK(name_field_name IS NULL OR (name_field_name NOT GLOB '*[^A-Za-z0-9_.]*'
   AND name_field_name NOT GLOB '.*' AND name_field_name NOT GLOB '*.'
   AND length(name_field_name)-length(replace(name_field_name,'.',''))=1
   AND lower(substr(name_field_name, instr(name_field_name,'.')+1)) NOT IN
     ('diretor','email_administrador','site','servico_atendimento_cotista','entidade_administradora')
   AND lower(substr(name_field_name, instr(name_field_name,'.')+1)) NOT GLOB '*cpf*'
   AND lower(substr(name_field_name, instr(name_field_name,'.')+1)) NOT GLOB '*cnpj*')),
 investee_name TEXT CHECK(investee_name IS NULL OR length(trim(investee_name))>0),
 quantity_field_name TEXT CHECK(quantity_field_name IS NULL OR (quantity_field_name NOT GLOB '*[^A-Za-z0-9_.]*'
   AND quantity_field_name NOT GLOB '.*' AND quantity_field_name NOT GLOB '*.'
   AND length(quantity_field_name)-length(replace(quantity_field_name,'.',''))=1
   AND lower(substr(quantity_field_name, instr(quantity_field_name,'.')+1)) NOT GLOB '*cpf*'
   AND lower(substr(quantity_field_name, instr(quantity_field_name,'.')+1)) NOT GLOB '*cnpj*')),
 quantity TEXT CHECK(quantity IS NULL OR (quantity NOT GLOB '*[^0-9.-]*'
   AND quantity GLOB '*[0-9]' AND quantity NOT GLOB '?*-*' AND quantity NOT GLOB '.*'
   AND quantity NOT GLOB '-.*' AND length(quantity)-length(replace(quantity,'.',''))<=1)),
 value_field_name TEXT NOT NULL CHECK(value_field_name NOT GLOB '*[^A-Za-z0-9_.]*'
   AND value_field_name NOT GLOB '.*' AND value_field_name NOT GLOB '*.'
   AND length(value_field_name)-length(replace(value_field_name,'.',''))=1
   AND lower(substr(value_field_name, instr(value_field_name,'.')+1)) NOT GLOB '*cpf*'
   AND lower(substr(value_field_name, instr(value_field_name,'.')+1)) NOT GLOB '*cnpj*'),
 market_value TEXT NOT NULL CHECK(market_value NOT GLOB '*[^0-9.-]*'
   AND market_value GLOB '*[0-9]' AND market_value NOT GLOB '?*-*' AND market_value NOT GLOB '.*'
   AND market_value NOT GLOB '-.*' AND length(market_value)-length(replace(market_value,'.',''))<=1),
 source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 collection_run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 raw_record_id INTEGER NOT NULL REFERENCES raw_records(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 reference_date TEXT NOT NULL CHECK(date(reference_date) IS NOT NULL AND date(reference_date)=reference_date),
 line_order INTEGER NOT NULL CHECK(typeof(line_order)='integer' AND line_order>=1),
 collected_at TEXT NOT NULL CHECK(datetime(collected_at) IS NOT NULL),
 checksum TEXT NOT NULL UNIQUE CHECK(length(checksum)=64 AND checksum NOT GLOB '*[^0-9a-f]*'),
 CHECK((fund_id IS NOT NULL)+(fund_class_id IS NOT NULL)=1),
 CHECK((name_field_name IS NULL)=(investee_name IS NULL)),
 CHECK((quantity_field_name IS NULL)=(quantity IS NULL))
);

CREATE TABLE IF NOT EXISTS confidential_holdings (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 fund_id INTEGER REFERENCES funds(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 fund_class_id INTEGER REFERENCES fund_classes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 value_field_name TEXT NOT NULL CHECK(value_field_name NOT GLOB '*[^A-Za-z0-9_.]*'
   AND value_field_name NOT GLOB '.*' AND value_field_name NOT GLOB '*.'
   AND length(value_field_name)-length(replace(value_field_name,'.',''))=1
   AND lower(substr(value_field_name, instr(value_field_name,'.')+1)) NOT GLOB '*cpf*'
   AND lower(substr(value_field_name, instr(value_field_name,'.')+1)) NOT GLOB '*cnpj*'),
 market_value TEXT NOT NULL CHECK(market_value NOT GLOB '*[^0-9.-]*'
   AND market_value GLOB '*[0-9]' AND market_value NOT GLOB '?*-*' AND market_value NOT GLOB '.*'
   AND market_value NOT GLOB '-.*' AND length(market_value)-length(replace(market_value,'.',''))<=1),
 confidential_until_field_name TEXT NOT NULL CHECK(confidential_until_field_name NOT GLOB '*[^A-Za-z0-9_.]*'
   AND confidential_until_field_name NOT GLOB '.*' AND confidential_until_field_name NOT GLOB '*.'
   AND length(confidential_until_field_name)-length(replace(confidential_until_field_name,'.',''))=1
   AND lower(substr(confidential_until_field_name, instr(confidential_until_field_name,'.')+1)) NOT GLOB '*cpf*'
   AND lower(substr(confidential_until_field_name, instr(confidential_until_field_name,'.')+1)) NOT GLOB '*cnpj*'),
 confidential_until TEXT NOT NULL CHECK(date(confidential_until) IS NOT NULL AND date(confidential_until)=confidential_until),
 source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 collection_run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 raw_record_id INTEGER NOT NULL REFERENCES raw_records(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 reference_date TEXT NOT NULL CHECK(date(reference_date) IS NOT NULL AND date(reference_date)=reference_date),
 collected_at TEXT NOT NULL CHECK(datetime(collected_at) IS NOT NULL),
 checksum TEXT NOT NULL UNIQUE CHECK(length(checksum)=64 AND checksum NOT GLOB '*[^0-9a-f]*'),
 CHECK((fund_id IS NOT NULL)+(fund_class_id IS NOT NULL)=1)
);

-- Mesma chave com valores diferentes. Espelham party_conflicts; sem
-- field_name, porque a linha de posicao tem mais de um valor.
CREATE TABLE IF NOT EXISTS holding_conflicts (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 reference_date TEXT NOT NULL CHECK(date(reference_date) IS NOT NULL AND date(reference_date)=reference_date),
 holding_a_id INTEGER NOT NULL REFERENCES holdings(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 holding_b_id INTEGER NOT NULL REFERENCES holdings(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','ignored')),
 resolution_note TEXT,
 resolved_at TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(holding_a_id<holding_b_id),
 CHECK(status<>'resolved' OR (resolved_at IS NOT NULL AND resolution_note IS NOT NULL)),
 UNIQUE(holding_a_id, holding_b_id)
);

CREATE TABLE IF NOT EXISTS confidential_holding_conflicts (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 reference_date TEXT NOT NULL CHECK(date(reference_date) IS NOT NULL AND date(reference_date)=reference_date),
 confidential_holding_a_id INTEGER NOT NULL REFERENCES confidential_holdings(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 confidential_holding_b_id INTEGER NOT NULL REFERENCES confidential_holdings(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','ignored')),
 resolution_note TEXT,
 resolved_at TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(confidential_holding_a_id<confidential_holding_b_id),
 CHECK(status<>'resolved' OR (resolved_at IS NOT NULL AND resolution_note IS NOT NULL)),
 UNIQUE(confidential_holding_a_id, confidential_holding_b_id)
);

CREATE INDEX IF NOT EXISTS idx_holdings_fund ON holdings(fund_id, investee_cnpj, reference_date, line_order) WHERE fund_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_holdings_class ON holdings(fund_class_id, investee_cnpj, reference_date, line_order) WHERE fund_class_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_holdings_investee ON holdings(investee_cnpj, reference_date);
CREATE INDEX IF NOT EXISTS idx_holdings_raw_record ON holdings(raw_record_id);
CREATE INDEX IF NOT EXISTS idx_holdings_run ON holdings(collection_run_id);
CREATE INDEX IF NOT EXISTS idx_confidential_holdings_fund ON confidential_holdings(fund_id, reference_date) WHERE fund_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_confidential_holdings_class ON confidential_holdings(fund_class_id, reference_date) WHERE fund_class_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_confidential_holdings_raw_record ON confidential_holdings(raw_record_id);
CREATE INDEX IF NOT EXISTS idx_confidential_holdings_run ON confidential_holdings(collection_run_id);
CREATE INDEX IF NOT EXISTS idx_holding_conflicts_status ON holding_conflicts(status);
CREATE INDEX IF NOT EXISTS idx_holding_conflicts_b ON holding_conflicts(holding_b_id);
CREATE INDEX IF NOT EXISTS idx_confidential_holding_conflicts_status ON confidential_holding_conflicts(status);
CREATE INDEX IF NOT EXISTS idx_confidential_holding_conflicts_b ON confidential_holding_conflicts(confidential_holding_b_id);

CREATE TRIGGER IF NOT EXISTS trg_holdings_no_update BEFORE UPDATE ON holdings
BEGIN SELECT RAISE(ABORT, 'holdings e imutavel: registre uma nova posicao'); END;

CREATE TRIGGER IF NOT EXISTS trg_holdings_no_delete BEFORE DELETE ON holdings
BEGIN SELECT RAISE(ABORT, 'holdings e imutavel: o historico nao e apagado'); END;

CREATE TRIGGER IF NOT EXISTS trg_confidential_holdings_no_update BEFORE UPDATE ON confidential_holdings
BEGIN SELECT RAISE(ABORT, 'confidential_holdings e imutavel: registre uma nova posicao'); END;

CREATE TRIGGER IF NOT EXISTS trg_confidential_holdings_no_delete BEFORE DELETE ON confidential_holdings
BEGIN SELECT RAISE(ABORT, 'confidential_holdings e imutavel: o historico nao e apagado'); END;

INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(4,'holdings');
