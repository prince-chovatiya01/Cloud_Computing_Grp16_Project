"""
test_app.py - Unified test suite for the Mini-Netflix Flask application.

Covers:
  - Health endpoint
  - Movie listing, lookup, and 404
  - Personalised recommendations
  - Login success and failure
  - X-Served-By header
  - Idempotent seeding
  - Circuit-breaker fallback behaviour
  - Fault-injection admin endpoint
"""
import importlib
import os
import tempfile

import pytest


def make_client(service="monolith", breaker="on", faults="0"):
    """Build a Flask test client with the given configuration."""
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    fault_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    fault_file.close()

    os.environ["SQLITE_PATH"] = db_file.name
    os.environ["DATABASE_URL"] = ""
    os.environ["SERVICE"] = service
    os.environ["BREAKER"] = breaker
    os.environ["FAULTS_ENABLED"] = faults
    os.environ["FAULT_FILE"] = fault_file.name

    # Reload modules so they pick up new env vars
    from app.src import db, main, recommendations
    importlib.reload(db)
    importlib.reload(recommendations)
    importlib.reload(main)

    app = main.create_app(service)
    app.config["TESTING"] = True
    return app.test_client(), db_file.name, fault_file.name


# ── Monolith tests ─────────────────────────────────────────────────────────

class TestMonolith:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client, self.db_path, self.fault_path = make_client()
        yield
        try:
            os.unlink(self.db_path)
            os.unlink(self.fault_path)
        except OSError:
            pass

    def test_health(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_movies_list(self):
        resp = self.client.get("/movies")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] > 0
        assert len(data["items"]) == data["count"]

    def test_movie_lookup(self):
        resp = self.client.get("/movies/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == 1

    def test_movie_not_found(self):
        resp = self.client.get("/movies/999999")
        assert resp.status_code == 404

    def test_recommendations(self):
        resp = self.client.get("/recommendations/user1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] > 0

    def test_login_success(self):
        resp = self.client.post(
            "/login",
            json={"username": "user1", "password": "password123"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert "token" in resp.get_json()

    def test_login_failure(self):
        resp = self.client.post(
            "/login",
            json={"username": "user1", "password": "wrong"},
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_served_by_header(self):
        resp = self.client.get("/health")
        assert "X-Served-By" in resp.headers
        assert "/monolith" in resp.headers["X-Served-By"]


# ── Idempotent seed test ───────────────────────────────────────────────────

class TestSeedIdempotent:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client, self.db_path, self.fault_path = make_client()
        yield
        try:
            os.unlink(self.db_path)
            os.unlink(self.fault_path)
        except OSError:
            pass

    def test_seed_twice_no_duplicates(self):
        from app.src import db
        db.init()
        resp = self.client.get("/movies?page=1")
        count_before = resp.get_json()["count"]

        db.init()
        resp = self.client.get("/movies?page=1")
        count_after = resp.get_json()["count"]

        assert count_before == count_after


# ── Circuit-breaker tests ──────────────────────────────────────────────────

class TestCircuitBreaker:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client, self.db_path, self.fault_path = make_client(
            service="monolith", breaker="on"
        )
        yield
        try:
            os.unlink(self.db_path)
            os.unlink(self.fault_path)
        except OSError:
            pass

    def test_home_returns_200_with_fallback(self):
        resp = self.client.get("/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trending" in data
        assert "recommendations" in data


# ── Fault-injection tests ──────────────────────────────────────────────────

class TestFaultInjection:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client, self.db_path, self.fault_path = make_client(
            faults="1"
        )
        yield
        try:
            os.unlink(self.db_path)
            os.unlink(self.fault_path)
        except OSError:
            pass

    def test_admin_fault_set_and_clear(self):
        resp = self.client.post(
            "/admin/fault",
            json={"error_rate": 1.0},
            content_type="application/json",
        )
        assert resp.status_code == 200

        resp = self.client.get("/recommendations/user1")
        assert resp.status_code == 500

        resp = self.client.delete("/admin/fault")
        assert resp.status_code == 200

        resp = self.client.get("/recommendations/user1")
        assert resp.status_code == 200


class TestFaultInjectionDisabled:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client, self.db_path, self.fault_path = make_client(
            faults="0"
        )
        yield
        try:
            os.unlink(self.db_path)
            os.unlink(self.fault_path)
        except OSError:
            pass

    def test_admin_fault_returns_404(self):
        resp = self.client.get("/admin/fault")
        assert resp.status_code == 404
