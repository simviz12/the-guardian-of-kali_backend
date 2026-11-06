"""Unit tests for the WSLShellExecutor adapter (asyncio subprocess based)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.terminal.wsl_shell_executor import WSLShellExecutor
from src.application.ports.shell_executor import ShellExecutor
from src.domain.entities.command import Command
from src.domain.value_objects.command_origin import CommandOrigin


def _make_process(returncode: int, stdout: bytes, stderr: bytes) -> MagicMock:
    """Builds a mock asyncio subprocess whose ``communicate`` returns the given output."""
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(return_value=(stdout, stderr))
    process.wait = AsyncMock(return_value=returncode)
    process.terminate = MagicMock()
    process.kill = MagicMock()
    return process


def test_wsl_shell_executor_implements_interface() -> None:
    """Ensure WSLShellExecutor implements the ShellExecutor port."""
    executor = WSLShellExecutor()
    assert isinstance(executor, ShellExecutor)


@pytest.mark.asyncio
async def test_execute_successful_command() -> None:
    """Test successful command execution capturing stdout and exit code 0."""
    executor = WSLShellExecutor(distro="kali-linux", user="ia-user", timeout_seconds=10.0)
    command = Command(text="whoami", origin=CommandOrigin.AI)

    mock_process = _make_process(0, b"ia-user\n", b"")

    with patch(
        "asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)
    ) as mock_exec:
        result = await executor.execute(command)

        mock_exec.assert_called_once_with(
            "wsl.exe",
            "-d",
            "kali-linux",
            "-u",
            "ia-user",
            "-e",
            "bash",
            "-c",
            "whoami",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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

    mock_process = _make_process(1, b"", b"cat: /etc/shadow: Permission denied\n")

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
        result = await executor.execute(command)

        assert result.command_text == "cat /etc/shadow"
        assert result.exit_code == 1
        assert result.stdout == ""
        assert "Permission denied" in result.stderr


@pytest.mark.asyncio
async def test_execute_command_timeout_clean_termination() -> None:
    """Test a hung command: communicate() times out → exit code 124 and clean termination."""
    executor = WSLShellExecutor(timeout_seconds=2.0)
    command = Command(text="sleep 100", origin=CommandOrigin.AI)

    mock_process = _make_process(0, b"", b"")
    # communicate never returns normally: it raises TimeoutError (via wait_for).
    mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    # After terminate(), the process reports it has exited.
    mock_process.returncode = None

    def _mark_terminated() -> None:
        mock_process.returncode = 143

    mock_process.terminate = MagicMock(side_effect=_mark_terminated)

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
        result = await executor.execute(command)

        assert result.command_text == "sleep 100"
        assert result.exit_code == 124
        assert "timed out after 2.0 seconds" in result.stderr
        assert result.duration_ms >= 0.0
        mock_process.terminate.assert_called_once()
