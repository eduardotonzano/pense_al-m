from datetime import datetime, timezone

from debenture_search.parsers.snd_parser import SndParser
from debenture_search.parsers.snd_tabular_parser import SndTabularParser
from debenture_search.services.ingestion_service import IngestionService


class SndImportService:
    # D-08: campos de identificacao gravados tambem como observacoes, para
    # terem fonte e data de observacao. Nenhum vira coluna do export: ele so
    # emite DEFAULT_FIELDS e, nas chaves de identificacao (inclusive "isin",
    # que tem o mesmo nome), mantem o valor de debentures/issuers.
    # "emissor" e a razao social (issuers.legal_name), nao o nome fantasia.
    IDENTITY_OBSERVATIONS = (
        ("codigo_ativo", "asset_code"),
        ("isin", "isin"),
        ("emissor", "issuer_legal_name"),
        ("cnpj_emissor", "issuer_cnpj"),
    )

    def __init__(self, db, ingestion_service=None):
        self.db = db
        self.ingestion = ingestion_service or IngestionService(db)

    @staticmethod
    def _observations(parsed, observed_at):
        result = []
        for item in parsed.observations:
            data = {"field_name": item.field_name, "value_type": item.value_type,
                    "value": item.value, "confidence": item.confidence}
            if item.unit is not None:
                data["unit"] = item.unit
            data["observed_at"] = observed_at
            result.append(data)
        for field_name, attribute in SndImportService.IDENTITY_OBSERVATIONS:
            value = getattr(parsed, attribute, None)
            if value:
                result.append({"field_name": field_name, "value_type": "text",
                               "value": value, "observed_at": observed_at,
                               "confidence": "reported"})
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
        # Um unico instante para todas as observacoes do documento.
        observed_at = (kwargs.get("observed_at")
                       or datetime.now(timezone.utc).isoformat())
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
