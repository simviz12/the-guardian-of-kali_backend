"""Use case for evaluating security policies against candidate commands."""
from typing import List, Optional

from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.entities.policy_rule import PolicyRule
from src.domain.value_objects.policy_action import PolicyAction
from src.domain.value_objects.risk_level import RiskLevel
from src.domain.exceptions import CommandBlockedException


class EvaluatePolicyUseCase:
    """Evaluates safety and risk policies against a candidate command within a session context.

    This use case does NOT execute anything; it strictly acts as a decision gate.
    When the evaluated action is BLOCK and the session is in autonomous mode,
    it strictly raises a CommandBlockedException.

    Attributes:
        _rules (List[PolicyRule]): Injected ordered list of security rules to evaluate.
        _default_action (PolicyAction): Fallback action when no specific rule matches.
    """

    def __init__(
        self,
        rules: Optional[List[PolicyRule]] = None,
        default_action: PolicyAction = PolicyAction.REQUIRE_CONFIRMATION,
    ) -> None:
        """Initializes the policy evaluation use case.

        Args:
            rules (Optional[List[PolicyRule]]): List of policy rules. Defaults to empty list.
            default_action (PolicyAction): Fallback policy action.
        """
        self._rules = rules or []
        self._default_action = default_action

    def evaluate(self, command: Command, session: Session) -> PolicyAction:
        """Evaluates policy rules against the command text and session state.

        Args:
            command (Command): The command entity to inspect.
            session (Session): The current session context.

        Returns:
            PolicyAction: The determined enforcement action (AUTO_EXECUTE, REQUIRE_CONFIRMATION, BLOCK).

        Raises:
            CommandBlockedException: If decision is BLOCK and session is in autonomous mode.
        """
        for rule in self._rules:
            if rule.matches(command.text):
                command.risk_level = rule.risk_level

                if rule.action == PolicyAction.BLOCK:
                    if session.is_autonomous:
                        raise CommandBlockedException(
                            command=command.text,
                            reason=f"Blocked by policy rule '{rule.id}' in autonomous mode",
                        )
                    return PolicyAction.BLOCK

                return rule.action

        # Default fallback when no rule pattern explicitly matches
        if command.risk_level is None:
            command.risk_level = RiskLevel.LOW

        return self._default_action
