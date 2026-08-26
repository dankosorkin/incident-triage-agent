# Runbook: Cache Invalidation Failure

## Symptoms
- Users or clients report stale data — a value they know was updated still shows the old version.
- Inconsistent responses across replicas or requests for the same resource (some hit stale cache, some don't).
- Cache hit ratio may look anomalously high or unstable rather than showing an obvious error.

## Immediate Mitigation
1. Confirm it's a caching issue and not a data-write failure — check that the underlying data store actually has the updated value before blaming the cache.
2. Manually flush or invalidate the affected cache keys (or the whole cache, if the affected set is unclear and the cache is cheap to rewarm).
3. If a specific cache-warming or invalidation worker is stuck or behind, restart it.
4. If invalidation depends on an event stream, check for consumer lag — a backed-up queue means invalidations are just delayed, not lost, and will resolve once it catches up.

## Root Cause Investigation
- Check the invalidation trigger path end-to-end: what's supposed to fire it, and did it actually fire for the affected keys.
- Check for a race condition where a read repopulates the cache with a stale value immediately after a write invalidates it (write-then-read-before-invalidation ordering).
- Check TTL configuration — a TTL set too long turns any invalidation gap into a much longer-lived staleness window.

## Prevention
- Version or namespace cache keys by the underlying data's version, so stale entries simply miss instead of serving wrong data.
- Monitor invalidation-event lag as its own signal, separate from general cache hit-rate metrics.
- Prefer short TTLs with reliable invalidation over long TTLs relying on invalidation always working.
