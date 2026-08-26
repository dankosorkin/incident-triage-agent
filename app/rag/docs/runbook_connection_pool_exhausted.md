# Runbook: Database Connection Pool Exhausted

## Symptoms
- Requests fail or hang with "unable to acquire connection from pool" / connection timeout errors.
- Request latency degrades sharply as requests queue up waiting for a free connection.
- The database itself may show normal load — the bottleneck is the pool, not the database server.

## Immediate Mitigation
1. Check the pool's current active/idle connection counts against its configured max — confirm it's actually exhausted, not a different symptom with a similar error message.
2. Identify and kill any long-running or stuck queries holding connections open on the database side.
3. If connections are leaking (opened but never released), a rolling restart of the affected service releases them immediately as a stopgap.
4. As a short-term measure only, increasing the pool size can relieve pressure — but this treats the symptom, not the leak or query pattern causing it.

## Root Cause Investigation
- Check for a code path that opens a connection without a matching close/release, especially in exception-handling branches that skip cleanup on error.
- Check for a recent query or batch job that runs unusually long, holding a connection for far longer than typical requests.
- Compare pool size against current traffic level — a pool sized for average load will exhaust during a legitimate traffic spike even with no bug present.

## Prevention
- Use connection-handling patterns (context managers / try-finally) that guarantee release even on exceptions.
- Set a query timeout so a single slow query can't hold a connection indefinitely.
- Size the pool from load-testing data, not guesswork, and alert on pool utilization before it hits 100%.
