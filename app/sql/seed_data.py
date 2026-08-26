"""Generates a deterministic synthetic incidents dataset (fixed seed and
date range) so hand-written eval questions stay valid across reruns.
"""

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "incidents.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

SERVICES = [
    "payments-api",
    "auth-service",
    "checkout-service",
    "search-api",
    "notifications-service",
    "user-profile-service",
    "inventory-service",
    "recommendation-engine",
]

ISSUE_TYPES = [
    "OOM crash",
    "high latency",
    "elevated error rate",
    "database connection pool exhausted",
    "deployment rollback",
    "cache invalidation failure",
    "rate limit misconfiguration",
    "disk space exhaustion",
    "memory leak",
    "timeout spike",
]

ENGINEERS = [
    "Alice Chen",
    "Marcus Webb",
    "Priya Patel",
    "Jordan Lee",
    "Sam Okafor",
    "Elena Petrov",
]

SEVERITY_WEIGHTS = {"P1": 0.10, "P2": 0.20, "P3": 0.35, "P4": 0.35}
STATUS_WEIGHTS = {"resolved": 0.50, "closed": 0.35, "investigating": 0.10, "open": 0.05}
RESOLUTION_HOURS_RANGE = {"P1": (0.5, 6), "P2": (1, 24), "P3": (4, 48), "P4": (12, 96)}

YEAR_START = datetime(2025, 1, 1)
YEAR_END = datetime(2025, 12, 31, 23, 59, 59)


def random_datetime(start: datetime, end: datetime) -> datetime:
    seconds_between = int((end - start).total_seconds())
    offset = random.randint(0, seconds_between)
    return start + timedelta(seconds=offset)


def weighted_choice(weights: dict[str, float]) -> str:
    return random.choices(list(weights.keys()), weights=list(weights.values()))[0]


def generate_incident(incident_id: int) -> dict:
    service = random.choice(SERVICES)
    issue = random.choice(ISSUE_TYPES)
    severity = weighted_choice(SEVERITY_WEIGHTS)
    status = weighted_choice(STATUS_WEIGHTS)
    created_at = random_datetime(YEAR_START, YEAR_END)

    resolved_at = None
    resolved_by = None
    if status in ("resolved", "closed"):
        low, high = RESOLUTION_HOURS_RANGE[severity]
        resolved_at = created_at + timedelta(hours=random.uniform(low, high))
        resolved_by = random.choice(ENGINEERS)

    return {
        "id": incident_id,
        "title": f"{service}: {issue}",
        "service": service,
        "severity": severity,
        "status": status,
        "created_at": created_at.isoformat(timespec="seconds"),
        "resolved_at": resolved_at.isoformat(timespec="seconds") if resolved_at else None,
        "resolved_by": resolved_by,
    }


def main(count: int = 80) -> None:
    random.seed(42)
    incidents = [generate_incident(i) for i in range(1, count + 1)]

    if DB_PATH.exists():
        DB_PATH.unlink()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.executemany(
        """
        INSERT INTO incidents
            (id, title, service, severity, status, created_at, resolved_at, resolved_by)
        VALUES
            (:id, :title, :service, :severity, :status, :created_at, :resolved_at, :resolved_by)
        """,
        incidents,
    )
    conn.commit()
    conn.close()
    print(f"Seeded {count} incidents into {DB_PATH}")


if __name__ == "__main__":
    main()
