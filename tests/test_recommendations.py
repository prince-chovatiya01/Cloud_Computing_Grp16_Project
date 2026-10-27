"""
test_recommendations.py — tests for GET /recommendations

Covers:
  - Normal path (recommendations from DB)
  - Fault-injection guard (forbidden when ENABLE_FAULT_INJECTION=false)
  - Graceful degradation via simulate_failure (when injection is enabled)
  - Static fallback field presence
"""
import pytest
from unittest.mock import patch, AsyncMock

REQUIRED_FIELDS = {"source", "fallback_reason", "count", "items"}
ITEM_FIELDS = {"media_id", "score", "title", "genre", "rating"}


@pytest.mark.asyncio
async def test_recommendations_returns_200(client):
    response = await client.get("/recommendations")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_recommendations_schema(client):
    data = (await client.get("/recommendations")).json()
    missing = REQUIRED_FIELDS - set(data.keys())
    assert not missing, f"Response missing fields: {missing}"


@pytest.mark.asyncio
async def test_recommendations_items_have_fields(client):
    data = (await client.get("/recommendations")).json()
    assert data["count"] > 0
    for item in data["items"]:
        missing = ITEM_FIELDS - set(item.keys())
        assert not missing, f"Item missing fields: {missing}"


@pytest.mark.asyncio
async def test_recommendations_source_is_recommendations(client):
    """Normal path: source should be 'recommendations'."""
    data = (await client.get("/recommendations")).json()
    assert data["source"] == "recommendations"


@pytest.mark.asyncio
async def test_recommendations_limit(client):
    response = await client.get("/recommendations?limit=3")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] <= 3
    assert len(data["items"]) <= 3


@pytest.mark.asyncio
async def test_fault_injection_blocked_by_default(client):
    """Fault injection must return 403 when ENABLE_FAULT_INJECTION is false."""
    response = await client.get("/recommendations?simulate_failure=true")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_fault_injection_delay_blocked_by_default(client):
    response = await client.get("/recommendations?simulate_delay=100")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_simulate_failure_activates_fallback(client):
    """When fault injection is enabled and failure is simulated, fallback is used."""
    with patch("app.routers.recommendations.get_settings") as mock_settings:
        settings = mock_settings.return_value
        settings.enable_fault_injection = True
        settings.recommendation_timeout_ms = 500

        response = await client.get("/recommendations?simulate_failure=true")
        assert response.status_code == 200
        data = response.json()
        assert data["source"] in ("fallback_static", "fallback_top_rated")
        assert data["count"] > 0


@pytest.mark.asyncio
async def test_fallback_still_returns_items(client):
    """Even on fallback, items list must be non-empty and have correct fields."""
    with patch("app.routers.recommendations.get_settings") as mock_settings:
        settings = mock_settings.return_value
        settings.enable_fault_injection = True
        settings.recommendation_timeout_ms = 500

        data = (await client.get("/recommendations?simulate_failure=true")).json()
        assert len(data["items"]) > 0
        for item in data["items"]:
            missing = ITEM_FIELDS - set(item.keys())
            assert not missing, f"Fallback item missing fields: {missing}"
