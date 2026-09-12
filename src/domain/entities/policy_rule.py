"""Domain entity representing a security policy rule."""

import re
from dataclasses import dataclass

from src.domain.value_objects.policy_action import PolicyAction
from src.domain.value_objects.risk_level import RiskLevel


@dataclass(frozen=True)
class PolicyRule:
    """Security rule used by the policy engine to inspect and classify commands.

    Attributes:
        id (str): Unique rule identifier (e.g., 'block-rm-rf', 'require-confirm-nmap-agg').
        pattern (str): Regular expression pattern or keyword string to match against commands.
        risk_level (RiskLevel): Assessed risk level when this rule matches.
        action (PolicyAction): Enforcement action (AUTO_EXECUTE, REQUIRE_CONFIRMATION, or BLOCK).
        description (Optional[str]): Human-readable rationale for this rule.
    """

    id: str
    pattern: str
    risk_level: RiskLevel
    action: PolicyAction
    description: str | None = None

    def matches(self, command_text: str) -> bool:
        """Determines whether the given command matches this rule's regex pattern.

        Args:
            command_text (str): The raw terminal command to inspect.

        Returns:
            bool: True if the pattern matches anywhere in the command text, False otherwise.
        """
        try:
            return bool(re.search(self.pattern, command_text.strip(), re.IGNORECASE))
        except re.error:
            # Fallback to direct substring matching if regex pattern compilation fails
            return self.pattern.lower() in command_text.lower()
