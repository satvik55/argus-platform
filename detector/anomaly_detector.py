"""
Argus Anomaly Detector — Main entry point.

This script runs as a Kubernetes CronJob every 2 minutes.  It:
  1. Queries Prometheus for the last 30 min of CPU, request rate,
     error rate, and p99 latency metrics
  2. Calculates rolling Z-scores for each metric
  3. Correlates anomalies across metrics to produce root-cause hints
  4. On anomaly: creates a Kubernetes Event + Grafana annotation
  5. On normal: logs "all metrics nominal"

Exit codes:
  0 — completed successfully (anomaly or not)
  1 — fatal error (cannot reach Prometheus, etc.)
"""

import logging
import sys
from datetime import datetime, timezone

from config import DetectorConfig
from prometheus_client import PrometheusClient
from analyzer import ZScoreAnalyzer
from correlator import correlate_anomalies
from actions import create_kubernetes_event, create_grafana_annotation

# -- Logging setup -----------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("argus.detector")

# -- PromQL queries for each metric -----------------------------------------
# These queries aggregate across all argus-api pods.
METRIC_QUERIES = {
    "cpu": (
        'sum(rate(container_cpu_usage_seconds_total'
        '{namespace="argus", container="argus-api"}[5m])) * 100'
    ),
    "request_rate": (
        'sum(rate(request_count_total{namespace="argus"}[5m]))'
    ),
    "error_rate": (
        'sum(rate(request_count_total{namespace="argus", status=~"5.."}[5m]))'
    ),
    "latency_p99": (
        "histogram_quantile(0.99, "
        'sum(rate(request_latency_seconds_bucket{namespace="argus"}[5m])) by (le))'
    ),
}


def run_detection() -> bool:
    """
    Execute one detection cycle.

    Returns:
        True if any anomaly was detected, False otherwise.
    """
    config = DetectorConfig()
    prom = PrometheusClient(config.PROMETHEUS_URL)
    analyzer = ZScoreAnalyzer(
        window=config.ZSCORE_WINDOW,
        threshold=config.ZSCORE_THRESHOLD,
    )

    logger.info("=" * 60)
    logger.info(
        "Argus Anomaly Detector — run started at %s",
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    logger.info(
        "Config: range=%d min, window=%d, threshold=%.1f",
        config.QUERY_RANGE_MINUTES,
        config.ZSCORE_WINDOW,
        config.ZSCORE_THRESHOLD,
    )
    logger.info("Prometheus: %s", config.PROMETHEUS_URL)

    # -- Step 1: Query all metrics -------------------------------------------
    results = {}
    for metric_name, query in METRIC_QUERIES.items():
        logger.info("Querying metric: %s", metric_name)
        data_points = prom.query_range(
            query,
            range_minutes=config.QUERY_RANGE_MINUTES,
            step=config.QUERY_STEP,
        )

        if not data_points:
            logger.warning(
                "No data for %s — skipping (Prometheus may still be collecting)",
                metric_name,
            )
            results[metric_name] = {"is_anomaly": False, "data_point_count": 0}
            continue

        # -- Step 2: Analyze for anomalies -----------------------------------
        analysis = analyzer.analyze(data_points)
        results[metric_name] = analysis

        if analysis["is_anomaly"]:
            logger.warning(
                "⚠️  ANOMALY in %s — Z-score: %.2f (threshold: %.1f) "
                "| latest: %.4f | mean: %.4f | stddev: %.4f "
                "| anomaly points: %d",
                metric_name,
                analysis["max_zscore"],
                analyzer.threshold,
                analysis["latest_value"],
                analysis["mean"],
                analysis["stddev"],
                len(analysis["anomaly_points"]),
            )
        else:
            logger.info(
                "✅  %s — normal (Z-score: %.2f, latest: %.4f, points: %d)",
                metric_name,
                analysis["max_zscore"],
                analysis["latest_value"],
                analysis["data_point_count"],
            )

    # -- Step 3: Correlate across metrics ------------------------------------
    any_anomaly = any(r.get("is_anomaly", False) for r in results.values())
    hint = correlate_anomalies(results)
    logger.info("Root-cause analysis: %s", hint)

    # -- Step 4: Take action -------------------------------------------------
    if any_anomaly:
        # Build a summary of which metrics are anomalous
        anomalous_metrics = [
            f"{name} (Z={r['max_zscore']:.1f})"
            for name, r in results.items()
            if r.get("is_anomaly", False)
        ]
        summary = (
            f"Anomaly detected in: {', '.join(anomalous_metrics)}. "
            f"Root-cause: {hint}"
        )

        logger.warning("🚨 ANOMALY DETECTED — %s", summary)

        # Create Kubernetes Event
        create_kubernetes_event(
            namespace=config.NAMESPACE,
            message=summary,
            reason="AnomalyDetected",
            event_type="Warning",
        )

        # Create Grafana Annotation
        create_grafana_annotation(
            grafana_url=config.GRAFANA_URL,
            api_key=config.GRAFANA_API_KEY,
            dashboard_uid=config.DASHBOARD_UID,
            title="Argus: Anomaly Detected",
            text=summary,
            tags=["argus", "anomaly", "detector"],
        )
    else:
        logger.info("✅ All metrics nominal — no anomalies detected.")

    logger.info("=" * 60)
    return any_anomaly


def main():
    """Entry point — run detection and exit."""
    try:
        anomaly_found = run_detection()
        sys.exit(0)  # Always exit 0 — anomaly is not an error
    except Exception as e:
        logger.critical("Fatal error in detector: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
