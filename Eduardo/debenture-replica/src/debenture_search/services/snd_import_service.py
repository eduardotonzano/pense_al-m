from debenture_search.parsers.snd_parser import SndParser
from debenture_search.parsers.snd_tabular_parser import SndTabularParser
from debenture_search.services.ingestion_service import IngestionService


class SndImportService:
    def __init__(self, db, ingestion_service=None):
        self.db = db
        self.ingestion = ingestion_service or IngestionService(db)

    @staticmethod
    def _observations(parsed, observed_at=None):
        result = []
        for item in parsed.observations:
            data = {"field_name": item.field_name, "value_type": item.value_type,
                    "value": item.value, "confidence": item.confidence}
            if item.unit is not None:
                data["unit"] = item.unit
            if observed_at is not None:
                data["observed_at"] = observed_at
            result.append(data)
        return result

    def import_document(self, document, asset_code=None, content_type=None, **kwargs):
        if not isinstance(document, str):
            raise ValueError("O documento do SND deve ser fornecido como texto.")
        if not document.strip():
            raise ValueError("O documento do SND nao pode ficar vazio.")
        content_type = str(content_type or "").lower()
        is_tabular = (content_type in {"application/vnd.ms-excel", "text/plain"}
                      or ("	" in document and "codigo do ativo" in document.lower()))
        parsed = (SndTabularParser.parse(document, asset_code)
                  if is_tabular else SndParser.parse(document))
        ingestion_keys = {"request_url", "request_parameters", "http_status",
                          "parser_version", "actor"}
        ingestion_args = {key: value for key, value in kwargs.items()
                          if key in ingestion_keys}
        observed_at = kwargs.get("observed_at")
        return self.ingestion.ingest(
            source_code="SND", payload=document, asset_code=parsed.asset_code,
            isin=parsed.isin, issuer_legal_name=parsed.issuer_legal_name,
            issuer_cnpj=parsed.issuer_cnpj, issue_number=parsed.issue_number,
            series=parsed.series, debenture_status=parsed.status,
            observations=self._observations(parsed, observed_at),
            content_type=content_type or ("text/plain" if is_tabular else "text/html"),
            **ingestion_args)

    def import_html(self, document, **kwargs):
        return self.import_document(document, content_type="text/html", **kwargs)
