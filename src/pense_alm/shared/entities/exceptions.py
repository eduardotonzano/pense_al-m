"""Excecoes da Shared Entity Layer."""


class EntityLayerError(Exception):
    """Erro-base da camada compartilhada de entidades."""


class EntityValidationError(EntityLayerError, ValueError):
    """Entidade ou atributo invalido."""


class IdentifierValidationError(EntityLayerError, ValueError):
    """Identificador invalido ou inconsistente."""


class DuplicateEntityError(EntityLayerError):
    """Possivel duplicidade de entidade."""


class ProvenanceValidationError(EntityLayerError, ValueError):
    """Proveniencia ausente ou invalida."""
