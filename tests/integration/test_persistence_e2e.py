"""End-to-end integration test verifying command execution, SQLite persistence, and history retrieval."""
import os
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.dependencies import (
    get_shell_executor,
    get_session_repository,
    get_execute_command_use_case,
    get_session_history_use_case,
)
from src.adapters.storage.sqlite_session_repository import SQLiteSessionRepository
from src.application.ports.shell_executor import ShellExecutor
from src.application.dtos.responses import CommandResult
from src.application.use_cases.execute_command import ExecuteCommandUseCase
from src.application.use_cases.get_session_history import GetSessionHistoryUseCase
from src.domain.entities.command import Command
from src.domain.value_objects.risk_level import RiskLevel


class MockShellExecutor(ShellExecutor):
    """Predictable shell executor simulating terminal output without external system dependencies."""

    async def execute(self, command: Command) -> CommandResult:
        if "fail" in command.text:
            return CommandResult(
                command_text=command.text,
                exit_code=1,
                stdout="",
                stderr="Command execution failed",
                duration_ms=10.0,
            )
        return CommandResult(
            command_text=command.text,
            exit_code=0,
            stdout=f"Simulated output for: {command.text}\n",
            stderr="",
            duration_ms=25.5,
        )


@pytest.fixture
def persistence_client(tmp_path):
    """Provides a TestClient connected to a real SQLite file repository with a deterministic ShellExecutor."""
    db_path = str(tmp_path / "e2e_persistence.db")
    real_repo = SQLiteSessionRepository(db_path=db_path)
    mock_shell = MockShellExecutor()

    # Build real use cases wired to this isolated SQLite DB
    execute_uc = ExecuteCommandUseCase(executor=mock_shell, repository=real_repo)
    history_uc = GetSessionHistoryUseCase(repository=real_repo)

    app.dependency_overrides[get_session_repository] = lambda: real_repo
    app.dependency_overrides[get_shell_executor] = lambda: mock_shell
    app.dependency_overrides[get_execute_command_use_case] = lambda: execute_uc
    app.dependency_overrides[get_session_history_use_case] = lambda: history_uc

    with TestClient(app) as client:
        yield client, db_path

    app.dependency_overrides.clear()


def test_full_stack_command_execution_and_sqlite_persistence(persistence_client) -> None:
    """E2E Test:
    1. POST /execute with a command
    2. Verify HTTP response
    3. Query GET /history with filters
    4. Re-instantiate a fresh SQLiteSessionRepository from the same file (simulating app restart)
    5. Verify data persisted on disk across restarts
    """
    client, db_path = persistence_client

    # 1. Execute initial command
    exec_payload = {
        "command": "nmap -sV 10.10.10.5",
        "target": "10.10.10.5",
        "origin": "AI",
    }
    exec_resp = client.post("/execute", json=exec_payload)
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()

    assert exec_data["command"] == "nmap -sV 10.10.10.5"
    assert exec_data["exit_code"] == 0
    assert "Simulated output for: nmap -sV 10.10.10.5" in exec_data["stdout"]
    session_id = exec_data["session_id"]
    assert session_id is not None

    # 2. Execute second command under the same session
    exec_payload_2 = {
        "command": "ping -c 3 10.10.10.5",
        "target": "10.10.10.5",
        "origin": "AI",
        "session_id": session_id,
    }
    exec_resp_2 = client.post("/execute", json=exec_payload_2)
    assert exec_resp_2.status_code == 200
    assert exec_resp_2.json()["session_id"] == session_id

    # 3. Query GET /history filtered by session_id
    hist_resp = client.get(f"/history?session_id={session_id}")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["count"] == 2
    assert hist_data["commands"][0]["text"] == "nmap -sV 10.10.10.5"
    assert hist_data["commands"][1]["text"] == "ping -c 3 10.10.10.5"

    # 4. Simulate App Restart: create a fresh repository instance pointing to the same disk file
    restarted_repo = SQLiteSessionRepository(db_path=db_path)
    restarted_history_uc = GetSessionHistoryUseCase(repository=restarted_repo)

    app.dependency_overrides[get_session_history_use_case] = lambda: restarted_history_uc

    # 5. Query GET /history after restart
    restarted_resp = client.get(f"/history?session_id={session_id}")
    assert restarted_resp.status_code == 200
    restarted_data = restarted_resp.json()
    assert restarted_data["count"] == 2
    assert restarted_data["commands"][0]["text"] == "nmap -sV 10.10.10.5"
    assert restarted_data["commands"][1]["text"] == "ping -c 3 10.10.10.5"
