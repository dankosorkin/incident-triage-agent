import random
import sqlite3

import pytest

from app.rag.generate_postmortems import SAMPLE_PER_SEVERITY, select_incidents


@pytest.fixture
def conn_with_incidents():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE incidents (id INTEGER PRIMARY KEY, severity TEXT, status TEXT)"
    )
    rows = []
    incident_id = 1
    # Enough rows in each severity/status bucket to satisfy SAMPLE_PER_SEVERITY.
    for severity, needed in SAMPLE_PER_SEVERITY.items():
        for _ in range(needed + 5):
            rows.append((incident_id, severity, "resolved"))
            incident_id += 1
        rows.append((incident_id, severity, "open"))  # should never be selected
        incident_id += 1
    conn.executemany("INSERT INTO incidents VALUES (?, ?, ?)", rows)
    conn.commit()
    yield conn
    conn.close()


def test_select_incidents_returns_expected_count_per_severity(conn_with_incidents):
    random.seed(0)
    selected = select_incidents(conn_with_incidents)
    expected_total = sum(SAMPLE_PER_SEVERITY.values())
    assert len(selected) == expected_total

    counts = {}
    for row in selected:
        counts[row["severity"]] = counts.get(row["severity"], 0) + 1
    for severity, expected_count in SAMPLE_PER_SEVERITY.items():
        assert counts.get(severity, 0) == expected_count


def test_select_incidents_never_selects_open_status(conn_with_incidents):
    random.seed(0)
    selected = select_incidents(conn_with_incidents)
    assert all(row["status"] in ("resolved", "closed") for row in selected)


def test_select_incidents_returns_no_duplicates(conn_with_incidents):
    random.seed(0)
    selected = select_incidents(conn_with_incidents)
    ids = [row["id"] for row in selected]
    assert len(ids) == len(set(ids))
