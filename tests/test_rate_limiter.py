import time

from app.api.rate_limiter import RateLimiter


def test_allows_up_to_max_requests():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.allow("a") is True
    assert limiter.allow("a") is True
    assert limiter.allow("a") is True


def test_rejects_once_over_max():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.allow("a") is True
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False


def test_different_keys_are_independent():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("a") is True
    assert limiter.allow("b") is True
    assert limiter.allow("a") is False
    assert limiter.allow("b") is False


def test_old_entries_expire_out_of_the_window():
    limiter = RateLimiter(max_requests=1, window_seconds=0.05)
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False
    time.sleep(0.1)
    assert limiter.allow("a") is True
