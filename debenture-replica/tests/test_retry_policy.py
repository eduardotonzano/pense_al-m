import sqlite3
from types import SimpleNamespace

import pytest

from debenture_search.services.retry_policy import RetryPolicy


class HttpError(RuntimeError):
    def __init__(self, status_code):
        super().__init__("http error")
        self.response = SimpleNamespace(status_code=status_code)


class ParseError(RuntimeError):
    pass


@pytest.mark.parametrize("status", [429, 502, 503, 504])
def test_retryable_http_statuses(status):
    decision = RetryPolicy().classify(HttpError(status))
    assert decision.retryable is True
    assert decision.category == "transient_http"
    assert decision.http_status == status


@pytest.mark.parametrize("status", [400, 401, 403, 404, 500])
def test_non_retryable_http_statuses(status):
    decision = RetryPolicy().classify(HttpError(status))
    assert decision.retryable is False
    assert decision.category == "permanent_http"


def test_timeout_is_retryable():
    decision = RetryPolicy().classify(TimeoutError("tempo esgotado"))
    assert decision.retryable is True
    assert decision.category == "timeout"


def test_connection_error_is_retryable():
    decision = RetryPolicy().classify(ConnectionError("conexao caiu"))
    assert decision.retryable is True
    assert decision.category == "connection"


def test_value_error_is_not_retryable():
    decision = RetryPolicy().classify(ValueError("ativo invalido"))
    assert decision.retryable is False
    assert decision.category == "permanent_application"


def test_parse_error_is_not_retryable():
    decision = RetryPolicy().classify(ParseError("layout invalido"))
    assert decision.retryable is False
    assert decision.category == "permanent_application"


def test_sqlite_error_is_not_retryable():
    decision = RetryPolicy().classify(sqlite3.OperationalError("database locked"))
    assert decision.retryable is False
    assert decision.category == "permanent_application"


def test_unknown_error_is_not_retryable():
    decision = RetryPolicy().classify(RuntimeError("erro desconhecido"))
    assert decision.retryable is False
    assert decision.category == "unknown"


def test_should_retry_respects_attempt_limit():
    policy = RetryPolicy(max_attempts=3)
    error = TimeoutError("timeout")
    assert policy.should_retry(error, 1) is True
    assert policy.should_retry(error, 2) is True
    assert policy.should_retry(error, 3) is False


def test_non_retryable_error_never_retries():
    policy = RetryPolicy(max_attempts=3)
    assert policy.should_retry(ValueError("invalido"), 1) is False


def test_exponential_delay_is_capped():
    policy = RetryPolicy(
        max_attempts=3,
        base_delay_seconds=2,
        max_delay_seconds=3,
    )
    assert policy.delay_for_attempt(1) == 2
    assert policy.delay_for_attempt(2) == 3


def test_rejects_invalid_configuration():
    with pytest.raises(ValueError, match="entre 1 e 3"):
        RetryPolicy(max_attempts=4)
    with pytest.raises(ValueError, match="nao pode ser negativo"):
        RetryPolicy(base_delay_seconds=-1)
