"""In-memory observability (NFR-12). Swap for Prometheus in production."""
import threading
from collections import defaultdict, deque

_lock = threading.Lock()
_latencies: dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
_counters: dict[str, float] = defaultdict(float)


def observe(name: str, value: float):
    with _lock:
        _latencies[name].append(value)


def incr(name: str, amount: float = 1):
    with _lock:
        _counters[name] += amount


def summary() -> dict:
    with _lock:
        out = {"counters": dict(_counters), "latency_ms": {}}
        for k, v in _latencies.items():
            s = sorted(v)
            if s:
                out["latency_ms"][k] = {
                    "count": len(s),
                    "avg": round(sum(s) / len(s), 1),
                    "p95": round(s[int(0.95 * (len(s) - 1))], 1),
                }
        return out
