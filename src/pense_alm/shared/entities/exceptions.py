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


class EntityNotFoundError(EntityLayerError, LookupError):
    """Entidade solicitada nao foi encontrada."""


class RelationshipNotFoundError(
    EntityLayerError,
    LookupError,
):
    """Relacionamento solicitado nao foi encontrado."""


class DuplicateRelationshipError(EntityLayerError):
    """Relacionamento duplicado ou inconsistente."""


class RepositoryValidationError(
    EntityLayerError,
    ValueError,
):
    """Operacao de repositorio invalida."""
