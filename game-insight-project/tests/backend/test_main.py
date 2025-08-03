"""Tests for the main FastAPI application."""

import os
import httpx
import pytest

# The base URL for the backend service, configured via environment variable
BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://backend:8000")


@pytest.mark.asyncio
async def test_health_check():
    """
    Tests that the /health endpoint returns a successful response.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
