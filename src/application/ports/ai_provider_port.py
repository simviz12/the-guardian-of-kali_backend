"""Abstract interface for AI intelligence providers."""

from abc import ABC, abstractmethod
from typing import Any


class AIProviderPort(ABC):
    """Port defining operations for AI model interactions and tool calling."""

    @abstractmethod
    async def generate_command_suggestion(self, prompt: str, context: dict[str, Any]) -> str:
        """Generates a suggested terminal command from natural language prompt."""
        raise NotImplementedError
