"""Initial unit test to verify pytest discovery and environment health."""


def test_environment_health() -> None:
    """Verifies that test runner executes correctly in the clean architecture environment."""
    # Intentional failure to test CI status checks and branch protection gate
    assert False, "Intentional failure: testing GitHub Actions CI blocking mechanism"
