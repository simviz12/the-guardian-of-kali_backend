"""Unit tests for the central command policy validator."""

import logging

import pytest

from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.entities.target import Target
from src.domain.policies.validator import validate_command
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.policy_action import PolicyAction
from src.domain.value_objects.risk_level import RiskLevel


@pytest.fixture
def suggestion_session() -> Session:
    """Fixture returning a session in suggestion mode with authorized target."""
    return Session(
        user="carlos",
        is_autonomous=False,
        authorized_targets=[
            Target(value="10.10.10.10", description="HTB Target"),
            Target(value="192.168.1.0/24", description="Local Lab"),
            Target(value="hackthebox.com", description="HTB Domain"),
        ],
    )


@pytest.fixture
def autonomous_session() -> Session:
    """Fixture returning a session in autonomous mode with authorized target."""
    return Session(
        user="carlos",
        is_autonomous=True,
        authorized_targets=[
            Target(value="10.10.10.10", description="HTB Target"),
            Target(value="192.168.1.0/24", description="Local Lab"),
            Target(value="hackthebox.com", description="HTB Domain"),
        ],
    )


# ============================================================================
# 1. Blacklist and Destructive Command Blocking Tests
# ============================================================================


@pytest.mark.parametrize(
    "destructive_cmd",
    [
        "rm -rf /",
        "rm -r -f /",
        "rm -rf /etc",
        "mkfs.ext4 /dev/sda1",
        "fdisk /dev/sda",
        "dd if=/dev/zero of=/dev/sda",
        "shutdown -h now",
        "reboot",
        "iptables -F",
        "ufw disable",
    ],
)
def test_blacklist_commands_are_strictly_blocked_in_suggestion_mode(
    suggestion_session: Session, destructive_cmd: str
) -> None:
    cmd = Command(text=destructive_cmd, origin=CommandOrigin.AI)
    decision = validate_command(cmd, suggestion_session)

    assert decision.action == PolicyAction.BLOCK
    assert decision.risk_level == RiskLevel.BLOCKED
    assert "Blocked by destructive blacklist rule" in decision.reason
    assert decision.command_text == destructive_cmd
    assert cmd.risk_level == RiskLevel.BLOCKED


@pytest.mark.parametrize(
    "destructive_cmd",
    [
        "rm -rf /",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        "reboot",
        "iptables -F",
    ],
)
def test_blacklist_commands_are_strictly_blocked_in_autonomous_mode(
    autonomous_session: Session, destructive_cmd: str
) -> None:
    cmd = Command(text=destructive_cmd, origin=CommandOrigin.AI)
    decision = validate_command(cmd, autonomous_session)

    assert decision.action == PolicyAction.BLOCK
    assert decision.risk_level == RiskLevel.BLOCKED
    assert "Blocked by destructive blacklist rule" in decision.reason


def test_empty_or_whitespace_command_blocked(suggestion_session: Session) -> None:
    cmd = Command(text="   ", origin=CommandOrigin.MANUAL_USER)
    decision = validate_command(cmd, suggestion_session)

    assert decision.action == PolicyAction.BLOCK
    assert decision.risk_level == RiskLevel.LOW
    assert "Empty or whitespace command" in decision.reason


# ============================================================================
# 2. Target Scope Authorization Tests
# ============================================================================


def test_unauthorized_target_in_command_entity_is_blocked(suggestion_session: Session) -> None:
    cmd = Command(
        text="nmap -sn 8.8.8.8",
        origin=CommandOrigin.AI,
        target="8.8.8.8",
    )
    decision = validate_command(cmd, suggestion_session)

    assert decision.action == PolicyAction.BLOCK
    assert decision.risk_level == RiskLevel.HIGH
    assert "Target '8.8.8.8' is not within authorized session scope" in decision.reason


def test_unauthorized_extracted_ip_is_blocked(suggestion_session: Session) -> None:
    cmd = Command(text="ping -c 4 192.168.2.55", origin=CommandOrigin.AI)
    decision = validate_command(cmd, suggestion_session)

    assert decision.action == PolicyAction.BLOCK
    assert decision.risk_level == RiskLevel.HIGH
    assert "Target '192.168.2.55' is not within authorized session scope" in decision.reason


def test_unauthorized_domain_is_blocked(suggestion_session: Session) -> None:
    cmd = Command(text="whois google.com", origin=CommandOrigin.AI)
    decision = validate_command(cmd, suggestion_session)

    assert decision.action == PolicyAction.BLOCK
    assert decision.risk_level == RiskLevel.HIGH
    assert "Target 'google.com' is not within authorized session scope" in decision.reason


