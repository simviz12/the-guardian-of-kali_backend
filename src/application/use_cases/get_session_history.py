"""Use case for querying session command history with optional filters."""

from datetime import datetime
from typing import Any
from uuid import UUID

from src.application.ports.session_repository import SessionRepository
from src.domain.entities.command import Command
from src.domain.value_objects.risk_level import RiskLevel


class GetSessionHistoryUseCase:
    """Retrieves executed command history across sessions or for specific filters.

    Attributes:
        _repository (SessionRepository): Abstract repository for session persistence.
    """

    def __init__(self, repository: SessionRepository) -> None:
        """Initializes the history retrieval use case.

        Args:
            repository (SessionRepository): Abstract session repository.
        """
        self._repository = repository

    async def run(
        self,
        session_id: UUID | None = None,
        user: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        risk_level: RiskLevel | None = None,
    ) -> list[Command]:
        """Queries the session repository for commands matching criteria.

        Args:
            session_id (Optional[UUID]): Filter by specific session ID.
            user (Optional[str]): Filter by session operator user.
            start_date (Optional[datetime]): Start of date range (inclusive).
            end_date (Optional[datetime]): End of date range (inclusive).
            risk_level (Optional[RiskLevel]): Filter by evaluated risk level.

        Returns:
            List[Command]: Chronologically ordered list of matching commands.
        """
        filters: dict[str, Any] = {}
        if session_id is not None:
            filters["session_id"] = session_id
        if user is not None:
            filters["user"] = user
        if start_date is not None:
            filters["start_date"] = start_date
        if end_date is not None:
            filters["end_date"] = end_date
        if risk_level is not None:
            filters["risk_level"] = risk_level

        return await self._repository.get_history(filters)
