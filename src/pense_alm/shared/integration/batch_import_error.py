"""Detalhes auditaveis de erros da importacao em lote."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BatchImportError:
    """Erro ocorrido durante a importacao de um registro."""

    legacy_id: int | None
    error_type: str
    message: str

    def __post_init__(self) -> None:
        if (
            self.legacy_id is not None
            and not isinstance(self.legacy_id, int)
        ):
            raise TypeError(
                "legacy_id deve ser inteiro ou None."
            )

        if (
            self.legacy_id is not None
            and self.legacy_id <= 0
        ):
            raise ValueError(
                "legacy_id deve ser maior que zero."
            )

        if not isinstance(self.error_type, str):
            raise TypeError(
                "error_type deve ser texto."
            )

        normalized_error_type = self.error_type.strip()

        if not normalized_error_type:
            raise ValueError(
                "error_type nao pode ser vazio."
            )

        if not isinstance(self.message, str):
            raise TypeError(
                "message deve ser texto."
            )

        normalized_message = " ".join(
            self.message.split()
        )

        if not normalized_message:
            raise ValueError(
                "message nao pode ser vazia."
            )

        object.__setattr__(
            self,
            "error_type",
            normalized_error_type,
        )
        object.__setattr__(
            self,
            "message",
            normalized_message,
        )
