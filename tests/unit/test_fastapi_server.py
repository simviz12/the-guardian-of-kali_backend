"""Unit and integration tests for FastAPI application server, CORS, and Dependency Injection."""
import pytest
from fastapi.testclient import TestClient

from src.main import app, create_app
from src.dependencies import (
    get_execute_command_use_case,
    get_evaluate_policy_use_case,
    get_chat_with_ai_use_case,
)
from src.application.use_cases.execute_command import ExecuteCommandUseCase
from src.application.use_cases.evaluate_policy import EvaluatePolicyUseCase
from src.application.use_cases.chat_with_ai import ChatWithAIUseCase


@pytest.fixture
def client() -> TestClient:
    """Fixture providing a test client for the FastAPI app."""
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    """Verifies that /health returns HTTP 200 and expected health status payload."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "the-guardian-of-kali-backend"
    assert data["version"] == "0.1.0"


def test_di_check_endpoint_resolves_use_cases(client: TestClient) -> None:
    """Verifies that route handlers resolve all injected use cases via Depends()."""
    response = client.get("/api/di-check")
    assert response.status_code == 200
    data = response.json()
    assert data["execute_use_case"] == "ExecuteCommandUseCase"
    assert data["evaluate_use_case"] == "EvaluatePolicyUseCase"
    assert data["chat_use_case"] == "ChatWithAIUseCase"


def test_di_override_capabilities(client: TestClient) -> None:
    """Verifies that FastAPI dependency overrides function properly for testing."""
    class MockExecuteUseCase:
        pass

    app.dependency_overrides[get_execute_command_use_case] = lambda: MockExecuteUseCase()

    response = client.get("/api/di-check")
    assert response.status_code == 200
    data = response.json()
    assert data["execute_use_case"] == "MockExecuteUseCase"

    # Clean up override
    app.dependency_overrides.clear()


def test_cors_allowed_origin(client: TestClient) -> None:
    """Verifies that allowed Electron origins receive appropriate CORS headers."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_disallowed_origin(client: TestClient) -> None:
    """Verifies that unauthorized origins are rejected by CORS headers."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://malicious-site.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # When CORS rejects an origin, Access-Control-Allow-Origin header is omitted
    assert response.headers.get("access-control-allow-origin") is None
