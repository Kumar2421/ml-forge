# OAuth Login & 402 Quota Error Handling Implementation

Complete implementation of cross-platform OAuth authentication for MLForge SDKs and 402 (Payment Required) error handling across all client libraries.

## Overview

This implementation adds:
1. **Cross-platform OAuth login** for Python SDK with callback server
2. **402 Payment Required handling** in both Python and JavaScript SDKs
3. **User-friendly quota error messages** in CLI
4. **Production-ready error handling** with edge case coverage

## Part 1: Python SDK OAuth (`mlforge_sdk/auth.py`)

### AuthClient Class

**Features:**
- Async OAuth flow with browser redirect
- Callback server listening on localhost with port fallback (3333→3334→3335)
- Token storage in `~/.mlforge/credentials.json` with expiration tracking
- Graceful ENOENT handling for missing credentials
- 30-second timeout for OAuth callback
- Environment variable support (MLFORGE_TOKEN, MLFORGE_HF_TOKEN, HF_TOKEN)

**Key Methods:**

```python
class AuthClient:
    async def login() -> str:
        """Start OAuth flow, return token, store to file"""
        
    async def get_stored_token() -> Optional[str]:
        """Load token from credentials file or env vars"""
        
    async def logout() -> None:
        """Remove token from storage"""
        
    async def has_token() -> bool:
        """Check if valid token exists"""
```

**Callback Server:**
- Uses http.server.HTTPServer with threading
- Listens on `http://localhost:{port}/callback`
- Parses OAuth redirect with token parameter
- Returns HTML success/error page
- Auto-closes server after callback or timeout
- Handles missing token and error parameters gracefully

**Token Storage:**
```json
{
  "accessToken": "token-value",
  "expiresAt": 1717332800
}
```
- Uses 0o600 permissions (owner-read-only)
- Maintains backward compatibility with old `hf_token` format
- Tracks 24-hour expiration

**Error Handling:**
- Port conflicts → Try next available port (max 3 attempts)
- Timeout → RuntimeError with clear message
- Browser open failure → Handled with try/catch
- Missing callback parameters → 400 response + error message
- Token file corruption → Returns None (graceful degradation)

### Integration with MLForge Factory

```python
class MLForge:
    def __init__(self, ...):
        self.auth = AuthClient()
        # ... rest of init
    
    async def login(self) -> str:
        """Perform OAuth login and update HTTP headers"""
        token = await self.auth.login()
        self.http._headers["Authorization"] = f"Bearer {token}"
        return token
    
    async def logout(self) -> None:
        """Logout and remove authorization"""
        await self.auth.logout()
        if "Authorization" in self.http._headers:
            del self.http._headers["Authorization"]
    
    async def initAuth(self) -> None:
        """Load stored token on init/reload"""
        token = await self.auth.get_stored_token()
        if token:
            self.http._headers["Authorization"] = f"Bearer {token}"
```

## Part 2: 402 Error Handling

### Python SDK (`mlforge_sdk/http.py`)

**Enhanced ApiError:**
```python
class ApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        status: int = 0,
        payload: Optional[dict[str, Any]] = None,
    ):
        self.status = status
        self.payload = payload or {}
```

**402 Detection & Response:**
```python
if resp.status_code == 402:
    msg = "Limit exceeded"
    if payload and isinstance(payload, dict):
        resource = payload.get("resource", "unknown")
        used = payload.get("used", "?")
        limit = payload.get("limit", "?")
        msg = f"Limit exceeded: {resource} ({used}/{limit})"
    
    raise ApiError(msg, status=402, payload=payload)
```

**Expected 402 Response Format:**
```json
{
  "resource": "training_runs",
  "used": 5,
  "limit": 3,
  "upgrade_url": "https://mlforge.in/upgrade"
}
```

### JavaScript SDK (`mlforge_js_sdk/src/http.ts`)

**402 Handling in _fetch:**
```typescript
if (res.status === 402) {
  let message = "Limit exceeded";
  if (body && typeof body === "object") {
    const payload = body as Record<string, unknown>;
    const resource = payload.resource || "unknown";
    const used = payload.used || "?";
    const limit = payload.limit || "?";
    message = `Limit exceeded: ${resource} (${used}/${limit})`;
  }
  throw new ApiError(res.status, message, body);
}
```

**Features:**
- Parses both JSON and plain text error bodies
- Extracts quota details (resource, used, limit)
- Includes upgrade_url in error body
- Falls back to generic message if payload missing

## Part 3: CLI Error Handling (`mlforge_cli/main.py`)

**Enhanced `_handle_api_error` function:**

```python
def _handle_api_error(e: Exception):
    # ... connection error handling ...
    
    if isinstance(e, ApiError):
        if e.status == 402:
            console.print("\n[bold red]Limit exceeded[/bold red]")
            
            if e.payload and isinstance(e.payload, dict):
                resource = e.payload.get("resource", "unknown")
                used = e.payload.get("used", "?")
                limit = e.payload.get("limit", "?")
                console.print(f"[error]{resource}: {used}/{limit}[/error]")
                console.print("[yellow]You've reached your free tier limit[/yellow]")
                
                upgrade_url = e.payload.get("upgrade_url")
                if upgrade_url:
                    console.print(f"[info]Upgrade to Pro: {upgrade_url}[/info]")
                else:
                    console.print("[info]Upgrade to Pro: https://mlforge.in/upgrade[/info]")
            
            raise typer.Exit(code=1)
        
        # Other API errors...
        console.print(f"\n[bold red]API Error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)
```

