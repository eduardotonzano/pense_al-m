from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CurrentValue:
    field_name: str
    value_type: str
    value: object
    unit: str | None
    observed_at: str
    source_code: str
    confidence: str


@dataclass(frozen=True)
class DebentureSummary:
    id: int
    asset_code: str
    isin: str | None
    issuer_id: int | None
    issuer_name: str | None
    issuer_cnpj: str | None
    issue_number: str | None
    series: str | None
    status: str


@dataclass(frozen=True)
class DebentureDetails:
    debenture: DebentureSummary
    current_values: dict
    open_conflicts: int


class DebentureQueryService:
    """Fornece consultas consolidadas e somente leitura."""

    def __init__(self, db):
        self.db = db

    @staticmethod
    def normalize_search(value):
        if value is None or not str(value).strip():
            raise ValueError("O valor de pesquisa e obrigatorio.")
        return str(value).strip()

    @staticmethod
    def row_value(row):
        value_type = str(row["value_type"])
        if value_type == "text":
            return row["value_text"]
        if value_type == "numeric":
            value = row["value_numeric"]
            return None if value is None else Decimal(str(value))
        if value_type == "date":
            return row["value_date"]
        if value_type == "boolean":
            value = row["value_boolean"]
            return None if value is None else bool(value)
        return None

    @staticmethod
    def row_to_summary(row):
        return DebentureSummary(
            id=int(row["id"]),
            asset_code=str(row["asset_code"]),
            isin=row["isin"],
            issuer_id=row["issuer_id"],
            issuer_name=row["issuer_name"],
            issuer_cnpj=row["issuer_cnpj"],
            issue_number=row["issue_number"],
            series=row["series"],
            status=str(row["status"]),
        )

    def base_query(self):
        return """
            SELECT
                d.id,
                d.asset_code,
                d.isin,
                d.issuer_id,
                i.legal_name AS issuer_name,
                i.cnpj AS issuer_cnpj,
                d.issue_number,
                d.series,
                d.status
            FROM debentures d
            LEFT JOIN issuers i ON i.id = d.issuer_id
        """

    def list_all(self):
        rows = self.db.fetch_all(
            self.base_query() + " ORDER BY d.asset_code"
        )
        return [self.row_to_summary(row) for row in rows]

    def find_by_code(self, asset_code):
        code = self.normalize_search(asset_code).upper()
        row = self.db.fetch_one(
            self.base_query() + " WHERE d.asset_code = ?",
            (code,),
        )
        return None if row is None else self.row_to_summary(row)

    def find_by_isin(self, isin):
        normalized = "".join(self.normalize_search(isin).upper().split())
        row = self.db.fetch_one(
            self.base_query() + " WHERE d.isin = ?",
            (normalized,),
        )
        return None if row is None else self.row_to_summary(row)

    def search_by_issuer(self, issuer_name):
        term = self.normalize_search(issuer_name)
        rows = self.db.fetch_all(
            self.base_query()
            + " WHERE i.legal_name LIKE ? COLLATE NOCASE ORDER BY d.asset_code",
            ("%" + term + "%",),
        )
        return [self.row_to_summary(row) for row in rows]

    def current_values(self, debenture_id):
        rows = self.db.fetch_all(
            """
            SELECT
                o.field_name,
                o.value_type,
                o.value_text,
                o.value_numeric,
                o.value_date,
                o.value_boolean,
                o.unit,
                o.observed_at,
                o.confidence,
                s.code AS source_code
            FROM observations o
            JOIN sources s ON s.id = o.source_id
            WHERE o.debenture_id = ?
              AND o.id = (
                  SELECT o2.id
                  FROM observations o2
                  WHERE o2.debenture_id = o.debenture_id
                    AND o2.field_name = o.field_name
                  ORDER BY o2.observed_at DESC,
                           o2.collected_at DESC,
                           o2.id DESC
                  LIMIT 1
              )
            ORDER BY o.field_name
            """,
            (debenture_id,),
        )

        result = {}
        for row in rows:
            field_name = str(row["field_name"])
            result[field_name] = CurrentValue(
                field_name=field_name,
                value_type=str(row["value_type"]),
                value=self.row_value(row),
                unit=row["unit"],
                observed_at=str(row["observed_at"]),
                source_code=str(row["source_code"]),
                confidence=str(row["confidence"]),
            )
        return result

    def count_open_conflicts(self, debenture_id):
        row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM data_conflicts
            WHERE debenture_id = ?
              AND status = 'open'
            """,
            (debenture_id,),
        )
        return int(row["total"])

    def get_details(self, identifier, by="code"):
        if by == "code":
            debenture = self.find_by_code(identifier)
        elif by == "isin":
            debenture = self.find_by_isin(identifier)
        else:
            raise ValueError("Tipo de consulta invalido.")

        if debenture is None:
            return None

        return DebentureDetails(
            debenture=debenture,
            current_values=self.current_values(debenture.id),
            open_conflicts=self.count_open_conflicts(debenture.id),
        )

    def history(self, asset_code, field_name):
        debenture = self.find_by_code(asset_code)
        if debenture is None:
            return []

        field = self.normalize_search(field_name).strip().lower()
        rows = self.db.fetch_all(
            """
            SELECT
                o.field_name,
                o.value_type,
                o.value_text,
                o.value_numeric,
                o.value_date,
                o.value_boolean,
                o.unit,
                o.observed_at,
                o.confidence,
                s.code AS source_code
            FROM observations o
            JOIN sources s ON s.id = o.source_id
            WHERE o.debenture_id = ?
              AND o.field_name = ?
            ORDER BY o.observed_at DESC,
                     o.collected_at DESC,
                     o.id DESC
            """,
            (debenture.id, field),
        )

        return [
            CurrentValue(
                field_name=str(row["field_name"]),
                value_type=str(row["value_type"]),
                value=self.row_value(row),
                unit=row["unit"],
                observed_at=str(row["observed_at"]),
                source_code=str(row["source_code"]),
                confidence=str(row["confidence"]),
            )
            for row in rows
        ]