def test_authorized_target_proceeds_to_mode_evaluation(suggestion_session: Session) -> None:
    cmd = Command(
        text="ping -c 4 10.10.10.10",
        origin=CommandOrigin.AI,
        target="10.10.10.10",
    )
    decision = validate_command(cmd, suggestion_session)

    assert decision.action == PolicyAction.AUTO_EXECUTE
    assert decision.risk_level == RiskLevel.LOW
    assert "Suggestion mode: LOW risk command permitted for auto-execution" in decision.reason


# ============================================================================
# 3. Suggestion Mode Tests (is_autonomous=False)
# Everything above LOW requires confirmation; LOW auto-executes.
# ============================================================================


def test_suggestion_mode_low_risk_auto_executes(suggestion_session: Session) -> None:
    cmd = Command(text="whois hackthebox.com", origin=CommandOrigin.AI)
    decision = validate_command(cmd, suggestion_session)

    assert decision.action == PolicyAction.AUTO_EXECUTE
    assert decision.risk_level == RiskLevel.LOW
    assert "Suggestion mode: LOW risk command permitted for auto-execution" in decision.reason


def test_suggestion_mode_medium_risk_requires_confirmation(suggestion_session: Session) -> None:
    cmd = Command(text="nmap -sV -p 80,443 10.10.10.10", origin=CommandOrigin.AI)
    decision = validate_command(cmd, suggestion_session)

    assert decision.action == PolicyAction.REQUIRE_CONFIRMATION
    assert decision.risk_level == RiskLevel.MEDIUM
    assert "Suggestion mode: MEDIUM risk command requires operator confirmation" in decision.reason


def test_suggestion_mode_high_risk_requires_confirmation(suggestion_session: Session) -> None:
    cmd = Command(
        text="sqlmap -u http://10.10.10.10/vuln.php?id=1 --batch", origin=CommandOrigin.AI
    )
    decision = validate_command(cmd, suggestion_session)

    assert decision.action == PolicyAction.REQUIRE_CONFIRMATION
    assert decision.risk_level == RiskLevel.HIGH
    assert "Suggestion mode: HIGH risk command requires operator confirmation" in decision.reason


# ============================================================================
# 4. Autonomous Mode Tests (is_autonomous=True)
# LOW and MEDIUM auto-execute, HIGH always requires confirmation.
# ============================================================================


def test_autonomous_mode_low_risk_auto_executes(autonomous_session: Session) -> None:
    cmd = Command(text="dig hackthebox.com", origin=CommandOrigin.AI)
    decision = validate_command(cmd, autonomous_session)

    assert decision.action == PolicyAction.AUTO_EXECUTE
    assert decision.risk_level == RiskLevel.LOW
    assert "Autonomous mode: LOW risk command permitted for auto-execution" in decision.reason


def test_autonomous_mode_medium_risk_auto_executes(autonomous_session: Session) -> None:
    cmd = Command(text="nmap -sV 10.10.10.10", origin=CommandOrigin.AI)
    decision = validate_command(cmd, autonomous_session)

    assert decision.action == PolicyAction.AUTO_EXECUTE
    assert decision.risk_level == RiskLevel.MEDIUM
    assert "Autonomous mode: MEDIUM risk command permitted for auto-execution" in decision.reason


def test_autonomous_mode_high_risk_always_requires_confirmation(
    autonomous_session: Session,
) -> None:
    cmd = Command(
        text="hydra -l admin -P /usr/share/wordlists/rockyou.txt 10.10.10.10 ssh",
        origin=CommandOrigin.AI,
    )
    decision = validate_command(cmd, autonomous_session)

    assert decision.action == PolicyAction.REQUIRE_CONFIRMATION
    assert decision.risk_level == RiskLevel.HIGH
    assert (
        "Autonomous mode: HIGH risk command strictly requires operator confirmation"
        in decision.reason
    )


# ============================================================================
# 5. Logging and Triggering Reason Verification
# ============================================================================


def test_every_decision_logs_exact_triggering_reason(
    caplog: pytest.LogCaptureFixture, suggestion_session: Session
) -> None:
    caplog.set_level(logging.INFO, logger="guardian.policy_validator")

    cmd = Command(text="whois hackthebox.com", origin=CommandOrigin.AI)
    decision = validate_command(cmd, suggestion_session)

    assert decision.reason != ""
    assert "Suggestion mode: LOW risk command permitted for auto-execution" in decision.reason

    matching_logs = [record for record in caplog.records if decision.reason in record.message]
    assert len(matching_logs) > 0