**User-Facing Output:**
```
[bold red]Limit exceeded[/bold red]
[error]training_runs: 5/3[/error]
[yellow]You've reached your free tier limit[/yellow]
[info]Upgrade to Pro: https://mlforge.in/upgrade[/info]
```

## Usage Examples

### Python SDK

```python
from mlforge_sdk import MLForge

# Initialize
mlforge = MLForge()

# Option 1: OAuth Login
try:
    token = await mlforge.login()  # Opens browser → mlforge.in/auth
    print(f"Logged in! Token: {token}")
except RuntimeError as e:
    print(f"Login failed: {e}")

# Option 2: Manual token
mlforge.http._headers["Authorization"] = "Bearer my-token"

# Option 3: Environment variable
import os
os.environ["MLFORGE_TOKEN"] = "my-token"
mlforge = MLForge()

# Auto-load stored token
await mlforge.initAuth()

# Logout
await mlforge.logout()

# Check if token exists
if await mlforge.auth.has_token():
    print("You are logged in")
```

### JavaScript SDK

```typescript
import { MLForge } from "mlforge";

const mlforge = new MLForge();

// Option 1: OAuth Login (Node.js)
try {
  const token = await mlforge.auth.login();
  console.log(`Logged in! Token: ${token}`);
} catch (e) {
  console.error(`Login failed: ${e.message}`);
}

// Option 2: Manual token
const mlforge = new MLForge({ token: "my-token" });

// Check if token exists
if (await mlforge.auth.hasToken()) {
  console.log("You are logged in");
}

// Logout
await mlforge.auth.logout();
```

### CLI

```bash
# OAuth login (opens browser)
mlforge login

# Manual token
mlforge login --token "my-token"

# Logout
mlforge logout

# Use CLI (will auto-load stored token)
mlforge models list
```

## Error Handling Examples

### 402 Quota Exceeded

**Python:**
```python
try:
    mlforge.train.create(...)
except ApiError as e:
    if e.status == 402:
        print(f"Quota exceeded: {e.payload['resource']}")
        print(f"Used: {e.payload['used']}/{e.payload['limit']}")
        print(f"Upgrade: {e.payload['upgrade_url']}")
```

**JavaScript:**
```typescript
try {
  await mlforge.train.create(...);
} catch (e) {
  if (e instanceof ApiError && e.status === 402) {
    console.error(`Quota exceeded: ${e.body?.resource}`);
    console.error(`Used: ${e.body?.used}/${e.body?.limit}`);
  }
}
```

**CLI:**
```
[bold red]Limit exceeded[/bold red]
[error]training_runs: 2/2[/error]
[yellow]You've reached your free tier limit[/yellow]
[info]Upgrade to Pro: https://mlforge.in/upgrade[/info]
```

## Testing

### Run Python Tests

```bash
# All tests
cd packages/mlforge_sdk
python -m pytest tests/test_auth.py tests/test_402_errors.py -v

# Token storage tests
python -m pytest tests/test_auth.py::TestTokenStorage -v

# OAuth callback tests
python -m pytest tests/test_auth.py::TestAuthClientCallback -v

# 402 error handling tests
python -m pytest tests/test_402_errors.py::TestQuotaExceededHandling -v
```

### Run JavaScript Tests

```bash
cd packages/mlforge_js_sdk
npm test -- src/__tests__/http.test.ts
```

## Security Considerations

1. **Token Storage:** Uses 0o600 file permissions (owner-read-only)
2. **Environment Variables:** Prioritized before file storage for flexibility
3. **HTTPS:** OAuth endpoints should always use HTTPS in production
4. **Callback Validation:** Validates OAuth callback parameters
5. **Error Messages:** Don't leak internal error details to users
6. **Timeout:** 30-second timeout prevents hanging callback servers

## Edge Cases Handled

✅ Port conflicts (tries up to 3 alternate ports)
✅ Missing credentials file (returns None gracefully)
✅ Corrupted JSON file (returns None gracefully)
✅ Browser open failure (catches exception, user can visit URL manually)
✅ Timeout on OAuth callback (raises RuntimeError with message)
✅ Missing token in callback (returns 400 error)
✅ OAuth error parameter (returns 400 error with error details)
✅ 402 response without JSON payload (uses generic message)
✅ Token expiration tracking (24-hour window)
✅ Cross-platform support (browser detection, file paths, etc.)

## Files Modified

### Python SDK
- `packages/mlforge_sdk/mlforge_sdk/auth.py` - Complete OAuth implementation
- `packages/mlforge_sdk/mlforge_sdk/__init__.py` - MLForge factory integration
- `packages/mlforge_sdk/mlforge_sdk/http.py` - 402 error handling
- `packages/mlforge_sdk/tests/test_auth.py` - OAuth tests (new)
- `packages/mlforge_sdk/tests/test_402_errors.py` - 402 tests (new)

### JavaScript SDK
- `packages/mlforge_js_sdk/src/http.ts` - 402 error handling
- `packages/mlforge_js_sdk/src/__tests__/http.test.ts` - 402 tests (new)

### CLI
- `packages/mlforge_cli/mlforge_cli/main.py` - 402 error handling

## Next Steps

1. Configure OAuth provider (mlforge.in/auth):
   - Set callback URL: `http://localhost:{port}/callback`
   - Provide client ID to SDK users

2. Backend 402 responses should include:
   ```json
   {
     "resource": "training_runs",
     "used": 5,
     "limit": 3,
     "upgrade_url": "https://mlforge.in/upgrade"
   }
   ```

3. Update SDK documentation with login/logout examples

4. Add to CI/CD pipeline for regression testing
