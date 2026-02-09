"""Rate limiting utilities to respect API limits."""

import time
from collections import deque


class RateLimiter:
    """Token-bucket style rate limiter."""

    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.interval = 60.0 / calls_per_minute
        self._timestamps: deque[float] = deque()

    def wait(self) -> None:
        """Block until a request is allowed."""
        now = time.time()
        # Remove timestamps older than 60 seconds
        while self._timestamps and now - self._timestamps[0] > 60:
            self._timestamps.popleft()
        if len(self._timestamps) >= self.calls_per_minute:
            sleep_time = 60 - (now - self._timestamps[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        self._timestamps.append(time.time())
