"""Generates postmortem markdown docs for a subset of resolved/closed
incidents from data/incidents.db, so RAG content stays consistent with
the SQL source of truth. Deterministic (fixed seed) for the same
reason as seed_data.py: eval questions must stay valid across reruns.
"""

import random
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "incidents.db"
DOCS_DIR = Path(__file__).resolve().parent / "docs"

SAMPLE_PER_SEVERITY = {"P1": 7, "P2": 8, "P3": 3, "P4": 0}

NARRATIVES = {
    "OOM crash": {
        "root_cause": [
            "A recent traffic increase pushed per-instance memory usage past the configured limit, "
            "triggering repeated OOM kills under load.",
            "An unbounded in-memory cache introduced in a recent change grew until it exceeded "
            "the container's memory limit.",
        ],
        "resolution": [
            "Rolled back the recent deploy and raised the memory limit temporarily while a proper fix "
            "was prepared.",
            "Restarted the affected instances to clear accumulated memory, then patched the cache to "
            "enforce a bounded size.",
        ],
        "lessons": [
            "Add alerting on memory usage trending toward the limit, not just on the OOM kill itself.",
            "Load-test with realistic payload sizes before raising traffic limits.",
        ],
    },
    "high latency": {
        "root_cause": [
            "A downstream dependency's response time degraded, and the lack of a per-hop timeout budget "
            "let that slowness propagate through the whole request chain.",
            "A missing index on a frequently-queried table caused query time to grow with table size "
            "until it crossed the latency alert threshold.",
        ],
        "resolution": [
            "Added a timeout and circuit breaker around the slow dependency, and scaled out the affected "
            "service as an immediate stopgap.",
            "Added the missing index and confirmed p95 latency returned to baseline.",
        ],
        "lessons": [
            "Alert on p95/p99 latency specifically; the average latency graph never showed the problem.",
            "Review query plans for new endpoints before they reach production traffic levels.",
        ],
    },
    "elevated error rate": {
        "root_cause": [
            "A recent deploy introduced a regression on an edge case (empty input) that wasn't covered "
            "by existing tests.",
            "An upstream dependency began returning malformed responses, which the service didn't "
            "handle gracefully.",
        ],
        "resolution": [
            "Rolled back the deploy; error rate returned to baseline within minutes.",
            "Added defensive handling for malformed upstream responses and deployed a hotfix.",
        ],
        "lessons": [
            "Add a regression test for this edge case so it can't recur silently.",
            "Adopt canary rollouts so a bad deploy is caught on a small fraction of traffic.",
        ],
    },
    "database connection pool exhausted": {
        "root_cause": [
            "A code path introduced in a recent change failed to release its database connection on an "
            "error branch, slowly leaking connections until the pool was exhausted.",
            "A batch job ran far longer than expected, holding a large share of the pool's connections "
            "for its entire duration.",
        ],
        "resolution": [
            "Restarted the service to release leaked connections, then fixed the code path to release "
            "connections in a finally block.",
            "Killed the long-running batch job's query and added a query timeout to prevent recurrence.",
        ],
        "lessons": [
            "Use connection-handling patterns that guarantee release even on exceptions.",
            "Size the connection pool from load-testing data and alert before it reaches full utilization.",
        ],
    },
    "deployment rollback": {
        "root_cause": [
            "A configuration change bundled with the deploy was incompatible with the current production "
            "environment.",
            "A database migration included in the deploy was not backward-compatible with instances "
            "still running the previous version during the rollout.",
        ],
        "resolution": [
            "Rolled back to the previous known-good version; metrics recovered within minutes.",
            "Halted the in-progress rollout and rolled back before the migration reached the remaining "
            "instances.",
        ],
        "lessons": [
            "Keep migrations backward-compatible with the previous app version for at least one deploy "
            "cycle.",
            "Diff config changes with the same rigor as code changes during review.",
        ],
    },
    "cache invalidation failure": {
        "root_cause": [
            "The event stream driving cache invalidation fell behind under load, so invalidations were "
            "delayed well past their intended window.",
            "A race condition let a read repopulate the cache with a stale value immediately after a "
            "write had just invalidated it.",
        ],
        "resolution": [
            "Manually flushed the affected cache keys and restarted the invalidation worker.",
            "Added key versioning tied to the underlying data's version so stale entries miss instead "
            "of serving wrong data.",
        ],
        "lessons": [
            "Monitor invalidation-event lag as its own signal, separate from general cache hit rate.",
            "Prefer short TTLs with reliable invalidation over long TTLs relying on invalidation always "
            "working.",
        ],
    },
    "rate limit misconfiguration": {
        "root_cause": [
            "A recent change to the rate limiter's scope applied a per-client limit globally, throttling "
            "all traffic far below intended capacity.",
            "A units mismatch (per-second vs. per-minute) in a rate-limit config change caused the "
            "effective limit to be far stricter than intended.",
        ],
        "resolution": [
            "Reverted the rate-limit config change; legitimate traffic resumed immediately.",
            "Corrected the units in the config and redeployed with the intended limit.",
        ],
        "lessons": [
            "Require review for rate-limit config changes with the same rigor as code changes.",
            "Alert on 429 rate so an overly strict limit is caught quickly, not reported by users first.",
        ],
    },
    "disk space exhaustion": {
        "root_cause": [
            "Log rotation had been silently disabled by a configuration change, letting logs grow "
            "unbounded until the volume filled.",
            "A bug caused a single error to be logged repeatedly in a tight loop, generating an unusual "
            "volume of log data in a short window.",
        ],
        "resolution": [
            "Cleared old logs to free space, then re-enabled log rotation and confirmed it ran.",
            "Fixed the logging bug, cleared the excess log volume, and expanded the volume as a safety "
            "margin.",
        ],
        "lessons": [
            "Alert on disk usage trending toward full well before it's actually full.",
            "Cap local log/temp directory size with automatic eviction as a backstop against future bugs.",
        ],
    },
    "memory leak": {
        "root_cause": [
            "An unbounded in-memory collection accumulated entries over the process lifetime without "
            "ever evicting old ones.",
            "A subscription/listener registered on every request was never unregistered, accumulating "
            "over the life of the process.",
        ],
        "resolution": [
            "Restarted affected instances to reclaim memory, then patched the collection to evict old "
            "entries.",
            "Rolled back the recent deploy that introduced the leaking listener registration.",
        ],
        "lessons": [
            "Add memory-growth profiling to CI, not just production monitoring.",
            "Load-test over a long duration; short load tests systematically miss slow leaks.",
        ],
    },
    "timeout spike": {
        "root_cause": [
            "A downstream dependency became slow but not fully unresponsive, and requests waited out "
            "their full timeout instead of failing fast.",
            "A retry storm triggered by an initial minor slowdown amplified load on an already-degraded "
            "downstream, worsening the timeout rate.",
        ],
        "resolution": [
            "Added a circuit breaker around the slow dependency so requests failed fast instead of "
            "waiting out the timeout.",
            "Disabled aggressive retries and added exponential backoff, which relieved load on the "
            "downstream and let it recover.",
        ],
        "lessons": [
            "Set explicit timeout budgets per hop in the call chain.",
            "Retries must always use backoff with a cap; unbounded immediate retries turn slowdowns into "
            "outages.",
        ],
    },
}


