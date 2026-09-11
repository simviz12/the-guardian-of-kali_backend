"""Unit tests for ClaudeAIGateway adapter using Anthropic SDK."""
from unittest.mock import AsyncMock, MagicMock
import pytest

from src.adapters.ai.claude_ai_gateway import ClaudeAIGateway, PROPOSE_COMMAND_TOOL
from src.application.ports.ai_gateway import AIGateway
from src.application.dtos.responses import AIResponse


def test_claude_ai_gateway_implements_interface() -> None:
    """Verifies that ClaudeAIGateway implements the AIGateway abstract port."""
    gateway = ClaudeAIGateway(api_key="test-key")
    assert isinstance(gateway, AIGateway)


def test_propose_command_tool_schema_definition() -> None:
    """Verifies schema structure of propose_command tool."""
    assert PROPOSE_COMMAND_TOOL["name"] == "propose_command"
    schema = PROPOSE_COMMAND_TOOL["input_schema"]
    assert "command" in schema["properties"]
    assert "target" in schema["properties"]
    assert "justification" in schema["properties"]
    assert schema["required"] == ["command", "target", "justification"]


@pytest.mark.asyncio
async def test_send_message_plain_text_response() -> None:
    """Verifies handling of a conversational response without tool use."""
    mock_client = MagicMock()
    mock_messages = AsyncMock()
    mock_client.messages = mock_messages

    # Create mock text content block
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Here is an explanation of active vs passive scanning."

    mock_response = MagicMock()
    mock_response.content = [text_block]
    mock_response.model = "claude-3-5-sonnet-20241022"
    mock_response.stop_reason = "end_turn"
    mock_response.usage = MagicMock(input_tokens=50, output_tokens=30)

    mock_messages.create.return_value = mock_response

    gateway = ClaudeAIGateway(client=mock_client)
    result = await gateway.send_message(
        prompt="Explain nmap scanning",
        history=[{"role": "user", "content": "Hello"}],
    )

    assert isinstance(result, AIResponse)
    assert result.content == "Here is an explanation of active vs passive scanning."
    assert result.suggested_command is None
    assert result.metadata["model"] == "claude-3-5-sonnet-20241022"
    assert result.metadata["usage"]["input_tokens"] == 50


@pytest.mark.asyncio
async def test_send_message_tool_use_response() -> None:
    """Verifies handling when Claude triggers propose_command tool."""
    mock_client = MagicMock()
    mock_messages = AsyncMock()
    mock_client.messages = mock_messages

    # Create mock text block + tool_use block
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "I recommend running a service version scan."

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "propose_command"
    tool_block.input = {
        "command": "nmap -sV -p 22,80 10.10.10.15",
        "target": "10.10.10.15",
        "justification": "Detect open services and versions for vulnerability assessment.",
    }

    mock_response = MagicMock()
    mock_response.content = [text_block, tool_block]
    mock_response.model = "claude-3-5-sonnet-20241022"
    mock_response.stop_reason = "tool_use"
    mock_response.usage = MagicMock(input_tokens=120, output_tokens=85)

    mock_messages.create.return_value = mock_response

    gateway = ClaudeAIGateway(client=mock_client)
    result = await gateway.send_message(
        prompt="Scan 10.10.10.15",
        history=[],
    )

    assert isinstance(result, AIResponse)
    assert "I recommend running a service version scan." in result.content
    assert result.suggested_command == "nmap -sV -p 22,80 10.10.10.15"


@pytest.mark.asyncio
async def test_send_message_tool_use_without_text_fallback() -> None:
    """Verifies fallback content generation when Claude outputs tool_use with empty text block."""
    mock_client = MagicMock()
    mock_messages = AsyncMock()
    mock_client.messages = mock_messages

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "propose_command"
    tool_block.input = {
        "command": "traceroute 10.10.10.1",
        "target": "10.10.10.1",
        "justification": "Trace hops to gateway.",
    }

    mock_response = MagicMock()
    mock_response.content = [tool_block]
    mock_response.model = "claude-3-5-sonnet-20241022"
    mock_response.stop_reason = "tool_use"
    mock_response.usage = MagicMock(input_tokens=80, output_tokens=40)

    mock_messages.create.return_value = mock_response

    gateway = ClaudeAIGateway(client=mock_client)
    result = await gateway.send_message(
        prompt="Trace gateway",
        history=[],
    )

    assert result.suggested_command == "traceroute 10.10.10.1"
    assert "Trace hops to gateway." in result.content
