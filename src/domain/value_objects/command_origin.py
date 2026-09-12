"""Value object representing the origin source of a command."""

from enum import Enum


class CommandOrigin(str, Enum):
    """Enumeration of origins from which a command was initiated."""

    MANUAL_USER = "MANUAL_USER"
    AI = "AI"
