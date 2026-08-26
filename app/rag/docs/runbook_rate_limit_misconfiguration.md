# Runbook: Rate Limit Misconfiguration

## Symptoms
- Legitimate clients receiving `429 Too Many Requests` at traffic levels that previously worked fine.
- Alternatively: no throttling at all during a genuine traffic spike, because a limit was accidentally raised or removed — leading to downstream overload instead.
- Often follows a recent change to rate-limiting config or the rollout of a new limiting rule.

## Immediate Mitigation
1. Check the rate limiter's current configuration against its last known-good version — misconfiguration incidents are almost always a recent config change, not a code bug.
2. If clients are being wrongly throttled: revert the limit change, or temporarily whitelist the affected client(s) while the fix is prepared.
3. If limiting failed to engage during a spike: apply an emergency limit manually to protect the service from overload while the config is fixed properly.

## Root Cause Investigation
- Check whether the limit is scoped correctly — a limit intended per-client can accidentally apply globally (or vice versa), which explains both failure directions above.
- Check for a units mismatch (requests/second vs requests/minute) introduced during the change.
- Check whether the new limit was tested against realistic traffic patterns before rollout, including legitimate burst traffic (e.g. client retries, batch jobs).

## Prevention
- Require review for rate-limit config changes the same as for code changes — they're just as capable of causing an incident.
- Roll out new limits gradually, and alert on 429 rate so an overly strict limit is caught quickly.
- Keep a documented "known good" baseline config to diff against.
