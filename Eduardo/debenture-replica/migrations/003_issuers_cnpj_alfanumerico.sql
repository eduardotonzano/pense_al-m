-- apply_migration: foreign_keys=off
-- apply_migration: recria=issuers
--
-- 003: o CHECK de issuers.cnpj passa a aceitar o CNPJ alfanumerico
-- (IN RFB 2.229/2024; docs/architecture/ADR-011-cnpj-alfanumerico.md):
-- 12 caracteres em [0-9A-Z] e 2 digitos. O novo CHECK e um superconjunto
-- do antigo (14 digitos), entao nenhuma linha existente pode ser recusada.
-- O DV nao e conferido no banco; isso fica com o codigo.
--
-- O SQLite nao altera CHECK: a tabela e recriada (cria, copia, apaga,
-- renomeia) com o mesmo esquema. debentures.issuer_id aponta para issuers
-- com ON DELETE RESTRICT, entao o DROP so passa com as chaves estrangeiras
-- desligadas antes do BEGIN. Aplicar SO pelo scripts/apply_migration.py,
-- que le as marcas acima; nunca com executescript nem com o sqlite3 de
-- linha de comando.
CREATE TABLE issuers_new (
 id INTEGER PRIMARY KEY AUTOINCREMENT, cnpj TEXT UNIQUE, legal_name TEXT NOT NULL CHECK(length(trim(legal_name))>0), trade_name TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(cnpj IS NULL OR (length(cnpj)=14 AND substr(cnpj,1,12) NOT GLOB '*[^0-9A-Z]*' AND substr(cnpj,13,2) NOT GLOB '*[^0-9]*'))
);
-- Preserva o AUTOINCREMENT: sem esta linha o seq cairia para o maior id e
-- os ids de emissoras apagadas voltariam a ser usados.
INSERT INTO sqlite_sequence(name, seq) SELECT 'issuers_new', seq FROM sqlite_sequence WHERE name = 'issuers';
INSERT INTO issuers_new (id, cnpj, legal_name, trade_name, created_at, updated_at)
SELECT id, cnpj, legal_name, trade_name, created_at, updated_at FROM issuers ORDER BY id;
DROP TABLE issuers;
ALTER TABLE issuers_new RENAME TO issuers;
CREATE INDEX idx_issuers_legal_name ON issuers(legal_name);
INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(3,'issuers_cnpj_alfanumerico');
