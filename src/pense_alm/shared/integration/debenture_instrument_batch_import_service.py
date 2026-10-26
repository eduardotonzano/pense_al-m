"""Servico de importacao em lote de debentures legadas."""

from dataclasses import dataclass

from pense_alm.shared.entities import (
    EntityRepository,
    RelationshipRepository,
)

from .batch_import_error import BatchImportError
from .batch_import_report import BatchImportReport
from .debenture_instrument_import_service import (
    DebentureInstrumentImportService,
)
from .import_result import (
    EntityImportAction,
    InstrumentImportResult,
)
from .legacy_instrument_reader import (
    LegacyDebentureInstrumentReader,
    LegacyInstrumentReadError,
)


@dataclass(frozen=True, slots=True)
class InstrumentBatchOutcome:
    """Relatorio do lote e os casos que nao foram gravados."""

    report: BatchImportReport
    pending: tuple[InstrumentImportResult, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "pending",
            tuple(self.pending),
        )

        if len(self.pending) != (
            self.report.review + self.report.blocked
        ):
            raise ValueError(
                "pending deve listar os registros em revisao "
                "e bloqueados."
            )


class DebentureInstrumentBatchImportService:
    """Importa debentures legadas de forma controlada.

    O parametro dry_run apenas identifica o relatorio: quem chama
    deve entregar repositorios descartaveis quando for simular.
    """

    def __init__(
        self,
        reader: LegacyDebentureInstrumentReader,
        entity_repository: EntityRepository,
        relationship_repository: RelationshipRepository,
    ) -> None:
        if not isinstance(
            reader,
            LegacyDebentureInstrumentReader,
        ):
            raise TypeError(
                "reader deve ser "
                "LegacyDebentureInstrumentReader."
            )

        self._reader = reader
        self._service = DebentureInstrumentImportService(
            entity_repository,
            relationship_repository,
        )

    def run(
        self,
        batch_size: int = 100,
        dry_run: bool = False,
    ) -> InstrumentBatchOutcome:
        """Executa a importacao e retorna o relatorio."""

        if not isinstance(dry_run, bool):
            raise TypeError(
                "dry_run deve ser booleano."
            )

        counters = {
            EntityImportAction.CREATED: 0,
            EntityImportAction.MATCHED: 0,
            EntityImportAction.REVIEW: 0,
            EntityImportAction.BLOCKED: 0,
        }

        total_read = 0
        errors = 0
        error_details = []
        pending = []

        for item in self._reader.iter_records(
            batch_size=batch_size
        ):
            total_read += 1

            if isinstance(item, LegacyInstrumentReadError):
                errors += 1
                error_details.append(
                    BatchImportError(
                        legacy_id=item.legacy_id,
                        error_type=item.error_type,
                        message=(
                            item.message or item.error_type
                        ),
                    )
                )
                continue

            try:
                result = self._service.import_record(item)
            except Exception as error:
                errors += 1
                error_details.append(
                    BatchImportError(
                        legacy_id=item.legacy_id,
                        error_type=type(error).__name__,
                        message=(
                            str(error) or type(error).__name__
                        ),
                    )
                )
                continue

            counters[result.action] += 1

            if result.action in (
                EntityImportAction.REVIEW,
                EntityImportAction.BLOCKED,
            ):
                pending.append(result)

        report = BatchImportReport(
            total_read=total_read,
            created=counters[EntityImportAction.CREATED],
            matched=counters[EntityImportAction.MATCHED],
            review=counters[EntityImportAction.REVIEW],
            blocked=counters[EntityImportAction.BLOCKED],
            errors=errors,
            dry_run=dry_run,
            error_details=tuple(error_details),
        )

        return InstrumentBatchOutcome(
            report=report,
            pending=tuple(pending),
        )
