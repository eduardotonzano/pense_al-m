import csv
import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from debenture_search.services.debenture_query_service import (
    DebentureQueryService,
)


class DebentureExportService:
    """Exporta consultas consolidadas para CSV ou JSON."""

    DEFAULT_FIELDS = [
        "asset_code",
        "isin",
        "issuer_name",
        "issuer_cnpj",
        "issue_number",
        "series",
        "status",
        "data_emissao",
        "data_vencimento",
        "garantia",
        "classe",
        "quantidade_emitida",
        "quantidade_em_mercado",
        "valor_nominal",
        "indexador",
        "agente_fiduciario",
        "incentivada",
        "resgate_antecipado",
        "open_conflicts",
    ]

    HISTORY_FIELDS = [
        "asset_code",
        "field_name",
        "value_type",
        "value",
        "unit",
        "source_code",
        "observed_at",
        "confidence",
    ]

    def __init__(self, db, query_service=None):
        self.db = db
        self.query_service = query_service or DebentureQueryService(db)

    @staticmethod
    def serialize_value(value):
        """Converte valores para formatos portaveis sem perder precisao."""

        if isinstance(value, Decimal):
            return format(value, "f")
        if value is True:
            return "Sim"
        if value is False:
            return "Nao"
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def normalize_format(file_format):
        normalized = str(file_format or "").strip().lower()
        if normalized not in {"csv", "json"}:
            raise ValueError("Formato de exportacao invalido.")
        return normalized

    @staticmethod
    def prepare_path(path):
        candidate = Path(path)
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate

    def details_to_row(self, details):
        debenture = details.debenture
        row = {
            "asset_code": debenture.asset_code,
            "isin": debenture.isin,
            "issuer_name": debenture.issuer_name,
            "issuer_cnpj": debenture.issuer_cnpj,
            "issue_number": debenture.issue_number,
            "series": debenture.series,
            "status": debenture.status,
            "open_conflicts": details.open_conflicts,
        }

        for field_name, current in details.current_values.items():
            row[field_name] = self.serialize_value(current.value)

        return {
            field_name: self.serialize_value(row.get(field_name))
            for field_name in self.DEFAULT_FIELDS
        }

    def consolidated_rows(self, asset_code=None):
        if asset_code is not None:
            details = self.query_service.get_details(asset_code, by="code")
            if details is None:
                raise ValueError("Debenture nao encontrada.")
            return [self.details_to_row(details)]

        rows = []
        for summary in self.query_service.list_all():
            details = self.query_service.get_details(
                summary.asset_code,
                by="code",
            )
            if details is not None:
                rows.append(self.details_to_row(details))
        return rows

    def history_rows(self, asset_code=None):
        summaries = (
            [self.query_service.find_by_code(asset_code)]
            if asset_code is not None
            else self.query_service.list_all()
        )

        if asset_code is not None and summaries[0] is None:
            raise ValueError("Debenture nao encontrada.")

        rows = []
        for summary in summaries:
            observation_rows = self.db.fetch_all(
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
                ORDER BY o.field_name,
                         o.observed_at DESC,
                         o.collected_at DESC,
                         o.id DESC
                """,
                (summary.id,),
            )

            for record in observation_rows:
                rows.append(
                    {
                        "asset_code": summary.asset_code,
                        "field_name": str(record["field_name"]),
                        "value_type": str(record["value_type"]),
                        "value": self.serialize_value(
                            self.query_service.row_value(record)
                        ),
                        "unit": self.serialize_value(record["unit"]),
                        "source_code": str(record["source_code"]),
                        "observed_at": str(record["observed_at"]),
                        "confidence": str(record["confidence"]),
                    }
                )
        return rows

    def write_csv(self, rows, path, fieldnames):
        destination = self.prepare_path(path)
        with destination.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return destination

    def write_json(self, rows, path):
        destination = self.prepare_path(path)
        destination.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return destination

    def export(
        self,
        file_format,
        output_path,
        asset_code=None,
        history=False,
    ):
        normalized_format = self.normalize_format(file_format)
        rows = (
            self.history_rows(asset_code)
            if history
            else self.consolidated_rows(asset_code)
        )
        fieldnames = self.HISTORY_FIELDS if history else self.DEFAULT_FIELDS

        if normalized_format == "csv":
            path = self.write_csv(rows, output_path, fieldnames)
        else:
            path = self.write_json(rows, output_path)

        return {
            "path": path,
            "format": normalized_format,
            "history": bool(history),
            "rows": len(rows),
        }
