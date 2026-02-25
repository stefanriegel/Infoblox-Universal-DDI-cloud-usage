"""Platform preflight checks for the cloud usage estimator.

Detects platform, Python version, ANSI terminal capability, Windows
long-path support, PowerShell execution policy, and cloud CLI presence.
Called at CLI startup to warn users about potential issues before any
scan work begins.

Never blocks execution except for Python < 3.10 which is a hard requirement.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys


def _check_long_path_registry() -> bool:
    """Check Windows registry for LongPathsEnabled setting.

    Returns:
        True if long path support is enabled, False otherwise.
        Always returns True on non-Windows platforms.
    """
    if sys.platform != "win32":
        return True
    try:
        import winreg  # type: ignore[import]

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
        )
        value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
        winreg.CloseKey(key)
        return bool(value)
    except OSError:
        return False


def _check_execution_policy() -> str | None:
    """Check PowerShell ExecutionPolicy on Windows.

    Returns:
        Policy string (e.g., "RemoteSigned") on Windows, or None on
        non-Windows or if the check fails for any reason.
    """
    if sys.platform != "win32":
        return None
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Get-ExecutionPolicy"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def _check_ansi() -> bool:
    """Check if the terminal supports ANSI escape codes.

    On Windows, requires both a TTY and a known ANSI-capable terminal
    (Windows Terminal via WT_SESSION, or TERM environment variable).
    On other platforms, a TTY is sufficient.

    Returns:
        True if ANSI output is supported, False otherwise.
    """
    if sys.platform == "win32":
        return sys.stderr.isatty() and bool(
            os.environ.get("WT_SESSION") or os.environ.get("TERM")
        )
    return sys.stderr.isatty()


def check_platform() -> dict:
    """Gather platform and environment information.

    Returns a dict with the following keys:
        python_ok (bool): True if Python 3.10+ is running.
        python_version (str): Formatted version string (e.g., "3.11.4").
        system (str): OS name — "Windows", "Darwin", or "Linux".
        is_wsl (bool): True if running inside WSL.
        long_path_enabled (bool): True if Windows long-path support is on.
        execution_policy (str | None): PowerShell policy or None.
        ansi_capable (bool): True if terminal supports ANSI colors.
        cli_aws (bool): True if the aws CLI is on PATH.
        cli_az (bool): True if the az CLI is on PATH.
        cli_gcloud (bool): True if the gcloud CLI is on PATH.

    Returns:
        Dict with platform detection results.
    """
    version_info = sys.version_info
    python_version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"

    system = platform.system()  # "Windows", "Darwin", "Linux"
    is_wsl = sys.platform == "linux" and "microsoft" in platform.release().lower()

    return {
        "python_ok": version_info >= (3, 10),
        "python_version": python_version,
        "system": system,
        "is_wsl": is_wsl,
        "long_path_enabled": _check_long_path_registry(),
        "execution_policy": _check_execution_policy(),
        "ansi_capable": _check_ansi(),
        "cli_aws": shutil.which("aws") is not None,
        "cli_az": shutil.which("az") is not None,
        "cli_gcloud": shutil.which("gcloud") is not None,
    }


def print_preflight_warnings(results: dict) -> None:
    """Print platform warnings and a summary line to stderr.

    The only hard stop is Python < 3.10 — all other checks produce
    warnings that never block execution.

    Args:
        results: Dict returned by check_platform().
    """
    if not results["python_ok"]:
        sys.stderr.write(
            f"Python 3.10+ required (found {results['python_version']})\n"
        )
        return

    system = results["system"]
    version = results["python_version"]
    is_wsl = results["is_wsl"]

    # Windows-specific warnings
    if system == "Windows":
        if not results["long_path_enabled"]:
            sys.stderr.write(
                "[WARN] Windows long path support is disabled. Enable:\n"
                "       New-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet"
                "\\Control\\FileSystem' -Name 'LongPathsEnabled' -Value 1 "
                "-PropertyType DWORD -Force\n"
            )

        policy = results.get("execution_policy")
        if policy in ("Restricted", "Undefined"):
            sys.stderr.write(
                f"[WARN] PowerShell ExecutionPolicy is '{policy}'. "
                "Set-ExecutionPolicy RemoteSigned -Scope CurrentUser\n"
            )

        if not results["ansi_capable"]:
            sys.stderr.write(
                "[WARN] Terminal does not support ANSI colors -- "
                "output may contain escape codes\n"
            )

    # Summary line
    wsl_tag = " (WSL)" if is_wsl else ""
    cli_aws = "yes" if results["cli_aws"] else "no"
    cli_az = "yes" if results["cli_az"] else "no"
    cli_gcloud = "yes" if results["cli_gcloud"] else "no"
    sys.stderr.write(
        f"Platform: {system}{wsl_tag} | Python {version} | "
        f"CLIs: aws={cli_aws}, az={cli_az}, gcloud={cli_gcloud}\n"
    )
