"""Unit tests verifying EvaluatePolicyUseCase rule matching and autonomous mode enforcement."""

import pytest

from src.application.use_cases.evaluate_policy import EvaluatePolicyUseCase
from src.domain.entities.command import Command
from src.domain.entities.policy_rule import PolicyRule
from src.domain.entities.session import Session
from src.domain.exceptions import CommandBlockedException
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.policy_action import PolicyAction
from src.domain.value_objects.risk_level import RiskLevel


def test_evaluate_policy_blocks_in_manual_mode() -> None:
    """Verifies that a BLOCK rule returns PolicyAction.BLOCK for AI commands in manual/suggestion session mode."""
    block_rule = PolicyRule(
        id="block-rm",
        pattern=r"\brm\s+-rf\b",
        risk_level=RiskLevel.BLOCKED,
        action=PolicyAction.BLOCK,
    )
    use_case = EvaluatePolicyUseCase(rules=[block_rule])

    session = Session(user="carlos", is_autonomous=False)
    cmd = Command(text="rm -rf /", origin=CommandOrigin.AI)

    decision = use_case.evaluate(command=cmd, session=session)

    assert decision == PolicyAction.BLOCK
    assert cmd.risk_level == RiskLevel.BLOCKED


def test_evaluate_policy_skips_filter_for_manual_user() -> None:
    """Verifies that commands with origin='MANUAL_USER' skip policy filters (user direct responsibility)."""
    block_rule = PolicyRule(
        id="block-rm",
        pattern=r"\brm\s+-rf\b",
        risk_level=RiskLevel.BLOCKED,
        action=PolicyAction.BLOCK,
    )
    use_case = EvaluatePolicyUseCase(rules=[block_rule])

    session = Session(user="carlos", is_autonomous=False)
    cmd = Command(text="rm -rf /", origin=CommandOrigin.MANUAL_USER)

    decision = use_case.evaluate(command=cmd, session=session)
    rich_decision = use_case.evaluate_decision(command=cmd, session=session)

    assert decision == PolicyAction.AUTO_EXECUTE
    assert rich_decision.action == PolicyAction.AUTO_EXECUTE
    assert "bypassed AI policy gate" in rich_decision.reason


def test_evaluate_policy_raises_exception_in_autonomous_mode() -> None:
    """Verifies that a BLOCK decision raises CommandBlockedException when session is autonomous."""
    block_rule = PolicyRule(
        id="block-shadow",
        pattern=r"cat\s+/etc/shadow",
        risk_level=RiskLevel.BLOCKED,
        action=PolicyAction.BLOCK,
    )
    use_case = EvaluatePolicyUseCase(rules=[block_rule])

    session = Session(user="carlos", is_autonomous=True)
    cmd = Command(text="cat /etc/shadow", origin=CommandOrigin.AI)

    with pytest.raises(CommandBlockedException) as exc_info:
        use_case.evaluate(command=cmd, session=session)

    assert "cat /etc/shadow" in str(exc_info.value)
    assert "block-shadow" in exc_info.value.reason


def test_evaluate_policy_require_confirmation() -> None:
    """Verifies that intermediate risk commands yield REQUIRE_CONFIRMATION."""
    rule = PolicyRule(
        id="nmap-agg",
        pattern=r"nmap\s+.*-A",
        risk_level=RiskLevel.MEDIUM,
        action=PolicyAction.REQUIRE_CONFIRMATION,
    )
    use_case = EvaluatePolicyUseCase(rules=[rule])

    session = Session(user="carlos", is_autonomous=True)
    cmd = Command(text="nmap -A 10.10.10.1", origin=CommandOrigin.AI)

    decision = use_case.evaluate(command=cmd, session=session)

    assert decision == PolicyAction.REQUIRE_CONFIRMATION
    assert cmd.risk_level == RiskLevel.MEDIUM


def test_evaluate_policy_auto_execute_safe_command() -> None:
    """Verifies safe commands return AUTO_EXECUTE."""
    rule = PolicyRule(
        id="safe-ping",
        pattern=r"^ping\b",
        risk_level=RiskLevel.LOW,
        action=PolicyAction.AUTO_EXECUTE,
    )
    use_case = EvaluatePolicyUseCase(rules=[rule])

    session = Session(user="carlos", is_autonomous=True)
    cmd = Command(text="ping -c 1 127.0.0.1", origin=CommandOrigin.AI)

    decision = use_case.evaluate(command=cmd, session=session)

    assert decision == PolicyAction.AUTO_EXECUTE
    assert cmd.risk_level == RiskLevel.LOW
