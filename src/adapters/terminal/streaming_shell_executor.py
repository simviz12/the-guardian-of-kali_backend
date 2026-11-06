"""Streaming shell session for real-time bidirectional terminal I/O over WSL2.

This adapter spawns a long-lived interactive ``bash`` process inside the target
WSL2 distribution and exposes continuous, non-blocking streaming of stdout/stderr
plus a writable stdin channel. It is consumed by the ``/ws/terminal`` WebSocket
endpoint to give the frontend a live backend-driven terminal in addition to the
Electron node-pty bridge.

Design notes:
    * Pipes (``|``), redirections, environment variables and compound statements
      work because input is fed verbatim to a real ``bash`` session.
    * Exit codes are reported when the session ends.
    * ``bash`` is launched via ``wsl.exe``; a best-effort terminate/kill reaps the
      process on disconnect so no orphaned WSL process is left behind.
    * Full controlling-tty semantics (e.g. Ctrl-C interrupting a foreground job,
      curses UIs) are provided by the Electron node-pty bridge; this channel is a
      robust line/stream oriented transport.
"""

import asyncio
from collections.abc import AsyncIterator


class StreamingShellSession:
    """Manages a single long-lived interactive bash session inside WSL2.

    Attributes:
        _distro (str): Target WSL2 distribution name.
        _user (str): Linux user account to run under.
        _process (asyncio.subprocess.Process | None): The live bash process.
    """

    def __init__(self, distro: str = "kali-linux", user: str = "root") -> None:
        self._distro = distro
        self._user = user
        self._process: asyncio.subprocess.Process | None = None

    @property
    def is_running(self) -> bool:
        """True while the underlying bash process is alive."""
        return self._process is not None and self._process.returncode is None

    async def start(self) -> None:
        """Spawns the interactive bash process inside the WSL2 distribution."""
        self._process = await asyncio.create_subprocess_exec(
            "wsl.exe",
            "-d",
            self._distro,
            "-u",
            self._user,
            "-e",
            "bash",
            "-i",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

    async def write(self, data: str) -> None:
        """Writes operator input (keystrokes / command lines) to the shell stdin."""
        if self._process and self._process.stdin and not self._process.stdin.is_closing():
            self._process.stdin.write(data.encode(errors="replace"))
            await self._process.stdin.drain()

    async def stream_output(self) -> AsyncIterator[str]:
        """Yields decoded chunks of combined stdout/stderr as they arrive in real time."""
        if not self._process or not self._process.stdout:
            return
        while True:
            chunk = await self._process.stdout.read(4096)
            if not chunk:
                break
            yield chunk.decode(errors="replace")

    async def wait(self) -> int:
        """Waits for the shell to exit and returns its exit code."""
        if not self._process:
            return 0
        return await self._process.wait()

    async def close(self) -> None:
        """Terminates and reaps the shell process, escalating to kill if needed."""
        if not self._process or self._process.returncode is not None:
            return
        try:
            if self._process.stdin and not self._process.stdin.is_closing():
                self._process.stdin.close()
            self._process.terminate()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            try:
                self._process.kill()
            except ProcessLookupError:
                return
            await self._process.wait()
