# Runbook: OOM Crash

## Symptoms
- Service process restarts unexpectedly, container status shows `OOMKilled`.
- Memory usage graph climbs steadily to the configured limit right before the restart.
- Latency spikes in the minute before the crash as the process struggles under memory pressure.
- Logs may show allocation failures right before the process dies (or nothing at all — OOM kills are often silent from the app's own logs).

## Immediate Mitigation
1. Confirm it's OOM, not a crash from an unrelated exception — check the container/orchestrator event log for `OOMKilled`, not just the app log.
2. If a specific pod/instance is affected, let the orchestrator restart it; if it's cluster-wide, consider a rolling restart to relieve memory pressure while investigating.
3. If a recent deploy correlates with the onset, roll back first and investigate after — don't debug a live incident on a suspect build.
4. If traffic is unusually high, consider temporary horizontal scale-out to spread memory load across more instances.

## Root Cause Investigation
- Pull a heap/memory profile from an instance close to the limit, if the runtime supports live profiling.
- Check for a recent change that increased per-request memory usage (larger payloads, new caching, batch size changes).
- Check whether memory grows gradually (leak) or spikes suddenly (large request, bad input, unbounded batch job) — the shape of the graph tells you which runbook you actually need.
- Compare the configured memory limit against actual steady-state usage — a limit set too close to normal usage will OOM on any load spike.

## Prevention
- Set memory limits with headroom above observed p99 usage, not just the average.
- Add alerting on memory usage trending toward the limit, well before the kill happens.
- Load-test with realistic payload sizes before raising traffic limits or enabling new features that change memory footprint.
