# Runbook: Memory Leak

## Symptoms
- Memory usage climbs gradually over hours or days, distinct from a sudden spike — this is the key symptom that distinguishes a leak from a one-off large request.
- Eventually leads to OOM crashes or degraded performance (increased GC activity, if the runtime has a garbage collector) as available memory shrinks.
- Restarting the affected process temporarily resolves the symptom, which is itself a strong signal it's a leak rather than a workload change.

## Immediate Mitigation
1. Restart the affected instances to reclaim memory and buy time — this is a mitigation, not a fix; the leak will recur.
2. If a specific recent deploy correlates with the onset of the growth trend, roll it back.
3. Set up a rolling-restart schedule as a temporary stopgap only if the leak can't be fixed immediately and the growth rate is well understood.

## Root Cause Investigation
- Take heap/memory snapshots at two points in time and diff them — the object types growing between snapshots point directly at the leaking code path.
- Check for unbounded in-memory caches or collections (a dict/list that grows but is never pruned).
- Check for resources opened but never released over the process lifetime — file handles, network connections, subscriptions/listeners that accumulate.
- Check whether the growth rate correlates with request volume (leak per-request) or is constant regardless of traffic (leak in a background task).

## Prevention
- Add memory-growth profiling to CI or periodic staging runs, not just production monitoring.
- Use bounded caches with explicit eviction policies instead of plain unbounded collections.
- Load-test over a long duration (hours, not seconds) — short load tests systematically miss slow leaks.
