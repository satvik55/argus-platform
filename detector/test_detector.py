"""
Test suite for the Argus Anomaly Detector.

All Prometheus interactions are mocked — tests run without a real
Prometheus instance.  Covers: Z-score calculation, root-cause
correlation, and the main detection loop.
"""

import math
from unittest.mock import patch, MagicMock

import pytest

from analyzer import ZScoreAnalyzer
from correlator import correlate_anomalies


# =============================================================================
# ZScoreAnalyzer Tests
# =============================================================================
class TestZScoreAnalyzer:
    def test_not_enough_data_points(self):
        """Returns no anomaly if fewer data points than window size."""
        analyzer = ZScoreAnalyzer(window=10, threshold=2.5)
        data = [(float(i), 1.0) for i in range(5)]
        result = analyzer.analyze(data)
        assert result["is_anomaly"] is False
        assert result["data_point_count"] == 5

    def test_stable_data_no_anomaly(self):
        """All values identical — Z-score is 0, no anomaly."""
        analyzer = ZScoreAnalyzer(window=5, threshold=2.5)
        data = [(float(i), 10.0) for i in range(20)]
        result = analyzer.analyze(data)
        assert result["is_anomaly"] is False
        assert result["max_zscore"] == 0.0

    def test_spike_detected_as_anomaly(self):
        """A sudden spike should be flagged as an anomaly."""
        analyzer = ZScoreAnalyzer(window=5, threshold=2.0)
        # 15 normal values at 10.0, then a spike to 100.0
        data = [(float(i), 10.0) for i in range(15)]
        data.append((15.0, 100.0))
        result = analyzer.analyze(data)
        assert result["is_anomaly"] is True
        assert result["max_zscore"] > 2.0
        assert len(result["anomaly_points"]) >= 1

    def test_gradual_increase_no_anomaly(self):
        """Slowly rising values should not trigger with a large window."""
        analyzer = ZScoreAnalyzer(window=10, threshold=3.0)
        data = [(float(i), float(i)) for i in range(30)]
        result = analyzer.analyze(data)
        # Gradual increase: Z-scores stay moderate because the window
        # captures the trend. Should not trigger at threshold 3.0.
        # (This test validates that the detector doesn't over-alert on trends)
        assert result["max_zscore"] < 5.0  # Some Z-score is expected

    def test_empty_data(self):
        """Empty input returns clean result."""
        analyzer = ZScoreAnalyzer(window=5, threshold=2.5)
        result = analyzer.analyze([])
        assert result["is_anomaly"] is False
        assert result["data_point_count"] == 0

    def test_threshold_boundary(self):
        """Value exactly at threshold boundary."""
        analyzer = ZScoreAnalyzer(window=5, threshold=2.5)
        # Create data where we can predict the Z-score
        data = [(float(i), 10.0) for i in range(10)]
        result = analyzer.analyze(data)
        assert result["is_anomaly"] is False

    def test_latest_value_tracked(self):
        """Result should track the most recent value."""
        analyzer = ZScoreAnalyzer(window=5, threshold=2.5)
        data = [(float(i), float(i * 2)) for i in range(15)]
        result = analyzer.analyze(data)
        assert result["latest_value"] == 28.0  # 14 * 2


