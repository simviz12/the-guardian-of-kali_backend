"""Use case for interacting with the AI co-pilot and interpreting proposed commands."""

from typing import Any

from src.application.dtos.responses import ChatResult
from src.application.ports.ai_gateway import AIGateway
from src.application.ports.session_repository import SessionRepository
from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.value_objects.command_origin import CommandOrigin


class ChatWithAIUseCase:
    """Orchestrates natural language conversations with the AI co-pilot.

    Extracts conversational guidance and optionally constructs a proposed Command
    entity from tool use, WITHOUT executing it in the terminal.

    Attributes:
        _ai_gateway (AIGateway): Abstract interface for AI model communications.
        _repository (SessionRepository): Repository to access chat and command history.
    """

    def __init__(self, ai_gateway: AIGateway, repository: SessionRepository) -> None:
        """Initializes the chat use case via constructor dependency injection.

        Args:
            ai_gateway (AIGateway): Abstract AI gateway port.
            repository (SessionRepository): Repository for history.
        """
        self._ai_gateway = ai_gateway
        self._repository = repository

    async def run(self, message: str, session: Session) -> ChatResult:
        """Sends the user message with recent session history to the AI co-pilot.

        Args:
            message (str): User prompt or query.
            session (Session): The current session context providing recent command history.

        Returns:
            ChatResult: Conversational text and proposed command entity (if any).
        """
        # Format recent session commands and authorized targets as contextual history for the AI
        history: list[dict[str, Any]] = []

        targets_str = ", ".join([t.value for t in session.authorized_targets]) if session.authorized_targets else "10.10.10.10, target.htb, localhost"
        history.append({
            "role": "system",
            "content": (
                f"Active authorized scope for this lab/CTF session: [{targets_str}]. "
                "You have full authorization for all ethical reconnaissance, scanning, cracking, OSINT, and enumeration actions. "
                "Whenever the user asks how to do something, immediately provide the practical command using the propose_command function call."
            ),
        })

        # Fetch actual chat messages for this session
        if session.id:
            chat_messages = await self._repository.get_chat_messages(str(session.id))
            # Take the last 20 messages for context
            for msg in chat_messages[-20:]:
                sender = msg.get("sender")
                text = msg.get("text", "")
                proposed = msg.get("proposed_command_text")
                status = msg.get("execution_status")
                stdout = msg.get("execution_stdout")
                
                content = text
                if proposed:
                    content += f"\n\n[System] Proposed command: {proposed}"
                if status == "executed" and stdout:
                    content += f"\n\n[System] Command executed successfully. Output snippet:\n{stdout[:500]}"
                elif status == "failed":
                    content += f"\n\n[System] Command failed to execute."

                role = "user" if sender == "User" else "assistant"
                history.append({
                    "role": role,
                    "content": content,
                })
        else:
            # Fallback to executed commands if no session ID provided
            for cmd in session.commands[-10:]:
                history.append({
                    "role": "system",
                    "content": f"Executed command: '{cmd.text}' (origin: {cmd.origin.value})",
                })

        # Call the abstract AI gateway
        ai_response = await self._ai_gateway.send_message(prompt=message, history=history)

        # Interpret whether the AI proposed a command
        proposed_command: Command | None = None
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
