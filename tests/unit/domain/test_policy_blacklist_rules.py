"""Unit tests for policy blacklist regex patterns, default rules, and target authorization validation."""
import pytest

from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.entities.target import Target
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.policy_action import PolicyAction
from src.domain.value_objects.risk_level import RiskLevel
from src.domain.policies.policy_rules import (
    DEFAULT_BLACKLIST_RULES,
    is_target_authorized,
)
from src.application.use_cases.evaluate_policy import EvaluatePolicyUseCase
from src.domain.exceptions import CommandBlockedException


@pytest.fixture
def policy_evaluator() -> EvaluatePolicyUseCase:
    """Fixture providing EvaluatePolicyUseCase armed with default blacklist rules."""
    return EvaluatePolicyUseCase(rules=DEFAULT_BLACKLIST_RULES)


# ============================================================================
# Blacklist Real Command Matching Tests
# ============================================================================

@pytest.mark.parametrize(
    "destructive_cmd",
    [
        "rm -rf /",
        "rm -rf /*",
        "rm -r -f /",
        "rm -rf /etc",
        "rm -rf /var/log",
        "rm --no-preserve-root",
        "mkfs.ext4 /dev/sda1",
        "mkfs -t vfat /dev/sdb",
        "mke2fs /dev/sda",
        "fdisk /dev/sda",
        "parted /dev/sda mklabel gpt",
        "dd if=/dev/zero of=/dev/sda bs=1M",
        "dd if=/dev/urandom of=/dev/nvme0n1",
        "cat /dev/zero > /dev/sda",
        "shutdown -h now",
        "shutdown -r 0",
        "reboot",
        "poweroff",
        "init 0",
        "init 6",
        "iptables -F",
        "iptables --flush",
        "ip6tables -F",
        "ufw disable",
        "ufw reset",
        "nft flush ruleset",
        "sudo nmap --script=default 10.10.10.1",
        "sudo nmap --script /tmp/evil.nse 10.10.10.1",
        "sudo nmap --interactive",
        "sudo su",
        "sudo -i",
        "sudo bash",
        "sudo sh",
    ],
)
def test_blacklist_matches_destructive_commands(policy_evaluator: EvaluatePolicyUseCase, destructive_cmd: str) -> None:
    """Verifies that each known dangerous command matches a blacklist rule with action BLOCK."""
    session = Session(user="carlos", is_autonomous=False)
    cmd = Command(text=destructive_cmd, origin=CommandOrigin.AI)

    action = policy_evaluator.evaluate(command=cmd, session=session)
    assert action == PolicyAction.BLOCK
    assert cmd.risk_level == RiskLevel.BLOCKED


@pytest.mark.parametrize(
    "destructive_cmd",
    [
        "rm -rf /",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        "shutdown now",
        "iptables -F",
    ],
)
def test_blacklist_raises_in_autonomous_mode(policy_evaluator: EvaluatePolicyUseCase, destructive_cmd: str) -> None:
    """Verifies that blocked commands strictly raise CommandBlockedException in autonomous mode."""
    session = Session(user="carlos", is_autonomous=True)
    cmd = Command(text=destructive_cmd, origin=CommandOrigin.AI)

    with pytest.raises(CommandBlockedException) as exc_info:
        policy_evaluator.evaluate(command=cmd, session=session)

    assert destructive_cmd in str(exc_info.value)


@pytest.mark.parametrize(
    "safe_cmd",
    [
        "nmap -sV -p 80,443 10.10.10.15",
        "ping -c 4 127.0.0.1",
        "cat /var/log/syslog",
        "rm temp_file.txt",
        "rm -f scan_results.xml",
        "curl http://10.10.10.20",
        "whoami",
        "ls -la /etc/nginx",
    ],
)
def test_blacklist_does_not_block_legitimate_commands(policy_evaluator: EvaluatePolicyUseCase, safe_cmd: str) -> None:
    """Verifies that legitimate pentesting or inspection commands are NOT falsely flagged as BLOCKED."""
    session = Session(user="carlos", is_autonomous=False)
    cmd = Command(text=safe_cmd, origin=CommandOrigin.AI)

    action = policy_evaluator.evaluate(command=cmd, session=session)
    assert action != PolicyAction.BLOCK
    assert cmd.risk_level != RiskLevel.BLOCKED


# ============================================================================
# Target Authorization Scope Tests
# ============================================================================

def test_is_target_authorized_with_exact_ip() -> None:
    """Verifies target authorization matches identical IP addresses."""
    target = Target(value="10.10.10.50")
    session = Session(user="carlos", authorized_targets=[target])

    assert is_target_authorized("10.10.10.50", session) is True
    assert is_target_authorized("10.10.10.51", session) is False


def test_is_target_authorized_with_cidr_subnet() -> None:
    """Verifies target authorization correctly scopes IP within CIDR subnet."""
    target = Target(value="192.168.1.0/24")
    session = Session(user="carlos", authorized_targets=[target])

    assert is_target_authorized("192.168.1.100", session) is True
    assert is_target_authorized("192.168.2.100", session) is False


def test_is_target_authorized_with_domain() -> None:
    """Verifies target authorization matches domains and subdomains."""
    target = Target(value="hackthebox.com")
    session = Session(user="carlos", authorized_targets=[target])

    assert is_target_authorized("hackthebox.com", session) is True
    assert is_target_authorized("app.hackthebox.com", session) is True
    assert is_target_authorized("google.com", session) is False


def test_is_target_authorized_empty_scope_fails() -> None:
    """Verifies zero implicit trust: empty targets or empty candidates return False."""
    empty_session = Session(user="carlos", authorized_targets=[])
    assert is_target_authorized("10.10.10.5", empty_session) is False

    scoped_session = Session(user="carlos", authorized_targets=[Target(value="10.10.10.0/24")])
    assert is_target_authorized("", scoped_session) is False
    assert is_target_authorized("   ", scoped_session) is False
