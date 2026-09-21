"""Enumeracoes da Shared Entity Layer."""

from enum import StrEnum


class EntityType(StrEnum):
    """Tipos de participantes reconhecidos pela plataforma."""

    BANK = "bank"
    COMPANY = "company"
    HOLDING = "holding"
    FINANCIAL_INSTITUTION = "financial_institution"
    COOPERATIVE = "cooperative"
    ASSET_MANAGER = "asset_manager"
    FUND = "fund"
    FIDC = "fidc"
    FIAGRO = "fiagro"
    SECURITIZER = "securitizer"
    GOVERNMENT = "government"
    OTHER = "other"


class EntityStatus(StrEnum):
    """Situacao conhecida da entidade."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    UNDER_INTERVENTION = "under_intervention"
    IN_LIQUIDATION = "in_liquidation"
    UNKNOWN = "unknown"


class IdentifierType(StrEnum):
    """Identificadores aceitos pela primeira versao."""

    CNPJ = "cnpj"
    BACEN_CODE = "bacen_code"
    CVM_CODE = "cvm_code"
    ANBIMA_CODE = "anbima_code"
    LEI = "lei"
    INTERNAL = "internal"
    OTHER = "other"


class SourceType(StrEnum):
    """Tipos de fonte usados na proveniencia."""

    BACEN = "bacen"
    CVM = "cvm"
    ANBIMA = "anbima"
    SPECIALIZED = "specialized"
    INSTITUTIONAL = "institutional"
    MANUAL = "manual"


class ValidationStatus(StrEnum):
    """Estado de validacao de um dado coletado."""

    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    CONFLICT = "conflict"


class MatchStrength(StrEnum):
    """Forca da evidencia encontrada entre duas entidades."""

    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    CONFLICT = "conflict"


class MatchDecision(StrEnum):
    """Decisao recomendada pelo mecanismo de matching."""

    NO_MATCH = "no_match"
    REVIEW = "review"
    AUTO_MATCH = "auto_match"
    BLOCKED = "blocked"
