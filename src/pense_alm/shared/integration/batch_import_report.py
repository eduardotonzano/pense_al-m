"""Relatorio agregado da importacao em lote."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BatchImportReport:
    """Resumo auditavel de uma importacao em lote."""

    total_read: int = 0
    created: int = 0
    matched: int = 0
    review: int = 0
    blocked: int = 0
    errors: int = 0
    dry_run: bool = False

    def __post_init__(self) -> None:
        counters = (
            self.total_read,
            self.created,
            self.matched,
            self.review,
            self.blocked,
            self.errors,
        )

        if any(
            not isinstance(value, int)
            for value in counters
        ):
            raise TypeError(
                "Os contadores devem ser inteiros."
            )

        if any(value < 0 for value in counters):
            raise ValueError(
                "Os contadores nao podem ser negativos."
            )

        processed = (
            self.created
            + self.matched
            + self.review
            + self.blocked
            + self.errors
        )

        if processed != self.total_read:
            raise ValueError(
                "A soma dos resultados deve ser igual "
                "ao total lido."
            )

        if not isinstance(self.dry_run, bool):
            raise TypeError(
                "dry_run deve ser booleano."
            )

    @property
    def successful(self) -> int:
        """Retorna criados e correspondentes."""

        return self.created + self.matched

    @property
    def pending(self) -> int:
        """Retorna registros que exigem revisao."""

        return self.review

    @property
    def failed(self) -> int:
        """Retorna bloqueios e erros."""

        return self.blocked + self.errors
