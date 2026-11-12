-- Migration 002 do modulo de Fundos: papeis com varios valores por assunto.
-- O cadastro da CVM tem uma linha por gestor (e repete a classe por
-- custodiante ou controlador). Em observations, que guarda um valor por
-- assunto, campo e competencia, isso abriria conflito falso. Cada papel vira
-- uma linha aqui: assunto (fundo ou classe), papel, CNPJ da parte e, quando
-- houver, o nome, com a mesma proveniencia de observations.
-- So CNPJ: nenhuma coluna guarda CPF, e o nome so entra junto de um CNPJ
-- valido (docs/decisoes-em-aberto.md, decisao 3 de Fundos). 'cedente' fica
-- no CHECK de role para nao exigir reconstruir a tabela, mas os cedentes do
-- informe (FU4.3) ainda precisam de migration propria: esta tabela nao
-- guarda o percentual do cedente.
-- Chave: assunto + papel + field_name + party_cnpj + competencia; o valor e
-- o nome. Nome diferente para a mesma chave gera linha nova e conflito
-- aberto em party_conflicts; nenhuma linha e sobrescrita. Limitacao: uma
-- parte que some numa reapresentacao da mesma competencia nao gera
-- conflito (as linhas se somam).
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS party_observations (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 fund_id INTEGER REFERENCES funds(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 fund_class_id INTEGER REFERENCES fund_classes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 role TEXT NOT NULL CHECK(role IN ('gestor','administrador','custodiante','controlador','auditor','cedente')),
 field_name TEXT NOT NULL CHECK(field_name NOT GLOB '*[^A-Za-z0-9_.]*' AND field_name NOT GLOB '.*'
   AND field_name NOT GLOB '*.' AND length(field_name)-length(replace(field_name,'.',''))=1
   AND lower(substr(field_name, instr(field_name,'.')+1)) GLOB '*cnpj*'),
 party_cnpj TEXT NOT NULL CHECK(length(party_cnpj)=14
   AND substr(party_cnpj,1,12) NOT GLOB '*[^0-9A-Z]*'
   AND substr(party_cnpj,13,2) NOT GLOB '*[^0-9]*'),
 name_field_name TEXT CHECK(name_field_name IS NULL OR (name_field_name NOT GLOB '*[^A-Za-z0-9_.]*'
   AND name_field_name NOT GLOB '.*' AND name_field_name NOT GLOB '*.'
   AND length(name_field_name)-length(replace(name_field_name,'.',''))=1
   AND lower(substr(name_field_name, instr(name_field_name,'.')+1)) NOT IN
     ('diretor','email_administrador','site','servico_atendimento_cotista','entidade_administradora')
   AND lower(substr(name_field_name, instr(name_field_name,'.')+1)) NOT GLOB '*cpf*'
   AND lower(substr(name_field_name, instr(name_field_name,'.')+1)) NOT GLOB '*cnpj*')),
 party_name TEXT CHECK(party_name IS NULL OR length(trim(party_name))>0),
 source_id INTEGER NOT NULL REFERENCES sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 collection_run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 raw_record_id INTEGER NOT NULL REFERENCES raw_records(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 reference_date TEXT NOT NULL CHECK(date(reference_date) IS NOT NULL AND date(reference_date)=reference_date),
 collected_at TEXT NOT NULL CHECK(datetime(collected_at) IS NOT NULL),
 checksum TEXT NOT NULL UNIQUE CHECK(length(checksum)=64 AND checksum NOT GLOB '*[^0-9a-f]*'),
 CHECK((fund_id IS NOT NULL)+(fund_class_id IS NOT NULL)=1),
 CHECK((name_field_name IS NULL)=(party_name IS NULL))
);

-- Mesmo assunto, papel, campo, CNPJ e competencia com nomes diferentes.
-- Espelha data_conflicts, que so aponta para observations.
CREATE TABLE IF NOT EXISTS party_conflicts (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 field_name TEXT NOT NULL,
 reference_date TEXT NOT NULL CHECK(date(reference_date) IS NOT NULL AND date(reference_date)=reference_date),
 party_observation_a_id INTEGER NOT NULL REFERENCES party_observations(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 party_observation_b_id INTEGER NOT NULL REFERENCES party_observations(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','ignored')),
 resolution_note TEXT,
 resolved_at TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(party_observation_a_id<party_observation_b_id),
 CHECK(status<>'resolved' OR (resolved_at IS NOT NULL AND resolution_note IS NOT NULL)),
 UNIQUE(party_observation_a_id, party_observation_b_id)
);

CREATE INDEX IF NOT EXISTS idx_party_observations_fund ON party_observations(fund_id, role, reference_date DESC) WHERE fund_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_party_observations_class ON party_observations(fund_class_id, role, reference_date DESC) WHERE fund_class_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_party_observations_party ON party_observations(party_cnpj, role);
CREATE INDEX IF NOT EXISTS idx_party_observations_raw_record ON party_observations(raw_record_id);
CREATE INDEX IF NOT EXISTS idx_party_observations_run ON party_observations(collection_run_id);
CREATE INDEX IF NOT EXISTS idx_party_conflicts_status ON party_conflicts(status);
CREATE INDEX IF NOT EXISTS idx_party_conflicts_b ON party_conflicts(party_observation_b_id);

CREATE TRIGGER IF NOT EXISTS trg_party_observations_no_update BEFORE UPDATE ON party_observations
BEGIN SELECT RAISE(ABORT, 'party_observations e imutavel: registre um novo papel'); END;

CREATE TRIGGER IF NOT EXISTS trg_party_observations_no_delete BEFORE DELETE ON party_observations
BEGIN SELECT RAISE(ABORT, 'party_observations e imutavel: o historico nao e apagado'); END;

INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(2,'party_observations');
