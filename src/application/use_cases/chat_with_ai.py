"""Use case for interacting with the AI co-pilot and interpreting proposed commands."""
from typing import Any, Dict, List, Optional

from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.value_objects.command_origin import CommandOrigin
from src.application.ports.ai_gateway import AIGateway
from src.application.dtos.responses import ChatResult


class ChatWithAIUseCase:
    """Orchestrates natural language conversations with the AI co-pilot.

    Extracts conversational guidance and optionally constructs a proposed Command
    entity from tool use, WITHOUT executing it in the terminal.

    Attributes:
        _ai_gateway (AIGateway): Abstract interface for AI model communications.
    """

    def __init__(self, ai_gateway: AIGateway) -> None:
        """Initializes the chat use case via constructor dependency injection.

        Args:
            ai_gateway (AIGateway): Abstract AI gateway port.
        """
        self._ai_gateway = ai_gateway

    async def run(self, message: str, session: Session) -> ChatResult:
        """Sends the user message with recent session history to the AI co-pilot.

        Args:
            message (str): User prompt or query.
            session (Session): The current session context providing recent command history.

        Returns:
            ChatResult: Conversational text and proposed command entity (if any).
        """
        # Format recent session commands as contextual history for the AI
        history: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": f"Executed command: '{cmd.text}' (origin: {cmd.origin.value})",
            }
            for cmd in session.commands[-10:]  # Last 10 commands for focused context
        ]

        # Call the abstract AI gateway
        ai_response = await self._ai_gateway.send_message(prompt=message, history=history)

        # Interpret whether the AI proposed a command
        proposed_command: Optional[Command] = None
        if ai_response.suggested_command:
            primary_target = (
                session.authorized_targets[0].value if session.authorized_targets else None
            )
            proposed_command = Command(
                text=ai_response.suggested_command.strip(),
                origin=CommandOrigin.AI,
                target=primary_target,
            )

        return ChatResult(
            response_text=ai_response.content,
            proposed_command=proposed_command,
        )
