"""Abstract interface for terminal execution engines."""

from abc import ABC, abstractmethod
from typing import Any


class TerminalExecutorPort(ABC):
    """Port defining command execution inside WSL2 under restricted or operator contexts."""

    @abstractmethod
    async def execute_command(
        self, command: str, as_restricted_user: bool = True
    ) -> dict[str, Any]:
        """Executes a command and returns execution metadata (exit code, stdout, stderr)."""
        raise NotImplementedError
