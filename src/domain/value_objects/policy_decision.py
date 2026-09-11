"""Value object representing the evaluated policy decision for a command."""
from dataclasses import dataclass
from src.domain.value_objects.policy_action import PolicyAction
from src.domain.value_objects.risk_level import RiskLevel


@dataclass(frozen=True)
class PolicyDecision:
    """Represents the safety and authorization decision resulting from validating a command.

    Attributes:
        action (PolicyAction): Enforcement action (AUTO_EXECUTE, REQUIRE_CONFIRMATION, BLOCK).
        risk_level (RiskLevel): Evaluated command risk category (LOW, MEDIUM, HIGH, BLOCKED).
        reason (str): Exact triggering rationale behind this policy decision.
        command_text (str): The raw text of the evaluated command.
    """

    action: PolicyAction
    risk_level: RiskLevel
    reason: str
    command_text: str
