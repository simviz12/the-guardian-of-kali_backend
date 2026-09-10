"""Comprehensive Checkpoint #3 unit tests for all application layer use cases.

Uses pure in-memory Fake/Mock implementations for AIGateway, ShellExecutor,
and SessionRepository. Tests all standard execution paths, error handling,
exception fallbacks, and security gates with zero external dependencies
(no WSL, no network, no database).
"""
import pytest
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.entities.target import Target
from src.domain.entities.policy_rule import PolicyRule
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.risk_level import RiskLevel
from src.domain.value_objects.policy_action import PolicyAction
from src.domain.exceptions import CommandBlockedException

from src.application.ports.ai_gateway import AIGateway
from src.application.ports.shell_executor import ShellExecutor
from src.application.ports.session_repository import SessionRepository
from src.application.dtos.responses import AIResponse, CommandResult, ChatResult
from src.application.use_cases.execute_command import ExecuteCommandUseCase
from src.application.use_cases.evaluate_policy import EvaluatePolicyUseCase
from src.application.use_cases.chat_with_ai import ChatWithAIUseCase


# ============================================================================
# Pure In-Memory Fakes (Zero Dependencies)
# ============================================================================

class FakeAIGateway(AIGateway):
    """In-memory fake AI gateway for simulating LLM interaction and errors."""

    def __init__(
        self,
        canned_response: str = "Assistant response",
        suggested_command: Optional[str] = None,
        should_fail: bool = False,
    ) -> None:
        self.canned_response = canned_response
        self.suggested_command = suggested_command
        self.should_fail = should_fail
        self.recorded_calls: List[Dict[str, Any]] = []

    async def send_message(self, prompt: str, history: List[Dict[str, Any]]) -> AIResponse:
        if self.should_fail:
            raise ConnectionError("AI Provider API unreachable")
        self.recorded_calls.append({"prompt": prompt, "history": history})
        return AIResponse(
            content=self.canned_response,
            suggested_command=self.suggested_command,
        )


class FakeShellExecutor(ShellExecutor):
    """In-memory fake shell executor simulating command run, output, and failures."""

    def __init__(self, exit_code: int = 0, stdout: str = "", stderr: str = "", should_raise: bool = False) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.should_raise = should_raise
        self.executed_commands: List[Command] = []

    async def execute(self, command: Command) -> CommandResult:
        if self.should_raise:
            raise BrokenPipeError("WSL2 bridge channel abruptly closed")
        self.executed_commands.append(command)
        return CommandResult(
            command_text=command.text,
            exit_code=self.exit_code,
            stdout=self.stdout,
            stderr=self.stderr,
            duration_ms=12.5,
        )


class FakeSessionRepository(SessionRepository):
    """In-memory dictionary-backed fake session repository."""

    def __init__(self) -> None:
        self.sessions: Dict[UUID, Session] = {}

    async def save(self, session: Session) -> None:
        self.sessions[session.id] = session

    async def get_history(self, filters: Dict[str, Any]) -> List[Command]:
        user_filter = filters.get("user")
        results: List[Command] = []
        for session in self.sessions.values():
            if user_filter is None or session.user == user_filter:
                results.extend(session.commands)
        return results


# ============================================================================
# ExecuteCommandUseCase Tests
# ============================================================================

@pytest.mark.asyncio
async def test_execute_command_success_normal_flow() -> None:
    """Verifies standard command execution, history recording, and persistence."""
    executor = FakeShellExecutor(exit_code=0, stdout="nmap output", stderr="")
    repo = FakeSessionRepository()
    use_case = ExecuteCommandUseCase(executor=executor, repository=repo)

    session = Session(user="carlos")
    cmd = Command(text="nmap -sV 10.10.10.5", origin=CommandOrigin.AI)

    result = await use_case.run(command=cmd, session=session)

    assert result.exit_code == 0
    assert result.stdout == "nmap output"
    assert len(executor.executed_commands) == 1
    assert session.id in repo.sessions
    assert len(session.commands) == 1


@pytest.mark.asyncio
async def test_execute_command_executor_crash_resilience() -> None:
    """Verifies that an unexpected executor crash is caught gracefully without terminating the application."""
    executor = FakeShellExecutor(should_raise=True)
    repo = FakeSessionRepository()
    use_case = ExecuteCommandUseCase(executor=executor, repository=repo)

    session = Session(user="carlos")
    cmd = Command(text="ping -c 4 10.10.10.1", origin=CommandOrigin.MANUAL_USER)

    result = await use_case.run(command=cmd, session=session)

    assert result.exit_code == 1
    assert "WSL2 bridge channel abruptly closed" in result.stderr
    assert len(session.commands) == 1
    assert session.id in repo.sessions


