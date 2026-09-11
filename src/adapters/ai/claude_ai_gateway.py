"""Claude AI Gateway adapter implementing AIGateway using Anthropic's official Python SDK."""
import os
from typing import Any, Dict, List, Optional
import anthropic

from src.application.dtos.responses import AIResponse
from src.application.ports.ai_gateway import AIGateway
from src.infrastructure.config.system_prompt import KALI_GUARDIAN_SYSTEM_PROMPT


PROPOSE_COMMAND_TOOL: Dict[str, Any] = {
    "name": "propose_command",
    "description": "Proposes an offensive or defensive cybersecurity command to run in Kali Linux for ethical hacking or CTFs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The exact bash command to execute inside Kali Linux.",
            },
            "target": {
                "type": "string",
                "description": "The target host, IP, or network range.",
            },
            "justification": {
                "type": "string",
                "description": "Security rationale explaining why this command is needed for this pentest/CTF stage.",
            },
        },
        "required": ["command", "target", "justification"],
    },
}


class ClaudeAIGateway(AIGateway):
    """Adapter connecting to Anthropic Claude models supporting function / tool calling.

    Attributes:
        _client (anthropic.AsyncAnthropic): Official Anthropic async client.
        _model (str): Anthropic model identifier.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        system_prompt: str = KALI_GUARDIAN_SYSTEM_PROMPT,
        client: Optional[anthropic.AsyncAnthropic] = None,
    ) -> None:
        """Initializes the Claude AI gateway adapter.

        Args:
            api_key (Optional[str]): Anthropic API key (defaults to ANTHROPIC_API_KEY environment variable).
            model (str): Claude model identifier.
            system_prompt (str): System prompt establishing role and security context.
            client (Optional[anthropic.AsyncAnthropic]): Optional pre-configured AsyncAnthropic client.
        """
        self._model = model
        self._system_prompt = system_prompt
        self._client = client or anthropic.AsyncAnthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY", "dummy-key"))

    async def send_message(
        self,
        prompt: str,
        history: List[Dict[str, Any]],
    ) -> AIResponse:
        """Sends user prompt and historical turns to Claude, interpreting tool_use blocks or text.

        Args:
            prompt (str): Current query or instruction from the operator.
            history (List[Dict[str, Any]]): Prior conversation turn history.

        Returns:
            AIResponse: Parsed natural language content and optional suggested command.
        """
        # Convert internal history format to Anthropic messages
        messages: List[Dict[str, Any]] = []

        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")
            # Anthropic API requires roles to alternate between user and assistant
            normalized_role = "assistant" if role == "assistant" else "user"
            messages.append({"role": normalized_role, "content": content})

        # Append current user prompt
        messages.append({"role": "user", "content": prompt})

        # Request completion with tool definition
        response = await self._client.messages.create(
            model=self._model,
            system=self._system_prompt,
            messages=messages,
            tools=[PROPOSE_COMMAND_TOOL],
            max_tokens=1024,
        )

        text_content_parts: List[str] = []
        suggested_command: Optional[str] = None
        tool_justification: Optional[str] = None
        tool_target: Optional[str] = None

        # Inspect response content blocks (Text and ToolUse)
        for block in response.content:
            if getattr(block, "type", "") == "text":
                text_content_parts.append(block.text)
            elif getattr(block, "type", "") == "tool_use":
                if block.name == "propose_command":
                    input_args = block.input or {}
                    suggested_command = input_args.get("command")
                    tool_target = input_args.get("target")
                    tool_justification = input_args.get("justification")

        full_text = "\n\n".join(text_content_parts).strip()

        # If model only returned tool_use with justification, use justification as fallback content
        if not full_text and tool_justification:
            full_text = f"Proposed command for target '{tool_target}': {tool_justification}"

        metadata = {
            "model": response.model,
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
            },
        }

        return AIResponse(
            content=full_text,
            suggested_command=suggested_command,
            metadata=metadata,
        )
