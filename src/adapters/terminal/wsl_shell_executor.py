"""Adapter implementing ShellExecutor to run commands inside Kali Linux on WSL2.

Uses a fully non-blocking asyncio subprocess so the FastAPI event loop is never
blocked, with robust timeout handling that cleanly terminates (and, if needed,
kills) hung processes to avoid orphaned/zombie WSL processes.
"""

import asyncio
import time

from src.application.dtos.responses import CommandResult
from src.application.ports.shell_executor import ShellExecutor
from src.domain.entities.command import Command


class WSLShellExecutor(ShellExecutor):
    """Executes terminal commands inside a target WSL2 distribution.

    Attributes:
        _distro (str): Target WSL2 distribution name (defaults to 'kali-linux').
        _user (str): Linux user account to execute under.
        _timeout_seconds (float): Maximum execution duration before the process is
            cleanly terminated to prevent hung or orphaned processes.
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
            user (str): Linux username to run under. Defaults to 'root'.
            timeout_seconds (float): Execution timeout in seconds. Defaults to 180.0.
        """
        self._distro = distro
        self._user = user
        self._timeout_seconds = timeout_seconds

    def _build_args(self, command_text: str) -> list[str]:
        """Builds the wsl.exe argument vector for a bash ``-c`` invocation.

        Running through ``bash -c`` preserves pipes, redirections, environment
        variables and compound statements exactly as the operator typed them.
        """
        return [
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

    async def execute(self, command: Command) -> CommandResult:
        """Executes a command entity inside Kali Linux WSL2.

        Captures stdout, stderr, exit code and execution duration without blocking
        the event loop. Hung processes are cleanly terminated when the timeout is
        reached, and the child is always reaped to avoid zombies.

        Args:
            command (Command): The command entity to execute.

        Returns:
            CommandResult: Standard output, error, exit code and execution time (ms).
        """
        start_time = time.perf_counter()
        args = self._build_args(command.text)

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout_seconds
            )
        except asyncio.TimeoutError:
            await self._terminate(process)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return CommandResult(
                command_text=command.text,
                exit_code=124,  # Standard Linux timeout exit code
                stdout="",
                stderr=(
                    f"Command timed out after {self._timeout_seconds} seconds "
                    "and was cleanly terminated."
                ),
                duration_ms=duration_ms,
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return CommandResult(
            command_text=command.text,
            exit_code=process.returncode if process.returncode is not None else 1,
            stdout=stdout_bytes.decode(errors="replace") if stdout_bytes else "",
            stderr=stderr_bytes.decode(errors="replace") if stderr_bytes else "",
            duration_ms=duration_ms,
        )

    @staticmethod
    async def _terminate(process: asyncio.subprocess.Process) -> None:
        """Gracefully terminates a process, escalating to kill, then reaps it.

        Sends SIGTERM first to allow a clean shutdown; if the process does not exit
        within a short grace period it is forcibly killed. The process is always
        awaited afterwards so no zombie/orphan child is left behind.
        """
        if process.returncode is not None:
            return
        try:
            process.terminate()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                return
            await process.wait()
