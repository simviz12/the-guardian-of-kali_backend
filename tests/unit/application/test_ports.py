"""Unit tests verifying application port abstractions and DTOs."""
import pytest
from src.application.dtos import AIResponse, CommandResult
from src.application.ports import AIGateway, ShellExecutor, SessionRepository


def test_dtos_initialization() -> None:
    """Verifies that application DTOs hold accurate fields."""
    ai_resp = AIResponse(content="Nmap scan completed", suggested_command="nmap -sn 10.10.10.1")
    assert ai_resp.content == "Nmap scan completed"
    assert ai_resp.suggested_command == "nmap -sn 10.10.10.1"

    cmd_res = CommandResult(
        command_text="ping 127.0.0.1",
        exit_code=0,
        stdout="64 bytes from 127.0.0.1",
        stderr="",
        duration_ms=45.2,
    )
    assert cmd_res.exit_code == 0
    assert cmd_res.duration_ms == 45.2


def test_abstract_ports_cannot_be_instantiated_directly() -> None:
    """Verifies that abstract ports enforce ABC implementation."""
    with pytest.raises(TypeError):
        AIGateway()  # type: ignore

    with pytest.raises(TypeError):
        ShellExecutor()  # type: ignore

    with pytest.raises(TypeError):
        SessionRepository()  # type: ignore
