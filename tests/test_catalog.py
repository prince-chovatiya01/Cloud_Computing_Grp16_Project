"""
test_catalog.py — tests for GET /catalog
"""
import pytest

REQUIRED_FIELDS = {"id", "title", "genre", "release_year", "rating", "description"}


@pytest.mark.asyncio
async def test_catalog_returns_200(client):
    response = await client.get("/catalog")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_catalog_minimum_items(client):
    data = (await client.get("/catalog")).json()
    assert data["count"] >= 10, f"Expected ≥10 items, got {data['count']}"
    assert len(data["items"]) == data["count"]


@pytest.mark.asyncio
async def test_catalog_item_schema(client):
    data = (await client.get("/catalog")).json()
    for item in data["items"]:
        missing = REQUIRED_FIELDS - set(item.keys())
        assert not missing, f"Item missing fields: {missing}"


@pytest.mark.asyncio
async def test_catalog_rating_values(client):
    data = (await client.get("/catalog")).json()
    for item in data["items"]:
        assert 0 <= item["rating"] <= 10, f"Rating out of range: {item['rating']}"


@pytest.mark.asyncio
async def test_catalog_genre_filter(client):
    response = await client.get("/catalog?genre=Drama")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert "drama" in item["genre"].lower(), f"Genre filter failed: {item['genre']}"


@pytest.mark.asyncio
async def test_catalog_limit(client):
    response = await client.get("/catalog?limit=3")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] <= 3
    assert len(data["items"]) <= 3


@pytest.mark.asyncio
async def test_catalog_ordered_by_rating_desc(client):
    data = (await client.get("/catalog")).json()
    ratings = [item["rating"] for item in data["items"]]
    assert ratings == sorted(ratings, reverse=True), "Catalog not sorted by rating desc"
