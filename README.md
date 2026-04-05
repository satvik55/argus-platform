# Argus — Intelligent Kubernetes Observability Platform

> Kubernetes-native observability with GitOps deployment (ArgoCD), full-stack monitoring (Prometheus + Grafana), and AI-powered anomaly detection using statistical analysis.

**🚧 This project is under active development. Full README coming soon.**

## Quick Start (Local Development)

```bash
# Run locally with Docker
docker compose up --build

# Run tests
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Tech Stack

| Layer | Tool |
|-------|------|
| Application | Python 3.11, Flask, prometheus_client |
| Container | Docker (multi-stage build) |
| CI | GitHub Actions |
| CD / GitOps | ArgoCD |
| Orchestration | k3s |
| Packaging | Helm 3 |
| Monitoring | Prometheus + Grafana |
| AI / AIOps | Z-score anomaly detection |
| Auto-scaling | HPA + metrics-server |

