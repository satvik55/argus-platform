"""
Z-score anomaly detection for the Argus Detector.

Uses a rolling window to calculate mean and standard deviation, then
flags data points where the Z-score exceeds the configured threshold.

Why Z-score (not ML):
  - No training data required — works from the first minute of operation
  - Explainable — "this value is 3.1 standard deviations above normal"
  - Low compute — runs in a CronJob, no GPU or model serving needed
  - Real SRE teams start here; ML (LSTM, Isolation Forest) is a later step
"""

import logging
import math

logger = logging.getLogger("argus.analyzer")


class ZScoreAnalyzer:
    """Rolling Z-score anomaly detector."""

    def __init__(self, window: int = 10, threshold: float = 2.5):
        """
        Args:
            window: number of data points for rolling mean/stddev
            threshold: Z-score value above which a point is anomalous
        """
        self.window = window
        self.threshold = threshold

    def analyze(
        self, data_points: list[tuple[float, float]]
    ) -> dict:
        """
        Analyze a time series for anomalies.

        Args:
            data_points: [(timestamp, value), ...] sorted by timestamp

        Returns:
            {
                "is_anomaly": bool,
                "max_zscore": float,
                "latest_value": float,
                "mean": float,
                "stddev": float,
                "anomaly_points": [(timestamp, value, zscore), ...],
                "data_point_count": int,
            }
        """
        result = {
            "is_anomaly": False,
            "max_zscore": 0.0,
            "latest_value": 0.0,
            "mean": 0.0,
            "stddev": 0.0,
            "anomaly_points": [],
            "data_point_count": len(data_points),
        }

        if len(data_points) < self.window:
            logger.info(
                "Not enough data points (%d) for window size %d",
                len(data_points),
                self.window,
            )
            return result

        values = [v for _, v in data_points]
        result["latest_value"] = values[-1]

        # Calculate rolling Z-scores for the last N points
        anomaly_points = []
        max_zscore = 0.0

        for i in range(self.window, len(values)):
            window_slice = values[i - self.window : i]
            mean = sum(window_slice) / len(window_slice)
            variance = sum((x - mean) ** 2 for x in window_slice) / len(
                window_slice
            )
            stddev = math.sqrt(variance)

            current_value = values[i]
            timestamp = data_points[i][0]

            if stddev == 0:
                # All values in window are identical.
                # If current value differs from mean, it's a clear anomaly.
                if current_value != mean:
                    zscore = float("inf")
                else:
                    zscore = 0.0
            else:
                zscore = abs(current_value - mean) / stddev

            if zscore > max_zscore:
                max_zscore = zscore
                result["mean"] = mean
                result["stddev"] = stddev

            if zscore > self.threshold:
                anomaly_points.append((timestamp, current_value, zscore))

        result["max_zscore"] = round(max_zscore, 3)
        result["anomaly_points"] = anomaly_points
        result["is_anomaly"] = len(anomaly_points) > 0

        return result
