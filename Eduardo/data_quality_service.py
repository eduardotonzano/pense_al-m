from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from debenture_search.database import database


@dataclass(frozen=True)
class DataQualityIssue:
    """Representa um problema de qualidade de dados."""

    code: str
    severity: str
    entity_type: str
    entity_id: int | None
    field_name: str | None
    message: str


@dataclass(frozen=True)
class DataQualityReport:
    """Resume a qualidade dos dados armazenados."""

    status: str
    checked_at: str
    total_debentures: int
    total_observations: int
    issue_count: int
    critical_count: int
    warning_count: int
    issues: tuple

    @property
    def valid(self):
        """Informa se nenhum problema critico foi encontrado."""

        return self.critical_count == 0


class DataQualityService:
    """Executa regras de qualidade sobre os dados financeiros."""

    def __init__(self, db=database, stale_days=30):
        self.db = db
        self.stale_days = int(stale_days)

        if self.stale_days < 1:
            raise ValueError(
                "stale_days deve ser maior que zero."
            )

    @staticmethod
    def utc_now():
        """Retorna o horario atual em UTC."""

        return datetime.now(timezone.utc)

    @staticmethod
    def issue(
        code,
        severity,
        entity_type,
        entity_id,
        message,
        field_name=None,
    ):
        """Cria um registro padronizado de problema."""

        return DataQualityIssue(
            code=code,
            severity=severity,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            message=message,
        )

    def check_debentures_without_issuer(self):
        """Encontra debentures sem emissor associado."""

        rows = self.db.fetch_all(
            """
            SELECT id, asset_code, isin
            FROM debentures
            WHERE issuer_id IS NULL
            """
        )

        return [
            self.issue(
                code="DEBENTURE_WITHOUT_ISSUER",
                severity="warning",
                entity_type="debenture",
                entity_id=int(row["id"]),
                message=(
                    "Debenture sem emissor associado: "
                    + str(row["asset_code"] or row["isin"])
                ),
            )
            for row in rows
        ]

    def check_debentures_without_observations(self):
        """Encontra ativos sem qualquer observacao."""

        rows = self.db.fetch_all(
            """
            SELECT d.id, d.asset_code, d.isin
            FROM debentures AS d
            LEFT JOIN observations AS o
                ON o.debenture_id = d.id
            GROUP BY d.id, d.asset_code, d.isin
            HAVING COUNT(o.id) = 0
            """
        )

        return [
            self.issue(
                code="DEBENTURE_WITHOUT_OBSERVATIONS",
                severity="warning",
                entity_type="debenture",
                entity_id=int(row["id"]),
                message=(
                    "Debenture sem observacoes: "
                    + str(row["asset_code"] or row["isin"])
                ),
            )
            for row in rows
        ]

    def check_non_positive_values(self):
        """Encontra valores financeiros que deveriam ser positivos."""

        positive_fields = {
            "valor_nominal",
            "quantidade_emitida",
            "quantidade_em_mercado",
        }

        placeholders = ",".join("?" for _ in positive_fields)
        rows = self.db.fetch_all(
            """
            SELECT id, debenture_id, field_name, value_numeric
            FROM observations
            WHERE value_type = 'numeric'
              AND field_name IN (""" + placeholders + """)
              AND value_numeric <= 0
            """,
            tuple(sorted(positive_fields)),
        )

        return [
            self.issue(
                code="NON_POSITIVE_FINANCIAL_VALUE",
                severity="critical",
                entity_type="observation",
                entity_id=int(row["id"]),
                field_name=str(row["field_name"]),
                message="Valor financeiro deve ser maior que zero.",
            )
            for row in rows
        ]

    def check_suspect_observations(self):
        """Encontra observacoes marcadas como suspeitas."""

        rows = self.db.fetch_all(
            """
            SELECT id, field_name
            FROM observations
            WHERE confidence = 'suspect'
            """
        )

        return [
            self.issue(
                code="SUSPECT_OBSERVATION",
                severity="warning",
                entity_type="observation",
                entity_id=int(row["id"]),
                field_name=str(row["field_name"]),
                message="Observacao marcada como suspeita.",
            )
            for row in rows
        ]

    def check_stale_observations(self):
        """Encontra valores atuais antigos demais."""

        cutoff = (
            self.utc_now() - timedelta(days=self.stale_days)
        ).isoformat()

        rows = self.db.fetch_all(
            """
            SELECT id, debenture_id, field_name, observed_at
            FROM current_observations
            WHERE observed_at < ?
            """,
            (cutoff,),
        )

        return [
            self.issue(
                code="STALE_CURRENT_OBSERVATION",
                severity="warning",
                entity_type="observation",
                entity_id=int(row["id"]),
                field_name=str(row["field_name"]),
                message=(
                    "Observacao atual mais antiga que "
                    + str(self.stale_days)
                    + " dias."
                ),
            )
            for row in rows
        ]

    def check_open_conflicts(self):
        """Encontra conflitos de dados ainda abertos."""

        rows = self.db.fetch_all(
            """
            SELECT id, debenture_id, field_name
            FROM data_conflicts
            WHERE status = 'open'
            """
        )

        return [
            self.issue(
                code="OPEN_DATA_CONFLICT",
                severity="critical",
                entity_type="conflict",
                entity_id=int(row["id"]),
                field_name=str(row["field_name"]),
                message="Conflito de dados ainda nao resolvido.",
            )
            for row in rows
        ]

    def check_failed_collections(self):
        """Encontra execucoes de coleta com falha."""

        rows = self.db.fetch_all(
            """
            SELECT id
            FROM collection_runs
            WHERE status = 'failed'
            """
        )

        return [
            self.issue(
                code="FAILED_COLLECTION",
                severity="warning",
                entity_type="collection_run",
                entity_id=int(row["id"]),
                message="Execucao de coleta finalizada com falha.",
            )
            for row in rows
        ]

    def check(self):
        """Executa todas as regras de qualidade."""

        issues = []
        issues.extend(self.check_debentures_without_issuer())
        issues.extend(
            self.check_debentures_without_observations()
        )
        issues.extend(self.check_non_positive_values())
        issues.extend(self.check_suspect_observations())
        issues.extend(self.check_stale_observations())
        issues.extend(self.check_open_conflicts())
        issues.extend(self.check_failed_collections())

        total_debentures = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM debentures"
        )["total"]
        total_observations = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM observations"
        )["total"]

        critical_count = sum(
            1 for item in issues if item.severity == "critical"
        )
        warning_count = sum(
            1 for item in issues if item.severity == "warning"
        )

        if critical_count > 0:
            status = "critical"
        elif warning_count > 0:
            status = "attention"
        else:
            status = "healthy"

        return DataQualityReport(
            status=status,
            checked_at=self.utc_now().isoformat(),
            total_debentures=int(total_debentures),
            total_observations=int(total_observations),
            issue_count=len(issues),
            critical_count=critical_count,
            warning_count=warning_count,
            issues=tuple(issues),
        )


quality_service = DataQualityService()
