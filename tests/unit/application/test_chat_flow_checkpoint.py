"""Comprehensive integration and unit tests for Day 30 - Checkpoint #6.

Covers:
1. AI proposes a reasonable command for a clear, targeted request.
2. AI does NOT invent an arbitrary command for a vague, conceptual request.
3. Rejecting an AI proposal does NOT execute it in the shell nor record it in session/SQLite history.
"""
from typing import Any, Dict, List, Optional
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.dependencies import (
    get_ai_gateway,
    get_session_repository,
    get_shell_executor,
    get_chat_with_ai_use_case,
    get_session_history_use_case,
    get_execute_command_use_case,
)
from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.entities.target import Target
from src.domain.value_objects.command_origin import CommandOrigin
from src.application.ports.ai_gateway import AIGateway
from src.application.ports.shell_executor import ShellExecutor
from src.application.dtos.responses import AIResponse, CommandResult
from src.application.use_cases.chat_with_ai import ChatWithAIUseCase
from src.application.use_cases.get_session_history import GetSessionHistoryUseCase
from src.application.use_cases.execute_command import ExecuteCommandUseCase
from src.adapters.storage.sqlite_session_repository import SQLiteSessionRepository


class FakeScenarioAIGateway(AIGateway):
    """Simulates realistic Claude responses for clear vs vague user inputs."""

    async def send_message(self, prompt: str, history: List[Dict[str, Any]]) -> AIResponse:
        prompt_lower = prompt.lower()

        # Scenario 1: Clear, scoped request
        if "scan" in prompt_lower and ("10.10.10.15" in prompt_lower or "ports" in prompt_lower):
            return AIResponse(
                content="I recommend performing a version detection scan against open web ports 80 and 443.",
                suggested_command="nmap -sV -p 80,443 10.10.10.15",
                metadata={"model": "claude-3-5-sonnet-20241022"},
            )

        # Scenario 2: Vague, conceptual or conversational request
        return AIResponse(
            content="Port scanning is the process of probing host ports to determine active services. SYN scanning sends SYN packets without completing the 3-way handshake.",
            suggested_command=None,
            metadata={"model": "claude-3-5-sonnet-20241022"},
        )


class TrackingShellExecutor(ShellExecutor):
    """Monitors any execution attempt to ensure rejected proposals never hit the shell."""

    def __init__(self) -> None:
        self.executed_commands: List[Command] = []

    async def execute(self, command: Command) -> CommandResult:
        self.executed_commands.append(command)
        return CommandResult(
            command_text=command.text,
            exit_code=0,
            stdout="Executed cleanly",
            stderr="",
            duration_ms=5.0,
        )


@pytest.fixture
def checkpoint_env(tmp_path):
    """Sets up a complete isolated environment with real SQLite and simulated AI gateway."""
    db_path = str(tmp_path / "checkpoint6.db")
    repo = SQLiteSessionRepository(db_path=db_path)
    gateway = FakeScenarioAIGateway()
    shell = TrackingShellExecutor()

    chat_uc = ChatWithAIUseCase(ai_gateway=gateway)
    history_uc = GetSessionHistoryUseCase(repository=repo)
    execute_uc = ExecuteCommandUseCase(executor=shell, repository=repo)

    app.dependency_overrides[get_ai_gateway] = lambda: gateway
    app.dependency_overrides[get_session_repository] = lambda: repo
    app.dependency_overrides[get_shell_executor] = lambda: shell
    app.dependency_overrides[get_chat_with_ai_use_case] = lambda: chat_uc
    app.dependency_overrides[get_session_history_use_case] = lambda: history_uc
    app.dependency_overrides[get_execute_command_use_case] = lambda: execute_uc

    with TestClient(app) as client:
        yield client, repo, shell

    app.dependency_overrides.clear()


