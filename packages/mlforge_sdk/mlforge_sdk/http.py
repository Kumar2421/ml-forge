import json
from typing import Any, Optional

import requests


class ApiError(RuntimeError):
    pass


class HttpClient:
    def __init__(self, base_url: str, timeout_s: float = 30.0, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._headers = {"Accept": "application/json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def get(self, path: str, *, params: Optional[dict[str, Any]] = None) -> Any:
        resp = requests.get(self._url(path), params=params, headers=self._headers, timeout=self.timeout_s)
        return self._handle(resp)

    def post(self, path: str, *, json_body: Any = None, params: Optional[dict[str, Any]] = None) -> Any:
        resp = requests.post(self._url(path), json=json_body, params=params, headers=self._headers, timeout=self.timeout_s)
        return self._handle(resp)

    def delete(self, path: str, *, params: Optional[dict[str, Any]] = None) -> Any:
        resp = requests.delete(self._url(path), params=params, headers=self._headers, timeout=self.timeout_s)
        return self._handle(resp)

    @staticmethod
    def _handle(resp: requests.Response) -> Any:
        if resp.status_code == 204:
            return None
        if not resp.ok:
            try:
                payload = resp.json()
                detail = payload.get("detail") if isinstance(payload, dict) else payload
            except Exception:
                detail = resp.text
            raise ApiError(f"API {resp.status_code}: {detail}")
        # some endpoints can return empty bodies
        if not resp.content:
            return None
        ctype = resp.headers.get("content-type", "")
        if "application/json" in ctype:
            return resp.json()
        return resp.text
