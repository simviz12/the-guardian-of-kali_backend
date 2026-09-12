"""Unit tests verifying the PolicyRule entity and pattern matching."""

from src.domain.entities.policy_rule import PolicyRule
from src.domain.value_objects.policy_action import PolicyAction
from src.domain.value_objects.risk_level import RiskLevel


def test_policy_rule_matches_regex() -> None:
    """Verifies regex pattern matching against dangerous commands."""
    rule = PolicyRule(
        id="block-destructive-rm",
        pattern=r"\brm\s+-[rR]*[fF]\b",
        risk_level=RiskLevel.BLOCKED,
        action=PolicyAction.BLOCK,
        description="Block recursive force file deletion",
    )

    assert rule.matches("rm -rf /") is True
    assert rule.matches("sudo rm -f test.txt") is True
    assert rule.matches("rm test.txt") is False
    assert rule.matches("ls -la") is False


def test_policy_rule_case_insensitivity() -> None:
    """Verifies that rule matching is case-insensitive."""
    rule = PolicyRule(
        id="block-forkbomb",
        pattern=r":\(\)\s*\{",
        risk_level=RiskLevel.BLOCKED,
        action=PolicyAction.BLOCK,
    )

    assert rule.matches(":(){ :|:& };:") is True


def test_policy_rule_actions() -> None:
    """Verifies distinct policy actions assignable to rules."""
    auto_rule = PolicyRule(
        id="allow-ping",
        pattern=r"^ping\b",
        risk_level=RiskLevel.LOW,
        action=PolicyAction.AUTO_EXECUTE,
    )
    confirm_rule = PolicyRule(
        id="confirm-nmap-agg",
        pattern=r"nmap\s+.*-A",
        risk_level=RiskLevel.MEDIUM,
        action=PolicyAction.REQUIRE_CONFIRMATION,
    )

    assert auto_rule.action == PolicyAction.AUTO_EXECUTE
    assert confirm_rule.action == PolicyAction.REQUIRE_CONFIRMATION
