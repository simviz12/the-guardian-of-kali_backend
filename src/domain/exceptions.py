"""Domain exceptions representing business and security policy violation conditions."""


class DomainException(Exception):
    """Base exception for all domain-specific errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CommandBlockedException(DomainException):
    """Raised when a command violates safety policy or blacklist rules."""

    def __init__(
        self, command: str, reason: str = "Command execution blocked by security policy"
    ) -> None:
        super().__init__(f"{reason}: '{command}'")
        self.command = command
        self.reason = reason


class TargetNotAuthorizedException(DomainException):
    """Raised when an operation targets an unauthorized host, IP, or network range."""

    def __init__(
        self, target: str, reason: str = "Target is not within authorized session scope"
    ) -> None:
        super().__init__(f"{reason}: '{target}'")
        self.target = target
        self.reason = reason


class InvalidSessionException(DomainException):
    """Raised when an operation is performed on an inactive, missing, or closed session."""

    def __init__(self, session_id: str, reason: str = "Session is invalid or closed") -> None:
        super().__init__(f"{reason}: '{session_id}'")
        self.session_id = session_id
        self.reason = reason
