"""Helpers to decide whether WSL2 integration tests can run on the current host.

Integration tests in this package execute real commands inside the Kali Linux
WSL2 distribution. They must be skipped not only when ``wsl.exe`` is absent
(e.g. Linux CI runners) but also when the target distro is not installed
(e.g. a Windows dev box that has WSL for Docker Desktop but no Kali), otherwise
``wsl.exe`` returns an error for a missing distro and the assertions fail for
environmental reasons unrelated to the code under test.
"""

import os
import shutil
import subprocess

TARGET_DISTRO = os.environ.get("WSL_DISTRO", "kali-linux")


def _installed_distros() -> list[str]:
    """Returns the list of installed WSL distributions (lower-cased), or []."""
    wsl = shutil.which("wsl.exe")
    if wsl is None:
        return []
    try:
        # wsl -l -q prints one distro name per line; output is UTF-16 on Windows.
        raw = subprocess.run(
            [wsl, "-l", "-q"],
            capture_output=True,
            timeout=15,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    text = raw.decode("utf-16-le", errors="ignore") if b"\x00" in raw else raw.decode(errors="ignore")
    return [line.strip().lower() for line in text.splitlines() if line.strip()]


TARGET_USER = "ia-user"


def _user_exists() -> bool:
    """True when the restricted Linux account the tests run as exists in the distro."""
    try:
        return (
            subprocess.run(
                ["wsl.exe", "-d", TARGET_DISTRO, "-u", TARGET_USER, "-e", "true"],
                capture_output=True,
                timeout=30,
                check=False,
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        return False


def wsl_distro_available() -> bool:
    """True only when the target distro is installed and has the test account.

    The app itself enters Kali as root; these tests additionally exercise a
    restricted ``ia-user`` account, which a default Kali install does not have.
    Create it with: ``wsl -d kali-linux -u root useradd -m ia-user``.
    """
    return TARGET_DISTRO.lower() in _installed_distros() and _user_exists()


WSL_UNAVAILABLE_REASON = (
    f"WSL2 distro '{TARGET_DISTRO}' with the '{TARGET_USER}' account is not available "
    "on this host (wsl.exe missing, distro not installed, or account not created)."
)
