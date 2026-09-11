"""Full End-to-End (E2E) integration test suite for Day 41.

Simulates the complete system workflow:
1. Session Initialization (Session creation with authorized targets and operating mode).
2. AI Co-Pilot Conversation (POST /chat) yielding structured command proposals.
3. Central Policy Evaluation (Verification that commands pass policy gate: blacklist, target scope, risk classification).
4. Real Execution against WSL2 Kali Linux (as ia-user) using harmless system diagnostics.
5. Persistent Audit & History Verification in SQLite.
"""
import shutil
import sqlite3
from typing import Any, Dict, List
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.dependencies import (
    get_shell_executor,
    get_session_repository,
    get_ai_gateway,
    get_execute_command_use_case,
    get_evaluate_policy_use_case,
    get_chat_with_ai_use_case,
    get_session_history_use_case,
)
from src.adapters.terminal.wsl_shell_executor import WSLShellExecutor
from src.adapters.storage.sqlite_session_repository import SQLiteSessionRepository
from src.application.ports.ai_gateway import AIGateway
from src.application.dtos.responses import AIResponse
from src.application.use_cases.execute_command import ExecuteCommandUseCase
from src.application.use_cases.evaluate_policy import EvaluatePolicyUseCase
from src.application.use_cases.chat_with_ai import ChatWithAIUseCase
from src.application.use_cases.get_session_history import GetSessionHistoryUseCase
from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.entities.target import Target
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.exceptions import CommandBlockedException


class FakeClaudeAIGateway(AIGateway):
    """Simulates deterministic Claude co-pilot responses for testing the end-to-end pipeline."""

    async def send_message(self, prompt: str, history: List[Dict[str, Any]]) -> AIResponse:
        prompt_lower = prompt.lower()

        # Scenario 1: Harmless recon / inspection request against authorized localhost
        if "uname" in prompt_lower or "kernel" in prompt_lower or "system" in prompt_lower:
            return AIResponse(
                content="I recommend inspecting the active Linux kernel version on the target machine.",
                suggested_command="uname -s",
                metadata={"model": "claude-3-5-sonnet-20241022"},
            )

        # Scenario 2: Echo test command for WSL validation
        if "echo" in prompt_lower or "identity" in prompt_lower:
            return AIResponse(
                content="Let's verify execution identity inside the Kali Linux environment.",
                suggested_command="echo 'GUARDIAN_E2E_CONFIRMED'",
                metadata={"model": "claude-3-5-sonnet-20241022"},
            )

        # Scenario 3: Malicious / destructive injection attempt
        if "delete" in prompt_lower or "wipe" in prompt_lower or "destroy" in prompt_lower:
            return AIResponse(
                content="Here is a destructive command to purge system directories.",
                suggested_command="rm -rf /",
                metadata={"model": "claude-3-5-sonnet-20241022"},
            )

        # Default fallback
        return AIResponse(
            content="I am ready to assist with your ethical hacking workflow.",
            suggested_command=None,
            metadata={"model": "claude-3-5-sonnet-20241022"},
        )


@pytest.fixture
def e2e_system(tmp_path):
    """Provisions a full end-to-end environment wired to an isolated SQLite file
    and a real WSLShellExecutor executing against Kali Linux WSL2.
    """
    db_file = str(tmp_path / "e2e_guardian_test.db")
    real_repo = SQLiteSessionRepository(db_path=db_file)
    real_wsl_shell = WSLShellExecutor(distro="kali-linux", user="ia-user", timeout_seconds=15.0)
    fake_ai = FakeClaudeAIGateway()
    policy_uc = EvaluatePolicyUseCase()

    execute_uc = ExecuteCommandUseCase(
        executor=real_wsl_shell,
        repository=real_repo,
        policy_evaluator=policy_uc,
    )
    chat_uc = ChatWithAIUseCase(ai_gateway=fake_ai)
    history_uc = GetSessionHistoryUseCase(repository=real_repo)

    app.dependency_overrides[get_session_repository] = lambda: real_repo
    app.dependency_overrides[get_shell_executor] = lambda: real_wsl_shell
    app.dependency_overrides[get_ai_gateway] = lambda: fake_ai
    app.dependency_overrides[get_evaluate_policy_use_case] = lambda: policy_uc
    app.dependency_overrides[get_execute_command_use_case] = lambda: execute_uc
    app.dependency_overrides[get_chat_with_ai_use_case] = lambda: chat_uc
    app.dependency_overrides[get_session_history_use_case] = lambda: history_uc

    with TestClient(app) as client:
        yield client, real_repo, db_file

    app.dependency_overrides.clear()


