# ===========================================================================
# Stage 1: Builder — install Python dependencies into an isolated prefix.
# Using a separate stage keeps the final image small (no build tools, no pip
# cache, no .pyc compilation artifacts from the install process).
# ===========================================================================
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ===========================================================================
# Stage 2: Runtime — minimal image with only the app and its dependencies.
# Result: ~130 MB instead of ~450 MB with a single-stage build.
# ===========================================================================
FROM python:3.11-slim

# Security: run as non-root.  If the container is compromised, the attacker
# can't escalate to root inside the pod.
RUN groupadd -r argus && useradd -r -g argus -d /app -s /sbin/nologin argus

WORKDIR /app

# Copy pre-built Python packages from the builder stage
COPY --from=builder /install /usr/local

# Copy application source code
COPY app/ ./app/

# Drop privileges
USER argus

EXPOSE 5000

# Gunicorn config:
#   --workers 2    → matches k8s resource limits (250m CPU cap)
#   --threads 2    → handle concurrent requests within each worker
#   --timeout 120  → generous timeout for /api/stress endpoint
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "app.main:app"]
