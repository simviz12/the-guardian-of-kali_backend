"""Abstract interface for terminal shell executors."""

from abc import ABC, abstractmethod

from src.application.dtos.responses import CommandResult
from src.domain.entities.command import Command


class ShellExecutor(ABC):
    """Port defining command execution inside the Kali Linux environment."""

    @abstractmethod
    async def execute(self, command: Command) -> CommandResult:
        """Executes a command entity in the underlying system.

        Args:
            command (Command): The command entity to execute.

        Returns:
            CommandResult: Standard output, error, and exit status.
        """
        raise NotImplementedError
