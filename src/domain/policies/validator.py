"""Central policy validator combining blacklist verification, target authorization, and risk classification."""
import logging
import re
from typing import Optional

from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.policies.policy_rules import (
    DEFAULT_BLACKLIST_RULES,
    is_target_authorized,
)
from src.domain.policies.risk_classifier import classify_command_risk
from src.domain.value_objects.policy_action import PolicyAction
from src.domain.value_objects.policy_decision import PolicyDecision
from src.domain.value_objects.risk_level import RiskLevel

logger = logging.getLogger("guardian.policy_validator")

# Regex to heuristically capture explicit IPv4 addresses or domains in commands
IPV4_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b")
DOMAIN_REGEX = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+(?:com|org|net|edu|io|local|lab|htb|thm)\b",
    re.IGNORECASE,
)


def _extract_command_target(command_text: str) -> Optional[str]:
    """Heuristically extracts the first target IP or domain found within command arguments."""
    # Look for explicit IPv4 or CIDR first
    ip_match = IPV4_REGEX.search(command_text)
    if ip_match:
        return ip_match.group(0)

    # Look for explicit domain next
    domain_match = DOMAIN_REGEX.search(command_text)
    if domain_match:
        return domain_match.group(0)

    return None


def validate_command(command: Command, session: Session) -> PolicyDecision:
    """Evaluates a candidate command against safety policies, scope authorization, and risk classification.

    Evaluation steps:
    1. Blacklist check: Destructive/irreversible commands are blocked immediately.
    2. Target authorization: Targets targeted by the command must be explicitly authorized.
    3. Risk classification: Categorizes command risk into LOW, MEDIUM, or HIGH.
    4. Execution mode policy enforcement:
       - Suggestion mode (is_autonomous=False): Everything above LOW requires confirmation.
         LOW auto-executes.
       - Autonomous mode (is_autonomous=True): LOW and MEDIUM auto-execute.
         HIGH always requires confirmation even in autonomous mode.
    5. Audit log: Emits an audit log entry with the exact triggering reason.

    Args:
        command (Command): The candidate command entity to validate.
        session (Session): The active session context containing authorized targets and mode.

    Returns:
        PolicyDecision: The structured decision with action, risk level, triggering reason, and command text.
    """
    cmd_text = command.text.strip()
    if not cmd_text:
        reason = "Empty or whitespace command text provided"
        logger.warning("Policy validation rejected empty command: %s", reason)
        return PolicyDecision(
            action=PolicyAction.BLOCK,
            risk_level=RiskLevel.LOW,
            reason=reason,
            command_text=cmd_text,
        )

    # 1. Blacklist check: Destructive and irreversible operations
    for rule in DEFAULT_BLACKLIST_RULES:
        if rule.matches(cmd_text):
            reason = f"Blocked by destructive blacklist rule '{rule.id}': {rule.description}"
            command.risk_level = RiskLevel.BLOCKED
            logger.warning("Policy decision: BLOCK command '%s' - Reason: %s", cmd_text, reason)
            return PolicyDecision(
                action=PolicyAction.BLOCK,
                risk_level=RiskLevel.BLOCKED,
                reason=reason,
                command_text=cmd_text,
            )

    # 2. Target authorization check
    # If the session has defined authorized targets, enforce zero-trust boundary
    if session.authorized_targets:
        target_to_check = command.target or _extract_command_target(cmd_text)
        if target_to_check and not is_target_authorized(target_to_check, session):
            reason = (
                f"Target '{target_to_check}' is not within authorized session scope "
                f"({len(session.authorized_targets)} authorized targets defined)"
            )
            command.risk_level = RiskLevel.HIGH
            logger.warning("Policy decision: BLOCK command '%s' - Reason: %s", cmd_text, reason)
            return PolicyDecision(
                action=PolicyAction.BLOCK,
                risk_level=RiskLevel.HIGH,
                reason=reason,
                command_text=cmd_text,
            )

    # 3. Risk classification
    risk = classify_command_risk(cmd_text)
    command.risk_level = risk

    # 4. Mode-based enforcement decision
    if session.is_autonomous:
        # Autonomous mode: LOW and MEDIUM auto-execute, HIGH always requires confirmation
        if risk == RiskLevel.HIGH:
            action = PolicyAction.REQUIRE_CONFIRMATION
            reason = "Autonomous mode: HIGH risk command strictly requires operator confirmation"
        elif risk in (RiskLevel.LOW, RiskLevel.MEDIUM):
            action = PolicyAction.AUTO_EXECUTE
            reason = f"Autonomous mode: {risk.value} risk command permitted for auto-execution"
        else:
            action = PolicyAction.BLOCK
            reason = f"Autonomous mode: command assessed with unexpected risk level '{risk}'"
    else:
        # Suggestion mode: Everything above LOW requires confirmation (MEDIUM and HIGH require confirmation, LOW auto-executes)
        if risk == RiskLevel.LOW:
            action = PolicyAction.AUTO_EXECUTE
            reason = "Suggestion mode: LOW risk command permitted for auto-execution"
        else:
            action = PolicyAction.REQUIRE_CONFIRMATION
            reason = f"Suggestion mode: {risk.value} risk command requires operator confirmation"

    logger.info("Policy decision: %s for command '%s' (Risk: %s) - Reason: %s", action.value, cmd_text, risk.value, reason)

    return PolicyDecision(
        action=action,
        risk_level=risk,
        reason=reason,
        command_text=cmd_text,
    )
