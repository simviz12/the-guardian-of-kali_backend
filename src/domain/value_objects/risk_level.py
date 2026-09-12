"""Value object representing the risk level classification of a command."""

from enum import Enum


class RiskLevel(str, Enum):
    """Enumeration of safety risk levels assigned to commands by the policy engine."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"
