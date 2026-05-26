"""PyPI update checker for the MLForge CLI.

Design:
- Check is **read-only** — we never call pip on the user's behalf.
- Synchronous startup nudge reads from a 24h disk cache (~instant, no network).
- Cache is refreshed in a background daemon thread when stale; refresh never
  blocks the foreground command.
- Disabled via `MLFORGE_NO_UPDATE_CHECK=1` or `--no-update-check`.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional

CACHE_DIR = Path.home() / ".mlforge"
CACHE_FILE = CACHE_DIR / ".update-cache.json"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours
PYPI_TIMEOUT_SECONDS = 2.0
PACKAGES = ["ml-forge-cli", "ml-forge-sdk"]


def installed_version(package: str) -> Optional[str]:
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            return version(package)
        except PackageNotFoundError:
            return None
    except Exception:
        return None


def _read_cache() -> Dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {}


def _write_cache(data: Dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _fetch_pypi_latest(package: str, timeout: float = PYPI_TIMEOUT_SECONDS) -> Optional[str]:
    """Fetch the latest published version from PyPI. Returns None on failure."""
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        import urllib.request
        installed = installed_version(package) or "unknown"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"mlforge-cli/{installed} ({sys.platform})",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("info", {}).get("version")
    except Exception:
        return None


def refresh_cache(timeout: float = PYPI_TIMEOUT_SECONDS) -> Dict:
    """Synchronously hit PyPI and rewrite the cache."""
    fresh: Dict = {"checked_at": int(time.time()), "packages": {}}
    for pkg in PACKAGES:
        latest = _fetch_pypi_latest(pkg, timeout=timeout)
        fresh["packages"][pkg] = {
            "installed": installed_version(pkg),
            "latest": latest,
        }
    _write_cache(fresh)
    return fresh


def _is_disabled() -> bool:
    return os.environ.get("MLFORGE_NO_UPDATE_CHECK") in ("1", "true", "yes")


def _refresh_cache_in_background() -> None:
    def _runner():
        try:
            refresh_cache()
        except Exception:
            # Never let the background refresh crash the CLI.
            pass

    t = threading.Thread(target=_runner, daemon=True)
    t.start()


def startup_nudge() -> Optional[str]:
    """Read the cache and return a one-line nudge if an update is available.

    Triggers a non-blocking background refresh when the cache is stale.
    Always safe to call from CLI entry point — never raises, never blocks > a
    file read.
    """
    if _is_disabled():
        return None

    cache = _read_cache()
    checked_at = cache.get("checked_at", 0)
    is_stale = (time.time() - checked_at) > CACHE_TTL_SECONDS

    if is_stale:
        _refresh_cache_in_background()

    pkgs = cache.get("packages", {})
    nudges = []
    for name in PACKAGES:
        info = pkgs.get(name) or {}
        installed = info.get("installed") or installed_version(name)
        latest = info.get("latest")
        if installed and latest and installed != latest:
            nudges.append(
                f"{name}: a newer version ({latest}) is available — "
                f"run `pip install -U {name}` to upgrade"
            )

    if not nudges:
        return None
    return "mlforge: " + "; ".join(nudges)


def status_report() -> Dict:
    """Force a synchronous PyPI check and return the full status dict.

    Used by `mlforge update check`.
    """
    return refresh_cache()
