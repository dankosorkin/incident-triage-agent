import random
from datetime import datetime

from app.sql.seed_data import (
    SEVERITY_WEIGHTS,
    STATUS_WEIGHTS,
    generate_incident,
    random_datetime,
    weighted_choice,
)


def test_random_datetime_stays_within_bounds():
    random.seed(0)
    start = datetime(2025, 1, 1)
    end = datetime(2025, 1, 2)
    for _ in range(200):
        result = random_datetime(start, end)
        assert start <= result <= end


def test_random_datetime_same_bounds_returns_that_instant():
    same = datetime(2025, 6, 1, 12, 0, 0)
    assert random_datetime(same, same) == same


def test_weighted_choice_only_returns_known_keys():
    random.seed(1)
    weights = {"a": 0.9, "b": 0.1}
    results = {weighted_choice(weights) for _ in range(100)}
    assert results <= {"a", "b"}


def test_weighted_choice_deterministic_with_fixed_seed():
    random.seed(42)
    first_run = [weighted_choice(SEVERITY_WEIGHTS) for _ in range(10)]
    random.seed(42)
    second_run = [weighted_choice(SEVERITY_WEIGHTS) for _ in range(10)]
    assert first_run == second_run


def test_generate_incident_has_valid_severity_and_status():
    random.seed(7)
    incident = generate_incident(1)
    assert incident["severity"] in SEVERITY_WEIGHTS
    assert incident["status"] in STATUS_WEIGHTS


def test_generate_incident_open_status_has_no_resolution():
    random.seed(0)
    # Find a generated incident with an unresolved status to check the invariant.
    for i in range(1, 200):
        incident = generate_incident(i)
        if incident["status"] in ("open", "investigating"):
            assert incident["resolved_at"] is None
            assert incident["resolved_by"] is None
            return
    raise AssertionError("no open/investigating incident generated in 200 tries -- weights may have changed")


def test_generate_incident_resolved_status_has_resolution():
    random.seed(0)
    for i in range(1, 200):
        incident = generate_incident(i)
        if incident["status"] in ("resolved", "closed"):
            assert incident["resolved_at"] is not None
            assert incident["resolved_by"] is not None
            assert incident["resolved_at"] > incident["created_at"]
            return
    raise AssertionError("no resolved/closed incident generated in 200 tries")


def test_generate_incident_title_matches_service_and_issue():
    random.seed(3)
    incident = generate_incident(1)
    assert incident["title"].startswith(incident["service"] + ": ")
