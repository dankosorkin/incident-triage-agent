# Runbook: Disk Space Exhaustion

## Symptoms
- Writes fail with "no space left on device" errors, including log writes — which can mean the service loses its own logging right when you need it most.
- Service crash or hang on any operation that touches local disk (temp files, local cache, write-ahead logs).
- Disk usage graph shows a steady climb rather than a sudden jump, in most cases.

## Immediate Mitigation
1. Confirm which volume is full — the root filesystem, a data volume, and a logs volume are different problems with different fixes.
2. Clear obviously safe space first: old rotated logs, temp files, stale build/cache artifacts.
3. If safe cleanup isn't enough, expand the volume as an immediate stopgap while investigating the growth source.
4. Force a log rotation immediately if rotation is configured but hasn't run recently.

## Root Cause Investigation
- Check log rotation configuration — a misconfigured or disabled rotation policy is the most common cause of "slowly fills disk over days."
- Check for a bug causing runaway log volume (a log statement inside a hot loop, an error being logged repeatedly instead of once).
- Check for an accumulating local cache or temp-file directory that's never cleaned up.
- Plot the disk-usage growth rate against the incident's actual timeline to estimate how long until the next occurrence if the root cause isn't fixed.

## Prevention
- Enforce log rotation and retention policies on every service, not just the ones that have already had an incident.
- Alert on disk usage trending toward full well before it's actually full (e.g. at 80%), not only at capacity.
- Cap local temp/cache directory size with automatic eviction.
