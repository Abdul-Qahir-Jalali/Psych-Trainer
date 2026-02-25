import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_api_session_start(async_client: AsyncClient, mock_redis, mock_litellm):
    """
    Test that the /api/session/start endpoint correctly initializes a new session
    and returns a valid session ID prefixed by the mocked user ID.
    """
    response = await async_client.post("/api/session/start")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "session_id" in data
    assert "phase" in data
    assert "message" in data
    
    # Assert multi-tenancy enforcement (prefix is the mocked user ID)
    assert data["session_id"].startswith("test_user_001_")

@pytest.mark.asyncio
async def test_api_session_unauthorized(async_client: AsyncClient, mock_redis):
    """
    Test that endpoints requiring auth throw a 401 if we remove the auth override.
    """
    from psychtrainer.service.api import app, get_current_user
    
    # Temporarily remove the mock dependency
    app.dependency_overrides.pop(get_current_user, None)
    
    response = await async_client.post("/api/session/start")
    
    # Re-apply the mock for future tests
    async def override_get_current_user(): return "test_user_001"
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    assert response.status_code == 403 # FastAPI Depends throws 403 if missing Authorization header
