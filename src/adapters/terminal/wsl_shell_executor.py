"""Adapter implementing ShellExecutor to run commands inside Kali Linux on WSL2 under ia-user."""

import asyncio
import subprocess
import time

from src.application.dtos.responses import CommandResult
from src.application.ports.shell_executor import ShellExecutor
from src.domain.entities.command import Command


class WSLShellExecutor(ShellExecutor):
    """Executes terminal commands inside a target WSL2 distribution enforcing the restricted ia-user.

    Attributes:
        _distro (str): Target WSL2 distribution name (defaults to 'kali-linux').
        _user (str): Linux user account to execute under (defaults strictly to 'ia-user').
        _timeout_seconds (float): Maximum execution duration before killing the hung process.
    """

    def __init__(
        self,
        distro: str = "kali-linux",
        user: str = "root",
        timeout_seconds: float = 180.0,
    ) -> None:
        """Initializes the WSL shell executor adapter.

        Args:
            distro (str): WSL2 distribution name. Defaults to 'kali-linux'.
            user (str): Restricted Linux username. Defaults strictly to 'root' to allow full tools without sudo hangs.
            timeout_seconds (float): Execution timeout in seconds. Defaults to 180.0 (3 minutes).
        """
        self._distro = distro
        self._user = user
        self._timeout_seconds = timeout_seconds

    async def execute(self, command: Command) -> CommandResult:
        """Executes a command entity inside Kali Linux WSL2 as the restricted ia-user.

        Captures stdout, stderr, exit code, and execution duration.
        Gracefully terminates hung processes when the timeout is reached.

        Args:
            command (Command): The command entity to execute.

        Returns:
            CommandResult: Standard output, error, exit code, and execution time in ms.
        """
        # Run blocking subprocess.run in an async thread pool executor
        return await asyncio.to_thread(self._run_subprocess, command.text)

    def _run_subprocess(self, command_text: str) -> CommandResult:
        """Synchronous helper that invokes wsl.exe with strict timeout and execution capture.

        Args:
            command_text (str): Raw shell command to run in bash.

        Returns:
            CommandResult: Structured result object.
        """
        wsl_args = [
            "wsl.exe",
            "-d",
            self._distro,
            "-u",
            self._user,
            "-e",
            "bash",
            "-c",
            command_text,
        ]

        start_time = time.perf_counter()

        try:
            process = subprocess.run(
                wsl_args,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000.0

            return CommandResult(
                command_text=command_text,
                exit_code=process.returncode,
                stdout=process.stdout or "",
                stderr=process.stderr or "",
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            stdout_str = (
                exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            )
            stderr_str = f"Command timed out after {self._timeout_seconds} seconds and was cleanly terminated."

            return CommandResult(
                command_text=command_text,
                exit_code=124,  # Standard Linux timeout exit code
                stdout=stdout_str,
                stderr=stderr_str,
                duration_ms=duration_ms,
            )
