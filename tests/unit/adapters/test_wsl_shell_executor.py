"""Unit tests for the WSLShellExecutor adapter."""
import subprocess
from unittest.mock import MagicMock, patch
import pytest

from src.domain.entities.command import Command
from src.domain.value_objects.command_origin import CommandOrigin
from src.adapters.terminal.wsl_shell_executor import WSLShellExecutor
from src.application.ports.shell_executor import ShellExecutor


def test_wsl_shell_executor_implements_interface() -> None:
    """Ensure WSLShellExecutor implements the ShellExecutor port."""
    executor = WSLShellExecutor()
    assert isinstance(executor, ShellExecutor)


@pytest.mark.asyncio
async def test_execute_successful_command() -> None:
    """Test successful command execution capturing stdout and exit code 0."""
    executor = WSLShellExecutor(distro="kali-linux", user="ia-user", timeout_seconds=10.0)
    command = Command(text="whoami", origin=CommandOrigin.AI)

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = "ia-user\n"
    mock_process.stderr = ""

    with patch("subprocess.run", return_value=mock_process) as mock_run:
        result = await executor.execute(command)

        mock_run.assert_called_once_with(
            ["wsl.exe", "-d", "kali-linux", "-u", "ia-user", "-e", "bash", "-c", "whoami"],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )

        assert result.command_text == "whoami"
        assert result.exit_code == 0
        assert result.stdout == "ia-user\n"
        assert result.stderr == ""
        assert result.duration_ms >= 0.0


@pytest.mark.asyncio
async def test_execute_command_with_stderr_and_non_zero_exit_code() -> None:
    """Test command execution returning non-zero returncode and stderr output."""
    executor = WSLShellExecutor()
    command = Command(text="cat /etc/shadow", origin=CommandOrigin.AI)

    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout = ""
    mock_process.stderr = "cat: /etc/shadow: Permission denied\n"

    with patch("subprocess.run", return_value=mock_process):
        result = await executor.execute(command)

        assert result.command_text == "cat /etc/shadow"
        assert result.exit_code == 1
        assert result.stdout == ""
        assert "Permission denied" in result.stderr


@pytest.mark.asyncio
async def test_execute_command_timeout_clean_termination() -> None:
    """Test hung command execution triggering TimeoutExpired and resulting in exit code 124."""
    executor = WSLShellExecutor(timeout_seconds=2.0)
    command = Command(text="sleep 100", origin=CommandOrigin.AI)

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["wsl.exe"], timeout=2.0)):
        result = await executor.execute(command)

        assert result.command_text == "sleep 100"
        assert result.exit_code == 124
        assert "timed out after 2.0 seconds" in result.stderr
        assert result.duration_ms >= 0.0
