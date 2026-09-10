"""Unit tests verifying the Target entity and its IP/domain containment logic."""
from src.domain.entities.target import Target


def test_target_single_ip_contains() -> None:
    """Verifies containment for a single IP address target."""
    target = Target(value="192.168.1.100", description="Primary lab host")

    assert target.contains("192.168.1.100") is True
    assert target.contains("192.168.1.101") is False
    assert target.contains("10.0.0.1") is False


def test_target_cidr_range_contains() -> None:
    """Verifies containment for a CIDR network range target."""
    target = Target(value="10.10.10.0/24", description="HackTheBox subnet")

    # Inside subnet
    assert target.contains("10.10.10.1") is True
    assert target.contains("10.10.10.150") is True
    assert target.contains("10.10.10.254") is True

    # Outside subnet
    assert target.contains("10.10.11.1") is False
    assert target.contains("192.168.1.1") is False


def test_target_domain_contains() -> None:
    """Verifies containment for exact domain and subdomain targets."""
    target = Target(value="hackthebox.com", description="HTB target scope")

    assert target.contains("hackthebox.com") is True
    assert target.contains("academy.hackthebox.com") is True
    assert target.contains("lab.ctf.hackthebox.com") is True

    assert target.contains("tryhackme.com") is False
    assert target.contains("not-hackthebox.com") is False


def test_target_invalid_input_resilience() -> None:
    """Verifies that malformed inputs do not raise unhandled exceptions."""
    target = Target(value="10.10.10.0/24")

    assert target.contains("invalid-ip-string") is False
    assert target.contains("") is False
