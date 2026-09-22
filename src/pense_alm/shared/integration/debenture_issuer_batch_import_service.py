"""Servico de importacao em lote de emissores legados."""

from pense_alm.shared.entities import (
    EntityRepository,
    InMemoryEntityRepository,
)

from .batch_import_report import BatchImportReport
from .debenture_issuer_import_service import (
    DebentureIssuerImportService,
)
from .import_result import EntityImportAction
from .legacy_issuer_reader import (
    LegacyDebentureIssuerReader,
)


class DebentureIssuerBatchImportService:
    """Importa emissores legados de forma controlada."""

    def __init__(
        self,
        reader: LegacyDebentureIssuerReader,
        repository: EntityRepository,
    ) -> None:
        if not isinstance(
            reader,
            LegacyDebentureIssuerReader,
        ):
            raise TypeError(
                "reader deve ser LegacyDebentureIssuerReader."
            )

        required_methods = (
            "save",
            "get_by_identifier",
            "list_all",
        )

        if any(
            not callable(getattr(repository, method, None))
            for method in required_methods
        ):
            raise TypeError(
                "repository nao implementa EntityRepository."
            )

        self._reader = reader
        self._repository = repository

    def run(
        self,
        batch_size: int = 100,
        dry_run: bool = False,
    ) -> BatchImportReport:
        """Executa a importacao e retorna um relatorio."""

        if not isinstance(dry_run, bool):
            raise TypeError(
                "dry_run deve ser booleano."
            )

        target_repository = self._repository

        if dry_run:
            target_repository = (
                self._create_simulation_repository()
            )

        import_service = DebentureIssuerImportService(
            target_repository
        )

        counters = {
            EntityImportAction.CREATED: 0,
            EntityImportAction.MATCHED: 0,
            EntityImportAction.REVIEW: 0,
            EntityImportAction.BLOCKED: 0,
        }

        total_read = 0
        errors = 0

        for record in self._reader.iter_records(
            batch_size=batch_size
        ):
            total_read += 1

            try:
                result = import_service.import_record(
                    record
                )
            except Exception:
                errors += 1
                continue

            counters[result.action] += 1

        return BatchImportReport(
            total_read=total_read,
            created=counters[
                EntityImportAction.CREATED
            ],
            matched=counters[
                EntityImportAction.MATCHED
            ],
            review=counters[
                EntityImportAction.REVIEW
            ],
            blocked=counters[
                EntityImportAction.BLOCKED
            ],
            errors=errors,
            dry_run=dry_run,
        )

    def _create_simulation_repository(
        self,
    ) -> InMemoryEntityRepository:
        """Copia o estado para um repositorio temporario."""

        simulation_repository = (
            InMemoryEntityRepository()
        )

        for entity in self._repository.list_all():
            simulation_repository.save(entity)

        return simulation_repository
