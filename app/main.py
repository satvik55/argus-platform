"""
Argus API — Flask application with built-in Prometheus instrumentation.

Endpoints:
    GET  /health      → Liveness/readiness probe target
    GET  /metrics     → Prometheus-format metrics scrape target
    GET  /api/items   → List all monitored items
    POST /api/items   → Add a new item
    POST /api/stress  → Burn CPU for N seconds (demo/testing only)

Every request is instrumented automatically via before_request / after_request
hooks — no per-endpoint boilerplate needed.
"""

import os
import time
import threading

from flask import Flask, jsonify, request
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.metrics import (
    REQUEST_COUNT,
    REQUEST_LATENCY,
    ERROR_COUNT,
    ACTIVE_REQUESTS,
)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# In-memory data store.  No database needed — Argus is an observability
# platform demo, not a CRUD app.  The items exist so we have a realistic
# endpoint to throw load at.
# ---------------------------------------------------------------------------
ITEMS = [
    {"id": 1, "name": "kubernetes-cluster", "status": "healthy"},
    {"id": 2, "name": "monitoring-stack", "status": "active"},
    {"id": 3, "name": "ci-cd-pipeline", "status": "configured"},
]

VERSION = os.environ.get("APP_VERSION", "dev")


# ---------------------------------------------------------------------------
# Request instrumentation — runs on every request automatically
# ---------------------------------------------------------------------------
@app.before_request
def _start_timer():
    """Record request start time and increment the active-requests gauge."""
    request._start_time = time.time()
    ACTIVE_REQUESTS.inc()


@app.after_request
def _record_metrics(response):
    """Record latency, request count, and error count after each response."""
    ACTIVE_REQUESTS.dec()

    latency = time.time() - getattr(request, "_start_time", time.time())

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.path,
        status=response.status_code,
    ).inc()

    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.path,
    ).observe(latency)

    if response.status_code >= 500:
        ERROR_COUNT.labels(
            method=request.method,
            endpoint=request.path,
        ).inc()

    return response


# ---------------------------------------------------------------------------
# Health endpoint — used by Kubernetes liveness & readiness probes
# ---------------------------------------------------------------------------
@app.route("/health")
def health():
    return jsonify({"status": "healthy", "version": VERSION})


# ---------------------------------------------------------------------------
# Prometheus metrics endpoint — scraped by Prometheus every 15 s
# ---------------------------------------------------------------------------
@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ---------------------------------------------------------------------------
# Items CRUD — gives us a realistic endpoint to load-test
# ---------------------------------------------------------------------------
@app.route("/api/items", methods=["GET"])
def get_items():
    return jsonify({"items": ITEMS, "count": len(ITEMS)})


@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"error": "name is required"}), 400

    new_id = max((item["id"] for item in ITEMS), default=0) + 1
    new_item = {
        "id": new_id,
        "name": data["name"],
        "status": data.get("status", "active"),
    }
    ITEMS.append(new_item)
    return jsonify(new_item), 201


# ---------------------------------------------------------------------------
# Stress endpoint — intentionally burns CPU so we can trigger HPA scaling
# and test the anomaly detector.  Duration is capped at 30 s for safety.
# ---------------------------------------------------------------------------
@app.route("/api/stress", methods=["POST"])
def stress():
    duration = request.args.get("duration", 5, type=int)
    duration = min(duration, 30)  # hard cap — don't melt the t3.medium

    def _burn_cpu(seconds: int):
        end = time.time() + seconds
        while time.time() < end:
            _ = sum(i * i for i in range(10000))

    thread = threading.Thread(target=_burn_cpu, args=(duration,), daemon=True)
    thread.start()

    return jsonify(
        {"message": f"CPU stress started for {duration}s", "duration_seconds": duration}
    )


# ---------------------------------------------------------------------------
# Direct execution — only for local dev.  In production, gunicorn runs this.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Platform info — added via CI pipeline (Day 4)
# ---------------------------------------------------------------------------
@app.route("/api/info")
def info():
    return jsonify({
        "platform": "Argus Observability Platform",
        "components": [
            "Flask API with Prometheus metrics",
            "k3s Kubernetes cluster",
            "Helm-managed deployment",
            "GitHub Actions CI pipeline",
        ],
        "version": VERSION,
    })
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
