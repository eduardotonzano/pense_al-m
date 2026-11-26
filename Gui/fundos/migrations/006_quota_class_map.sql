-- Migration 006 do modulo de Fundos: mapa das series de FIDC (quota_class_map).
-- Decisao 8 de Fundos: o rotulo da serie (TAB_X_CLASSE_SERIE) segue um molde,
-- e o mapa e curado e revisado por uma pessoa a partir desse molde. A regra e
-- pelo inicio do rotulo NORMALIZADO, a mesma forma de
-- quota_series.series_label_key (sem acento, minusculo, sem '|' e com os
-- espacos colapsados); o rotulo original continua intocado nas observacoes.
-- Entre as regras que casam, vence a mais especifica (o padrao mais longo).
-- match_type 'inicio': a chave e igual ao padrao ou comeca com o padrao
-- seguido de espaco; 'igual': so a chave igual ao padrao.
-- level 'senior' tem subtype 'nao_se_aplica'; level 'nao_senior' tem subtype
-- 'mezanino', 'subordinada' ou 'ausente' (o rotulo nao diz o subtipo; nada e
-- estimado). Rotulo sem regra fica "ausente (rotulo nao mapeado)".
-- Revisao: so uma pessoa muda review_status, de 'proposto' para 'revisado' ou
-- 'rejeitado' (ou de 'revisado' para 'rejeitado'), com reviewer no formato
-- 'papel:<id>' (um papel, nunca o nome de uma pessoa), data e nota; cada
-- revisao tambem vai para o audit_log. Padrao, casamento, nivel, subtipo e o
-- inicio da vigencia sao imutaveis; o fim da vigencia so e preenchido uma
-- vez; nenhuma regra e apagada.
-- Numero: 006. A 005 esta reservada para a prioridade de fontes (ADR-010) e
-- e independente desta; o runner aplica toda migration nao registrada, entao
-- a 006 entra sem a 005, e a 005 entra depois.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS quota_class_map (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 pattern TEXT NOT NULL CHECK(length(pattern)>0 AND pattern=trim(pattern) AND pattern=lower(pattern)
   AND pattern NOT GLOB '*|*' AND pattern NOT GLOB '*  *'),
 match_type TEXT NOT NULL CHECK(match_type IN ('inicio','igual')),
 level TEXT NOT NULL CHECK(level IN ('senior','nao_senior')),
 subtype TEXT NOT NULL CHECK(subtype IN ('nao_se_aplica','mezanino','subordinada','ausente')),
 origin_note TEXT CHECK(origin_note IS NULL OR length(trim(origin_note))>0),
 review_status TEXT NOT NULL DEFAULT 'proposto' CHECK(review_status IN ('proposto','revisado','rejeitado')),
 reviewer TEXT CHECK(reviewer IS NULL OR (reviewer GLOB 'papel:[a-z]*'
   AND reviewer NOT GLOB '*[^a-z0-9_:]*' AND length(reviewer) BETWEEN 9 AND 46)),
 reviewed_at TEXT CHECK(reviewed_at IS NULL OR datetime(reviewed_at) IS NOT NULL),
 review_note TEXT CHECK(review_note IS NULL OR length(trim(review_note))>0),
 valid_from TEXT CHECK(valid_from IS NULL OR (date(valid_from) IS NOT NULL AND date(valid_from)=valid_from)),
 valid_to TEXT CHECK(valid_to IS NULL OR (date(valid_to) IS NOT NULL AND date(valid_to)=valid_to)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK((level='senior') = (subtype='nao_se_aplica')),
 CHECK((review_status='proposto') = (reviewer IS NULL AND reviewed_at IS NULL)),
 CHECK(review_status='proposto' OR (reviewer IS NOT NULL AND reviewed_at IS NOT NULL)),
 CHECK(valid_from IS NULL OR valid_to IS NULL OR valid_from<=valid_to)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_quota_class_map_rule
 ON quota_class_map(pattern, match_type, COALESCE(valid_from, ''))
 WHERE review_status <> 'rejeitado';

CREATE TRIGGER IF NOT EXISTS trg_quota_class_map_no_delete BEFORE DELETE ON quota_class_map
BEGIN SELECT RAISE(ABORT, 'quota_class_map nao apaga regra: rejeite a regra e registre outra'); END;

CREATE TRIGGER IF NOT EXISTS trg_quota_class_map_rule_fixed BEFORE UPDATE ON quota_class_map
WHEN NEW.id IS NOT OLD.id OR NEW.pattern IS NOT OLD.pattern OR NEW.match_type IS NOT OLD.match_type
  OR NEW.level IS NOT OLD.level OR NEW.subtype IS NOT OLD.subtype OR NEW.origin_note IS NOT OLD.origin_note
  OR NEW.valid_from IS NOT OLD.valid_from OR NEW.created_at IS NOT OLD.created_at
BEGIN SELECT RAISE(ABORT, 'quota_class_map: padrao, casamento, nivel, subtipo, origem e inicio da vigencia sao imutaveis'); END;

CREATE TRIGGER IF NOT EXISTS trg_quota_class_map_review BEFORE UPDATE OF review_status, reviewer, reviewed_at, review_note ON quota_class_map
WHEN NOT ((OLD.review_status = 'proposto' AND NEW.review_status IN ('revisado','rejeitado'))
  OR (OLD.review_status = 'revisado' AND NEW.review_status = 'rejeitado'))
BEGIN SELECT RAISE(ABORT, 'quota_class_map: a revisao so vai de proposto para revisado ou rejeitado, ou de revisado para rejeitado'); END;

CREATE TRIGGER IF NOT EXISTS trg_quota_class_map_valid_to BEFORE UPDATE OF valid_to ON quota_class_map
WHEN NEW.valid_to IS NOT OLD.valid_to AND (OLD.valid_to IS NOT NULL OR NEW.valid_to IS NULL)
BEGIN SELECT RAISE(ABORT, 'quota_class_map: o fim da vigencia so e preenchido uma vez'); END;

-- As 4 regras iniciais, como 'proposto', com a vigencia aberta. Idempotente:
-- a regra que ja existe (mesmo padrao e casamento) nao entra de novo.
INSERT INTO quota_class_map (pattern, match_type, level, subtype, origin_note)
SELECT 'subclasse senior', 'inicio', 'senior', 'nao_se_aplica',
 'derivada da secao 10.6 de docs/fundos-descoberta.md (09/2026); proposta do modulo de Fundos'
WHERE NOT EXISTS (SELECT 1 FROM quota_class_map WHERE pattern = 'subclasse senior' AND match_type = 'inicio');

INSERT INTO quota_class_map (pattern, match_type, level, subtype, origin_note)
SELECT 'subclasse subordinada mezanino', 'inicio', 'nao_senior', 'mezanino',
 'derivada da secao 10.6 de docs/fundos-descoberta.md (09/2026); proposta do modulo de Fundos'
WHERE NOT EXISTS (SELECT 1 FROM quota_class_map WHERE pattern = 'subclasse subordinada mezanino' AND match_type = 'inicio');

INSERT INTO quota_class_map (pattern, match_type, level, subtype, origin_note)
SELECT 'subclasse subordinada subordinada', 'inicio', 'nao_senior', 'subordinada',
 'derivada da secao 10.6 de docs/fundos-descoberta.md (09/2026); proposta do modulo de Fundos'
WHERE NOT EXISTS (SELECT 1 FROM quota_class_map WHERE pattern = 'subclasse subordinada subordinada' AND match_type = 'inicio');

INSERT INTO quota_class_map (pattern, match_type, level, subtype, origin_note)
SELECT 'subclasse subordinada', 'igual', 'nao_senior', 'ausente',
 'derivada da secao 10.6 de docs/fundos-descoberta.md (09/2026), sem segunda palavra: o rotulo nao diz o subtipo; proposta do modulo de Fundos'
WHERE NOT EXISTS (SELECT 1 FROM quota_class_map WHERE pattern = 'subclasse subordinada' AND match_type = 'igual');

INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(6,'quota_class_map');
