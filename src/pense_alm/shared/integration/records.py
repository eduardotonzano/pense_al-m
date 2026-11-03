"""Registros intermediarios de integracao."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DebentureIssuerRecord:
    """Representacao neutra de um emissor legado."""

    legacy_id: int
    legal_name: str
    created_at: str
    updated_at: str
    cnpj: str | None = None
    trade_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.legacy_id, int):
            raise TypeError(
                "legacy_id deve ser inteiro."
            )

        if self.legacy_id <= 0:
            raise ValueError(
                "legacy_id deve ser maior que zero."
            )

        if not isinstance(self.legal_name, str):
            raise TypeError(
                "legal_name deve ser texto."
            )

        normalized_name = " ".join(
            self.legal_name.split()
        )

        if not normalized_name:
            raise ValueError(
                "legal_name nao pode ser vazio."
            )

        object.__setattr__(
            self,
            "legal_name",
            normalized_name,
        )

        normalized_trade_name = self._normalize_optional_text(
            self.trade_name,
            "trade_name",
        )

        object.__setattr__(
            self,
            "trade_name",
            normalized_trade_name,
        )

        if self.cnpj is not None:
            if not isinstance(self.cnpj, str):
                raise TypeError(
                    "cnpj deve ser texto."
                )

            normalized_cnpj = "".join(
                character
                for character in self.cnpj
                if character.isdigit()
            )

            if len(normalized_cnpj) != 14:
                raise ValueError(
                    "cnpj deve conter 14 digitos."
                )

            object.__setattr__(
                self,
                "cnpj",
                normalized_cnpj,
            )

        for field_name in (
            "created_at",
            "updated_at",
        ):
            value = getattr(self, field_name)

            if not isinstance(value, str):
                raise TypeError(
                    f"{field_name} deve ser texto."
                )

            if not value.strip():
                raise ValueError(
                    f"{field_name} nao pode ser vazio."
                )

    @staticmethod
    def _normalize_optional_text(
        value: str | None,
        field_name: str,
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise TypeError(
                f"{field_name} deve ser texto."
            )

        normalized = " ".join(value.split())

        return normalized or None


_INSTRUMENT_STATUSES = frozenset(
    {
        "unknown",
        "active",
        "inactive",
        "matured",
        "cancelled",
    }
)


@dataclass(frozen=True, slots=True)
class DebentureInstrumentRecord:
    """Representacao neutra de uma debenture legada."""

    legacy_id: int
    created_at: str
    updated_at: str
    asset_code: str | None = None
    isin: str | None = None
    status: str = "unknown"
    issuer_legacy_id: int | None = None
    issuer_cnpj: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.legacy_id, int):
            raise TypeError(
                "legacy_id deve ser inteiro."
            )

        if self.legacy_id <= 0:
            raise ValueError(
                "legacy_id deve ser maior que zero."
            )

        asset_code = self._normalize_identifier(
            self.asset_code,
            "asset_code",
        )
        isin = self._normalize_identifier(
            self.isin,
            "isin",
        )

        if isin is not None and (
            len(isin) != 12 or not isin.isalnum()
        ):
            raise ValueError(
                "isin deve conter 12 caracteres alfanumericos."
            )

        if asset_code is None and isin is None:
            raise ValueError(
                "A debenture exige asset_code ou isin."
            )

        object.__setattr__(self, "asset_code", asset_code)
        object.__setattr__(self, "isin", isin)

        if not isinstance(self.status, str):
            raise TypeError(
                "status deve ser texto."
            )

        status = self.status.strip().lower()

        if status not in _INSTRUMENT_STATUSES:
            raise ValueError(
                "status legado desconhecido."
            )

        object.__setattr__(self, "status", status)

        if self.issuer_legacy_id is not None:
            if not isinstance(self.issuer_legacy_id, int):
                raise TypeError(
                    "issuer_legacy_id deve ser inteiro."
                )

            if self.issuer_legacy_id <= 0:
                raise ValueError(
                    "issuer_legacy_id deve ser maior que zero."
                )

        if self.issuer_cnpj is not None:
            if not isinstance(self.issuer_cnpj, str):
                raise TypeError(
                    "issuer_cnpj deve ser texto."
                )

            if self.issuer_legacy_id is None:
                raise ValueError(
                    "issuer_cnpj exige issuer_legacy_id."
                )

            normalized_cnpj = "".join(
                character
                for character in self.issuer_cnpj
                if character.isdigit()
            )

            if len(normalized_cnpj) != 14:
                raise ValueError(
                    "issuer_cnpj deve conter 14 digitos."
                )

            object.__setattr__(
                self,
                "issuer_cnpj",
                normalized_cnpj,
            )

        for field_name in (
            "created_at",
            "updated_at",
        ):
            value = getattr(self, field_name)

            if not isinstance(value, str):
                raise TypeError(
                    f"{field_name} deve ser texto."
                )

            if not value.strip():
                raise ValueError(
                    f"{field_name} nao pode ser vazio."
                )

    @staticmethod
    def _normalize_identifier(
        value: str | None,
        field_name: str,
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise TypeError(
                f"{field_name} deve ser texto."
            )

        normalized = value.strip().upper()

        if not normalized:
            return None

        if any(character.isspace() for character in normalized):
            raise ValueError(
                f"{field_name} nao pode conter espacos."
            )

        return normalized
