"""
Anomaly response actions for the Argus Detector.

When an anomaly is detected, two actions are taken:
  1. Kubernetes Event — visible in `kubectl get events -n argus`
  2. Grafana Annotation — red vertical line on the dashboard timeline

Both are best-effort: if either fails, the detector logs the error
and continues.  A monitoring tool should never crash itself.
"""

import json
import logging
import time

import requests

logger = logging.getLogger("argus.actions")


def create_kubernetes_event(
    namespace: str,
    message: str,
    reason: str = "AnomalyDetected",
    event_type: str = "Warning",
) -> bool:
    """
    Create a Kubernetes Event in the specified namespace.

    Uses the Kubernetes API directly via the in-cluster service account.
    This avoids the heavyweight `kubernetes` Python client library.

    Args:
        namespace: target namespace
        message: event message body
        reason: short CamelCase reason string
        event_type: "Normal" or "Warning"

    Returns:
        True if created successfully, False otherwise.
    """
    try:
        # In-cluster: service account token is mounted at this path
        token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

        with open(token_path) as f:
            token = f.read().strip()

        api_url = "https://kubernetes.default.svc"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        event_name = f"argus-anomaly-{int(time.time())}"

        event = {
            "apiVersion": "v1",
            "kind": "Event",
            "metadata": {
                "name": event_name,
                "namespace": namespace,
            },
            "involvedObject": {
                "kind": "Namespace",
                "name": namespace,
                "namespace": namespace,
                "apiVersion": "v1",
            },
            "reason": reason,
            "message": message[:1024],  # K8s event message limit
            "type": event_type,
            "firstTimestamp": now,
            "lastTimestamp": now,
            "source": {
                "component": "argus-detector",
            },
        }

        resp = requests.post(
            f"{api_url}/api/v1/namespaces/{namespace}/events",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=event,
            verify=ca_path,
            timeout=10,
        )

        if resp.status_code in (200, 201):
            logger.info("Kubernetes Event created: %s", event_name)
            return True
        else:
            logger.warning(
                "Failed to create K8s Event: %s %s",
                resp.status_code,
                resp.text[:200],
            )
            return False

    except FileNotFoundError:
        logger.warning(
            "Not running in-cluster (no service account token). "
            "Kubernetes Event skipped."
        )
        return False
    except Exception as e:
        logger.error("Failed to create Kubernetes Event: %s", e)
        return False


def create_grafana_annotation(
    grafana_url: str,
    api_key: str,
    dashboard_uid: str,
    title: str,
    text: str,
    tags: list[str] | None = None,
) -> bool:
    """
    Push an annotation to a Grafana dashboard.

    This creates a red vertical line on the dashboard timeline, marking
    when the anomaly was detected.  Hovering over it shows the title and
    root-cause hint.

    Args:
        grafana_url: Grafana base URL (e.g., http://grafana.monitoring:80)
        api_key: Grafana API key or service account token
        dashboard_uid: UID of the target dashboard
        title: annotation title (shown on hover)
        text: annotation body (root-cause hint shown on hover)
        tags: list of string tags for filtering

    Returns:
        True if created successfully, False otherwise.
    """
    if not api_key:
        logger.warning("No Grafana API key configured — annotation skipped.")
        return False

    if tags is None:
        tags = ["argus", "anomaly"]

    url = f"{grafana_url.rstrip('/')}/api/annotations"

    payload = {
        "dashboardUID": dashboard_uid,
        "time": int(time.time() * 1000),  # Grafana uses milliseconds
        "tags": tags,
        "text": f"<b>{title}</b><br/>{text}",
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            url, headers=headers, json=payload, timeout=10
        )

        if resp.status_code == 200:
            logger.info("Grafana annotation created on dashboard %s", dashboard_uid)
            return True
        else:
            logger.warning(
                "Failed to create Grafana annotation: %s %s",
                resp.status_code,
                resp.text[:200],
            )
            return False

    except Exception as e:
        logger.error("Failed to create Grafana annotation: %s", e)
        return False
