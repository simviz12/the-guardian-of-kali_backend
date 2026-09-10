"""Use case for executing a command in the terminal and recording it in the session."""
import time
from typing import Optional

from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.application.ports.shell_executor import ShellExecutor
from src.application.ports.session_repository import SessionRepository
from src.application.dtos.responses import CommandResult


class ExecuteCommandUseCase:
    """Orchestrates the execution of a validated command through the shell executor
    and ensures the session state is updated and saved.

    Attributes:
        _executor (ShellExecutor): Abstract interface for terminal execution.
        _repository (SessionRepository): Abstract interface for session persistence.
    """

    def __init__(
        self,
        executor: ShellExecutor,
        repository: SessionRepository
    ) -> None:
        """Initializes the use case via constructor dependency injection.

        Args:
            executor (ShellExecutor): Abstract terminal execution interface.
            repository (SessionRepository): Abstract session storage interface.
        """
        self._executor = executor
        self._repository = repository

    async def run(self, command: Command, session: Session) -> CommandResult:
        """Executes a command, attaches it to the session history, and persists the session.

        Safely handles any executor exceptions without terminating the application.

        Args:
            command (Command): The command entity to execute.
            session (Session): The active session context.

        Returns:
            CommandResult: Execution output (stdout, stderr, exit code, duration).
        """
        start_time = time.perf_counter()

        try:
            # Delegate command execution to the abstract shell executor
            result = await self._executor.execute(command)
        except Exception as exc:
            # Resilient exception fallback: do not crash the app on executor errors
            duration = (time.perf_counter() - start_time) * 1000.0
            result = CommandResult(
                command_text=command.text,
                exit_code=1,
                stdout="",
                stderr=f"Execution failed due to unexpected error: {str(exc)}",
                duration_ms=duration,
            )

        # Append command to session history (maintains ordering and prevents duplicates)
        session.add_command(command)

        # Persist session state via repository
        await self._repository.save(session)

        return result
