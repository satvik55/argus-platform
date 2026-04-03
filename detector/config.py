"""
Configuration for the Argus Anomaly Detector.

All values are loaded from environment variables, with sensible defaults
for running inside the k3s cluster.  When testing locally with a
port-forwarded Prometheus, override PROMETHEUS_URL and GRAFANA_URL.
"""

import os


class DetectorConfig:
    # -- Prometheus connection ------------------------------------------------
    PROMETHEUS_URL = os.environ.get(
        "PROMETHEUS_URL",
        "http://prometheus-prometheus.monitoring.svc.cluster.local:9090",
    )

    # -- Grafana connection (for pushing annotations) -------------------------
    GRAFANA_URL = os.environ.get(
        "GRAFANA_URL",
        "http://prometheus-grafana.monitoring.svc.cluster.local:80",
    )
    GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY", "")

    # -- Detection parameters -------------------------------------------------
    # How far back to query Prometheus (seconds)
    QUERY_RANGE_MINUTES = int(os.environ.get("QUERY_RANGE_MINUTES", "30"))

    # Rolling window size for Z-score calculation (number of data points)
    ZSCORE_WINDOW = int(os.environ.get("ZSCORE_WINDOW", "10"))

    # Z-score threshold — values above this are flagged as anomalies.
    # 2.5 means "2.5 standard deviations from the mean", which catches
    # roughly the top 0.6% of values in a normal distribution.
    ZSCORE_THRESHOLD = float(os.environ.get("ZSCORE_THRESHOLD", "2.5"))

    # Prometheus step interval for range queries
    QUERY_STEP = os.environ.get("QUERY_STEP", "30s")

    # -- Kubernetes namespace to watch ----------------------------------------
    NAMESPACE = os.environ.get("NAMESPACE", "argus")

    # -- Grafana dashboard UID for annotations --------------------------------
    DASHBOARD_UID = os.environ.get("DASHBOARD_UID", "argus-app-health")
