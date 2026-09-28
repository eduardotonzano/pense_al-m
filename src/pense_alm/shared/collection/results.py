"""Resultados agregados da camada compartilhada de coleta."""

from dataclasses import dataclass, field

from .errors import CollectionError
from .raw_records import RawCollectionRecord
from .responses import CollectedResponse
from .runs import CollectionRun


@dataclass(frozen=True, slots=True)
class CollectionResult:
    """Resultado auditavel de uma execucao de coleta."""

    run: CollectionRun
    responses: tuple[CollectedResponse, ...] = field(
        default_factory=tuple
    )
    raw_records: tuple[RawCollectionRecord, ...] = field(
        default_factory=tuple
    )
    errors: tuple[CollectionError, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        if not isinstance(self.run, CollectionRun):
            raise TypeError(
                "run deve ser CollectionRun."
            )

        if not isinstance(self.responses, tuple):
            raise TypeError(
                "responses deve ser uma tupla."
            )

        if any(
            not isinstance(
                response,
                CollectedResponse,
            )
            for response in self.responses
        ):
            raise TypeError(
                "responses possui item invalido."
            )

        if not isinstance(self.raw_records, tuple):
            raise TypeError(
                "raw_records deve ser uma tupla."
            )

        if any(
            not isinstance(
                raw_record,
                RawCollectionRecord,
            )
            for raw_record in self.raw_records
        ):
            raise TypeError(
                "raw_records possui item invalido."
            )

        if not isinstance(self.errors, tuple):
            raise TypeError(
                "errors deve ser uma tupla."
            )

        if any(
            not isinstance(
                error,
                CollectionError,
            )
            for error in self.errors
        ):
            raise TypeError(
                "errors possui item invalido."
            )

        if any(
            response.source_id != self.run.source_id
            for response in self.responses
        ):
            raise ValueError(
                "Todas as responses devem pertencer "
                "a fonte da execucao."
            )

        if any(
            raw_record.source_id != self.run.source_id
            for raw_record in self.raw_records
        ):
            raise ValueError(
                "Todos os raw_records devem pertencer "
                "a fonte da execucao."
            )

        if any(
            raw_record.collection_run_id
            not in (None, self.run.run_id)
            for raw_record in self.raw_records
        ):
            raise ValueError(
                "Todos os raw_records devem pertencer "
                "a execucao informada."
            )

        if any(
            error.run_id not in (None, self.run.run_id)
            for error in self.errors
        ):
            raise ValueError(
                "Todos os errors devem pertencer "
                "a execucao informada."
            )

        if len(self.errors) != self.run.failed_items:
            raise ValueError(
                "A quantidade de errors deve ser igual "
                "a failed_items."
            )
