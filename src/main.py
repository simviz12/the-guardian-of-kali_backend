"""FastAPI application entrypoint for The Guardian of Kali backend service."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import anthropic
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, status

load_dotenv()

from fastapi.middleware.cors import CORSMiddleware

from src.application.use_cases.chat_with_ai import ChatWithAIUseCase
from src.application.use_cases.evaluate_policy import EvaluatePolicyUseCase
from src.application.use_cases.execute_command import ExecuteCommandUseCase
from src.application.use_cases.get_session_history import GetSessionHistoryUseCase
from src.dependencies import (
    get_chat_with_ai_use_case,
    get_evaluate_policy_use_case,
    get_execute_command_use_case,
    get_session_history_use_case,
)
from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.entities.target import Target
from src.domain.exceptions import CommandBlockedException, TargetNotAuthorizedException
from src.domain.value_objects.risk_level import RiskLevel
from src.adapters.storage.sqlite_session_repository import SQLiteSessionRepository
from src.infrastructure.api.schemas import (
    ChatMessageItem,
    ChatMessagesResponse,
    ChatRequest,
    ChatResponse,
    CommandHistoryItem,
    ExecuteCommandRequest,
    ExecuteCommandResponse,
    HistoryResponse,
    ProposedCommandSchema,
    SaveChatMessageRequest,
    SaveChatMessageResponse,
    UpdateChatMessageRequest,
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance.

    Configures CORS restricted to local Electron origins and mounts health check,
    execution, history, chat, and dependency injection endpoints.

    Returns:
        FastAPI: The configured application instance.
    """
    app = FastAPI(
        title="The Guardian of Kali - Backend API",
        description="Backend API and Policy Engine co-pilot for Kali Linux WSL2",
        version="0.1.0",
    )

    # CORS configuration restricted strictly to local Electron origins
    allowed_origins = [
        "http://localhost:5173",  # Vite dev server default
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "app://-",  # Electron production custom protocol
        "file://",  # Electron local file rendering
    ]


    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
    async def health_check() -> dict[str, Any]:
        """Performs a service health check."""
        return {
            "status": "healthy",
            "service": "the-guardian-of-kali-backend",
            "version": "0.1.0",
        }

    @app.post(
        "/execute",
        response_model=ExecuteCommandResponse,
        status_code=status.HTTP_200_OK,
        tags=["Terminal Execution"],
    )
    async def execute_command(
        payload: ExecuteCommandRequest,
        execute_use_case: ExecuteCommandUseCase = Depends(get_execute_command_use_case),
    ) -> ExecuteCommandResponse:
        """Executes a terminal command via the injected ExecuteCommandUseCase and records it."""
        session_id = payload.session_id
        targets = (
            [Target(value=t) for t in payload.authorized_targets]
            if payload.authorized_targets
            else []
        )
        session = (
            Session(user="ia-user", id=session_id, authorized_targets=targets)
            if session_id
            else Session(user="ia-user", authorized_targets=targets)
        )

        command_entity = Command(
            text=payload.command,
            origin=payload.origin,
            target=payload.target,
        )

        try:
            result = await execute_use_case.run(command=command_entity, session=session)
        except (CommandBlockedException, TargetNotAuthorizedException) as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            )

        return ExecuteCommandResponse(
            command=result.command_text,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=result.duration_ms,
            session_id=session.id,
        )

    @app.get(
        "/history",
        response_model=HistoryResponse,
        status_code=status.HTTP_200_OK,
        tags=["Audit & History"],
    )
    async def get_history(
        session_id: UUID | None = Query(None, description="Filter by session UUID"),
        user: str | None = Query(None, description="Filter by session user"),
        start_date: datetime | None = Query(None, description="Start date filter (inclusive)"),
        end_date: datetime | None = Query(None, description="End date filter (inclusive)"),
        risk_level: RiskLevel | None = Query(None, description="Filter by risk level"),
        history_use_case: GetSessionHistoryUseCase = Depends(get_session_history_use_case),
    ) -> HistoryResponse:
        """Queries historical executed commands with optional date range, user, or risk filters."""
        commands = await history_use_case.run(
            session_id=session_id,
            user=user,
            start_date=start_date,
            end_date=end_date,
            risk_level=risk_level,
        )

        items = [
            CommandHistoryItem(
                text=cmd.text,
                origin=cmd.origin,
                target=cmd.target,
                risk_level=cmd.risk_level,
                timestamp=cmd.timestamp,
            )
            for cmd in commands
        ]

        return HistoryResponse(
            count=len(items),
            commands=items,
        )

    @app.post(
        "/chat",
        response_model=ChatResponse,
        status_code=status.HTTP_200_OK,
        tags=["AI Co-Pilot"],
    )
    async def chat_with_ai(
        payload: ChatRequest,
        chat_use_case: ChatWithAIUseCase = Depends(get_chat_with_ai_use_case),
    ) -> ChatResponse:
        """Sends an operator prompt to the AI co-pilot with session history and returns advice / proposed commands.

        Catches Anthropic rate limits and API errors gracefully returning appropriate HTTP statuses.
        """
        targets = (
            [Target(value=t) for t in payload.authorized_targets]
            if payload.authorized_targets
            else []
        )
        session = (
            Session(user="carlos", id=payload.session_id, authorized_targets=targets)
            if payload.session_id
            else Session(user="carlos", authorized_targets=targets)
        )

        try:
            chat_result = await chat_use_case.run(message=payload.message, session=session)
        except anthropic.RateLimitError as exc:
            logger.error(f"Claude API rate limit reached: {exc!s}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI service rate limit exceeded. Please wait a moment before trying again.",
            ) from exc
        except (anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
            logger.error(f"Claude API transient error: {exc!s}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"AI co-pilot service temporarily unavailable: {exc!s}",
            ) from exc
        except anthropic.APIError as exc:
            logger.error(f"Claude API error: {exc!s}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error communicating with AI service: {exc!s}",
            ) from exc
        except Exception as exc:
            logger.error(f"Unexpected chat processing error: {exc!s}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An internal error occurred while processing the chat request.",
            ) from exc

        proposed_command_schema = None
        if chat_result.proposed_command:
            proposed_command_schema = ProposedCommandSchema(
                text=chat_result.proposed_command.text,
                target=chat_result.proposed_command.target,
                origin=chat_result.proposed_command.origin,
            )

        return ChatResponse(
            response=chat_result.response_text,
            has_proposed_command=chat_result.has_proposed_command,
            proposed_command=proposed_command_schema,
            session_id=session.id,
        )

    @app.get("/api/di-check", status_code=status.HTTP_200_OK, tags=["Diagnostic"])
    async def di_check(
        execute_use_case: ExecuteCommandUseCase = Depends(get_execute_command_use_case),
        evaluate_use_case: EvaluatePolicyUseCase = Depends(get_evaluate_policy_use_case),
        chat_use_case: ChatWithAIUseCase = Depends(get_chat_with_ai_use_case),
        history_use_case: GetSessionHistoryUseCase = Depends(get_session_history_use_case),
    ) -> dict[str, str]:
        """Diagnostic route verifying dependency injection of application use cases."""
        return {
            "execute_use_case": execute_use_case.__class__.__name__,
            "evaluate_use_case": evaluate_use_case.__class__.__name__,
            "chat_use_case": chat_use_case.__class__.__name__,
            "history_use_case": history_use_case.__class__.__name__,
        }

    # ────────────────────────────────────────────
    # Chat Message Persistence Endpoints
    # ────────────────────────────────────────────

    _chat_repo = SQLiteSessionRepository(db_path="the_guardian_of_kali.db")

    @app.post(
        "/chat/message",
        response_model=SaveChatMessageResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["Chat History"],
    )
    async def save_chat_message(payload: SaveChatMessageRequest) -> SaveChatMessageResponse:
        """Persists a single chat message (user or AI) to the SQLite database."""
        msg_id = await _chat_repo.save_chat_message(
            session_id=payload.session_id,
            sender=payload.sender,
            text=payload.text,
            proposed_command_text=payload.proposed_command_text,
            proposed_command_target=payload.proposed_command_target,
            execution_status=payload.execution_status,
            execution_stdout=payload.execution_stdout,
            execution_stderr=payload.execution_stderr,
            execution_exit_code=payload.execution_exit_code,
            timestamp=payload.timestamp,
        )
        return SaveChatMessageResponse(message_id=msg_id, ok=True)

    @app.patch(
        "/chat/message/{message_id}",
        status_code=status.HTTP_200_OK,
        tags=["Chat History"],
    )
    async def update_chat_message(
        message_id: int, payload: UpdateChatMessageRequest
    ) -> dict:
        """Updates the execution result fields of an existing chat message."""
        await _chat_repo.update_chat_message_execution(
            message_id=message_id,
            execution_status=payload.execution_status,
            execution_stdout=payload.execution_stdout,
            execution_stderr=payload.execution_stderr,
            execution_exit_code=payload.execution_exit_code,
        )
        return {"ok": True, "message_id": message_id}

    @app.get(
        "/chat/messages/{session_id}",
        response_model=ChatMessagesResponse,
        status_code=status.HTTP_200_OK,
        tags=["Chat History"],
    )
    async def get_chat_messages(session_id: str) -> ChatMessagesResponse:
        """Returns the full chat history for a given session ID."""
        rows = await _chat_repo.get_chat_messages(session_id=session_id)
        messages = [ChatMessageItem(**row) for row in rows]
        return ChatMessagesResponse(
            session_id=session_id,
            count=len(messages),
            messages=messages,
        )

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )
