"""Use case for evaluating security policies against candidate commands."""
from typing import List, Optional

from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.entities.policy_rule import PolicyRule
from src.domain.policies.validator import validate_command
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.policy_action import PolicyAction
from src.domain.value_objects.policy_decision import PolicyDecision
from src.domain.value_objects.risk_level import RiskLevel
from src.domain.exceptions import CommandBlockedException


class EvaluatePolicyUseCase:
    """Evaluates safety and risk policies against a candidate command within a session context.

    This use case acts as the mandatory decision gate before commands reach execution.
    - Commands with origin='MANUAL_USER' skip this filter, as they are the direct
      responsibility of the human operator.
    - Commands with origin='AI' are strictly validated using the central policy validator
      (blacklist check, target authorization scope, and risk classification).
    - In autonomous mode or when blocked, appropriate enforcement actions/exceptions are triggered.

    Attributes:
        _rules (List[PolicyRule]): Injected ordered list of additional security rules to evaluate.
        _default_action (PolicyAction): Fallback action when no specific rule matches.
    """

    def __init__(
        self,
        rules: Optional[List[PolicyRule]] = None,
        default_action: PolicyAction = PolicyAction.REQUIRE_CONFIRMATION,
    ) -> None:
        """Initializes the policy evaluation use case.

        Args:
            rules (Optional[List[PolicyRule]]): List of custom policy rules. Defaults to empty list.
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
        decision = self.evaluate_decision(command=command, session=session)

        if decision.action == PolicyAction.BLOCK:
            if session.is_autonomous:
                raise CommandBlockedException(
                    command=command.text,
                    reason=decision.reason,
                )
            return PolicyAction.BLOCK

        return decision.action

    def evaluate_decision(self, command: Command, session: Session) -> PolicyDecision:
        """Performs full evaluation returning the rich PolicyDecision object.

        Commands originated by MANUAL_USER bypass the policy filter.
        Commands originated by AI must strictly pass through validation.

        Args:
            command (Command): The command entity to inspect.
            session (Session): The current session context.

        Returns:
            PolicyDecision: The structured policy evaluation result.
        """
        # Manual user commands bypass AI policy enforcement (direct user responsibility)
        if command.origin == CommandOrigin.MANUAL_USER:
            if command.risk_level is None:
                command.risk_level = RiskLevel.LOW
            return PolicyDecision(
                action=PolicyAction.AUTO_EXECUTE,
                risk_level=command.risk_level,
                reason="Manual operator command: bypassed AI policy gate under direct user responsibility",
                command_text=command.text,
            )

        # If specific custom rules were injected, evaluate them first
        if self._rules:
            for rule in self._rules:
                if rule.matches(command.text):
                    command.risk_level = rule.risk_level
                    return PolicyDecision(
                        action=rule.action,
                        risk_level=rule.risk_level,
                        reason=f"Matched custom policy rule '{rule.id}': {rule.description or ''}".strip(),
                        command_text=command.text,
                    )


        # Wire into central policy validator (Blacklist, Target Authorization, Risk Classifier)
        decision = validate_command(command, session)
        return decision

