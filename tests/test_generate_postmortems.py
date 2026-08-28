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
