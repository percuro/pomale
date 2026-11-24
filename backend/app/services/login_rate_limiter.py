from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from app.errors import AppError


class LoginRateLimiter:
    def __init__(self, window_seconds: int = 15 * 60):
        self.window_seconds = window_seconds
        self.account_limit = 5
        self.ip_limit = 20
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, username: str, ip_address: str) -> None:
        now = monotonic()
        with self._lock:
            account_attempts = self._active(f"account:{username.lower()}", now)
            ip_attempts = self._active(f"ip:{ip_address}", now)
            if len(account_attempts) >= self.account_limit or len(ip_attempts) >= self.ip_limit:
                raise AppError(
                    429,
                    "auth.rate_limited",
                    "Too many failed attempts. Please try again later.",
                    headers={"Retry-After": str(self.window_seconds)},
                )

    def record_failure(self, username: str, ip_address: str) -> None:
        now = monotonic()
        with self._lock:
            self._active(f"account:{username.lower()}", now).append(now)
            self._active(f"ip:{ip_address}", now).append(now)

    def record_success(self, username: str) -> None:
        with self._lock:
            self._attempts.pop(f"account:{username.lower()}", None)

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()

    def _active(self, key: str, now: float) -> deque[float]:
        attempts = self._attempts[key]
        cutoff = now - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        return attempts


login_rate_limiter = LoginRateLimiter()
