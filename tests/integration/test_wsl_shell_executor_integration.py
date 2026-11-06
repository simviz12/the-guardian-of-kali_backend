"""Integration tests for WSLShellExecutor running directly against WSL2 Kali Linux."""

import pytest

from src.adapters.terminal.wsl_shell_executor import WSLShellExecutor
from src.domain.entities.command import Command
from src.domain.value_objects.command_origin import CommandOrigin
from tests.integration._wsl_support import WSL_UNAVAILABLE_REASON, wsl_distro_available

# Skip when wsl.exe is absent OR the target Kali distro is not installed
# (e.g. Linux CI runners, or a Windows box with WSL for Docker but no Kali).
pytestmark = pytest.mark.skipif(
    not wsl_distro_available(),
    reason=WSL_UNAVAILABLE_REASON,
)


@pytest.mark.asyncio
async def test_wsl_shell_executor_runs_as_ia_user() -> None:
    """Integration test verifying command execution runs inside Kali as ia-user."""
    executor = WSLShellExecutor(distro="kali-linux", user="ia-user", timeout_seconds=10.0)
    command = Command(text="whoami", origin=CommandOrigin.AI)

    result = await executor.execute(command)

    assert result.exit_code == 0
    assert result.stdout.strip() == "ia-user"
    assert result.stderr == ""
    assert result.duration_ms > 0.0


@pytest.mark.asyncio
async def test_wsl_shell_executor_enforces_timeout_cleanly() -> None:
    """Integration test verifying a hung command (sleep 100) with a 5-second timeout is cleanly terminated."""
    executor = WSLShellExecutor(distro="kali-linux", user="ia-user", timeout_seconds=5.0)
    command = Command(text="sleep 100", origin=CommandOrigin.AI)

    result = await executor.execute(command)

    # Must be cut off cleanly with standard timeout exit code 124
    assert result.exit_code == 124
    assert "timed out after 5.0 seconds" in result.stderr
    # Execution should take at least 5000 ms (5 seconds) and be terminated without hanging indefinitely
    assert result.duration_ms >= 4500.0


@pytest.mark.asyncio
async def test_wsl_shell_executor_captures_stderr_and_failure_code() -> None:
    """Integration test verifying non-whitelisted sudo or forbidden file access fails cleanly."""
    executor = WSLShellExecutor(distro="kali-linux", user="ia-user", timeout_seconds=10.0)
    command = Command(text="cat /etc/shadow", origin=CommandOrigin.AI)

    result = await executor.execute(command)

    assert result.exit_code != 0
    assert "Permission denied" in result.stderr
