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
