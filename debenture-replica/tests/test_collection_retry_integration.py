from types import SimpleNamespace

import pytest

from debenture_search.services.retry_policy import RetryPolicy


class HttpError(RuntimeError):
    def __init__(self, status_code):
        super().__init__("http error")
        self.response = SimpleNamespace(status_code=status_code)


class Provider:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def collect(self, code):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def collect_with_policy(provider, policy, sleep, code="PETR27"):
    events = []
    for attempt in range(1, policy.max_attempts + 1):
        try:
            result = provider.collect(code)
            events.append(("success", attempt))
            return result, events
        except Exception as error:
            decision = policy.classify(error)
            events.append(
                (
                    "failure",
                    attempt,
                    decision.category,
                    decision.retryable,
                    decision.http_status,
                )
            )
            if not policy.should_retry(error, attempt):
                raise
            delay = policy.delay_for_attempt(attempt)
            events.append(("retry_scheduled", attempt, delay))
            sleep(delay)
    raise AssertionError("fluxo de retry inconsistente")


def success_result():
    return SimpleNamespace(
        observations_created=0,
        observations_reused=12,
        conflicts_created=0,
    )


def test_timeout_then_success_retries_once():
    provider = Provider([TimeoutError("timeout"), success_result()])
    sleeps = []
    result, events = collect_with_policy(
        provider,
        RetryPolicy(max_attempts=2, base_delay_seconds=1),
        sleeps.append,
    )
    assert provider.calls == 2
    assert sleeps == [1]
    assert result.observations_reused == 12
    assert events[-1] == ("success", 2)


def test_http_503_then_success_retries():
    provider = Provider([HttpError(503), success_result()])
    sleeps = []
    result, events = collect_with_policy(
        provider,
        RetryPolicy(max_attempts=2),
        sleeps.append,
    )
    assert provider.calls == 2
    assert events[0][2] == "transient_http"
    assert events[0][4] == 503


def test_http_404_does_not_retry():
    provider = Provider([HttpError(404), success_result()])
    sleeps = []
    with pytest.raises(HttpError):
        collect_with_policy(
            provider,
            RetryPolicy(max_attempts=3),
            sleeps.append,
        )
    assert provider.calls == 1
    assert sleeps == []


def test_parse_error_does_not_retry():
    class ParseError(RuntimeError):
        pass

    provider = Provider([ParseError("formato invalido"), success_result()])
    with pytest.raises(ParseError):
        collect_with_policy(
            provider,
            RetryPolicy(max_attempts=3),
            lambda seconds: None,
        )
    assert provider.calls == 1


def test_final_timeout_is_raised_after_limit():
    provider = Provider(
        [
            TimeoutError("timeout 1"),
            TimeoutError("timeout 2"),
            TimeoutError("timeout 3"),
        ]
    )
    sleeps = []
    with pytest.raises(TimeoutError, match="timeout 3"):
        collect_with_policy(
            provider,
            RetryPolicy(max_attempts=3, base_delay_seconds=0.5),
            sleeps.append,
        )
    assert provider.calls == 3
    assert sleeps == [0.5, 1.0]


def test_max_attempts_one_preserves_current_safe_behavior():
    provider = Provider([TimeoutError("timeout"), success_result()])
    with pytest.raises(TimeoutError):
        collect_with_policy(
            provider,
            RetryPolicy(max_attempts=1),
            lambda seconds: None,
        )
    assert provider.calls == 1
