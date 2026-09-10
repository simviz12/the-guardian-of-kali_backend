"""Abstract interface for AI model gateways."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.application.dtos.responses import AIResponse


class AIGateway(ABC):
    """Port defining operations for communicating with AI co-pilots and models."""

    @abstractmethod
    async def send_message(
        self,
        prompt: str,
        history: List[Dict[str, Any]]
    ) -> AIResponse:
        """Sends a natural language prompt with session history to the AI model.

        Args:
            prompt (str): Current query or instruction from the operator.
            history (List[Dict[str, Any]]): Prior conversation turn history.

        Returns:
            AIResponse: Generated response with explanation and optional suggested command.
        """
        raise NotImplementedError