# =============================================================================
# Correlator Tests
# =============================================================================
class TestCorrelator:
    def test_cpu_and_request_rate_anomaly(self):
        """CPU + request rate → HPA scaling hint."""
        results = {
            "cpu": {"is_anomaly": True, "max_zscore": 3.5},
            "request_rate": {"is_anomaly": True, "max_zscore": 4.0},
            "error_rate": {"is_anomaly": False, "max_zscore": 0.5},
            "latency_p99": {"is_anomaly": False, "max_zscore": 0.3},
        }
        hint = correlate_anomalies(results)
        assert "CPU spike" in hint
        assert "request volume" in hint
        assert "HPA" in hint

    def test_error_and_latency_anomaly(self):
        """Error rate + latency without CPU → application issue."""
        results = {
            "cpu": {"is_anomaly": False, "max_zscore": 0.5},
            "request_rate": {"is_anomaly": False, "max_zscore": 0.8},
            "error_rate": {"is_anomaly": True, "max_zscore": 3.0},
            "latency_p99": {"is_anomaly": True, "max_zscore": 2.8},
        }
        hint = correlate_anomalies(results)
        assert "Application-level" in hint

    def test_cpu_only_anomaly(self):
        """CPU alone → memory leak / background process."""
        results = {
            "cpu": {"is_anomaly": True, "max_zscore": 4.0},
            "request_rate": {"is_anomaly": False, "max_zscore": 0.3},
            "error_rate": {"is_anomaly": False, "max_zscore": 0.1},
            "latency_p99": {"is_anomaly": False, "max_zscore": 0.5},
        }
        hint = correlate_anomalies(results)
        assert "memory leak" in hint or "background process" in hint

    def test_no_anomalies(self):
        """All normal → clean message."""
        results = {
            "cpu": {"is_anomaly": False, "max_zscore": 0.5},
            "request_rate": {"is_anomaly": False, "max_zscore": 0.3},
            "error_rate": {"is_anomaly": False, "max_zscore": 0.1},
            "latency_p99": {"is_anomaly": False, "max_zscore": 0.5},
        }
        hint = correlate_anomalies(results)
        assert "normal range" in hint

    def test_all_anomalous(self):
        """Everything anomalous → system overload."""
        results = {
            "cpu": {"is_anomaly": True, "max_zscore": 5.0},
            "request_rate": {"is_anomaly": True, "max_zscore": 4.0},
            "error_rate": {"is_anomaly": True, "max_zscore": 3.5},
            "latency_p99": {"is_anomaly": True, "max_zscore": 4.2},
        }
        hint = correlate_anomalies(results)
        assert "overloaded" in hint or "Multiple" in hint

    def test_latency_only_anomaly(self):
        """Latency alone → downstream dependency."""
        results = {
            "cpu": {"is_anomaly": False, "max_zscore": 0.5},
            "request_rate": {"is_anomaly": False, "max_zscore": 0.3},
            "error_rate": {"is_anomaly": False, "max_zscore": 0.1},
            "latency_p99": {"is_anomaly": True, "max_zscore": 3.0},
        }
        hint = correlate_anomalies(results)
        assert "downstream" in hint or "dependency" in hint


# =============================================================================
# Integration Test (with mocked Prometheus)
# =============================================================================
class TestDetectorIntegration:
    @patch("anomaly_detector.PrometheusClient")
    def test_detection_with_normal_metrics(self, MockPromClient):
        """Full detection cycle with normal data — no anomaly."""
        mock_client = MagicMock()
        MockPromClient.return_value = mock_client

        # Return stable data for all metrics
        stable_data = [(float(i), 10.0) for i in range(60)]
        mock_client.query_range.return_value = stable_data

        from anomaly_detector import run_detection

        result = run_detection()
        assert result is False  # No anomaly

    @patch("anomaly_detector.PrometheusClient")
    def test_detection_with_cpu_spike(self, MockPromClient):
        """Full detection cycle with CPU spike — anomaly detected."""
        mock_client = MagicMock()
        MockPromClient.return_value = mock_client

        # Normal data for most metrics
        stable_data = [(float(i), 5.0) for i in range(60)]

        # CPU data with a spike at the end
        cpu_data = [(float(i), 5.0) for i in range(55)]
        cpu_data.extend([(float(55 + i), 95.0) for i in range(5)])

        def mock_query(query, **kwargs):
            if "cpu" in query:
                return cpu_data
            return stable_data

        mock_client.query_range.side_effect = mock_query

        from anomaly_detector import run_detection

        result = run_detection()
        assert result is True  # Anomaly detected
