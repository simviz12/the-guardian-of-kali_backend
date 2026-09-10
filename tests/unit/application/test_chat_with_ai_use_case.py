"""Unit tests verifying ChatWithAIUseCase conversation handling and command proposals."""
import pytest
from typing import Any, Dict, List, Optional

from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.entities.target import Target
from src.domain.value_objects.command_origin import CommandOrigin
from src.application.ports.ai_gateway import AIGateway
from src.application.dtos.responses import AIResponse, ChatResult
from src.application.use_cases.chat_with_ai import ChatWithAIUseCase


class MockAIGateway(AIGateway):
    """Mock implementation of AIGateway for testing."""

    def __init__(self, response_text: str, suggested_command: Optional[str] = None) -> None:
        self.response_text = response_text
        self.suggested_command = suggested_command
        self.last_prompt: Optional[str] = None
        self.last_history: Optional[List[Dict[str, Any]]] = None

    async def send_message(self, prompt: str, history: List[Dict[str, Any]]) -> AIResponse:
        self.last_prompt = prompt
        self.last_history = history
        return AIResponse(
            content=self.response_text,
            suggested_command=self.suggested_command,
        )


@pytest.mark.asyncio
async def test_chat_without_proposed_command() -> None:
    """Verifies that advisory queries return conversational text with no proposed command."""
    gateway = MockAIGateway(response_text="To scan open ports, you can use nmap or masscan.")
    use_case = ChatWithAIUseCase(ai_gateway=gateway)

    session = Session(user="carlos")
    result = await use_case.run(message="How do I find open ports?", session=session)

    assert isinstance(result, ChatResult)
    assert result.response_text == "To scan open ports, you can use nmap or masscan."
    assert result.has_proposed_command is False
    assert result.proposed_command is None
    assert gateway.last_prompt == "How do I find open ports?"


@pytest.mark.asyncio
async def test_chat_with_proposed_command_via_tool_use() -> None:
    """Verifies that tool use suggestions construct a Command entity without executing it."""
    gateway = MockAIGateway(
        response_text="Here is a fast SYN scan against your target.",
        suggested_command="nmap -sS -p- 10.10.10.100",
    )
    use_case = ChatWithAIUseCase(ai_gateway=gateway)

    target = Target(value="10.10.10.0/24")
    session = Session(user="carlos", authorized_targets=[target])

    result = await use_case.run(message="Scan all ports on the target", session=session)

    assert result.has_proposed_command is True
    assert result.proposed_command is not None
    assert result.proposed_command.text == "nmap -sS -p- 10.10.10.100"
    assert result.proposed_command.origin == CommandOrigin.AI
    assert result.proposed_command.target == "10.10.10.0/24"
    # Verification of zero execution: session commands remains empty until explicitly run
    assert len(session.commands) == 0


@pytest.mark.asyncio
async def test_chat_passes_recent_session_history_context() -> None:
    """Verifies that the use case supplies recent commands to the AI context."""
    gateway = MockAIGateway(response_text="Proceeding with next step.")
    use_case = ChatWithAIUseCase(ai_gateway=gateway)

    session = Session(user="carlos")
    session.add_command(Command(text="ping 10.10.10.1", origin=CommandOrigin.MANUAL_USER))
    session.add_command(Command(text="whois 10.10.10.1", origin=CommandOrigin.MANUAL_USER))

    await use_case.run(message="What should I do next?", session=session)

    assert gateway.last_history is not None
    assert len(gateway.last_history) == 2
    assert "ping 10.10.10.1" in gateway.last_history[0]["content"]
