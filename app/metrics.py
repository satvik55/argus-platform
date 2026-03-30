"""
Prometheus metric definitions for Argus API.

Metrics are registered globally and shared across request handlers.
Naming follows Prometheus conventions: <namespace>_<name>_<unit>_<suffix>
- Counters end with _total
- Histograms track _bucket, _sum, _count automatically
- Gauges have no suffix convention
"""

from prometheus_client import Counter, Histogram, Gauge

# -- Request volume ----------------------------------------------------------
# Labels: method (GET/POST), endpoint (/health, /api/items), status (200, 500)
REQUEST_COUNT = Counter(
    "request_count_total",
    "Total HTTP requests processed by the Argus API",
    ["method", "endpoint", "status"],
)

# -- Latency distribution ----------------------------------------------------
# Custom buckets tuned for a lightweight API: most requests should land in the
# 10-100ms range.  The 2.5s and 5s buckets catch stress-test outliers.
REQUEST_LATENCY = Histogram(
    "request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# -- Error tracking -----------------------------------------------------------
ERROR_COUNT = Counter(
    "error_count_total",
    "Total HTTP 5xx errors returned by the Argus API",
    ["method", "endpoint"],
)

# -- Concurrency gauge -------------------------------------------------------
# Inc on request start, dec on request end.  Useful for detecting request
# pile-ups that precede OOM or latency spikes.
ACTIVE_REQUESTS = Gauge(
    "active_requests",
    "Number of HTTP requests currently being processed",
)
