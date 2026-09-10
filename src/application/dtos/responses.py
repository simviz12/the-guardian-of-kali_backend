"""Data transfer objects for the application layer."""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AIResponse:
    """Response payload returned by an AI intelligence provider.

    Attributes:
        content (str): Natural language conversational response or explanation.
        suggested_command (Optional[str]): Optional terminal command proposed by the AI.
        metadata (Dict[str, Any]): Additional provider details (model, usage, token count).
    """

    content: str
    suggested_command: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandResult:
    """Result outcome of a terminal command execution.

    Attributes:
        command_text (str): Exact command executed in the terminal.
        exit_code (int): Process exit code (0 for success, non-zero for failure).
        stdout (str): Standard output generated during execution.
        stderr (str): Standard error output generated during execution.
        duration_ms: (float): Execution duration measured in milliseconds.
    """

    command_text: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float = 0.0
