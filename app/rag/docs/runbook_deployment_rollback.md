# Runbook: Deployment-Triggered Incident / Rollback

## Symptoms
- Error rate, latency, or crash rate spikes immediately (within minutes) after a deployment completes.
- The regression is reproducible across instances running the new version and absent on instances still on the old one, during a rolling rollout.

## Immediate Mitigation
1. Confirm the timing correlation — check the deploy timestamp against the metric onset before assuming causation.
2. Roll back to the previous known-good version immediately. This is the default first move for a deploy-correlated incident; investigating on the live bad build wastes time the rollback would have saved.
3. Verify metrics actually recover after the rollback completes — a rollback that doesn't fix the symptom means the deploy wasn't the cause, and the search continues elsewhere.
4. If the rollout is still in progress (partial), halt it before rolling back to avoid the rollback racing a still-advancing rollout.

## Root Cause Investigation
- Diff the deployed change against the previous version — look specifically for config changes and migrations, not just application code, since those are easy to overlook.
- Check whether a database migration in the deploy is backward-incompatible with the rolled-back application version — this can turn a rollback into a second incident.
- Reproduce in a staging environment before re-attempting the deploy.

## Prevention
- Canary or staged rollouts, so a bad deploy is caught on a small percentage of traffic.
- Automated rollback triggers tied to error-rate/latency thresholds, removing the delay of a human noticing and deciding.
- Keep migrations backward-compatible with the previous app version for at least one deploy cycle, so a rollback is always safe.
