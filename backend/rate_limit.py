"""
Minimal in-memory rate limiter.

This exists for one reason: once this service is public, every /analyze call
that isn't skip_ai_review spends the ANTHROPIC_API_KEY configured on the
server — that's your API credits, not the caller's. This is a simple
sliding-window limiter per client IP to put a ceiling on that before you
plug in real auth/API keys.

It is intentionally simple: in-memory, single-process. Fine for a small
demo deployment on a single Render/Railway instance. If you ever scale to
multiple instances, replace this with a shared store (Redis) — the
interface (`allow(key)`) is small enough to swap out.
"""
import os
import time
from collections import defaultdict, deque
from threading import Lock

# Requests allowed per window, per client IP. Override via env vars.
RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "3600"))

_lock = Lock()
_hits: dict = defaultdict(deque)


def allow(key: str) -> bool:
    """Return True if `key` (typically client IP) is still under the limit."""
    now = time.time()
    with _lock:
        window = _hits[key]
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= RATE_LIMIT_MAX_REQUESTS:
            return False
        window.append(now)
        return True


def remaining(key: str) -> int:
    now = time.time()
    with _lock:
        window = _hits[key]
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        while window and window[0] < cutoff:
            window.popleft()
        return max(RATE_LIMIT_MAX_REQUESTS - len(window), 0)
