from dataclasses import dataclass
from datetime import datetime
from datetime import timezone

from debenture_search.repositories.audit_repository import AuditRepository
from debenture_search.repositories.collection_repository import CollectionRepository
from debenture_search.repositories.conflict_repository import ConflictRepository
from debenture_search.repositories.debenture_repository import DebentureRepository
from debenture_search.repositories.issuer_repository import IssuerRepository
from debenture_search.repositories.observation_repository import ObservationRepository
from debenture_search.repositories.raw_record_repository import RawRecordRepository
from debenture_search.repositories.source_repository import SourceRepository


@dataclass(frozen=True)
class IngestionResult:
    """Resume o resultado de uma ingestao."""

    collection_run_id: int
    issuer_id: int | None
    debenture_id: int
    raw_record_id: int
    observations_created: int
    observations_reused: int
    conflicts_created: int
    status: str


class IngestionService:
    """Coordena a gravacao segura de dados coletados."""

    def __init__(
        self,
        db,
        issuer_repository=None,
        debenture_repository=None,
        source_repository=None,
        collection_repository=None,
        raw_record_repository=None,
        observation_repository=None,
        conflict_repository=None,
        audit_repository=None,
    ):
        self.db = db
        self.issuers = issuer_repository or IssuerRepository(db)
        self.debentures = debenture_repository or DebentureRepository(db)
        self.sources = source_repository or SourceRepository(db)
        self.collections = collection_repository or CollectionRepository(db)
        self.raw_records = raw_record_repository or RawRecordRepository(db)
        self.observations = observation_repository or ObservationRepository(db)
        self.conflicts = conflict_repository or ConflictRepository(db)
        self.audit = audit_repository or AuditRepository(db)

    @staticmethod
    def utc_now():
        """Retorna o horario atual em UTC."""

        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def normalize_observations(items):
        """Valida a lista de observacoes recebida."""

        if items is None:
            return []

        if not isinstance(items, list):
            raise ValueError(
                "As observacoes devem ser fornecidas em uma lista."
            )

        normalized = []

        for item in items:
            if not isinstance(item, dict):
                raise ValueError(
                    "Cada observacao deve ser um dicionario."
                )

            required = {"field_name", "value_type", "value"}
            missing = required.difference(item)

            if missing:
                raise ValueError(
                    "Observacao incompleta: "
                    + ", ".join(sorted(missing))
                )

            normalized.append(dict(item))

        return normalized

    def find_conflicting_observation(
        self,
        debenture_id,
        field_name,
        source_id,
        value,
    ):
        """Localiza valor atual divergente de outra fonte."""

        history = self.observations.list_history(
            debenture_id,
            field_name,
            limit=100,
        )

        normalized_value = str(value)

        for record in history:
            if record.source_id == source_id:
                continue

            if str(record.value) != normalized_value:
                return record

        return None

    def ingest(
        self,
        source_code,
        payload,
        asset_code=None,
        isin=None,
        issuer_legal_name=None,
        issuer_cnpj=None,
        issuer_trade_name=None,
        issue_number=None,
        series=None,
        debenture_status="unknown",
        observations=None,
        request_url=None,
        request_parameters=None,
        content_type=None,
        http_status=None,
        parser_version=None,
        actor="ingestion_service",
    ):
        """Executa o fluxo completo de ingestao."""

        source = self.sources.get_by_code(source_code)

        if source is None:
            raise ValueError("A fonte informada nao existe.")

        if not source.active:
            raise ValueError("A fonte informada esta desativada.")

        normalized_observations = self.normalize_observations(
            observations
        )

        collection = self.collections.start(
            source_id=source.id,
            requested_items=max(1, len(normalized_observations)),
        )

        successful_items = 0
        failed_items = 0
        errors = []

        try:
            raw_record, _ = self.raw_records.create(
                source_id=source.id,
                collection_run_id=collection.id,
                payload=payload,
                request_url=request_url,
                request_parameters=request_parameters,
                content_type=content_type,
                http_status=http_status,
                parser_version=parser_version,
            )

            issuer = None

            if issuer_legal_name is not None:
                issuer, _ = self.issuers.get_or_create(
                    legal_name=issuer_legal_name,
                    cnpj=issuer_cnpj,
                    trade_name=issuer_trade_name,
                )

            debenture, debenture_created = (
                self.debentures.get_or_create(
                    asset_code=asset_code,
                    isin=isin,
                    issuer_id=None if issuer is None else issuer.id,
                    issue_number=issue_number,
                    series=series,
                    status=debenture_status,
                )
            )

            created_count = 0
            reused_count = 0
            conflict_count = 0

            for item in normalized_observations:
                observed_at = item.get(
                    "observed_at",
                    self.utc_now(),
                )

                observation, was_created = self.observations.create(
                    debenture_id=debenture.id,
                    source_id=source.id,
                    raw_record_id=raw_record.id,
                    field_name=item["field_name"],
                    value_type=item["value_type"],
                    value=item["value"],
                    observed_at=observed_at,
                    unit=item.get("unit"),
                    valid_from=item.get("valid_from"),
                    valid_until=item.get("valid_until"),
                    confidence=item.get("confidence", "reported"),
                )

                if was_created:
                    created_count += 1
                else:
                    reused_count += 1

                other = self.find_conflicting_observation(
                    debenture_id=debenture.id,
                    field_name=observation.field_name,
                    source_id=source.id,
                    value=observation.value,
                )

                if other is not None:
                    _, conflict_created = self.conflicts.create(
                        debenture_id=debenture.id,
                        field_name=observation.field_name,
                        observation_a_id=observation.id,
                        observation_b_id=other.id,
                    )

                    if conflict_created:
                        conflict_count += 1

                successful_items += 1

            self.raw_records.update_processing(
                raw_record.id,
                status="processed",
                parser_version=parser_version,
            )

            self.audit.create(
                actor=actor,
                action="ingest",
                entity_type="debenture",
                entity_id=debenture.id,
                after={
                    "source": source.code,
                    "raw_record_id": raw_record.id,
                    "observations_created": created_count,
                    "observations_reused": reused_count,
                    "conflicts_created": conflict_count,
                    "debenture_created": debenture_created,
                },
                reason="Ingestao automatizada de dados.",
            )

            finished = self.collections.finish(
                collection_run_id=collection.id,
                status="success",
                successful_items=max(1, successful_items),
                failed_items=0,
            )

            return IngestionResult(
                collection_run_id=finished.id,
                issuer_id=None if issuer is None else issuer.id,
                debenture_id=debenture.id,
                raw_record_id=raw_record.id,
                observations_created=created_count,
                observations_reused=reused_count,
                conflicts_created=conflict_count,
                status=finished.status,
            )

        except Exception as error:
            failed_items = max(1, len(normalized_observations))
            errors.append(
                {
                    "type": type(error).__name__,
                    "message": str(error),
                }
            )

            current = self.collections.get_by_id(collection.id)

            if current is not None and current.status == "running":
                self.collections.finish(
                    collection_run_id=collection.id,
                    status="failed",
                    successful_items=successful_items,
                    failed_items=failed_items,
                    errors=errors,
                )

            raise
