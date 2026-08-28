import random
from datetime import datetime

from app.rag.generate_postmortems import NARRATIVES, format_duration, render_postmortem


def test_format_duration_under_an_hour():
    start = datetime(2025, 1, 1, 0, 0, 0)
    end = datetime(2025, 1, 1, 0, 45, 0)
    assert format_duration(start, end) == "45m"


def test_format_duration_over_an_hour():
    start = datetime(2025, 1, 1, 0, 0, 0)
    end = datetime(2025, 1, 1, 3, 15, 0)
    assert format_duration(start, end) == "3h 15m"


def test_format_duration_zero():
    same = datetime(2025, 1, 1, 0, 0, 0)
    assert format_duration(same, same) == "0m"


def test_render_postmortem_includes_all_fact_fields():
    incident = {
        "id": 7,
        "title": "payments-api: OOM crash",
        "service": "payments-api",
        "severity": "P1",
        "status": "resolved",
        "created_at": "2025-01-01T00:00:00",
        "resolved_at": "2025-01-01T02:00:00",
        "resolved_by": "Alice Chen",
    }
    text = render_postmortem(incident)
    assert "payments-api: OOM crash" in text
    assert "**Incident ID:** 7" in text
    assert "**Resolved by:** Alice Chen" in text
    assert "2h 0m" in text


def test_render_postmortem_narrative_from_known_issue_type():
    incident = {
        "id": 1,
        "title": "search-api: OOM crash",
        "service": "search-api",
        "severity": "P2",
        "status": "closed",
        "created_at": "2025-01-01T00:00:00",
        "resolved_at": "2025-01-01T01:00:00",
        "resolved_by": "Jordan Lee",
    }
    text = render_postmortem(incident)
    narrative = NARRATIVES["OOM crash"]
    assert any(root_cause in text for root_cause in narrative["root_cause"])
    assert any(resolution in text for resolution in narrative["resolution"])


def test_render_postmortem_root_cause_and_resolution_are_a_matching_pair():
    # Regression test: root_cause/resolution/lessons used to be drawn
    # independently, which could pair a cause with a resolution that
    # doesn't actually address it. They must always share the same
    # scenario index.
    incident = {
        "id": 1,
        "title": "checkout-service: high latency",
        "service": "checkout-service",
        "severity": "P2",
        "status": "resolved",
        "created_at": "2025-01-01T00:00:00",
        "resolved_at": "2025-01-01T01:00:00",
        "resolved_by": "Jordan Lee",
    }
    narrative = NARRATIVES["high latency"]

    random.seed(0)
    for _ in range(50):
        text = render_postmortem(incident)
        cause_index = next(i for i, rc in enumerate(narrative["root_cause"]) if rc in text)
        resolution_index = next(i for i, res in enumerate(narrative["resolution"]) if res in text)
        assert cause_index == resolution_index
