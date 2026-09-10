"""Domain entity representing an active or completed user work session."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from src.domain.entities.command import Command
from src.domain.entities.target import Target


@dataclass
class Session:
    """Represents a discrete ethical hacking or lab work session.

    Attributes:
        user (str): Operator username owning this session.
        id (UUID): Unique universal identifier for the session, generated via uuid4.
        commands (List[Command]): Chronologically ordered list of commands executed in this session.
        authorized_targets (List[Target]): List of targets permitted for interaction in this session.
        started_at (datetime): UTC timestamp recording when the session began.
        ended_at (Optional[datetime]): Optional UTC timestamp recording when the session was closed.
        is_autonomous (bool): Whether the session allows autonomous AI execution. Defaults to False.
    """

    user: str
    id: UUID = field(default_factory=uuid4)
    commands: List[Command] = field(default_factory=list)
    authorized_targets: List[Target] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    is_autonomous: bool = False

    def add_command(self, command: Command) -> None:
        """Adds a command to the session history, preventing duplicates and ensuring chronological ordering.

        Args:
            command (Command): The command entity to append to the session history.
        """
        # Prevent identical duplicates (same text, origin, and timestamp)
        for existing in self.commands:
            if (
                existing.text == command.text
                and existing.origin == command.origin
                and existing.timestamp == command.timestamp
            ):
                return

        self.commands.append(command)
        # Keep the history strictly ordered by timestamp
        self.commands.sort(key=lambda c: c.timestamp)

    def end_session(self) -> None:
        """Marks the session as closed by assigning the current UTC timestamp to ended_at."""
        self.ended_at = datetime.now(timezone.utc)
