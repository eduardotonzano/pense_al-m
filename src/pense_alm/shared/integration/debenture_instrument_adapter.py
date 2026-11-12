"""Adaptador de debentures (o instrumento) do modulo de Debentures."""

from uuid import NAMESPACE_URL, uuid5

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
)

from .legacy_datetime import parse_legacy_datetime
from .records import DebentureInstrumentRecord


_STATUS_MAP = {
    "active": EntityStatus.ACTIVE,
    "inactive": EntityStatus.INACTIVE,
    "matured": EntityStatus.INACTIVE,
    "cancelled": EntityStatus.INACTIVE,
    "unknown": EntityStatus.UNKNOWN,
}


class DebentureInstrumentAdapter:
    """Converte debentures legadas em entidades compartilhadas."""

    SOURCE_NAME = "Debenture Replica - Debenture Repository"
    ENTITY_NAMESPACE = "pense-alm:debenture-instrument"

    def convert(
        self,
        record: DebentureInstrumentRecord,
    ) -> Entity:
        """Converte um registro legado em Entity."""

        if not isinstance(record, DebentureInstrumentRecord):
            raise TypeError(
                "record deve ser DebentureInstrumentRecord."
            )

        created_at = parse_legacy_datetime(
            record.created_at
        )
        updated_at = parse_legacy_datetime(
            record.updated_at
        )

        if updated_at < created_at:
            raise ValueError(
                "updated_at nao pode ser anterior a created_at."
            )

        provenance = DataProvenance(
            source_type=SourceType.SPECIALIZED,
            source_name=self.SOURCE_NAME,
            source_reference=(
                f"debenture:{record.legacy_id}"
            ),
            collected_at=updated_at,
            reference_date=updated_at,
        )

        identifiers = []

        if record.asset_code is not None:
            identifiers.append(
                EntityIdentifier(
                    identifier_type=IdentifierType.ASSET_CODE,
                    value=record.asset_code,
                    provenance=provenance,
                    is_primary=True,
                )
            )

        if record.isin is not None:
            identifiers.append(
                EntityIdentifier(
                    identifier_type=IdentifierType.ISIN,
                    value=record.isin,
                    provenance=provenance,
                    is_primary=True,
                )
            )

        entity_id = uuid5(
            NAMESPACE_URL,
            (
                f"{self.ENTITY_NAMESPACE}:"
                f"{record.legacy_id}"
            ),
        )

        return Entity(
            entity_id=entity_id,
            legal_name=record.asset_code or record.isin,
            entity_type=EntityType.DEBENTURE,
            status=_STATUS_MAP[record.status],
            identifiers=tuple(identifiers),
            country_code="BR",
            provenance=provenance,
            created_at=created_at,
            updated_at=updated_at,
        )

    def build_issuance_relationship(
        self,
        issuer: Entity,
        instrument: Entity,
    ) -> EntityRelationship:
        """Cria a relacao de emissao: emissor ISSUES instrumento."""

        if not isinstance(issuer, Entity):
            raise TypeError("issuer deve ser Entity.")

        if not isinstance(instrument, Entity):
            raise TypeError("instrument deve ser Entity.")

        if instrument.entity_type is not EntityType.DEBENTURE:
            raise ValueError(
                "instrument deve ser do tipo DEBENTURE."
            )

        canonical_key = (
            f"{issuer.entity_id}:"
            f"{RelationshipType.ISSUES.value}:"
            f"{instrument.entity_id}"
        )

        return EntityRelationship(
            source_entity_id=issuer.entity_id,
            target_entity_id=instrument.entity_id,
            relationship_type=RelationshipType.ISSUES,
            provenance=instrument.provenance,
            relationship_id=uuid5(
                NAMESPACE_URL,
                canonical_key,
            ),
            status=RelationshipStatus.ACTIVE,
            created_at=instrument.provenance.collected_at,
        )