# ============================================================================
# EvaluatePolicyUseCase Tests
# ============================================================================

def test_evaluate_policy_blocks_critical_commands_in_autonomous_mode() -> None:
    """Verifies that a dangerous command raises CommandBlockedException in autonomous mode."""
    rules = [
        PolicyRule(
            id="rule-block-rm-rf",
            pattern=r"\brm\s+-[rR]*[fF]\b",
            risk_level=RiskLevel.BLOCKED,
            action=PolicyAction.BLOCK,
        ),
    ]
    use_case = EvaluatePolicyUseCase(rules=rules)
    session = Session(user="carlos", is_autonomous=True)
    cmd = Command(text="rm -rf /var/log", origin=CommandOrigin.AI)

    with pytest.raises(CommandBlockedException) as exc_info:
        use_case.evaluate(command=cmd, session=session)

    assert "rm -rf /var/log" in str(exc_info.value)
    assert cmd.risk_level == RiskLevel.BLOCKED


def test_evaluate_policy_manual_mode_returns_block_action() -> None:
    """Verifies that manual operator commands matching block rules return BLOCK action rather than raising."""
    rules = [
        PolicyRule(
            id="rule-block-dd",
            pattern=r"\bdd\s+if=",
            risk_level=RiskLevel.BLOCKED,
            action=PolicyAction.BLOCK,
        ),
    ]
    use_case = EvaluatePolicyUseCase(rules=rules)
    session = Session(user="carlos", is_autonomous=False)
    cmd = Command(text="dd if=/dev/zero of=/dev/sda", origin=CommandOrigin.MANUAL_USER)

    action = use_case.evaluate(command=cmd, session=session)

    assert action == PolicyAction.BLOCK
    assert cmd.risk_level == RiskLevel.BLOCKED


def test_evaluate_policy_requires_confirmation_on_medium_risk() -> None:
    """Verifies that high-impact scan commands return REQUIRE_CONFIRMATION."""
    rules = [
        PolicyRule(
            id="rule-aggressive-scan",
            pattern=r"nmap\s+.*-A",
            risk_level=RiskLevel.MEDIUM,
            action=PolicyAction.REQUIRE_CONFIRMATION,
        ),
    ]
    use_case = EvaluatePolicyUseCase(rules=rules)
    session = Session(user="carlos", is_autonomous=True)
    cmd = Command(text="nmap -A -T4 10.10.10.10", origin=CommandOrigin.AI)

    action = use_case.evaluate(command=cmd, session=session)

    assert action == PolicyAction.REQUIRE_CONFIRMATION
    assert cmd.risk_level == RiskLevel.MEDIUM


# ============================================================================
# ChatWithAIUseCase Tests
# ============================================================================

@pytest.mark.asyncio
async def test_chat_with_ai_tool_use_command_proposal() -> None:
    """Verifies conversational advice and command proposal via tool use without execution."""
    gateway = FakeAIGateway(
        canned_response="Let us enumerate SMB shares on the target.",
        suggested_command="smbclient -L //10.10.10.20",
    )
    use_case = ChatWithAIUseCase(ai_gateway=gateway)

    target = Target(value="10.10.10.20")
    session = Session(user="carlos", authorized_targets=[target])

    result = await use_case.run(message="How should I enumerate SMB?", session=session)

    assert isinstance(result, ChatResult)
    assert result.response_text == "Let us enumerate SMB shares on the target."
    assert result.has_proposed_command is True
    assert result.proposed_command is not None
    assert result.proposed_command.text == "smbclient -L //10.10.10.20"
    assert result.proposed_command.origin == CommandOrigin.AI
    assert result.proposed_command.target == "10.10.10.20"

    # Strict check: Session history must NOT have this command until explicit execution
    assert len(session.commands) == 0


@pytest.mark.asyncio
async def test_chat_with_ai_passes_command_history() -> None:
    """Verifies that previous commands in the session are passed into the context history."""
    gateway = FakeAIGateway(canned_response="Continuing analysis...")
    use_case = ChatWithAIUseCase(ai_gateway=gateway)

    session = Session(user="carlos")
    session.add_command(Command(text="nmap 10.10.10.5", origin=CommandOrigin.MANUAL_USER))

    await use_case.run(message="Analyze these results", session=session)

    assert len(gateway.recorded_calls) == 1
    history = gateway.recorded_calls[0]["history"]
    assert len(history) == 1
    assert "nmap 10.10.10.5" in history[0]["content"]
