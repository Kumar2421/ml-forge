import json
from typing import Any, Optional

import requests


class ApiError(RuntimeError):
    """
    MLForge API error with structured error information.

    Attributes:
        status: HTTP status code
        message: Error message
        payload: Response payload (if available)
    """

    def __init__(
        self,
        message: str,
        status: int = 0,
        payload: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}

    def __str__(self) -> str:
        if self.status:
            return f"API {self.status}: {super().__str__()}"
        return super().__str__()


class HttpClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 30.0,
        token: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._headers = {"Accept": "application/json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        if api_key:
            self._headers["x-api-key"] = api_key

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def get(self, path: str, *, params: Optional[dict[str, Any]] = None) -> Any:
        resp = requests.get(
            self._url(path),
            params=params,
            headers=self._headers,
            timeout=self.timeout_s,
        )
        return self._handle(resp)

    def post(
        self,
        path: str,
        *,
        json_body: Any = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        resp = requests.post(
            self._url(path),
            json=json_body,
            params=params,
            headers=self._headers,
            timeout=self.timeout_s,
        )
        return self._handle(resp)

    def delete(self, path: str, *, params: Optional[dict[str, Any]] = None) -> Any:
        resp = requests.delete(
            self._url(path),
            params=params,
            headers=self._headers,
            timeout=self.timeout_s,
        )
        return self._handle(resp)

    @staticmethod
    def _handle(resp: requests.Response) -> Any:
        if resp.status_code == 204:
            return None

        if not resp.ok:
            payload = None
            detail = resp.text

            # Try to parse JSON payload
            try:
                payload = resp.json()
                if isinstance(payload, dict):
                    detail = payload.get("detail", detail)
            except Exception:
                pass

            # Handle 402 Payment Required (quota exceeded)
            if resp.status_code == 402:
                msg = "Limit exceeded"
                if payload and isinstance(payload, dict):
                    resource = payload.get("resource", "unknown")
                    used = payload.get("used", "?")
                    limit = payload.get("limit", "?")
                    msg = f"Limit exceeded: {resource} ({used}/{limit})"

                raise ApiError(msg, status=402, payload=payload)

            # All other errors
            raise ApiError(detail, status=resp.status_code, payload=payload)

        # some endpoints can return empty bodies
        if not resp.content:
            return None

        ctype = resp.headers.get("content-type", "")
        if "application/json" in ctype:
            return resp.json()
        return resp.text
