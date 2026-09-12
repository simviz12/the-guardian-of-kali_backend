"""Domain entity representing a terminal command inside the system."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.risk_level import RiskLevel


@dataclass
class Command:
    """Core domain entity representing a terminal command.

    Attributes:
        text (str): The raw terminal command text to be inspected or executed.
        origin (CommandOrigin): Origin source of the command (MANUAL_USER or AI).
        target (Optional[str]): Optional host, IP address, CIDR, or scope targeted by the command.
        timestamp (datetime): UTC timestamp recording when the command was instantiated.
        risk_level (Optional[RiskLevel]): Safety classification evaluated by the policy engine.
            Defaults to None prior to policy evaluation.
    """

    text: str
    origin: CommandOrigin
    target: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    risk_level: RiskLevel | None = None
