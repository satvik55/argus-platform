"""
Root-cause correlation engine for the Argus Detector.

Compares anomaly results across metrics to produce actionable hints.
This is the "AI" in AIOps — not machine learning, but structured
reasoning about metric relationships.

Correlation rules are based on common patterns observed in production
Kubernetes environments:

  CPU high + request rate high + pod count stable
    → HPA is too slow or threshold too high

  Error rate high + latency high + CPU normal
    → Application-level bug, not a resource issue

  CPU high + request rate normal
    → Background process, memory leak, or GC pressure

  Latency high + CPU normal + error rate normal
    → Downstream dependency slow (DB, external API)
"""

import logging

logger = logging.getLogger("argus.correlator")


def correlate_anomalies(results: dict[str, dict]) -> str:
    """
    Given a dict of metric_name → analysis_result, produce a root-cause hint.

    Args:
        results: {
            "cpu": {"is_anomaly": bool, "max_zscore": float, ...},
            "request_rate": {...},
            "error_rate": {...},
            "latency_p99": {...},
        }

    Returns:
        Human-readable root-cause hint string.
    """
    cpu = results.get("cpu", {})
    request_rate = results.get("request_rate", {})
    error_rate = results.get("error_rate", {})
    latency = results.get("latency_p99", {})

    cpu_anomaly = cpu.get("is_anomaly", False)
    rate_anomaly = request_rate.get("is_anomaly", False)
    error_anomaly = error_rate.get("is_anomaly", False)
    latency_anomaly = latency.get("is_anomaly", False)

    hints = []

    # Pattern 6 (check FIRST): Everything is anomalous (system overload)
    if cpu_anomaly and error_anomaly and latency_anomaly:
        hints.append(
            "Multiple metrics anomalous simultaneously → "
            "Recommendation: System may be overloaded. "
            "Immediate action: scale up pods or reduce traffic. "
            f"CPU Z: {cpu.get('max_zscore', 0):.1f}, "
            f"Error Z: {error_rate.get('max_zscore', 0):.1f}, "
            f"Latency Z: {latency.get('max_zscore', 0):.1f}"
        )

    # Pattern 1: CPU spike + request surge + stable pod count
    elif cpu_anomaly and rate_anomaly:
        hints.append(
            "CPU spike correlates with elevated request volume → "
            "Recommendation: Check HPA threshold, scaling may be too slow. "
            f"CPU Z-score: {cpu.get('max_zscore', 0):.1f}, "
            f"Request rate Z-score: {request_rate.get('max_zscore', 0):.1f}"
        )

    # Pattern 2: Error rate + latency high + CPU normal
    elif error_anomaly and latency_anomaly and not cpu_anomaly:
        hints.append(
            "Error rate and latency elevated without CPU pressure → "
            "Recommendation: Application-level issue suspected. "
            "Check application logs for exceptions or failed dependencies. "
            f"Error Z-score: {error_rate.get('max_zscore', 0):.1f}, "
            f"Latency Z-score: {latency.get('max_zscore', 0):.1f}"
        )

    # Pattern 3: CPU high + request rate normal
    elif cpu_anomaly and not rate_anomaly:
        hints.append(
            "CPU elevated without corresponding request increase → "
            "Recommendation: Possible memory leak, background process, "
            "or GC pressure. Check container resource usage. "
            f"CPU Z-score: {cpu.get('max_zscore', 0):.1f}"
        )

    # Pattern 4: Latency high + everything else normal
    elif latency_anomaly and not cpu_anomaly and not error_anomaly:
        hints.append(
            "Latency spike without CPU or error anomalies → "
            "Recommendation: Possible downstream dependency slowness "
            "(database, external API) or network congestion. "
            f"Latency Z-score: {latency.get('max_zscore', 0):.1f}"
        )

    # Pattern 5: Error rate high alone
    elif error_anomaly and not cpu_anomaly and not latency_anomaly:
        hints.append(
            "Error rate elevated without resource pressure → "
            "Recommendation: Check for bad deployment, config change, "
            "or upstream sending malformed requests. "
            f"Error Z-score: {error_rate.get('max_zscore', 0):.1f}"
        )

    # Fallback: single metric anomaly not covered above
    else:
        anomalous = [
            name
            for name, r in results.items()
            if r.get("is_anomaly", False)
        ]
        if anomalous:
            hints.append(
                f"Anomaly detected in: {', '.join(anomalous)}. "
                "No strong cross-metric correlation found. "
                "Investigate individual metric trends."
            )

    if not hints:
        return "All metrics within normal range — no anomalies detected."

    return " | ".join(hints)
