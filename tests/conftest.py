from typing import AsyncGenerator
import pytest
from httpx import AsyncClient
import uuid

# We need to set up environment variables BEFORE importing the app
import os
os.environ["SUPABASE_URL"] = "http://fake-supabase.com"
os.environ["SUPABASE_ANON_KEY"] = "fake-key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "fake-service-key"
os.environ["GROQ_API_KEY"] = "fake-groq-key"
os.environ["REDIS_URI"] = "redis://fake-redis.com:6379"

# Now we can safely import the FastAPI app
from psychtrainer.service.api import app, get_current_user

# --- Mock Authentication ---
async def override_get_current_user():
    """Bypasses Supabase JWT validation during Pytest runs."""
    return "test_user_001"

app.dependency_overrides[get_current_user] = override_get_current_user

# --- Mock FastAPI App State (Bypassing Lifespan) ---
class MockWorkflow:
    def update_state(self, config, state):
        pass
        
    async def aupdate_state(self, config, state):
        pass
        
    async def aget_state(self, config):
        class MockSnapshot:
            pass
        snapshot = MockSnapshot()
        snapshot.values = {
            "turn_count": 0,
            "session_id": "test_session",
            "phase": "introduction"
        }
        return snapshot

app.state.few_shot_examples = "Mocked guidelines."
app.state.workflow = MockWorkflow()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provides a mocked async HTTP client to securely test FastAPI endpoints."""
    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

@pytest.fixture
def mock_redis(mocker):
    """Mocks the Upstash Redis rate limiter to prevent connection failures in CI."""
    mock_pool = mocker.patch("redis.asyncio.ConnectionPool.from_url")
    return mock_pool

@pytest.fixture
def mock_litellm(mocker):
    """
    Critically important fixture: intercepts all litellm.completion calls
    so that tests NEVER spend actual Groq API tokens.
    """
    class MockMessage:
        content = "This is a securely mocked response from the LLM."
        
    class MockChoice:
        message = MockMessage()
        
    class MockResponse:
        choices = [MockChoice()]

    return mocker.patch("litellm.completion", return_value=MockResponse())

@pytest.fixture(autouse=True)
def mock_prompt_registry(mocker):
    """
    Critically important fixture: Intercepts all calls to the Supabase Prompt Registry
    during testing to guarantee zero database hits and zero Redis hits.
    """
    async def mock_get_system_prompt(role: str, ignore_cache: bool = False):
        if role == "patient_persona":
            return "You are a simulated patient for testing."
        elif role == "professor_grader":
            return "You are a simulated professor for testing."
        elif role == "phase_router":
            return "Rules: Output ONLY one word: examination."
        return "Generic prompt."

    return mocker.patch(
        "psychtrainer.workflow.prompt_registry.get_system_prompt",
        side_effect=mock_get_system_prompt
    )
