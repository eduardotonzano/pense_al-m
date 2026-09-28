"""Modelo central da Shared Entity Layer."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .enums import EntityStatus, EntityType, IdentifierType
from .exceptions import EntityValidationError
from .identifiers import EntityIdentifier
from .provenance import DataProvenance


def normalize_name(value: str, field_name: str) -> str:
    """Normaliza e valida nomes da entidade."""

    if not isinstance(value, str):
        raise EntityValidationError(
            f"{field_name} deve ser texto."
        )

    normalized = " ".join(value.split())

    if not normalized:
        raise EntityValidationError(
            f"{field_name} nao pode ser vazio."
        )

    return normalized


def normalize_optional_text(value: str | None) -> str | None:
    """Normaliza um campo textual opcional."""

    if value is None:
        return None

    if not isinstance(value, str):
        raise EntityValidationError(
            "O valor opcional deve ser texto."
        )

    normalized = " ".join(value.split())

    return normalized or None


@dataclass(frozen=True, slots=True)
class Entity:
    """Participante universal coberto pela plataforma."""

    legal_name: str
    entity_type: EntityType
    provenance: DataProvenance
    entity_id: UUID = field(default_factory=uuid4)
    trade_name: str | None = None
    status: EntityStatus = EntityStatus.UNKNOWN
    identifiers: tuple[EntityIdentifier, ...] = field(
        default_factory=tuple
    )
    country_code: str = "BR"
    sector: str | None = None
    subsector: str | None = None
    website: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def __post_init__(self) -> None:
        legal_name = normalize_name(
            self.legal_name,
            "legal_name",
        )

        trade_name = normalize_optional_text(
            self.trade_name
        )

        sector = normalize_optional_text(self.sector)
        subsector = normalize_optional_text(self.subsector)
        website = normalize_optional_text(self.website)

        country_code = self.country_code.strip().upper()

        if len(country_code) != 2 or not country_code.isalpha():
            raise EntityValidationError(
                "country_code deve seguir o formato ISO de duas letras."
            )

        if self.created_at.tzinfo is None:
            raise EntityValidationError(
                "created_at deve possuir timezone."
            )

        if self.updated_at.tzinfo is None:
            raise EntityValidationError(
                "updated_at deve possuir timezone."
            )

        if self.updated_at < self.created_at:
            raise EntityValidationError(
                "updated_at nao pode ser anterior a created_at."
            )

        canonical_keys = [
            identifier.canonical_key
            for identifier in self.identifiers
        ]

        if len(canonical_keys) != len(set(canonical_keys)):
            raise EntityValidationError(
                "A entidade nao pode possuir identificadores duplicados."
            )

        primary_types = [
            identifier.identifier_type
            for identifier in self.identifiers
            if identifier.is_primary
        ]

        if len(primary_types) != len(set(primary_types)):
            raise EntityValidationError(
                "A entidade nao pode possuir mais de um identificador "
                "primario do mesmo tipo."
            )

        object.__setattr__(self, "legal_name", legal_name)
        object.__setattr__(self, "trade_name", trade_name)
        object.__setattr__(self, "country_code", country_code)
        object.__setattr__(self, "sector", sector)
        object.__setattr__(self, "subsector", subsector)
        object.__setattr__(self, "website", website)
        object.__setattr__(
            self,
            "identifiers",
            tuple(self.identifiers),
        )

    def get_identifier(
        self,
        identifier_type: IdentifierType,
    ) -> EntityIdentifier | None:
        """Retorna o identificador preferencial do tipo solicitado."""

        matching = [
            identifier
            for identifier in self.identifiers
            if identifier.identifier_type is identifier_type
        ]

        if not matching:
            return None

        primary = next(
            (
                identifier
                for identifier in matching
                if identifier.is_primary
            ),
            None,
        )

        return primary or matching[0]

    @property
    def cnpj(self) -> str | None:
        """Retorna o CNPJ principal, quando disponível."""

        identifier = self.get_identifier(
            IdentifierType.CNPJ
        )

        return identifier.value if identifier else None

    @property
    def display_name(self) -> str:
        """Retorna o nome apropriado para exibicao."""

        return self.trade_name or self.legal_name