@pytest.mark.skipif(
    shutil.which("wsl.exe") is None,
    reason="WSL2 (wsl.exe) is required for real end-to-end Kali Linux execution tests.",
)
def test_full_e2e_flow_session_chat_policy_real_wsl_and_sqlite(e2e_system) -> None:
    """End-to-End Integration Scenario 1:
    Full happy path:
    1. Create a session with authorized targets (127.0.0.1, 10.10.10.15).
    2. Operator sends message to POST /chat asking for system identification.
    3. AI proposes harmless command 'uname -s'.
    4. Operator reviews and executes the proposed command (POST /execute with origin='AI').
    5. Command passes through EvaluatePolicyUseCase without violations.
    6. Command executes REAL in Kali Linux WSL2 as restricted 'ia-user'.
    7. Exit code is 0, stdout contains 'Linux'.
    8. Command is persisted in SQLite with all audit metadata.
    9. GET /history confirms record retrieval.
    """
    client, repo, db_file = e2e_system
    session_uuid = uuid4()

    # 1. Initialize session in database with authorized targets
    session = Session(
        user="carlos",
        id=session_uuid,
        authorized_targets=[
            Target(value="127.0.0.1", description="Localhost Diagnostics"),
            Target(value="10.10.10.15", description="HTB Lab Target"),
        ],
    )
    # Save initial session
    import asyncio
    asyncio.run(repo.save(session))

    # 2. Operator sends message to AI co-pilot
    chat_payload = {
        "message": "What is the system kernel on the local machine?",
        "session_id": str(session_uuid),
    }
    chat_resp = client.post("/chat", json=chat_payload)
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()

    assert chat_data["has_proposed_command"] is True
    assert chat_data["proposed_command"] is not None
    proposed_cmd = chat_data["proposed_command"]["text"]
    assert proposed_cmd == "uname -s"
    assert chat_data["session_id"] == str(session_uuid)

    # 3. Operator approves the command: POST /execute with origin='AI'
    exec_payload = {
        "command": proposed_cmd,
        "target": "127.0.0.1",
        "origin": "AI",
        "session_id": str(session_uuid),
    }
    exec_resp = client.post("/execute", json=exec_payload)
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()

    # 4. Verify real execution in Kali Linux WSL2
    assert exec_data["command"] == "uname -s"
    assert exec_data["exit_code"] == 0
    assert "Linux" in exec_data["stdout"].strip()
    assert exec_data["stderr"] == ""
    assert exec_data["duration_ms"] > 0
    assert exec_data["session_id"] == str(session_uuid)

    # 5. Verify persistence via GET /history endpoint
    hist_resp = client.get(f"/history?session_id={session_uuid}")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()

    assert hist_data["count"] == 1
    recorded_item = hist_data["commands"][0]
    assert recorded_item["text"] == "uname -s"
    assert recorded_item["origin"] == "AI"
    assert recorded_item["target"] == "127.0.0.1"
    assert recorded_item["risk_level"] == "LOW"

    # 6. Low-level direct SQLite database file inspection
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT session_id, text, origin, target, risk_level FROM commands WHERE session_id = ?", (str(session_uuid),))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == str(session_uuid)
    assert row[1] == "uname -s"
    assert row[2] == "AI"
    assert row[3] == "127.0.0.1"
    assert row[4] == "LOW"


@pytest.mark.skipif(
    shutil.which("wsl.exe") is None,
    reason="WSL2 (wsl.exe) is required for real end-to-end Kali Linux execution tests.",
)
def test_full_e2e_flow_real_wsl_echo_command_identity(e2e_system) -> None:
    """End-to-End Integration Scenario 2:
    Verifies that real commands executed via /execute run strictly under ia-user in Kali Linux.
    """
    client, repo, db_file = e2e_system
    session_uuid = uuid4()

    exec_payload = {
        "command": "whoami",
        "target": "127.0.0.1",
        "origin": "AI",
        "session_id": str(session_uuid),
    }
    exec_resp = client.post("/execute", json=exec_payload)
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()

    # Must execute as ia-user in Kali Linux
    assert exec_data["exit_code"] == 0
    assert exec_data["stdout"].strip() == "ia-user"

    # History audit verification
    hist_resp = client.get(f"/history?session_id={session_uuid}")
    assert hist_resp.status_code == 200
    assert hist_resp.json()["count"] == 1
    assert hist_resp.json()["commands"][0]["text"] == "whoami"