def format_duration(start: datetime, end: datetime) -> str:
    total_minutes = int((end - start).total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def render_postmortem(incident: dict) -> str:
    service = incident["service"]
    issue_type = incident["title"].split(": ", 1)[1]
    narrative = NARRATIVES[issue_type]

    created_at = datetime.fromisoformat(incident["created_at"])
    resolved_at = datetime.fromisoformat(incident["resolved_at"])
    duration = format_duration(created_at, resolved_at)

    # One shared index, not three independent random.choice() calls --
    # root_cause[i]/resolution[i]/lessons[i] are written as a matching
    # scenario (a fix that addresses that specific cause). Drawing them
    # independently could pair a cause with a resolution that doesn't
    # actually address it.
    scenario = random.randrange(len(narrative["root_cause"]))
    root_cause = narrative["root_cause"][scenario]
    resolution = narrative["resolution"][scenario]
    lesson = narrative["lessons"][scenario]

    return f"""# Postmortem: {incident['title']}

**Incident ID:** {incident['id']}
**Service:** {service}
**Severity:** {incident['severity']}
**Status:** {incident['status']}
**Opened:** {incident['created_at']}
**Resolved:** {incident['resolved_at']}
**Resolved by:** {incident['resolved_by']}
**Duration:** {duration}

## Summary
{service} experienced {issue_type} (severity {incident['severity']}), opened at {incident['created_at']} \
and resolved by {incident['resolved_by']} after {duration}.

## Timeline
- {incident['created_at']} — Incident opened, {issue_type} detected on {service}.
- {incident['resolved_at']} — Incident resolved by {incident['resolved_by']}.

## Root Cause
{root_cause}

## Resolution
{resolution}

## Lessons Learned
{lesson}
"""


def select_incidents(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    selected: list[dict] = []
    for severity, count in SAMPLE_PER_SEVERITY.items():
        if count == 0:
            continue
        rows = conn.execute(
            "SELECT * FROM incidents WHERE severity = ? AND status IN ('resolved', 'closed')",
            (severity,),
        ).fetchall()
        selected.extend(random.sample([dict(row) for row in rows], count))
    return selected


def main() -> None:
    random.seed(42)
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    incidents = select_incidents(conn)
    conn.close()

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for incident in incidents:
        text = render_postmortem(incident)
        (DOCS_DIR / f"incident_{incident['id']}.md").write_text(text, encoding="utf-8")

    print(f"Wrote {len(incidents)} postmortems to {DOCS_DIR}")


if __name__ == "__main__":
    main()
