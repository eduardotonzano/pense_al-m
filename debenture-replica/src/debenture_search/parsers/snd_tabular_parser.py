import csv
import io
import unicodedata
from decimal import Decimal
from decimal import InvalidOperation

from debenture_search.parsers.snd_parser import ParsedDebenture
from debenture_search.parsers.snd_parser import ParsedObservation
from debenture_search.parsers.snd_parser import SndParser


class SndTabularParser:
    """Interpreta a resposta tabulada exportada pelo SND."""

    HEADER_MARKER = "codigo do ativo"

    COLUMN_MAPPING = {
        "codigo do ativo": "asset_code",
        "empresa": "issuer_legal_name",
        "serie": "series",
        "emissao": "issue_number",
        "situacao": "situacao",
        "isin": "isin",
        "data de emissao": "data_emissao",
        "data de vencimento": "data_vencimento",
        "garantia/especie": "garantia",
        "classe": "classe",
        "quantidade emitida": "quantidade_emitida",
        "quantidade em mercado": "quantidade_em_mercado",
        "valor nominal na emissao": "valor_nominal_emissao",
        "valor nominal atual": "valor_nominal",
        "indice": "indexador",
        "percentual multiplicador/rentabilidade": "spread",
        "agente fiduciario": "agente_fiduciario",
        "cnpj": "issuer_cnpj",
        "deb. incent. (lei 12.431)": "incentivada",
        "resgate antecipado": "resgate_antecipado",
    }

    DATE_FIELDS = {"data_emissao", "data_vencimento"}
    NUMERIC_FIELDS = {
        "quantidade_emitida",
        "quantidade_em_mercado",
        "valor_nominal_emissao",
        "valor_nominal",
        "spread",
    }
    BOOLEAN_FIELDS = {"incentivada", "resgate_antecipado"}

    @staticmethod
    def normalize_label(value):
        text = " ".join(str(value or "").replace("\xa0", " ").split())
        decomposed = unicodedata.normalize("NFKD", text)
        plain = "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )
        return plain.strip().casefold()

    @staticmethod
    def normalize_text(value):
        normalized = " ".join(str(value or "").replace("\xa0", " ").split())
        if normalized in {"", "-"}:
            return None
        return normalized

    @staticmethod
    def normalize_decimal(value):
        normalized = SndTabularParser.normalize_text(value)
        if normalized is None:
            return None

        cleaned = normalized.replace("R$", "").replace("%", "").strip()
        cleaned = cleaned.replace(".", "").replace(",", ".")
        cleaned = "".join(character for character in cleaned if character in "-+0123456789.")

        if cleaned in {"", "+", "-", "."}:
            return None

        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None

    @staticmethod
    def normalize_boolean(value):
        normalized = SndTabularParser.normalize_label(value)
        if normalized in {"s", "sim", "true", "1"}:
            return True
        if normalized in {"n", "nao", "false", "0"}:
            return False
        return None

    @classmethod
    def find_header_index(cls, lines):
        for index, line in enumerate(lines):
            first_column = line.split("\t", 1)[0]
            if cls.normalize_label(first_column) == cls.HEADER_MARKER:
                return index
        raise ValueError("A resposta do SND nao contem o cabecalho esperado.")

    @classmethod
    def read_rows(cls, document):
        if not isinstance(document, str):
            raise ValueError("A resposta tabular deve ser fornecida como texto.")
        if not document.strip():
            raise ValueError("A resposta tabular nao pode ficar vazia.")

        lines = [line for line in document.splitlines() if line.strip()]
        header_index = cls.find_header_index(lines)
        tabular_text = "\n".join(lines[header_index:])
        reader = csv.reader(io.StringIO(tabular_text), delimiter="\t")
        rows = list(reader)

        if len(rows) < 2:
            raise ValueError("A resposta do SND nao contem dados de ativos.")

        headers = [cls.normalize_label(item) for item in rows[0]]
        records = []

        for row in rows[1:]:
            if not any(str(item).strip() for item in row):
                continue
            padded = row + [""] * max(0, len(headers) - len(row))
            records.append(dict(zip(headers, padded[:len(headers)])))

        if not records:
            raise ValueError("A resposta do SND nao contem dados de ativos.")

        return records

    @classmethod
    def map_record(cls, record):
        mapped = {}
        for column, value in record.items():
            field_name = cls.COLUMN_MAPPING.get(column)
            if field_name is not None and field_name not in mapped:
                mapped[field_name] = value
        return mapped

    @classmethod
    def build_observations(cls, mapped):
        identity_fields = {
            "asset_code",
            "isin",
            "issuer_legal_name",
            "issuer_cnpj",
            "issue_number",
            "series",
            "situacao",
        }
        observations = []

        for field_name, raw_value in mapped.items():
            if field_name in identity_fields:
                continue

            if field_name in cls.DATE_FIELDS:
                value = SndParser.normalize_date(raw_value)
                if value is not None:
                    observations.append(ParsedObservation(field_name, "date", value))
                continue

            if field_name in cls.NUMERIC_FIELDS:
                value = cls.normalize_decimal(raw_value)
                if value is None:
                    continue
                unit = None
                if field_name == "spread":
                    unit = "percentual"
                elif field_name.startswith("valor_nominal"):
                    unit = "BRL"
                elif field_name.startswith("quantidade_"):
                    unit = "titulos"
                observations.append(
                    ParsedObservation(field_name, "numeric", value, unit)
                )
                continue

            if field_name in cls.BOOLEAN_FIELDS:
                value = cls.normalize_boolean(raw_value)
                if value is not None:
                    observations.append(ParsedObservation(field_name, "boolean", value))
                continue

            value = cls.normalize_text(raw_value)
            if value is not None:
                observations.append(ParsedObservation(field_name, "text", value))

        return tuple(observations)

    @classmethod
    def parse_record(cls, record):
        mapped = cls.map_record(record)
        asset_code = SndParser.normalize_asset_code(mapped.get("asset_code"))
        isin = SndParser.normalize_isin(mapped.get("isin"))

        if asset_code is None and isin is None:
            raise ValueError("O registro nao contem codigo do ativo nem ISIN valido.")

        return ParsedDebenture(
            asset_code=asset_code,
            isin=isin,
            issuer_legal_name=cls.normalize_text(mapped.get("issuer_legal_name")),
            issuer_cnpj=SndParser.normalize_cnpj(mapped.get("issuer_cnpj")),
            issue_number=cls.normalize_text(mapped.get("issue_number")),
            series=cls.normalize_text(mapped.get("series")),
            status=SndParser.infer_debenture_status(mapped.get("situacao")),
            observations=cls.build_observations(mapped),
        )

    @classmethod
    def parse_all(cls, document):
        return tuple(cls.parse_record(record) for record in cls.read_rows(document))

    @classmethod
    def parse(cls, document, asset_code=None):
        parsed_records = cls.parse_all(document)

        if asset_code is None:
            if len(parsed_records) != 1:
                raise ValueError("A resposta contem mais de um ativo; informe o codigo desejado.")
            return parsed_records[0]

        normalized_code = SndParser.normalize_asset_code(asset_code)
        for record in parsed_records:
            if record.asset_code == normalized_code:
                return record

        raise ValueError("O ativo solicitado nao foi encontrado na resposta do SND.")
