"""Strict Pydantic request and response schemas for FastAPI endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.risk_level import RiskLevel


class ExecuteCommandRequest(BaseModel):
    """Payload schema for POST /execute."""

    model_config = ConfigDict(extra="forbid")

    command: str = Field(..., min_length=1, description="Raw terminal command text to execute.")
    target: str | None = Field(None, description="Optional target IP, CIDR or domain.")
    origin: CommandOrigin = Field(
        default=CommandOrigin.AI,
        description="Origin source of the command ('MANUAL_USER' or 'AI').",
    )
    session_id: UUID | None = Field(
        None,
        description="Optional session UUID. A new session is created if omitted.",
    )
    authorized_targets: list[str] | None = Field(
        None,
        description="Optional list of authorized IP, CIDR, or domain targets for zero-trust scope enforcement.",
    )


class ExecuteCommandResponse(BaseModel):
    """Response schema for POST /execute."""

    model_config = ConfigDict(extra="forbid")

    command: str = Field(..., description="Executed command text.")
    exit_code: int = Field(..., description="Process exit code (0 for success).")
    stdout: str = Field(..., description="Standard output text.")
    stderr: str = Field(..., description="Standard error text.")
    duration_ms: float = Field(..., description="Execution duration in milliseconds.")
    session_id: UUID = Field(..., description="Session identifier under which execution occurred.")


class CommandHistoryItem(BaseModel):
    """Schema for individual command entries in history."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., description="Executed command text.")
    origin: CommandOrigin = Field(..., description="Command origin.")
    target: str | None = Field(None, description="Target host or IP.")
    risk_level: RiskLevel | None = Field(None, description="Evaluated risk level.")
    timestamp: datetime = Field(..., description="UTC timestamp of instantiation.")


class HistoryResponse(BaseModel):
    """Response schema for GET /history."""

    model_config = ConfigDict(extra="forbid")

    count: int = Field(..., description="Number of commands returned.")
    commands: list[CommandHistoryItem] = Field(..., description="List of command history items.")


class ChatRequest(BaseModel):
    """Payload schema for POST /chat."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        ..., min_length=1, description="Operator prompt or instruction for the AI."
    )
    session_id: UUID | None = Field(
        None,
        description="Optional session UUID. A new session context is instantiated if omitted.",
    )


class ProposedCommandSchema(BaseModel):
    """Schema for AI proposed commands."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., description="Proposed terminal command text.")
    target: str | None = Field(None, description="Target host or IP.")
    origin: CommandOrigin = Field(default=CommandOrigin.AI, description="Command origin.")


class ChatResponse(BaseModel):
    """Response schema for POST /chat."""

    model_config = ConfigDict(extra="forbid")

    response: str = Field(..., description="Conversational explanation or guidance from Claude.")
    has_proposed_command: bool = Field(..., description="True if a terminal command is proposed.")
    proposed_command: ProposedCommandSchema | None = Field(
        None,
        description="Structured proposed command details.",
    )
    session_id: UUID = Field(..., description="Active session context UUID.")
