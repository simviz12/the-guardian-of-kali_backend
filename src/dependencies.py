"""Dependency injection providers for use cases and infrastructure adapters."""
from functools import lru_cache
from typing import Optional, List

from src.application.ports.shell_executor import ShellExecutor
from src.application.ports.session_repository import SessionRepository
from src.application.ports.ai_gateway import AIGateway
from src.adapters.terminal.wsl_shell_executor import WSLShellExecutor
from src.adapters.storage.sqlite_session_repository import SQLiteSessionRepository
from src.application.use_cases.execute_command import ExecuteCommandUseCase
from src.application.use_cases.evaluate_policy import EvaluatePolicyUseCase
from src.application.use_cases.chat_with_ai import ChatWithAIUseCase
from src.domain.entities.policy_rule import PolicyRule


# Placeholder AI gateway for DI until Anthropic adapter is hooked
class DefaultAIGateway(AIGateway):
    """Default placeholder AI gateway for DI container."""
    async def send_message(self, prompt: str, history):
        from src.application.dtos.responses import AIResponse
        return AIResponse(content="AI co-pilot initialized.", suggested_command=None)


@lru_cache()
def get_shell_executor() -> ShellExecutor:
    """Provides a singleton WSLShellExecutor instance."""
    return WSLShellExecutor(distro="kali-linux", user="ia-user", timeout_seconds=30.0)


@lru_cache()
def get_session_repository() -> SessionRepository:
    """Provides a singleton SQLiteSessionRepository instance."""
    return SQLiteSessionRepository(db_path="the_guardian_of_kali.db")


@lru_cache()
def get_ai_gateway() -> AIGateway:
    """Provides a singleton AIGateway instance."""
    return DefaultAIGateway()


def get_execute_command_use_case() -> ExecuteCommandUseCase:
    """Provides the ExecuteCommandUseCase with injected dependencies."""
    return ExecuteCommandUseCase(
        executor=get_shell_executor(),
        repository=get_session_repository(),
    )


def get_evaluate_policy_use_case() -> EvaluatePolicyUseCase:
    """Provides the EvaluatePolicyUseCase with configured default rules."""
    return EvaluatePolicyUseCase()


def get_chat_with_ai_use_case() -> ChatWithAIUseCase:
    """Provides the ChatWithAIUseCase with injected AI gateway."""
    return ChatWithAIUseCase(
        ai_gateway=get_ai_gateway(),
    )
