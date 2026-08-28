"""In-memory sliding-window rate limiter, keyed by an arbitrary string
(client IP in practice). Single-process only -- correct for this
project's single-node architecture, would need a shared store (Redis
etc.) behind multiple workers or replicas.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._log: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        window_start = now - self.window_seconds
        with self._lock:
            log = self._log[key]
            while log and log[0] < window_start:
                log.popleft()
            if len(log) >= self.max_requests:
                return False
            log.append(now)
            return True
