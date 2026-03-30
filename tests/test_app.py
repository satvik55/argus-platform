"""
Test suite for Argus API.

Covers all public endpoints: health, metrics, items CRUD, and stress.
Run with: pytest tests/ -v
"""

import pytest

from app.main import app, ITEMS


@pytest.fixture
def client():
    """Create a Flask test client with testing mode enabled."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def reset_items():
    """Reset the in-memory items store before each test to avoid bleed."""
    original = ITEMS.copy()
    yield
    ITEMS.clear()
    ITEMS.extend(original)


# -- Health endpoint ---------------------------------------------------------
class TestHealth:
    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_status_healthy(self, client):
        data = resp = client.get("/health").get_json()
        assert data["status"] == "healthy"

    def test_includes_version(self, client):
        data = client.get("/health").get_json()
        assert "version" in data


# -- Metrics endpoint --------------------------------------------------------
class TestMetrics:
    def test_returns_200(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_contains_request_count(self, client):
        resp = client.get("/metrics")
        assert b"request_count_total" in resp.data

    def test_contains_latency_histogram(self, client):
        resp = client.get("/metrics")
        assert b"request_latency_seconds" in resp.data

    def test_contains_active_requests(self, client):
        resp = client.get("/metrics")
        assert b"active_requests" in resp.data


# -- Items CRUD --------------------------------------------------------------
class TestItems:
    def test_get_items_returns_list(self, client):
        resp = client.get("/api/items")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "items" in data
        assert "count" in data
        assert data["count"] == len(data["items"])

    def test_get_items_has_default_data(self, client):
        """App ships with seed data so the endpoint isn't empty on first demo."""
        data = client.get("/api/items").get_json()
        assert data["count"] >= 1

    def test_create_item_success(self, client):
        resp = client.post(
            "/api/items",
            json={"name": "test-service", "status": "provisioning"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "test-service"
        assert data["status"] == "provisioning"
        assert "id" in data

    def test_create_item_default_status(self, client):
        """If no status provided, default to 'active'."""
        resp = client.post("/api/items", json={"name": "new-service"})
        assert resp.status_code == 201
        assert resp.get_json()["status"] == "active"

    def test_create_item_missing_name_returns_400(self, client):
        resp = client.post("/api/items", json={"status": "active"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_item_empty_body_returns_400(self, client):
        resp = client.post(
            "/api/items", data="", content_type="application/json"
        )
        assert resp.status_code == 400


# -- Stress endpoint ---------------------------------------------------------
class TestStress:
    def test_returns_200(self, client):
        resp = client.post("/api/stress?duration=1")
        assert resp.status_code == 200

    def test_returns_duration(self, client):
        resp = client.post("/api/stress?duration=2")
        data = resp.get_json()
        assert data["duration_seconds"] == 2

    def test_caps_duration_at_30(self, client):
        """Safety: don't allow runaway CPU burn on a small node."""
        resp = client.post("/api/stress?duration=120")
        data = resp.get_json()
        assert data["duration_seconds"] == 30

    def test_default_duration_is_5(self, client):
        resp = client.post("/api/stress")
        data = resp.get_json()
        assert data["duration_seconds"] == 5
