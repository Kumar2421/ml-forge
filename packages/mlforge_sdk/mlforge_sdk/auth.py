import json
import os
from pathlib import Path
from typing import Optional


def _credentials_path() -> Path:
    return Path.home() / ".mlforge" / "credentials.json"


def load_token() -> Optional[str]:
    """Load auth token from env var or local credentials file."""
    token = os.getenv("MLFORGE_HF_TOKEN") or os.getenv("HF_TOKEN")
    if token:
        return token.strip()

    path = _credentials_path()
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        token = data.get("hf_token")
        return token.strip() if isinstance(token, str) and token.strip() else None
    except Exception:
        return None


def save_token(token: str) -> None:
    token = token.strip()
    if not token:
        raise ValueError("Token is empty")

    path = _credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"hf_token": token}, indent=2), encoding="utf-8")


def delete_token() -> None:
    path = _credentials_path()
    if path.exists():
        path.unlink()
