"""Claude AI Gateway adapter implementing AIGateway using Anthropic's official Python SDK."""
import asyncio
import os
import logging
from typing import Any, Dict, List, Optional
import anthropic

from src.application.dtos.responses import AIResponse
from src.application.ports.ai_gateway import AIGateway
from src.infrastructure.config.system_prompt import KALI_GUARDIAN_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

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
    """Adapter connecting to Anthropic Claude models supporting function / tool calling
    and resilient error handling with exponential backoff.

    Attributes:
        _client (anthropic.AsyncAnthropic): Official Anthropic async client.
        _model (str): Anthropic model identifier.
        _max_retries (int): Maximum retry attempts for transient API errors and rate limits.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        system_prompt: str = KALI_GUARDIAN_SYSTEM_PROMPT,
        client: Optional[anthropic.AsyncAnthropic] = None,
        max_retries: int = 3,
    ) -> None:
        """Initializes the Claude AI gateway adapter.

        Args:
            api_key (Optional[str]): Anthropic API key (defaults to ANTHROPIC_API_KEY environment variable).
            model (str): Claude model identifier.
            system_prompt (str): System prompt establishing role and security context.
            client (Optional[anthropic.AsyncAnthropic]): Optional pre-configured AsyncAnthropic client.
            max_retries (int): Max retry attempts for transient failures. Defaults to 3.
        """
        self._model = model
        self._system_prompt = system_prompt
        self._client = client or anthropic.AsyncAnthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY", "dummy-key"))
        self._max_retries = max_retries

    async def send_message(
        self,
        prompt: str,
        history: List[Dict[str, Any]],
    ) -> AIResponse:
        """Sends user prompt and historical turns to Claude, interpreting tool_use blocks or text.

        Includes exponential backoff (max 3 retries) for rate limits and server errors.

        Args:
            prompt (str): Current query or instruction from the operator.
            history (List[Dict[str, Any]]): Prior conversation turn history.

        Returns:
            AIResponse: Parsed natural language content and optional suggested command.

        Raises:
            anthropic.RateLimitError: If rate limit persists after max retries.
            anthropic.APIError: If Claude API failure persists after max retries.
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

        # Execute API call with exponential backoff for rate limits and transient errors
        response = await self._call_with_retry(messages)

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

    async def _call_with_retry(self, messages: List[Dict[str, Any]]) -> Any:
        """Executes the Anthropic messages.create call with exponential backoff on retryable errors."""
        delay = 1.0  # initial delay in seconds

        for attempt in range(1, self._max_retries + 1):
            try:
                return await self._client.messages.create(
                    model=self._model,
                    system=self._system_prompt,
                    messages=messages,
                    tools=[PROPOSE_COMMAND_TOOL],
                    max_tokens=1024,
                )
            except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError) as exc:
                if attempt == self._max_retries:
                    logger.error(f"Claude API failed after {attempt} attempts: {str(exc)}")
                    raise
                logger.warning(
                    f"Transient Claude API error (attempt {attempt}/{self._max_retries}): {str(exc)}. Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
                delay *= 2.0  # exponential backoff
