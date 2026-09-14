from dataclasses import dataclass

from debenture_search.services.backup_service import BackupService


@dataclass(frozen=True)
class BatchItemResult:
    asset_code: str
    status: str
    observations_created: int = 0
    observations_reused: int = 0
    conflicts_created: int = 0
    error: str | None = None


@dataclass(frozen=True)
class BatchImportResult:
    requested: int
    processed: int
    successes: int
    failures: int
    observations_created: int
    observations_reused: int
    conflicts_created: int
    backup_path: object | None
    items: tuple


class SndBatchImportService:
    """Coordena a coleta controlada de varios ativos do SND."""

    def __init__(self, db, provider, backup_service=None, max_items=20):
        self.db = db
        self.provider = provider
        self.backup_service = backup_service
        self.max_items = int(max_items)

        if self.max_items < 1:
            raise ValueError("O limite de ativos deve ser maior que zero.")

    def normalize_codes(self, asset_codes):
        """Normaliza codigos, remove vazios e elimina repeticoes."""

        if asset_codes is None:
            raise ValueError("A lista de ativos e obrigatoria.")

        normalized = []
        seen = set()

        for value in asset_codes:
            if value is None or not str(value).strip():
                continue

            code = self.provider.normalize_asset_code(value)

            if code not in seen:
                seen.add(code)
                normalized.append(code)

        if not normalized:
            raise ValueError("A lista de ativos nao possui codigos validos.")

        if len(normalized) > self.max_items:
            raise ValueError(
                "A lista excede o limite de "
                + str(self.max_items)
                + " ativos."
            )

        return normalized

    def run(self, asset_codes, commit=False):
        """Pre-visualiza ou importa os ativos informados."""

        codes = self.normalize_codes(asset_codes)
        backup_path = None

        if commit:
            selected_backup_service = (
                self.backup_service
                or BackupService(self.db)
            )

            backup_path = (
                selected_backup_service
                .create_backup()
                .path
            )

        items = []

        for code in codes:
            try:
                if commit:
                    result = self.provider.collect(code)
                    item = BatchItemResult(
                        asset_code=code,
                        status="success",
                        observations_created=result.observations_created,
                        observations_reused=result.observations_reused,
                        conflicts_created=result.conflicts_created,
                    )
                else:
                    response = self.provider.fetch_html(code)
                    item = BatchItemResult(
                        asset_code=code,
                        status="preview",
                    )
            except Exception as error:
                item = BatchItemResult(
                    asset_code=code,
                    status="failed",
                    error=type(error).__name__ + ": " + str(error),
                )

            items.append(item)

        if commit:
            if self.db.integrity_check() != "ok":
                raise RuntimeError("A integridade do banco falhou apos o lote.")

            if self.db.foreign_key_check():
                raise RuntimeError(
                    "Foram encontradas violacoes de chaves estrangeiras."
                )

        successes = sum(
            1 for item in items if item.status in {"success", "preview"}
        )
        failures = sum(1 for item in items if item.status == "failed")

        return BatchImportResult(
            requested=len(codes),
            processed=len(items),
            successes=successes,
            failures=failures,
            observations_created=sum(
                item.observations_created for item in items
            ),
            observations_reused=sum(
                item.observations_reused for item in items
            ),
            conflicts_created=sum(
                item.conflicts_created for item in items
            ),
            backup_path=backup_path,
            items=tuple(items),
        )

