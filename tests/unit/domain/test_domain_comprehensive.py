"""Comprehensive unit test suite for all Domain entities and edge cases.

Ensures pure domain compliance: zero external dependencies, no network,
no WSL/database interaction, executing well under 1 second.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.domain.entities.command import Command
from src.domain.entities.policy_rule import PolicyRule
from src.domain.entities.session import Session
from src.domain.entities.target import Target
from src.domain.exceptions import (
    CommandBlockedException,
    DomainException,
    TargetNotAuthorizedException,
)
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.policy_action import PolicyAction
from src.domain.value_objects.risk_level import RiskLevel

# ============================================================================
# Command Entity Edge Cases & Properties
# ============================================================================


def test_command_defaults_and_immutability_attributes() -> None:
    """Verifies default values and field assignment for Command."""
    cmd = Command(text="whoami", origin=CommandOrigin.MANUAL_USER)
    assert cmd.text == "whoami"
    assert cmd.origin == CommandOrigin.MANUAL_USER
    assert cmd.target is None
    assert cmd.risk_level is None
    assert isinstance(cmd.timestamp, datetime)
    assert cmd.timestamp.tzinfo is not None


def test_command_whitespace_preservation() -> None:
    """Verifies that command raw formatting is preserved accurately."""
    raw_cmd = "   cat /etc/passwd | grep root   "
    cmd = Command(text=raw_cmd, origin=CommandOrigin.AI)
    assert cmd.text == raw_cmd


# ============================================================================
# Target Entity: Edge Cases, Boundary CIDR & Malformed Inputs
# ============================================================================


@pytest.mark.parametrize(
    "cidr, candidate_ip, expected",
    [
        # /32 single host boundary
        ("192.168.1.50/32", "192.168.1.50", True),
        ("192.168.1.50/32", "192.168.1.51", False),
        # /24 subnet boundaries (network, first host, last host, broadcast, adjacent)
        ("10.10.10.0/24", "10.10.10.0", True),
        ("10.10.10.0/24", "10.10.10.1", True),
        ("10.10.10.0/24", "10.10.10.254", True),
        ("10.10.10.0/24", "10.10.10.255", True),
        ("10.10.10.0/24", "10.10.9.255", False),
        ("10.10.10.0/24", "10.10.11.0", False),
        # /16 broader boundary
        ("172.16.0.0/16", "172.16.255.254", True),
        ("172.16.0.0/16", "172.17.0.1", False),
    ],
)
def test_target_cidr_boundary_edges(cidr: str, candidate_ip: str, expected: bool) -> None:
    """Verifies edge boundaries of CIDR subnets including first, last, and off-by-one IPs."""
    target = Target(value=cidr)
    assert target.contains(candidate_ip) is expected


@pytest.mark.parametrize(
    "malformed_input",
    [
        "",
        "   ",
        "999.999.999.999",
        "10.10.10.256",
        "10.10.10.0/99",
        "http://invalid-url-with-protocol.com",
        "user@domain.com",
        "; rm -rf /",
    ],
)
def test_target_malformed_input_graceful_handling(malformed_input: str) -> None:
    """Verifies that invalid or adversarial inputs safely return False without exceptions."""
    target = Target(value="10.10.10.0/24")
    assert target.contains(malformed_input) is False


def test_target_domain_subdomain_hierarchies() -> None:
    """Verifies precise domain containment and rejects sibling or false prefixes."""
    target = Target(value="hackthebox.com")

    # True subdomains
    assert target.contains("hackthebox.com") is True
    assert target.contains("app.hackthebox.com") is True
    assert target.contains("vpn.lab.hackthebox.com") is True

    # Sibling or lookalike domains that must be rejected
    assert target.contains("fakehackthebox.com") is False
    assert target.contains("hackthebox.com.attacker.com") is False
    assert target.contains("htb.com") is False


# ============================================================================
# Session Entity: Duplicate Rejection & Chronological Ordering
# ============================================================================


def test_session_command_history_and_duplicate_deduplication() -> None:
    """Verifies session retains command history and deduplicates identical submissions."""
    session = Session(user="carlos")
    t0 = datetime(2026, 9, 10, 10, 0, 0, tzinfo=UTC)
    t1 = t0 + timedelta(seconds=10)
    t2 = t0 + timedelta(seconds=20)

    cmd_first = Command(text="ping -c 1 10.10.10.1", origin=CommandOrigin.MANUAL_USER, timestamp=t0)
    cmd_duplicate = Command(
        text="ping -c 1 10.10.10.1", origin=CommandOrigin.MANUAL_USER, timestamp=t0
    )
    cmd_later = Command(text="nmap -sS 10.10.10.1", origin=CommandOrigin.AI, timestamp=t2)
    cmd_middle = Command(text="traceroute 10.10.10.1", origin=CommandOrigin.AI, timestamp=t1)

    # Insert out of order with duplicate
    session.add_command(cmd_later)
    session.add_command(cmd_first)
    session.add_command(cmd_duplicate)  # Must be ignored
    session.add_command(cmd_middle)

    # Verify length and chronological order
    assert len(session.commands) == 3
    assert session.commands[0].text == "ping -c 1 10.10.10.1"
    assert session.commands[1].text == "traceroute 10.10.10.1"
    assert session.commands[2].text == "nmap -sS 10.10.10.1"


def test_session_lifecycle_and_target_association() -> None:
    """Verifies session target binding and termination lifecycle."""
    target1 = Target(value="10.10.10.0/24", description="HTB Lab")
    session = Session(user="carlos", authorized_targets=[target1])

    assert len(session.authorized_targets) == 1
    assert session.authorized_targets[0].value == "10.10.10.0/24"
    assert session.ended_at is None

    session.end_session()
    assert session.ended_at is not None
    assert session.ended_at >= session.started_at


# ============================================================================
# PolicyRule Entity & Pattern Matching
# ============================================================================


@pytest.mark.parametrize(
    "cmd_text, should_match",
    [
        ("rm -rf /etc", True),
        ("sudo rm -rf /home", True),
        ("RM -RF /VAR", True),
        ("rm -rf /tmp", True),
        ("rm -f test.txt", True),
        ("rm test.txt", False),
        ("ls -la /etc", False),
        ("cat /etc/passwd", False),
    ],
)
def test_policy_rule_regex_patterns(cmd_text: str, should_match: bool) -> None:
    """Verifies regex classification of destructive commands."""
    rule = PolicyRule(
        id="rule-rm-rf",
        pattern=r"\brm\s+-[a-zA-Z]*f\b",
        risk_level=RiskLevel.BLOCKED,
        action=PolicyAction.BLOCK,
    )
    assert rule.matches(cmd_text) is should_match


def test_policy_rule_invalid_regex_fallback() -> None:
    """Verifies fallback to substring matching if regex pattern is invalid."""
    rule = PolicyRule(
        id="broken-regex-rule",
        pattern="[invalid(regex",
        risk_level=RiskLevel.HIGH,
        action=PolicyAction.REQUIRE_CONFIRMATION,
    )
    assert rule.matches("prefix [invalid(regex suffix") is True
    assert rule.matches("other command") is False


# ============================================================================
# Domain Exceptions
# ============================================================================


def test_domain_exceptions_are_pure_and_catchable() -> None:
    """Verifies domain exceptions hierarchy and catching under DomainException."""
    with pytest.raises(DomainException) as exc_info:
        raise CommandBlockedException("mkfs.ext4 /dev/sda", reason="Format disk blocked")

    assert isinstance(exc_info.value, CommandBlockedException)
    assert exc_info.value.command == "mkfs.ext4 /dev/sda"

    with pytest.raises(DomainException) as exc_info2:
        raise TargetNotAuthorizedException("8.8.8.8")

    assert isinstance(exc_info2.value, TargetNotAuthorizedException)
    assert exc_info2.value.target == "8.8.8.8"
