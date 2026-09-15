import errno
import sqlite3
from dataclasses import dataclass


RETRYABLE_HTTP_STATUS = frozenset({429, 502, 503, 504})
NON_RETRYABLE_HTTP_STATUS = frozenset({400, 401, 403, 404})
RETRYABLE_ERRNO = frozenset(
    {
        errno.ECONNABORTED,
        errno.ECONNREFUSED,
        errno.ECONNRESET,
        errno.ENETDOWN,
        errno.ENETRESET,
        errno.ENETUNREACH,
        errno.ETIMEDOUT,
    }
)


@dataclass(frozen=True)
class RetryDecision:
    retryable: bool
    category: str
    reason: str
    http_status: int | None = None


class RetryPolicy:
    """Classifica falhas e calcula esperas limitadas entre tentativas."""

    def __init__(
        self,
        max_attempts=1,
        base_delay_seconds=2.0,
        max_delay_seconds=30.0,
    ):
        self.max_attempts = int(max_attempts)
        self.base_delay_seconds = float(base_delay_seconds)
        self.max_delay_seconds = float(max_delay_seconds)

        if self.max_attempts < 1 or self.max_attempts > 3:
            raise ValueError("max_attempts deve ficar entre 1 e 3.")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds nao pode ser negativo.")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError(
                "max_delay_seconds nao pode ser menor que base_delay_seconds."
            )

    @staticmethod
    def extract_http_status(error):
        """Extrai o status HTTP de excecoes sem depender de uma biblioteca."""

        for attribute in ("status_code", "status", "http_status"):
            value = getattr(error, attribute, None)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass

        response = getattr(error, "response", None)
        if response is not None:
            value = getattr(response, "status_code", None)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass

        return None

    @staticmethod
    def _is_timeout(error):
        if isinstance(error, TimeoutError):
            return True
        name = type(error).__name__.casefold()
        return "timeout" in name or "timedout" in name

    @staticmethod
    def _is_connection_error(error):
        if isinstance(error, ConnectionError):
            return True
        if isinstance(error, OSError) and error.errno in RETRYABLE_ERRNO:
            return True
        name = type(error).__name__.casefold()
        return name in {
            "connectionerror",
            "connecterror",
            "connectionreseterror",
            "connectionabortederror",
        }

    @staticmethod
    def _is_non_retryable_domain_error(error):
        if isinstance(error, (ValueError, sqlite3.Error)):
            return True
        name = type(error).__name__.casefold()
        markers = (
            "parse",
            "validation",
            "integrity",
            "format",
            "assetnotfound",
            "invalidasset",
        )
        return any(marker in name for marker in markers)

    def classify(self, error):
        status = self.extract_http_status(error)

        if status in RETRYABLE_HTTP_STATUS:
            return RetryDecision(
                True,
                "transient_http",
                "Status HTTP temporario.",
                status,
            )

        if status is not None:
            return RetryDecision(
                False,
                "permanent_http",
                "Status HTTP nao elegivel para retry.",
                status,
            )

        if self._is_timeout(error):
            return RetryDecision(
                True,
                "timeout",
                "Tempo limite excedido.",
            )

        if self._is_connection_error(error):
            return RetryDecision(
                True,
                "connection",
                "Falha temporaria de conexao.",
            )

        if self._is_non_retryable_domain_error(error):
            return RetryDecision(
                False,
                "permanent_application",
                "Erro de validacao, parsing, integridade ou banco.",
            )

        return RetryDecision(
            False,
            "unknown",
            "Erro nao classificado como transitorio.",
        )

    def delay_for_attempt(self, attempt):
        """Retorna backoff exponencial antes da tentativa seguinte."""

        current = int(attempt)
        if current < 1:
            raise ValueError("attempt deve ser maior que zero.")
        delay = self.base_delay_seconds * (2 ** (current - 1))
        return min(delay, self.max_delay_seconds)

    def should_retry(self, error, attempt):
        """Decide considerando a categoria e o limite de tentativas."""

        current = int(attempt)
        if current < 1:
            raise ValueError("attempt deve ser maior que zero.")
        decision = self.classify(error)
        return decision.retryable and current < self.max_attempts
