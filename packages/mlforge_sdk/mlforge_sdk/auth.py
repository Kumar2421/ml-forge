import json
import os
import time
import webbrowser
from pathlib import Path
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from threading import Event, Thread


def _credentials_path() -> Path:
    """Get the path to the credentials file."""
    return Path.home() / ".mlforge" / "credentials.json"


def load_token() -> Optional[str]:
    """Load auth token from env var or local credentials file."""
    # Priority 1: Environment variables
    token = os.getenv("MLFORGE_HF_TOKEN") or os.getenv("HF_TOKEN") or os.getenv("MLFORGE_TOKEN")
    if token:
        return token.strip()

    # Priority 2: Credentials file
    path = _credentials_path()
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Support both old (hf_token) and new (accessToken) format
        token = data.get("accessToken") or data.get("hf_token")
        return token.strip() if isinstance(token, str) and token.strip() else None
    except Exception:
        return None


def save_token(token: str) -> None:
    """Save token to credentials file."""
    token = token.strip()
    if not token:
        raise ValueError("Token is empty")

    path = _credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Store in new format with expiration
    token_data = {
        "accessToken": token,
        "expiresAt": int(time.time()) + 24 * 60 * 60,  # 24 hours
    }
    path.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
    path.chmod(0o600)  # Restrict permissions for security


def delete_token() -> None:
    """Remove token from storage."""
    path = _credentials_path()
    try:
        if path.exists():
            path.unlink()
    except OSError:
        # File already gone or permission issue - that's fine
        pass


class AuthClient:
    """
    Cross-platform OAuth authentication client for MLForge SDK.
    Handles OAuth flow with browser redirect and callback server.
    """

    def __init__(
        self,
        oauth_base_url: str = "https://mlforge.in/auth",
        default_port: int = 3333,
        callback_timeout: float = 30.0,
        client_id: str = "mlforge-sdk-default",
    ):
        """
        Initialize AuthClient.

        Args:
            oauth_base_url: Base URL for OAuth provider
            default_port: Starting port for callback server (will try +1, +2 if busy)
            callback_timeout: Timeout in seconds for OAuth callback
            client_id: OAuth client ID
        """
        self.oauth_base_url = oauth_base_url
        self.default_port = default_port
        self.callback_timeout = callback_timeout
        self.client_id = client_id
        self._callback_event: Optional[Event] = None
        self._callback_token: Optional[str] = None
        self._callback_error: Optional[str] = None
        self._server: Optional[HTTPServer] = None
        self._server_thread: Optional[Thread] = None

    async def login(self) -> str:
        """
        Initiate OAuth login flow.
        Opens browser → mlforge.in/auth → callback with token → stores locally

        Returns:
            The OAuth token

        Raises:
            RuntimeError: If login times out or fails
        """
        port = await self._find_available_port(self.default_port)
        callback_url = f"http://localhost:{port}/callback"

        # Start callback server
        self._start_callback_server(port)

        # Build auth URL
        auth_url = f"{self.oauth_base_url}?client_id={self.client_id}&callback={callback_url}&response_type=token"

        # Open browser
        try:
            webbrowser.open(auth_url)
        except Exception as e:
            self._stop_callback_server()
            raise RuntimeError(f"Failed to open browser: {e}")

        # Wait for callback with timeout
        try:
            if not self._callback_event.wait(timeout=self.callback_timeout):
                raise RuntimeError(f"OAuth callback timeout ({self.callback_timeout}s)")
        except Exception as e:
            self._stop_callback_server()
            raise RuntimeError(f"OAuth login failed: {e}")
        finally:
            self._stop_callback_server()

        if self._callback_error:
            raise RuntimeError(f"OAuth error: {self._callback_error}")

        if not self._callback_token:
            raise RuntimeError("OAuth callback missing token")

        # Store token
        token = self._callback_token
        save_token(token)

        return token

    async def get_stored_token(self) -> Optional[str]:
        """Get stored token from credentials file."""
        return load_token()

    async def logout(self) -> None:
        """Remove token from storage."""
        delete_token()

    async def has_token(self) -> bool:
        """Check if token exists and is valid."""
        token = await self.get_stored_token()
        return token is not None and len(token) > 0

    def _start_callback_server(self, port: int) -> None:
        """Start HTTP callback server to receive OAuth token."""
        self._callback_event = Event()
        self._callback_token = None
        self._callback_error = None

        handler = self._create_handler()

        try:
            self._server = HTTPServer(("127.0.0.1", port), handler)
        except OSError as e:
            raise RuntimeError(f"Failed to start callback server on port {port}: {e}")

        self._server_thread = Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()

    def _stop_callback_server(self) -> None:
        """Stop the callback server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=1.0)
            self._server_thread = None

    def _create_handler(self):
        """Create request handler for OAuth callback."""
        auth_client = self

        class OAuthCallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                """Handle GET request from OAuth redirect."""
                try:
                    # Parse URL and query parameters
                    parsed_url = urlparse(self.path)
                    params = parse_qs(parsed_url.query)

                    # Check for error
                    if "error" in params:
                        auth_client._callback_error = params["error"][0]
                        self.send_response(400)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(b"""
                            <html>
                            <head><title>Authentication Failed</title></head>
                            <body style='font-family:sans-serif; background:#0f172a; color:#ef4444;
                                         display:flex; flex-direction:column; align-items:center;
                                         justify-content:center; height:100vh;'>
                                <h1>Authentication Failed</h1>
                                <p>Error: """ + auth_client._callback_error.encode() + b"""</p>
                                <p>You can close this window.</p>
                            </body>
                            </html>
                        """)
                        auth_client._callback_event.set()
                        return

                    # Check for token
                    if "token" not in params:
                        auth_client._callback_error = "Missing token parameter"
                        self.send_response(400)
                        self.send_header("Content-Type", "text/plain")
                        self.end_headers()
                        self.wfile.write(b"Missing token parameter")
                        auth_client._callback_event.set()
                        return

                    # Success - save token
                    auth_client._callback_token = params["token"][0]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"""
                        <html>
                        <head><title>Authentication Successful</title></head>
                        <body style='font-family:sans-serif; background:#0f172a; color:white;
                                     display:flex; flex-direction:column; align-items:center;
                                     justify-content:center; height:100vh;'>
                            <h1 style='color:#10b981;'>Authentication Successful!</h1>
                            <p>You can now close this window and return to your terminal.</p>
                            <script>setTimeout(() => window.close(), 2000);</script>
                        </body>
                        </html>
                    """)
                    auth_client._callback_event.set()

                except Exception as e:
                    auth_client._callback_error = str(e)
                    self.send_response(500)
                    self.end_headers()
                    auth_client._callback_event.set()

            def log_message(self, format, *args):
                """Suppress server log messages."""
                return

        return OAuthCallbackHandler

    @staticmethod
    async def _find_available_port(start_port: int, max_attempts: int = 3) -> int:
        """
        Find an available port starting from start_port.
        Tries start_port, start_port+1, start_port+2, etc.

        Args:
            start_port: Initial port to try
            max_attempts: Maximum ports to try before giving up

        Returns:
            Available port number

        Raises:
            RuntimeError: If no port available after max_attempts
        """
        import socket

        for attempt in range(max_attempts):
            port = start_port + attempt
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                result = sock.connect_ex(("127.0.0.1", port))
                sock.close()

                if result != 0:  # Port is available
                    return port
            except Exception:
                pass

        raise RuntimeError(f"No available ports found from {start_port} to {start_port + max_attempts - 1}")
