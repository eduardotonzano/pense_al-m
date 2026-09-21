"""Migracao inicial da Shared Entity Layer."""

VERSION = 1
NAME = "initial_shared_entity_schema"

STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS data_provenance (
        provenance_id TEXT PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_name TEXT NOT NULL,
        source_reference TEXT,
        collected_at TEXT NOT NULL,
        reference_date TEXT,
        validation_status TEXT NOT NULL,
        confidence_score INTEGER NOT NULL
            CHECK (
                confidence_score >= 0
                AND confidence_score <= 100
            )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entities (
        entity_id TEXT PRIMARY KEY,
        legal_name TEXT NOT NULL,
        trade_name TEXT,
        entity_type TEXT NOT NULL,
        status TEXT NOT NULL,
        country_code TEXT NOT NULL
            CHECK (length(country_code) = 2),
        sector TEXT,
        subsector TEXT,
        website TEXT,
        provenance_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (provenance_id)
            REFERENCES data_provenance(provenance_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entity_identifiers (
        identifier_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_id TEXT NOT NULL,
        identifier_type TEXT NOT NULL,
        value TEXT NOT NULL,
        canonical_key TEXT NOT NULL UNIQUE,
        provenance_id TEXT NOT NULL,
        is_primary INTEGER NOT NULL
            CHECK (is_primary IN (0, 1)),
        FOREIGN KEY (entity_id)
            REFERENCES entities(entity_id)
            ON DELETE CASCADE,
        FOREIGN KEY (provenance_id)
            REFERENCES data_provenance(provenance_id),
        UNIQUE (
            entity_id,
            identifier_type,
            value
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entity_relationships (
        relationship_id TEXT PRIMARY KEY,
        source_entity_id TEXT NOT NULL,
        target_entity_id TEXT NOT NULL,
        relationship_type TEXT NOT NULL,
        canonical_key TEXT NOT NULL UNIQUE,
        provenance_id TEXT NOT NULL,
        status TEXT NOT NULL,
        valid_from TEXT,
        valid_to TEXT,
        confidence_score INTEGER NOT NULL
            CHECK (
                confidence_score >= 0
                AND confidence_score <= 100
            ),
        notes TEXT,
        created_at TEXT NOT NULL,
        CHECK (source_entity_id <> target_entity_id),
        CHECK (
            valid_from IS NULL
            OR valid_to IS NULL
            OR valid_to >= valid_from
        ),
        FOREIGN KEY (source_entity_id)
            REFERENCES entities(entity_id),
        FOREIGN KEY (target_entity_id)
            REFERENCES entities(entity_id),
        FOREIGN KEY (provenance_id)
            REFERENCES data_provenance(provenance_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS
        idx_entities_type
    ON entities(entity_type)
    """,
    """
    CREATE INDEX IF NOT EXISTS
        idx_entities_legal_name
    ON entities(legal_name)
    """,
    """
    CREATE INDEX IF NOT EXISTS
        idx_identifiers_entity
    ON entity_identifiers(entity_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS
        idx_relationships_source
    ON entity_relationships(source_entity_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS
        idx_relationships_target
    ON entity_relationships(target_entity_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS
        idx_relationships_type
    ON entity_relationships(relationship_type)
    """,
)
