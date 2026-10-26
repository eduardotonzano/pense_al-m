"""Leitura de timestamps de bancos legados."""

from datetime import UTC, datetime


def parse_legacy_datetime(
    value: str,
) -> datetime:
    """Converte timestamps SQLite legados para UTC."""

    if not isinstance(value, str):
        raise TypeError(
            "Timestamp legado deve ser texto."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            "Timestamp legado nao pode ser vazio."
        )

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(
            "Timestamp legado invalido."
        ) from error

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)
