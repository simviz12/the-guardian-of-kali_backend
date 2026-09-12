"""Value object representing the resulting action of a policy evaluation."""

from enum import Enum


class PolicyAction(str, Enum):
    """Action that must be taken based on policy evaluation."""

    AUTO_EXECUTE = "AUTO_EXECUTE"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    BLOCK = "BLOCK"
