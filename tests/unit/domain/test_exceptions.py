"""Unit tests verifying domain exception semantics and hierarchy."""

from src.domain.exceptions import (
    CommandBlockedException,
    DomainException,
    InvalidSessionException,
    TargetNotAuthorizedException,
)


def test_domain_exception_hierarchy() -> None:
    """Verifies that all specialized exceptions inherit from DomainException."""
    assert issubclass(CommandBlockedException, DomainException)
    assert issubclass(TargetNotAuthorizedException, DomainException)
    assert issubclass(InvalidSessionException, DomainException)


def test_command_blocked_exception_payload() -> None:
    """Verifies CommandBlockedException message and attribute retention."""
    exc = CommandBlockedException(command="rm -rf /", reason="Dangerous pattern detected")
    assert exc.command == "rm -rf /"
    assert "Dangerous pattern detected: 'rm -rf /'" in str(exc)


def test_target_not_authorized_exception_payload() -> None:
    """Verifies TargetNotAuthorizedException message and attribute retention."""
    exc = TargetNotAuthorizedException(target="192.168.1.1")
    assert exc.target == "192.168.1.1"
    assert "192.168.1.1" in str(exc)


def test_invalid_session_exception_payload() -> None:
    """Verifies InvalidSessionException message and attribute retention."""
    exc = InvalidSessionException(session_id="session-123")
    assert exc.session_id == "session-123"
    assert "session-123" in str(exc)
