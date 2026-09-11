"""High-speed Smoke Test suite for Day 44 Release Readiness.

Quickly verifies:
1. Application factory boots cleanly.
2. /health endpoint reports healthy status and correct service metadata.
3. Dependency injection graph wires all ports and use cases.
4. CORS middleware configuration accepts allowed Electron origins.
5. Inviolable policy guardrail blocks destructive payload immediately.
6. Target scope enforcement blocks out-of-scope executions.
"""
from fastapi.testclient import TestClient
import pytest

from src.main import create_app
from src.application.dtos.responses import CommandResult
from src.domain.value_objects.risk_level import RiskLevel
from src.dependencies import (
    get_execute_command_use_case,
    get_evaluate_policy_use_case,
    get_chat_with_ai_use_case,
    get_session_history_use_case,
    get_shell_executor,
    get_session_repository,
    get_ai_gateway,
)


@pytest.fixture(scope="module")
def smoke_client():
    """Module-scoped TestClient to ensure fast execution without re-initializing app."""
    app = create_app()
    with TestClient(app) as client:
        yield client


def test_smoke_health_check(smoke_client: TestClient) -> None:
    """Smoke: Verifies the backend service boots and /health responds with 200 OK."""
    response = smoke_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "the-guardian-of-kali-backend"
    assert data["version"] == "0.1.0"


def test_smoke_di_providers_wire_correctly() -> None:
    """Smoke: Ensures all dependency injection singletons and providers resolve cleanly."""
    shell = get_shell_executor()
    repo = get_session_repository()
    ai = get_ai_gateway()
    evaluate_uc = get_evaluate_policy_use_case()
    execute_uc = get_execute_command_use_case()
    chat_uc = get_chat_with_ai_use_case()
    history_uc = get_session_history_use_case()

    assert shell is not None
    assert repo is not None
    assert ai is not None
    assert evaluate_uc is not None
    assert execute_uc is not None
    assert chat_uc is not None
    assert history_uc is not None


def test_smoke_cors_configuration(smoke_client: TestClient) -> None:
    """Smoke: Verifies preflight CORS requests for Electron local origins are accepted."""
    response = smoke_client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_smoke_policy_gate_blocks_destructive_command(smoke_client: TestClient) -> None:
    """Smoke: Confirms that dangerous commands are stopped at the API gatekeeper."""
    response = smoke_client.post(
        "/execute",
        json={
            "command": "rm -rf /",
            "origin": "AI",
        },
    )
    assert response.status_code == 403
    assert "destructive blacklist rule" in response.json()["detail"].lower()


def test_smoke_policy_gate_blocks_out_of_scope_target(smoke_client: TestClient) -> None:
    """Smoke: Confirms that out-of-scope targets are strictly rejected."""
    response = smoke_client.post(
        "/execute",
        json={
            "command": "ping -c 1 8.8.8.8",
            "target": "8.8.8.8",
            "origin": "AI",
            "authorized_targets": ["10.10.10.0/24"],
        },
    )
    assert response.status_code == 403
    assert "not within authorized session scope" in response.json()["detail"].lower()
