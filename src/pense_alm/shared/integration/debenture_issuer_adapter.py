"""Adaptador de emissores do modulo de Debentures."""

from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityIdentifier,
    EntityStatus,
    EntityType,
    IdentifierType,
    SourceType,
)

from .legacy_datetime import parse_legacy_datetime
from .records import DebentureIssuerRecord


class DebentureIssuerAdapter:
    """Converte emissores legados em entidades compartilhadas."""

    SOURCE_NAME = "Debenture Replica - Issuer Repository"
    ENTITY_NAMESPACE = "pense-alm:debenture-issuer"

    def convert(
        self,
        record: DebentureIssuerRecord,
    ) -> Entity:
        """Converte um registro legado em Entity."""

        if not isinstance(record, DebentureIssuerRecord):
            raise TypeError(
                "record deve ser DebentureIssuerRecord."
            )

        created_at = self._parse_legacy_datetime(
            record.created_at
        )
        updated_at = self._parse_legacy_datetime(
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
                f"issuer:{record.legacy_id}"
            ),
            collected_at=updated_at,
            reference_date=updated_at,
        )

        identifiers = ()

        if record.cnpj is not None:
            identifiers = (
                EntityIdentifier(
                    identifier_type=IdentifierType.CNPJ,
                    value=record.cnpj,
                    provenance=provenance,
                    is_primary=True,
                ),
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
            legal_name=record.legal_name,
            trade_name=record.trade_name,
            entity_type=EntityType.COMPANY,
            status=EntityStatus.ACTIVE,
            identifiers=identifiers,
            country_code="BR",
            provenance=provenance,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _parse_legacy_datetime(
        value: str,
    ) -> datetime:
        """Converte timestamps SQLite legados para UTC."""

        return parse_legacy_datetime(value)