def test_ai_proposes_reasonable_command_for_clear_request(checkpoint_env) -> None:
    """Requirement 1: AI proposes a reasonable command for a clear, actionable request.
    Verifies that the command is proposed as a suggestion and NOT executed automatically.
    """
    client, repo, shell = checkpoint_env

    payload = {
        "message": "Please scan open ports 80 and 443 on target 10.10.10.15",
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Must contain both guidance and proposed command
    assert "version detection scan" in data["response"]
    assert data["has_proposed_command"] is True
    assert data["proposed_command"] is not None
    assert data["proposed_command"]["text"] == "nmap -sV -p 80,443 10.10.10.15"
    assert data["proposed_command"]["origin"] == "AI"

    # INVARIANT: Must NOT have executed yet
    assert len(shell.executed_commands) == 0


def test_ai_does_not_invent_arbitrary_command_for_vague_request(checkpoint_env) -> None:
    """Requirement 2: AI does NOT invent an arbitrary command for a vague or conceptual request."""
    client, repo, shell = checkpoint_env

    payload = {
        "message": "Explain what SYN scanning does and why it is useful.",
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Must return conceptual explanation without any proposed command
    assert "Port scanning is the process" in data["response"]
    assert data["has_proposed_command"] is False
    assert data["proposed_command"] is None

    # INVARIANT: Shell remains untouched
    assert len(shell.executed_commands) == 0


def test_rejecting_proposal_does_not_execute_or_log_it(checkpoint_env) -> None:
    """Requirement 3: Rejecting a proposal does not execute or log it as executed.

    Simulates the operator receiving a proposal, choosing to reject it (NOT invoking POST /execute),
    and validates that neither the shell was executed nor the command was written to SQLite history.
    """
    client, repo, shell = checkpoint_env

    # 1. Operator requests suggestion
    chat_resp = client.post(
        "/chat",
        json={"message": "Please scan 10.10.10.15"},
    )
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    session_id = chat_data["session_id"]
    proposed_cmd = chat_data["proposed_command"]["text"]
    assert proposed_cmd == "nmap -sV -p 80,443 10.10.10.15"

    # 2. Operator reviews the proposed card and clicks 'Reject' (no /execute call is made)
    # The proposal is dismissed in the UI.

    # 3. Query the audit history in SQLite for this session
    history_resp = client.get(f"/history?session_id={session_id}")
    assert history_resp.status_code == 200
    history_data = history_resp.json()

    # CRITICAL CHECK: History MUST be empty, nothing was logged as executed
    assert history_data["count"] == 0
    assert len(history_data["commands"]) == 0

    # CRITICAL CHECK: The shell executor was NEVER touched
    assert len(shell.executed_commands) == 0


def test_explicit_approval_executes_and_logs_command(checkpoint_env) -> None:
    """Contrasting Verification: Verifies that ONLY upon explicit operator approval
    (clicking 'Execute' -> POST /execute), the command is sent to the shell and recorded in history.
    """
    client, repo, shell = checkpoint_env

    # 1. Operator chat
    chat_resp = client.post("/chat", json={"message": "Please scan 10.10.10.15"})
    chat_data = chat_resp.json()
    session_id = chat_data["session_id"]
    proposed = chat_data["proposed_command"]

    # 2. Operator clicks 'Execute' -> POST /execute with origin='AI'
    exec_payload = {
        "command": proposed["text"],
        "target": "10.10.10.15",
        "origin": "AI",
        "session_id": session_id,
    }
    exec_resp = client.post("/execute", json=exec_payload)
    assert exec_resp.status_code == 200

    # 3. Now and ONLY now has the shell executed the command
    assert len(shell.executed_commands) == 1
    assert shell.executed_commands[0].text == "nmap -sV -p 80,443 10.10.10.15"

    # 4. Now and ONLY now is it persisted in SQLite history
    hist_resp = client.get(f"/history?session_id={session_id}")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["count"] == 1
    assert hist_data["commands"][0]["text"] == "nmap -sV -p 80,443 10.10.10.15"
    assert hist_data["commands"][0]["origin"] == "AI"
