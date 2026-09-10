"""Unit and integration tests for FastAPI application server, CORS, DI, /execute, and /history."""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from src.main import app, create_app
from src.dependencies import (
    get_execute_command_use_case,
    get_evaluate_policy_use_case,
    get_chat_with_ai_use_case,
    get_session_history_use_case,
)
from src.domain.entities.command import Command
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.risk_level import RiskLevel
from src.application.dtos.responses import CommandResult


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
    assert data["history_use_case"] == "GetSessionHistoryUseCase"


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
    assert response.headers.get("access-control-allow-origin") is None


def test_execute_endpoint_success(client: TestClient) -> None:
    """Verifies POST /execute processes payload and returns structured response."""
    class MockExecuteUseCase:
        async def run(self, command, session):
            return CommandResult(
                command_text=command.text,
                exit_code=0,
                stdout="mocked terminal output\n",
                stderr="",
                duration_ms=15.0,
            )

    app.dependency_overrides[get_execute_command_use_case] = lambda: MockExecuteUseCase()

    payload = {
        "command": "whoami",
        "target": "10.10.10.1",
        "origin": "AI",
    }
    response = client.post("/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["command"] == "whoami"
    assert data["exit_code"] == 0
    assert data["stdout"] == "mocked terminal output\n"
    assert data["session_id"] is not None

    app.dependency_overrides.clear()


def test_execute_endpoint_validation_error(client: TestClient) -> None:
    """Verifies POST /execute rejects empty command text or invalid origin."""
    # Empty command
    response = client.post("/execute", json={"command": "", "origin": "AI"})
    assert response.status_code == 422

    # Invalid origin
    response = client.post("/execute", json={"command": "whoami", "origin": "INVALID"})
    assert response.status_code == 422


def test_history_endpoint_success(client: TestClient) -> None:
    """Verifies GET /history returns list of commands with count."""
    sample_time = datetime.now(timezone.utc)
    mock_cmd = Command(
        text="nmap -sV 10.10.10.1",
        origin=CommandOrigin.AI,
        target="10.10.10.1",
        timestamp=sample_time,
        risk_level=RiskLevel.LOW,
    )

    class MockHistoryUseCase:
        async def run(self, session_id=None, user=None, start_date=None, end_date=None, risk_level=None):
            return [mock_cmd]

    app.dependency_overrides[get_session_history_use_case] = lambda: MockHistoryUseCase()

    response = client.get("/history?risk_level=LOW")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["commands"][0]["text"] == "nmap -sV 10.10.10.1"
    assert data["commands"][0]["origin"] == "AI"
    assert data["commands"][0]["risk_level"] == "LOW"

    app.dependency_overrides.clear()
