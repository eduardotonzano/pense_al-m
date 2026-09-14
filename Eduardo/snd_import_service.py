from dataclasses import asdict

from debenture_search.parsers.snd_parser import SndParser
from debenture_search.services.ingestion_service import IngestionService


class SndImportService:
    """Converte HTML do SND e envia os dados para a ingestao."""

    def __init__(self, db, parser=None, ingestion_service=None):
        self.db = db
        self.parser = parser or SndParser()
        self.ingestion = ingestion_service or IngestionService(db)

    @staticmethod
    def normalize_html(document):
        """Valida o documento HTML recebido."""

        if not isinstance(document, str):
            raise ValueError(
                "O HTML do SND deve ser fornecido como texto."
            )

        if not document.strip():
            raise ValueError(
                "O HTML do SND nao pode ficar vazio."
            )

        return document

    @staticmethod
    def observation_to_dict(observation, observed_at=None):
        """Converte uma observacao do parser para a ingestao."""

        result = {
            "field_name": observation.field_name,
            "value_type": observation.value_type,
            "value": observation.value,
            "confidence": observation.confidence,
        }

        if observation.unit is not None:
            result["unit"] = observation.unit

        if observed_at is not None:
            result["observed_at"] = observed_at

        return result

    def import_html(
        self,
        document,
        request_url=None,
        request_parameters=None,
        http_status=200,
        parser_version="1.0.0",
        observed_at=None,
        actor="snd_import_service",
    ):
        """Executa parsing e ingestao de uma pagina do SND."""

        normalized_html = self.normalize_html(document)
        parsed = self.parser.parse(normalized_html)

        observations = [
            self.observation_to_dict(item, observed_at)
            for item in parsed.observations
        ]

        return self.ingestion.ingest(
            source_code="SND",
            payload=normalized_html,
            asset_code=parsed.asset_code,
            isin=parsed.isin,
            issuer_legal_name=parsed.issuer_legal_name,
            issuer_cnpj=parsed.issuer_cnpj,
            issue_number=parsed.issue_number,
            series=parsed.series,
            debenture_status=parsed.status,
            observations=observations,
            request_url=request_url,
            request_parameters=request_parameters,
            content_type="text/html",
            http_status=http_status,
            parser_version=parser_version,
            actor=actor,
        )
