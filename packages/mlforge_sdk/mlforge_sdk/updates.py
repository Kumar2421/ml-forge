"""PyPI update check helper for the MLForge SDK.

This is a programmatic, opt-in helper for users embedding the SDK in their own
tools. It mirrors the behavior of the CLI's `updates` module (read-only,
never modifies the user's environment).

Usage:
    from mlforge_sdk.updates import check_for_updates
    info = check_for_updates("ml-forge-sdk")
    if info and info["update_available"]:
        print(f"Update available: {info['latest']}")
"""

from __future__ import annotations

import json
import sys
from typing import Dict, Optional

DEFAULT_TIMEOUT_SECONDS = 2.0


def _installed_version(package: str) -> Optional[str]:
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            return version(package)
        except PackageNotFoundError:
            return None
    except Exception:
        return None


def _pypi_latest(package: str, timeout: float) -> Optional[str]:
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        import urllib.request
        installed = _installed_version(package) or "unknown"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"mlforge-sdk/{installed} ({sys.platform})",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("info", {}).get("version")
    except Exception:
        return None


def check_for_updates(
    package: str = "ml-forge-sdk",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[Dict[str, object]]:
    """Query PyPI for the latest version of a package.

    Returns a dict ``{package, installed, latest, update_available}`` or
    ``None`` if the check could not be completed (offline, rate-limited, etc).
    """
    latest = _pypi_latest(package, timeout=timeout)
    if latest is None:
        return None
    installed = _installed_version(package)
    return {
        "package": package,
        "installed": installed,
        "latest": latest,
        "update_available": bool(installed and installed != latest),
    }
