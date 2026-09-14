import html
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from decimal import InvalidOperation


@dataclass(frozen=True)
class ParsedObservation:
    """Representa um campo extraido do HTML do SND."""

    field_name: str
    value_type: str
    value: object
    unit: str | None = None
    confidence: str = "reported"


@dataclass(frozen=True)
class ParsedDebenture:
    """Representa os dados estruturados extraidos do SND."""

    asset_code: str | None
    isin: str | None
    issuer_legal_name: str | None
    issuer_cnpj: str | None
    issue_number: str | None
    series: str | None
    status: str
    observations: tuple


class SndParser:
    """Extrai dados de uma pagina de caracteristicas do SND."""

    LABEL_MAPPING = {
        "codigo do ativo": "asset_code",
        "codigo": "asset_code",
        "ativo": "asset_code",
        "isin": "isin",
        "emissor": "issuer_legal_name",
        "razao social": "issuer_legal_name",
        "cnpj": "issuer_cnpj",
        "numero da emissao": "issue_number",
        "emissao": "issue_number",
        "serie": "series",
        "indexador": "indexador",
        "remuneracao": "spread",
        "taxa": "spread",
        "spread": "spread",
        "garantia": "garantia",
        "classe": "classe",
        "quantidade emitida": "quantidade_emitida",
        "quantidade em mercado": "quantidade_em_mercado",
        "quantidade em circulacao": "quantidade_em_mercado",
        "valor nominal": "valor_nominal",
        "agente fiduciario": "agente_fiduciario",
        "situacao": "situacao",
        "status": "situacao",
        "rating": "rating",
        "data de emissao": "data_emissao",
        "vencimento": "data_vencimento",
        "data de vencimento": "data_vencimento",
    }

    DATE_FIELDS = {
        "data_emissao",
        "data_vencimento",
    }

    NUMERIC_FIELDS = {
        "spread",
        "quantidade_emitida",
        "quantidade_em_mercado",
        "valor_nominal",
    }

    @staticmethod
    def normalize_space(value):
        """Remove tags, entidades HTML e espacos repetidos."""

        without_tags = re.sub(r"<[^>]+>", " ", str(value))
        decoded = html.unescape(without_tags)
        return " ".join(decoded.replace("\xa0", " ").split())

    @staticmethod
    def normalize_label(value):
        """Normaliza rotulos para comparacao."""

        text = SndParser.normalize_space(value).strip(" :-")
        decomposed = unicodedata.normalize("NFKD", text)
        without_accents = "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )
        return without_accents.casefold()

    @staticmethod
    def normalize_asset_code(value):
        """Normaliza o codigo do ativo."""

        normalized = "".join(
            SndParser.normalize_space(value).upper().split()
        )
        return normalized or None

    @staticmethod
    def normalize_isin(value):
        """Normaliza o ISIN sem aceitar formato invalido."""

        normalized = "".join(
            SndParser.normalize_space(value).upper().split()
        )

        if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{10}", normalized):
            return normalized

        return None

    @staticmethod
    def normalize_cnpj(value):
        """Mantem somente os 14 digitos de um CNPJ valido em formato."""

        digits = "".join(
            character
            for character in str(value)
            if character.isdigit()
        )

        if len(digits) == 14:
            return digits

        return None

    @staticmethod
    def normalize_date(value):
        """Converte DD/MM/AAAA para AAAA-MM-DD."""

        normalized = SndParser.normalize_space(value)
        match = re.search(
            r"\b(\d{2})/(\d{2})/(\d{4})\b",
            normalized,
        )

        if match is None:
            return None

        day, month, year = match.groups()
        return year + "-" + month + "-" + day

    @staticmethod
    def normalize_decimal(value):
        """Converte numero brasileiro para Decimal."""

        normalized = SndParser.normalize_space(value)
        match = re.search(
            r"[-+]?\d[\d.]*?(?:,\d+)?(?=\s|%|$)",
            normalized,
        )

        if match is None:
            return None

        number = match.group(0).replace(".", "").replace(",", ".")

        try:
            return Decimal(number)
        except InvalidOperation:
            return None

    @staticmethod
    def extract_pairs(document):
        """Extrai pares de rotulo e valor de tabelas e definition lists."""

        pairs = []

        row_pattern = re.compile(
            r"<tr\b[^>]*>\s*"
            r"<(?:th|td)\b[^>]*>(.*?)</(?:th|td)>\s*"
            r"<td\b[^>]*>(.*?)</td>\s*"
            r"</tr>",
            re.IGNORECASE | re.DOTALL,
        )

        for label, value in row_pattern.findall(document):
            clean_label = SndParser.normalize_space(label)
            clean_value = SndParser.normalize_space(value)

            if clean_label and clean_value:
                pairs.append((clean_label, clean_value))

        definition_pattern = re.compile(
            r"<dt\b[^>]*>(.*?)</dt>\s*"
            r"<dd\b[^>]*>(.*?)</dd>",
            re.IGNORECASE | re.DOTALL,
        )

        for label, value in definition_pattern.findall(document):
            clean_label = SndParser.normalize_space(label)
            clean_value = SndParser.normalize_space(value)

            if clean_label and clean_value:
                pairs.append((clean_label, clean_value))

        return pairs

    @classmethod
    def map_pairs(cls, pairs):
        """Mapeia rotulos conhecidos para campos internos."""

        mapped = {}

        for label, value in pairs:
            normalized_label = cls.normalize_label(label)
            field_name = cls.LABEL_MAPPING.get(normalized_label)

            if field_name is not None and field_name not in mapped:
                mapped[field_name] = cls.normalize_space(value)

        return mapped

    @staticmethod
    def infer_debenture_status(value):
        """Converte a situacao textual para o status interno."""

        if value is None:
            return "unknown"

        normalized = SndParser.normalize_label(value)

        if "ativa" in normalized or "em circulacao" in normalized:
            return "active"

        if "vencida" in normalized:
            return "matured"

        if "cancelada" in normalized:
            return "cancelled"

        if "inativa" in normalized or "encerrada" in normalized:
            return "inactive"

        return "unknown"

    @classmethod
    def build_observations(cls, mapped):
        """Transforma campos de caracteristicas em observacoes."""

        ignored = {
            "asset_code",
            "isin",
            "issuer_legal_name",
            "issuer_cnpj",
            "issue_number",
            "series",
        }
        observations = []

        for field_name, raw_value in mapped.items():
            if field_name in ignored:
                continue

            if field_name in cls.DATE_FIELDS:
                value = cls.normalize_date(raw_value)

                if value is not None:
                    observations.append(
                        ParsedObservation(field_name, "date", value)
                    )
                continue

            if field_name in cls.NUMERIC_FIELDS:
                value = cls.normalize_decimal(raw_value)

                if value is None:
                    continue

                unit = None

                if field_name == "spread":
                    unit = "percentual"
                elif field_name == "valor_nominal":
                    unit = "BRL"
                elif field_name.startswith("quantidade_"):
                    unit = "titulos"

                observations.append(
                    ParsedObservation(
                        field_name,
                        "numeric",
                        value,
                        unit,
                    )
                )
                continue

            value = cls.normalize_space(raw_value)

            if value:
                observations.append(
                    ParsedObservation(field_name, "text", value)
                )

        return tuple(observations)

    @classmethod
    def parse(cls, document):
        """Analisa uma pagina HTML e retorna dados estruturados."""

        if not isinstance(document, str):
            raise ValueError("O HTML deve ser fornecido como texto.")

        if not document.strip():
            raise ValueError("O HTML nao pode ficar vazio.")

        pairs = cls.extract_pairs(document)
        mapped = cls.map_pairs(pairs)

        asset_code = cls.normalize_asset_code(
            mapped.get("asset_code")
        )
        isin = cls.normalize_isin(mapped.get("isin"))

        if asset_code is None and isin is None:
            raise ValueError(
                "A pagina nao contem codigo do ativo nem ISIN valido."
            )

        issuer_name = cls.normalize_space(
            mapped.get("issuer_legal_name", "")
        ) or None
        issuer_cnpj = cls.normalize_cnpj(
            mapped.get("issuer_cnpj", "")
        )
        issue_number = cls.normalize_space(
            mapped.get("issue_number", "")
        ) or None
        series = cls.normalize_space(
            mapped.get("series", "")
        ) or None
        status = cls.infer_debenture_status(
            mapped.get("situacao")
        )

        return ParsedDebenture(
            asset_code=asset_code,
            isin=isin,
            issuer_legal_name=issuer_name,
            issuer_cnpj=issuer_cnpj,
            issue_number=issue_number,
            series=series,
            status=status,
            observations=cls.build_observations(mapped),
        )
