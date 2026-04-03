"""
Prometheus HTTP API client for the Argus Anomaly Detector.

Fetches time-series metrics using range queries.  Each query returns a list
of (timestamp, value) tuples that the Z-score analyzer can process.
"""

import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger("argus.prometheus")


class PrometheusClient:
    """Thin wrapper around the Prometheus /api/v1/query_range endpoint."""

    def __init__(self, base_url: str, timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def query_range(
        self, query: str, range_minutes: int = 30, step: str = "30s"
    ) -> list[tuple[float, float]]:
        """
        Execute a PromQL range query and return [(timestamp, value), ...].

        Args:
            query: PromQL expression
            range_minutes: how far back to look
            step: resolution (e.g. "30s", "1m")

        Returns:
            List of (unix_timestamp, float_value) tuples, sorted by time.
            Returns empty list on any error (logged, not raised).
        """
        now = datetime.now(timezone.utc)
        start = now.timestamp() - (range_minutes * 60)
        end = now.timestamp()

        url = f"{self.base_url}/api/v1/query_range"
        params = {
            "query": query,
            "start": start,
            "end": end,
            "step": step,
        }

        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "success":
                logger.warning("Prometheus query failed: %s", data)
                return []

            results = data.get("data", {}).get("result", [])
            if not results:
                logger.info("No data for query: %s", query)
                return []

            # Flatten all series into one list of (timestamp, value) pairs.
            # For aggregate queries (sum/rate) there's usually one series.
            # For per-pod queries we take the max across pods at each timestamp.
            points = []
            for series in results:
                for ts, val in series.get("values", []):
                    try:
                        points.append((float(ts), float(val)))
                    except (ValueError, TypeError):
                        continue

            # Sort by timestamp and deduplicate
            points.sort(key=lambda p: p[0])
            return points

        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Prometheus at %s", self.base_url)
            return []
        except requests.exceptions.Timeout:
            logger.error("Prometheus query timed out: %s", query)
            return []
        except Exception as e:
            logger.error("Prometheus query error: %s — %s", query, e)
            return []
