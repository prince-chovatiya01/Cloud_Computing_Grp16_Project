"""
test_health.py — tests for GET /health
"""
import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_schema(client):
    data = (await client.get("/health")).json()
    assert "status" in data
    assert "db" in data
    assert data["status"] in ("healthy", "degraded")


@pytest.mark.asyncio
async def test_health_db_connected(client):
    """With the seeded test DB the health endpoint should report connected."""
    data = (await client.get("/health")).json()
    assert data["db"] == "connected"
    assert data["status"] == "healthy"
    assert data["db_latency_ms"] is not None
    assert data["db_latency_ms"] >= 0
