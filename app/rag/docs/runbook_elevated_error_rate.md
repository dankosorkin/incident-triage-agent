# Runbook: Elevated Error Rate

## Symptoms
- 5xx response rate above baseline, error-budget-burn alert firing.
- Error rate may be concentrated on one endpoint, one client, or spread evenly across the service.
- Often (not always) correlates in time with a deploy.

## Immediate Mitigation
1. Check the deploy timeline first — if the error onset lines up with a recent release, roll back before investigating further. Don't debug forward on a build you can just remove.
2. If no recent deploy is implicated, check the health of direct dependencies (database, downstream services, third-party APIs) — a dependency outage surfaces as errors in every service that calls it.
3. If errors are concentrated on one endpoint, consider disabling that endpoint or the feature behind it (feature flag) while the rest of the service keeps serving traffic.
4. If a single noisy client is responsible (retry storm, malformed requests), consider temporarily rate-limiting or blocking that client.

## Root Cause Investigation
- Group errors by exception type / status code — "everything is 500" and "everything is a specific null-pointer trace" point to very different root causes.
- Check for an edge case the recent change didn't account for (empty input, unusual character encoding, a field that's newly optional/nullable).
- Check whether the error rate correlates with a specific data shape, region, or client version rather than being uniform.

## Prevention
- Canary or staged rollouts so a bad deploy affects a small fraction of traffic before it affects everyone.
- Automated rollback triggers when error rate crosses a threshold shortly after a deploy.
- Test coverage for edge cases identified in past incidents — every postmortem here should turn into a regression test.
