# Runbook: Timeout Spike

## Symptoms
- Sharp increase in client-observed request timeouts, distinct from errors — the request never gets a response at all within the configured deadline.
- Often traces back to one slow or unresponsive downstream dependency rather than the service itself being broken.
- May cascade: a timeout in one service can trigger retries that increase load on an already-struggling downstream, worsening the spike.

## Immediate Mitigation
1. Identify which downstream dependency in the call chain is actually slow or unresponsive — timeouts are a symptom of the chain, not necessarily the service reporting them.
2. If the downstream is degraded but recovering, a temporary timeout increase can reduce client-visible failures while avoiding making the downstream's load worse.
3. If a downstream is fully unresponsive, fail over to a backup/replica if one exists, or fail fast with a clear error rather than waiting out the full timeout on every request.
4. Check for a retry storm — if timeouts are triggering aggressive retries without backoff, that alone can turn a minor slowdown into a full outage. Disable or throttle retries if so.

## Root Cause Investigation
- Check the latency (not just error rate) of every dependency in the call chain around the incident window.
- Check for network-level issues (packet loss, DNS resolution delay) separate from application-level slowness.
- Check for thread-pool or connection-pool exhaustion on the calling side, which can produce timeouts even when the downstream itself is healthy.

## Prevention
- Set explicit timeout budgets per hop in the call chain so no single dependency can consume the entire request deadline.
- Use circuit breakers to stop calling a downstream that's already failing, instead of waiting out timeouts on every request.
- Implement retries with exponential backoff and a cap — never unbounded immediate retries.
