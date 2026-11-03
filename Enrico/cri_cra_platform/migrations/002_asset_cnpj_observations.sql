-- Fonte e data de cada CNPJ da securitizadora e do devedor (regra S-08).
-- Cada linha e uma observacao do Informe Mensal de CRI/CRA da CVM, ligada ao
-- ativo so por ISIN e CETIP: o CNPJ nunca vem do nome. O campo decision diz o
-- que o resolvedor fez com ela. applied: gravou em assets, que estava vazio.
-- confirmed: assets ja tinha o mesmo CNPJ. candidate: so registrada, assets
-- continua vazio. conflict: assets tem outro CNPJ e nada foi gravado.
CREATE TABLE IF NOT EXISTS asset_cnpj_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    field TEXT NOT NULL CHECK (field IN ('cnpj_securitizadora', 'cnpj_devedor')),
    cnpj TEXT NOT NULL CHECK (length(cnpj) = 14 AND cnpj NOT GLOB '*[^0-9]*'),
    decision TEXT NOT NULL CHECK (
        decision IN ('applied', 'confirmed', 'candidate', 'conflict')
    ),
    source_id TEXT NOT NULL CHECK (
        source_id IN ('cvm_inf_mensal_cri', 'cvm_inf_mensal_cra')
    ),
    matched_by TEXT NOT NULL CHECK (
        matched_by IN ('isin', 'codigo_cetip', 'isin+codigo_cetip')
    ),
    -- Data_Referencia dos informes que sustentam o CNPJ.
    reference_first TEXT NOT NULL CHECK (
        date(reference_first) IS NOT NULL AND date(reference_first) = reference_first
    ),
    reference_last TEXT NOT NULL CHECK (
        date(reference_last) IS NOT NULL AND date(reference_last) = reference_last
    ),
    filings INTEGER NOT NULL CHECK (filings >= 1),
    -- Data_Entrega do informe mais recente, quando a CVM a traz.
    delivered_last TEXT CHECK (
        delivered_last IS NULL OR (
            date(delivered_last) IS NOT NULL AND date(delivered_last) = delivered_last
        )
    ),
    -- Arquivos lidos: nome, URL oficial, SHA-256 do ZIP e linhas usadas.
    evidence_json TEXT NOT NULL,
    observed_at TEXT NOT NULL CHECK (datetime(observed_at) IS NOT NULL),
    run_id TEXT NOT NULL,
    -- Evidencia e decisao sem a hora da leitura: reler o mesmo arquivo nao
    -- grava de novo. applied e confirmed contam como a mesma decisao.
    checksum TEXT NOT NULL UNIQUE CHECK (
        length(checksum) = 64 AND checksum NOT GLOB '*[^0-9a-f]*'
    ),
    CHECK (reference_first <= reference_last),
    FOREIGN KEY(asset_id) REFERENCES assets(asset_id),
    FOREIGN KEY(run_id) REFERENCES executions(run_id)
);

CREATE INDEX IF NOT EXISTS ix_asset_cnpj_observations_asset_field
    ON asset_cnpj_observations(asset_id, field);

-- Fonte e data do CNPJ que esta hoje em assets: a ultima observacao applied ou
-- confirmed de cada ativo e campo, so se o CNPJ dela for o mesmo de assets.
-- CNPJ de assets sem linha aqui nao tem fonte registrada.
CREATE VIEW IF NOT EXISTS asset_cnpj_provenance AS
SELECT
    o.asset_id,
    o.field,
    o.cnpj,
    o.decision,
    o.source_id,
    o.matched_by,
    o.reference_first,
    o.reference_last,
    o.filings,
    o.delivered_last,
    o.observed_at,
    o.observation_id
FROM asset_cnpj_observations o
JOIN assets a ON a.asset_id = o.asset_id
WHERE o.decision IN ('applied', 'confirmed')
  AND o.observation_id = (
      SELECT MAX(p.observation_id)
      FROM asset_cnpj_observations p
      WHERE p.asset_id = o.asset_id
        AND p.field = o.field
        AND p.decision IN ('applied', 'confirmed')
  )
  AND o.cnpj = REPLACE(REPLACE(REPLACE(
      CASE o.field
          WHEN 'cnpj_securitizadora' THEN a.cnpj_securitizadora
          ELSE a.cnpj_devedor
      END,
      '.', ''), '/', ''), '-', '');
