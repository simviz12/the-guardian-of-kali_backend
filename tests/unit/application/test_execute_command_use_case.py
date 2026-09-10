"""Unit tests verifying ExecuteCommandUseCase execution flow and error handling."""
import pytest
from typing import Any, Dict, List

from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.value_objects.command_origin import CommandOrigin
from src.application.ports.shell_executor import ShellExecutor
from src.application.ports.session_repository import SessionRepository
from src.application.dtos.responses import CommandResult
from src.application.use_cases.execute_command import ExecuteCommandUseCase


class MockShellExecutor(ShellExecutor):
    """Mock implementation of ShellExecutor for unit testing."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.executed_commands: List[Command] = []

    async def execute(self, command: Command) -> CommandResult:
        if self.should_fail:
            raise RuntimeError("Underlying WSL process failed unexpectedly")
        self.executed_commands.append(command)
        return CommandResult(
            command_text=command.text,
            exit_code=0,
            stdout="sample output\n",
            stderr="",
            duration_ms=15.0,
        )


class MockSessionRepository(SessionRepository):
    """Mock implementation of SessionRepository for unit testing."""

    def __init__(self) -> None:
        self.saved_sessions: List[Session] = []

    async def save(self, session: Session) -> None:
        self.saved_sessions.append(session)

    async def get_history(self, filters: Dict[str, Any]) -> List[Command]:
        return []


@pytest.mark.asyncio
async def test_execute_command_success() -> None:
    """Verifies standard execution path: command executes, appends to session, and saves."""
    executor = MockShellExecutor()
    repo = MockSessionRepository()
    use_case = ExecuteCommandUseCase(executor=executor, repository=repo)

    session = Session(user="carlos")
    cmd = Command(text="ping -c 1 127.0.0.1", origin=CommandOrigin.MANUAL_USER)

    result = await use_case.run(command=cmd, session=session)

    assert result.exit_code == 0
    assert result.stdout == "sample output\n"
    assert len(session.commands) == 1
    assert session.commands[0].text == "ping -c 1 127.0.0.1"
    assert len(repo.saved_sessions) == 1


@pytest.mark.asyncio
async def test_execute_command_resilience_to_executor_exceptions() -> None:
    """Verifies that executor errors do not crash the app and produce error result."""
    executor = MockShellExecutor(should_fail=True)
    repo = MockSessionRepository()
    use_case = ExecuteCommandUseCase(executor=executor, repository=repo)

    session = Session(user="carlos")
    cmd = Command(text="nmap 10.10.10.1", origin=CommandOrigin.AI)

    result = await use_case.run(command=cmd, session=session)

    assert result.exit_code == 1
    assert "Underlying WSL process failed unexpectedly" in result.stderr
    assert len(session.commands) == 1
    assert len(repo.saved_sessions) == 1
