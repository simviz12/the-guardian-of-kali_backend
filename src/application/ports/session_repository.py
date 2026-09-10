"""Abstract interface for session persistence and command auditing."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.domain.entities.session import Session
from src.domain.entities.command import Command


class SessionRepository(ABC):
    """Port defining storage and retrieval of sessions and executed command logs."""

    @abstractmethod
    async def save(self, session: Session) -> None:
        """Persists the state of a session and its command history.

        Args:
            session (Session): The session entity to store.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_history(self, filters: Dict[str, Any]) -> List[Command]:
        """Retrieves past executed commands matching given search criteria.

        Args:
            filters (Dict[str, Any]): Filter parameters (e.g., session_id, user, date range).

        Returns:
            List[Command]: Chronologically matched command history.
        """
        raise NotImplementedError
