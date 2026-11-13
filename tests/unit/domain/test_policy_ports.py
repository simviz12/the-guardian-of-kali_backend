"""Unit tests for the allowed-ports check of the policy validator."""

import pytest

from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.entities.target import Target
from src.domain.policies.validator import parse_port_ranges, validate_command
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.policy_action import PolicyAction


def _decide(command_text: str, ports: str) -> PolicyAction:
    session = Session(
        user="tester",
        authorized_targets=[Target(value="10.10.10.10")],
        allowed_ports=parse_port_ranges(ports),
    )
    return validate_command(Command(text=command_text, origin=CommandOrigin.AI), session).action


def test_parse_port_ranges_accepts_lists_and_ranges_and_ignores_junk() -> None:
    assert parse_port_ranges("80, 443 8080-8090") == [(80, 80), (443, 443), (8080, 8090)]
    assert parse_port_ranges("abc, 0, 70000, 90-80, ") == []


@pytest.mark.parametrize(
    "command_text",
    [
        "nmap -p 22 10.10.10.10",
        "nmap -p- 10.10.10.10",
        "nmap -p1-1000 10.10.10.10",
        "nmap --ports=80,22 10.10.10.10",
        "curl http://10.10.10.10:9000/",
    ],
)
def test_ports_outside_the_allowed_list_are_blocked(command_text: str) -> None:
    assert _decide(command_text, "80, 443, 8000-8100") == PolicyAction.BLOCK


@pytest.mark.parametrize(
    "command_text",
    [
        "nmap -sV -p 80,443 10.10.10.10",
        "nmap -p 8000-8050 10.10.10.10",
        "curl http://10.10.10.10:8080/",
        "whois 10.10.10.10",
    ],
)
def test_allowed_or_unspecified_ports_are_not_blocked(command_text: str) -> None:
    assert _decide(command_text, "80, 443, 8000-8100") != PolicyAction.BLOCK


def test_no_port_restriction_when_the_session_defines_none() -> None:
    assert _decide("nmap -p 22 10.10.10.10", "") != PolicyAction.BLOCK
