"""Use case for executing a command in the terminal and recording it in the session."""

import time

from src.application.dtos.responses import CommandResult
from src.application.ports.session_repository import SessionRepository
from src.application.ports.shell_executor import ShellExecutor
from src.application.use_cases.evaluate_policy import EvaluatePolicyUseCase
from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.exceptions import CommandBlockedException
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.policy_action import PolicyAction


class ExecuteCommandUseCase:
    """Orchestrates the execution of a command through the shell executor
    and ensures policy enforcement and session state persistence.

    Commands with origin='AI' are strictly passed through EvaluatePolicyUseCase
    before touching the shell executor — preventing any execution bypass.
    Commands with origin='MANUAL_USER' skip this filter (direct human responsibility).

    Attributes:
        _executor (ShellExecutor): Abstract interface for terminal execution.
        _repository (SessionRepository): Abstract interface for session persistence.
        _policy_evaluator (Optional[EvaluatePolicyUseCase]): Mandatory policy gate for AI commands.
    """

    def __init__(
        self,
        executor: ShellExecutor,
        repository: SessionRepository,
        policy_evaluator: EvaluatePolicyUseCase | None = None,
    ) -> None:
        """Initializes the use case via constructor dependency injection.

        Args:
            executor (ShellExecutor): Abstract terminal execution interface.
            repository (SessionRepository): Abstract session storage interface.
            policy_evaluator (Optional[EvaluatePolicyUseCase]): Policy evaluation use case.
        """
        self._executor = executor
        self._repository = repository
        self._policy_evaluator = policy_evaluator or EvaluatePolicyUseCase()

    async def run(self, command: Command, session: Session) -> CommandResult:
        """Executes a command, attaches it to the session history, and persists the session.

        Enforces mandatory policy check for AI commands. Safely handles executor errors.

        Args:
            command (Command): The command entity to execute.
            session (Session): The active session context.

        Returns:
            CommandResult: Execution output (stdout, stderr, exit code, duration).

        Raises:
            CommandBlockedException: If command origin is AI and evaluation results in BLOCK.
        """
        # Enforce policy gate: AI commands MUST pass evaluation; MANUAL_USER commands skip
        if command.origin == CommandOrigin.AI:
            decision = self._policy_evaluator.evaluate_decision(command, session)
            command.risk_level = decision.risk_level

            if decision.action == PolicyAction.BLOCK:
                raise CommandBlockedException(
                    command=command.text,
                    reason=decision.reason,
                )

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
                stderr=f"Execution failed due to unexpected error: {exc!s}",
                duration_ms=duration,
            )

        # Append command to session history (maintains ordering and prevents duplicates)
        session.add_command(command)

        # Persist session state via repository
        await self._repository.save(session)

        return result
