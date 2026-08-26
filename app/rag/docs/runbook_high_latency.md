# Runbook: High Latency

## Symptoms
- p95/p99 latency alerts firing while p50 stays roughly normal (a tail-latency problem, not a total-outage problem).
- Request queue depth or in-flight request count climbing.
- Downstream dependency (database, external API, internal service) showing elevated response times of its own.

## Immediate Mitigation
1. Check whether the slowdown is isolated to one endpoint/service or system-wide — narrows the search space immediately.
2. Check resource saturation on the affected instances (CPU, memory, active connections) — a saturated instance degrades tail latency long before it errors outright.
3. Check the latency of the slowest downstream dependency in the call chain; if one dependency is clearly the bottleneck, that's the incident, not the service in front of it.
4. If a specific instance or replica is disproportionately slow, drain it out of the load balancer rotation rather than debugging live.
5. If load is the driver, scale out horizontally as an immediate stopgap.

## Root Cause Investigation
- Correlate the onset time with recent deploys, config changes, or traffic pattern shifts.
- Check for lock contention or serialized access to a shared resource (a single DB connection, a mutex, a rate-limited external call).
- Check the database's slow query log — a single new query pattern can quietly degrade an entire service's latency profile.
- Check for N+1 query patterns or missing pagination introduced by a recent change.

## Prevention
- Set per-dependency timeout budgets so one slow downstream can't unboundedly stretch the whole request.
- Add caching for expensive, frequently-repeated reads.
- Alert on p95/p99 specifically, not just average latency — averages hide exactly this class of problem.
- Autoscale on latency/queue depth signals, not CPU alone.
