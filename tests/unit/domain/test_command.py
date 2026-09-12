"""Unit tests verifying the Command entity and RiskLevel value object."""

from datetime import datetime

from src.domain.entities.command import Command
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.risk_level import RiskLevel


def test_command_creation_with_defaults() -> None:
    """Verifies that a Command entity is created with correct defaults and fields."""
    cmd = Command(text="nmap -sV 192.168.1.1", origin=CommandOrigin.AI)

    assert cmd.text == "nmap -sV 192.168.1.1"
    assert cmd.origin == CommandOrigin.AI
    assert cmd.target is None
    assert cmd.risk_level is None
    assert isinstance(cmd.timestamp, datetime)


def test_command_with_explicit_target_and_risk_level() -> None:
    """Verifies assigning target scope and risk levels to a Command entity."""
    cmd = Command(
        text="ping -c 4 10.10.10.1",
        origin=CommandOrigin.MANUAL_USER,
        target="10.10.10.1",
        risk_level=RiskLevel.LOW,
    )

    assert cmd.origin == CommandOrigin.MANUAL_USER
    assert cmd.target == "10.10.10.1"
    assert cmd.risk_level == RiskLevel.LOW


def test_risk_level_values() -> None:
    """Verifies that all required risk levels are properly defined."""
    assert RiskLevel.LOW.value == "LOW"
    assert RiskLevel.MEDIUM.value == "MEDIUM"
    assert RiskLevel.HIGH.value == "HIGH"
    assert RiskLevel.BLOCKED.value == "BLOCKED"
