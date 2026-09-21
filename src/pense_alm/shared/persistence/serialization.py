"""Serializacao dos objetos da Shared Entity Layer."""

from datetime import datetime
from hashlib import sha256
from json import dumps
from sqlite3 import Row
from typing import Any
from uuid import UUID

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityIdentifier,
    EntityRelationship,
    EntityStatus,
    EntityType,
    IdentifierType,
    RelationshipStatus,
    RelationshipType,
    SourceType,
    ValidationStatus,
)


def datetime_to_text(value: datetime | None) -> str | None:
    """Converte datetime em texto ISO 8601."""

    if value is None:
        return None

    return value.isoformat()


def datetime_from_text(value: str | None) -> datetime | None:
    """Reconstrói datetime a partir do formato ISO 8601."""

    if value is None:
        return None

    return datetime.fromisoformat(value)


def provenance_id(provenance: DataProvenance) -> str:
    """Cria uma identidade determinística para a proveniência."""

    payload = {
        "source_type": provenance.source_type.value,
        "source_name": provenance.source_name,
        "source_reference": provenance.source_reference,
        "collected_at": datetime_to_text(
            provenance.collected_at
        ),
        "reference_date": datetime_to_text(
            provenance.reference_date
        ),
        "validation_status": (
            provenance.validation_status.value
        ),
        "confidence_score": provenance.confidence_score,
    }

    serialized = dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )

    return sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def provenance_to_record(
    provenance: DataProvenance,
) -> dict[str, Any]:
    """Converte proveniência em registro persistente."""

    return {
        "provenance_id": provenance_id(provenance),
        "source_type": provenance.source_type.value,
        "source_name": provenance.source_name,
        "source_reference": provenance.source_reference,
        "collected_at": datetime_to_text(
            provenance.collected_at
        ),
        "reference_date": datetime_to_text(
            provenance.reference_date
        ),
        "validation_status": (
            provenance.validation_status.value
        ),
        "confidence_score": provenance.confidence_score,
    }


def provenance_from_row(row: Row) -> DataProvenance:
    """Reconstrói proveniência a partir de uma linha SQLite."""

    collected_at = datetime_from_text(
        row["collected_at"]
    )

    if collected_at is None:
        raise ValueError(
            "collected_at persistido nao pode ser nulo."
        )

    return DataProvenance(
        source_type=SourceType(row["source_type"]),
        source_name=row["source_name"],
        source_reference=row["source_reference"],
        collected_at=collected_at,
        reference_date=datetime_from_text(
            row["reference_date"]
        ),
        validation_status=ValidationStatus(
            row["validation_status"]
        ),
        confidence_score=int(
            row["confidence_score"]
        ),
    )


def entity_to_record(entity: Entity) -> dict[str, Any]:
    """Converte entidade em registro persistente."""

    return {
        "entity_id": str(entity.entity_id),
        "legal_name": entity.legal_name,
        "trade_name": entity.trade_name,
        "entity_type": entity.entity_type.value,
        "status": entity.status.value,
        "country_code": entity.country_code,
        "sector": entity.sector,
        "subsector": entity.subsector,
        "website": entity.website,
        "provenance_id": provenance_id(
            entity.provenance
        ),
        "created_at": datetime_to_text(
            entity.created_at
        ),
        "updated_at": datetime_to_text(
            entity.updated_at
        ),
    }


def identifier_to_record(
    entity_id: UUID,
    identifier: EntityIdentifier,
) -> dict[str, Any]:
    """Converte identificador em registro persistente."""

    return {
        "entity_id": str(entity_id),
        "identifier_type": (
            identifier.identifier_type.value
        ),
        "value": identifier.value,
        "canonical_key": identifier.canonical_key,
        "provenance_id": provenance_id(
            identifier.provenance
        ),
        "is_primary": int(identifier.is_primary),
    }


def identifier_from_row(
    row: Row,
    provenance: DataProvenance,
) -> EntityIdentifier:
    """Reconstrói um identificador persistido."""

    return EntityIdentifier(
        identifier_type=IdentifierType(
            row["identifier_type"]
        ),
        value=row["value"],
        provenance=provenance,
        is_primary=bool(row["is_primary"]),
    )


def entity_from_rows(
    entity_row: Row,
    entity_provenance: DataProvenance,
    identifiers: tuple[EntityIdentifier, ...],
) -> Entity:
    """Reconstrói uma entidade completa."""

    created_at = datetime_from_text(
        entity_row["created_at"]
    )
    updated_at = datetime_from_text(
        entity_row["updated_at"]
    )

    if created_at is None or updated_at is None:
        raise ValueError(
            "Datas persistidas da entidade nao podem ser nulas."
        )

    return Entity(
        entity_id=UUID(entity_row["entity_id"]),
        legal_name=entity_row["legal_name"],
        trade_name=entity_row["trade_name"],
        entity_type=EntityType(
            entity_row["entity_type"]
        ),
        status=EntityStatus(entity_row["status"]),
        identifiers=identifiers,
        country_code=entity_row["country_code"],
        sector=entity_row["sector"],
        subsector=entity_row["subsector"],
        website=entity_row["website"],
        provenance=entity_provenance,
        created_at=created_at,
        updated_at=updated_at,
    )


def relationship_to_record(
    relationship: EntityRelationship,
) -> dict[str, Any]:
    """Converte relacionamento em registro persistente."""

    return {
        "relationship_id": str(
            relationship.relationship_id
        ),
        "source_entity_id": str(
            relationship.source_entity_id
        ),
        "target_entity_id": str(
            relationship.target_entity_id
        ),
        "relationship_type": (
            relationship.relationship_type.value
        ),
        "canonical_key": relationship.canonical_key,
        "provenance_id": provenance_id(
            relationship.provenance
        ),
        "status": relationship.status.value,
        "valid_from": datetime_to_text(
            relationship.valid_from
        ),
        "valid_to": datetime_to_text(
            relationship.valid_to
        ),
        "confidence_score": (
            relationship.confidence_score
        ),
        "notes": relationship.notes,
        "created_at": datetime_to_text(
            relationship.created_at
        ),
    }


def relationship_from_row(
    row: Row,
    provenance: DataProvenance,
) -> EntityRelationship:
    """Reconstrói um relacionamento persistido."""

    created_at = datetime_from_text(
        row["created_at"]
    )

    if created_at is None:
        raise ValueError(
            "created_at persistido nao pode ser nulo."
        )

    return EntityRelationship(
        relationship_id=UUID(
            row["relationship_id"]
        ),
        source_entity_id=UUID(
            row["source_entity_id"]
        ),
        target_entity_id=UUID(
            row["target_entity_id"]
        ),
        relationship_type=RelationshipType(
            row["relationship_type"]
        ),
        provenance=provenance,
        status=RelationshipStatus(row["status"]),
        valid_from=datetime_from_text(
            row["valid_from"]
        ),
        valid_to=datetime_from_text(
            row["valid_to"]
        ),
        confidence_score=int(
            row["confidence_score"]
        ),
        notes=row["notes"],
        created_at=created_at,
    )

