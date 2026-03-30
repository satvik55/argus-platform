"""
Application configuration loaded from environment variables.

In Kubernetes these will be injected via ConfigMap → env vars.
Locally they fall back to development defaults.
"""

import os


class Config:
    APP_VERSION = os.environ.get("APP_VERSION", "dev")
    HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
    PORT = int(os.environ.get("FLASK_PORT", "5000"))
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
