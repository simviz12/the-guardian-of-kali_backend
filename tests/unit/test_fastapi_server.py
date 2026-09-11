"""Unit and integration tests for FastAPI application server, CORS, DI, /execute, /history, and /chat."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
import anthropic
import httpx

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
from src.application.dtos.responses import CommandResult, ChatResult


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


def test_execute_endpoint_blocks_destructive_ai_command(client: TestClient) -> None:
    """Verifies POST /execute returns HTTP 403 when an AI command is blocked by policy gate."""
    payload = {
        "command": "rm -rf /",
        "origin": "AI",
    }
    response = client.post("/execute", json=payload)
    assert response.status_code == 403
    assert "Blocked by destructive blacklist rule" in response.json()["detail"]


def test_execute_endpoint_blocks_unauthorized_target(client: TestClient) -> None:
    """Verifies POST /execute strictly blocks out-of-scope targets when authorized_targets is passed."""
    payload = {
        "command": "ping -c 3 8.8.8.8",
        "target": "8.8.8.8",
        "origin": "AI",
        "authorized_targets": ["10.10.10.0/24"],
    }
    response = client.post("/execute", json=payload)
    assert response.status_code == 403
    assert "not within authorized session scope" in response.json()["detail"].lower()



def test_execute_endpoint_allows_destructive_manual_user_command_bypassing_ai_gate(client: TestClient) -> None:
    """Verifies that manual user commands bypass the AI policy gate (operator responsibility)."""
    class MockExecuteUseCase:
        async def run(self, command, session):
            return CommandResult(
                command_text=command.text,
                exit_code=0,
                stdout="manual command executed\n",
                stderr="",
                duration_ms=10.0,
            )

    app.dependency_overrides[get_execute_command_use_case] = lambda: MockExecuteUseCase()

    payload = {
        "command": "rm -rf /tmp/test",
        "origin": "MANUAL_USER",
    }
    response = client.post("/execute", json=payload)
    assert response.status_code == 200
    assert response.json()["stdout"] == "manual command executed\n"

    app.dependency_overrides.clear()


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


def test_chat_endpoint_plain_response(client: TestClient) -> None:
    """Verifies POST /chat returns conversational guidance without tool proposal."""
    class MockChatUseCase:
        async def run(self, message, session):
            return ChatResult(
                response_text="Nmap SYN scan is stealthier than TCP connect scan.",
                proposed_command=None,
            )

    app.dependency_overrides[get_chat_with_ai_use_case] = lambda: MockChatUseCase()

    payload = {"message": "Explain SYN scan"}
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Nmap SYN scan is stealthier than TCP connect scan."
    assert data["has_proposed_command"] is False
    assert data["proposed_command"] is None
    assert data["session_id"] is not None

    app.dependency_overrides.clear()


def test_chat_endpoint_with_proposed_command(client: TestClient) -> None:
    """Verifies POST /chat returns conversational advice AND structured proposed command."""
    proposed = Command(
        text="nmap -sS -p 80,443 10.10.10.20",
        origin=CommandOrigin.AI,
        target="10.10.10.20",
    )

    class MockChatUseCase:
        async def run(self, message, session):
            return ChatResult(
                response_text="Scanning web ports on 10.10.10.20",
                proposed_command=proposed,
            )

    app.dependency_overrides[get_chat_with_ai_use_case] = lambda: MockChatUseCase()

    payload = {"message": "Scan web ports on 10.10.10.20"}
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Scanning web ports on 10.10.10.20"
    assert data["has_proposed_command"] is True
    assert data["proposed_command"]["text"] == "nmap -sS -p 80,443 10.10.10.20"
    assert data["proposed_command"]["target"] == "10.10.10.20"
    assert data["proposed_command"]["origin"] == "AI"

    app.dependency_overrides.clear()


def test_chat_endpoint_rate_limit_handling(client: TestClient) -> None:
    """Verifies POST /chat translates RateLimitError into HTTP 429."""
    class MockFailingChatUseCase:
        async def run(self, message, session):
            mock_response = httpx.Response(status_code=429, request=httpx.Request("POST", "https://api.anthropic.com"))
            raise anthropic.RateLimitError(
                message="Rate limit exceeded",
                response=mock_response,
                body=None,
            )

    app.dependency_overrides[get_chat_with_ai_use_case] = lambda: MockFailingChatUseCase()

    response = client.post("/chat", json={"message": "Hello"})
    assert response.status_code == 429
    assert "rate limit exceeded" in response.json()["detail"].lower()

    app.dependency_overrides.clear()


def test_chat_endpoint_service_unavailable_handling(client: TestClient) -> None:
    """Verifies POST /chat translates APIConnectionError into HTTP 503."""
    class MockFailingChatUseCase:
        async def run(self, message, session):
            mock_request = httpx.Request("POST", "https://api.anthropic.com")
            raise anthropic.APIConnectionError(
                message="Connection refused",
                request=mock_request,
            )

    app.dependency_overrides[get_chat_with_ai_use_case] = lambda: MockFailingChatUseCase()

    response = client.post("/chat", json={"message": "Hello"})
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"].lower()

    app.dependency_overrides.clear()
