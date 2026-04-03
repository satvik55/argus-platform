# =============================================================================
# Argus Anomaly Detector — Container Image
#
# Lightweight Python image that runs the Z-score anomaly detector.
# Deployed as a Kubernetes CronJob (every 2 minutes).
#
# Build (from repo root):
#   docker buildx build --platform linux/amd64 \
#     -t satvik55/argus-detector:latest \
#     -f detector/Dockerfile detector/ --push
# =============================================================================
FROM python:3.11-slim

# Security: run as non-root
RUN groupadd -r argus && useradd -r -g argus -d /app -s /sbin/nologin argus

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy detector source code
COPY config.py .
COPY prometheus_client.py .
COPY analyzer.py .
COPY correlator.py .
COPY actions.py .
COPY anomaly_detector.py .

# Drop privileges
USER argus

# Entry point — CronJob runs this
CMD ["python", "anomaly_detector.py"]