def test_full_e2e_flow_destructive_command_blocked_before_wsl(e2e_system) -> None:
    """End-to-End Integration Scenario 3:
    Security Guardrail:
    1. Operator asks for destructive action.
    2. AI proposes 'rm -rf /'.
    3. Even if execution is requested with origin='AI', the policy engine MUST
       intercept and raise HTTP 403 Forbidden, NEVER executing on WSL2.
    """
    client, repo, db_file = e2e_system
    session_uuid = uuid4()

    chat_resp = client.post("/chat", json={"message": "Wipe and delete the disk", "session_id": str(session_uuid)})
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert chat_data["proposed_command"]["text"] == "rm -rf /"

    # Attempt to execute destructive proposal
    exec_payload = {
        "command": "rm -rf /",
        "target": "127.0.0.1",
        "origin": "AI",
        "session_id": str(session_uuid),
    }
    exec_resp = client.post("/execute", json=exec_payload)

    # Must be rejected by the policy gatekeeper with 403 Forbidden
    assert exec_resp.status_code == 403
    assert "blocked" in exec_resp.json()["detail"].lower()

    # Ensure nothing was recorded in commands history as executed
    hist_resp = client.get(f"/history?session_id={session_uuid}")
    assert hist_resp.status_code == 200
    assert hist_resp.json()["count"] == 0


def test_full_e2e_flow_unauthorized_target_blocked_before_wsl(e2e_system) -> None:
    """End-to-End Integration Scenario 4:
    Zero-Trust Boundary:
    Attempting to execute an AI command targeting an unauthorized host must be blocked
    by the policy engine and never touch the shell executor.
    """
    client, repo, db_file = e2e_system
    session_uuid = uuid4()

    # Session only authorized for 10.10.10.15
    session = Session(
        user="carlos",
        id=session_uuid,
        authorized_targets=[Target(value="10.10.10.15", description="Only this target")],
    )
    import asyncio
    asyncio.run(repo.save(session))

    real_wsl_shell = WSLShellExecutor(distro="kali-linux", user="ia-user", timeout_seconds=15.0)
    policy_uc = EvaluatePolicyUseCase()
    execute_uc = ExecuteCommandUseCase(
        executor=real_wsl_shell,
        repository=repo,
        policy_evaluator=policy_uc,
    )

    # Command directed to unauthorized public IP
    unauthorized_cmd = Command(
        text="ping -c 1 8.8.8.8",
        target="8.8.8.8",
        origin=CommandOrigin.AI,
    )

    with pytest.raises(CommandBlockedException) as exc_info:
        asyncio.run(execute_uc.run(command=unauthorized_cmd, session=session))

    # Inviolable guarantee: reason explicitly mentions unauthorized scope
    assert "not authorized" in str(exc_info.value).lower() or "not within authorized" in str(exc_info.value).lower()


@pytest.mark.skipif(
    shutil.which("wsl.exe") is None,
    reason="WSL2 (wsl.exe) is required for real end-to-end Kali Linux execution tests.",
)
def test_full_e2e_flow_manual_user_command_bypasses_filter_and_executes_in_wsl(e2e_system) -> None:
    """End-to-End Integration Scenario 5:
    Commands with origin='MANUAL_USER' represent the human operator's direct intent,
    bypassing the AI policy gate while still executing and being recorded in SQLite.
    """
    client, repo, db_file = e2e_system
    session_uuid = uuid4()

    manual_payload = {
        "command": "echo 'MANUAL_OPERATOR_TEST'",
        "target": None,
        "origin": "MANUAL_USER",
        "session_id": str(session_uuid),
    }
    exec_resp = client.post("/execute", json=manual_payload)
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()

    assert exec_data["exit_code"] == 0
    assert "MANUAL_OPERATOR_TEST" in exec_data["stdout"]

    # History audit verification
    hist_resp = client.get(f"/history?session_id={session_uuid}")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["count"] == 1
    assert hist_data["commands"][0]["origin"] == "MANUAL_USER"
    assert hist_data["commands"][0]["text"] == "echo 'MANUAL_OPERATOR_TEST'"
