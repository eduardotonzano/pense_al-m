-- Migration 003 do modulo de Fundos: percentual do cedente do informe de FIDC.
-- O informe traz, para os 9 maiores cedentes de cada grupo (TAB_I2A12, com
-- risco; TAB_I2B12, sem risco), o CPF ou CNPJ e o percentual. O cedente vira
-- uma linha de party_observations (papel 'cedente', campo = coluna do
-- identificador com a posicao, sem nome); o percentual fica aqui, 1:1 com
-- essa linha. Tabela nova, e nao coluna nova em party_observations, porque
-- scripts/apply_migration.py recusa DDL alterado em objeto existente e
-- --allow-existing-changes desligaria tambem a conferencia de contagens.
-- So CNPJ: o cedente com CPF nao tem linha, nem percentual (decisao 3 de
-- Fundos). O percentual e guardado como veio no arquivo, em decimal exato
-- (inclusive negativo ou acima de 100); a regra para usa-lo e do Gui.
-- O percentual entra no checksum da linha do cedente so quando existe, e so
-- entra logo depois dela (trg_party_observation_shares_with_parent): uma
-- linha gravada sem percentual nao ganha percentual depois. Percentual
-- diferente para a mesma chave (assunto, papel, campo, CNPJ, competencia)
-- gera linha nova e conflito aberto em party_conflicts.
-- Limitacao conhecida: cedente que muda de posicao ou some numa
-- reapresentacao da mesma competencia nao gera conflito (a posicao esta no
-- campo, e as linhas se somam), como na 002.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS party_observation_shares (
 party_observation_id INTEGER PRIMARY KEY REFERENCES party_observations(id) ON UPDATE CASCADE ON DELETE RESTRICT,
 share_field_name TEXT NOT NULL CHECK(share_field_name NOT GLOB '*[^A-Za-z0-9_.]*'
   AND share_field_name NOT GLOB '.*' AND share_field_name NOT GLOB '*.'
   AND length(share_field_name)-length(replace(share_field_name,'.',''))=1
   AND lower(substr(share_field_name, instr(share_field_name,'.')+1)) NOT IN
     ('diretor','email_administrador','site','servico_atendimento_cotista','entidade_administradora')
   AND lower(substr(share_field_name, instr(share_field_name,'.')+1)) NOT GLOB '*cpf*'
   AND lower(substr(share_field_name, instr(share_field_name,'.')+1)) NOT GLOB '*cnpj*'),
 share_value TEXT NOT NULL CHECK(share_value NOT GLOB '*[^0-9.-]*'
   AND share_value GLOB '*[0-9]' AND share_value NOT GLOB '?*-*' AND share_value NOT GLOB '.*'
   AND share_value NOT GLOB '-.*' AND length(share_value)-length(replace(share_value,'.',''))<=1)
);

-- Percentual so para o papel cedente.
CREATE TRIGGER IF NOT EXISTS trg_party_observation_shares_only_cedente BEFORE INSERT ON party_observation_shares
WHEN (SELECT role FROM party_observations WHERE id = NEW.party_observation_id) IS NOT 'cedente'
BEGIN SELECT RAISE(ABORT, 'party_observation_shares so aceita percentual de cedente'); END;

-- O percentual entra logo depois da linha do cedente, na mesma conexao e sem
-- outro INSERT no meio; o checksum da linha ja conta com ele. As duas
-- condicoes juntas: a linha-pai e a ultima inserida nesta conexao
-- (last_insert_rowid) e a mais nova de party_observations (MAX(id)).
-- Limite: o SQLite nao diz em que tabela foi o ultimo INSERT; um INSERT em
-- outra tabela com o mesmo numero de linha, feito por SQL direto logo
-- depois do cedente, passaria. O repositorio sempre grava o percentual
-- logo depois da linha do cedente.
CREATE TRIGGER IF NOT EXISTS trg_party_observation_shares_with_parent BEFORE INSERT ON party_observation_shares
WHEN NEW.party_observation_id IS NOT last_insert_rowid()
  OR NEW.party_observation_id IS NOT (SELECT MAX(id) FROM party_observations)
BEGIN SELECT RAISE(ABORT, 'party_observation_shares: o percentual entra junto com a linha do cedente'); END;

CREATE TRIGGER IF NOT EXISTS trg_party_observation_shares_no_update BEFORE UPDATE ON party_observation_shares
BEGIN SELECT RAISE(ABORT, 'party_observation_shares e imutavel: registre um novo papel'); END;

CREATE TRIGGER IF NOT EXISTS trg_party_observation_shares_no_delete BEFORE DELETE ON party_observation_shares
BEGIN SELECT RAISE(ABORT, 'party_observation_shares e imutavel: o historico nao e apagado'); END;

-- Cedente sem nome: so o CNPJ e, quando houver, o percentual.
CREATE TRIGGER IF NOT EXISTS trg_party_observations_cedente_without_name BEFORE INSERT ON party_observations
WHEN NEW.role = 'cedente' AND (NEW.party_name IS NOT NULL OR NEW.name_field_name IS NOT NULL)
BEGIN SELECT RAISE(ABORT, 'party_observations: cedente nao tem nome gravado'); END;

INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(3,'party_observation_shares');
