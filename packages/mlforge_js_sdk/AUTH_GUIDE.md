# MLForge SDK OAuth Authentication Guide

The MLForge SDK now includes built-in cross-platform OAuth authentication that works seamlessly in both Node.js and browser environments.

## Quick Start

### Node.js (Desktop/Server)

```typescript
import { MLForge } from "@mlforge/sdk";

// Create client
const forge = new MLForge();

// Initialize and load stored token (if available)
await forge.initAuth();

// Check if already authenticated
if (forge.isAuthenticated()) {
  console.log("Already logged in!");
} else {
  // Start OAuth flow (opens browser)
  const token = await forge.login();
  console.log("Logged in! Token stored at ~/.mlforge/credentials.json");
}

// Use SDK normally
const models = await forge.models.list();
console.log(models);

// Logout
await forge.logout();
```

### Browser (Web App)

```typescript
import { MLForge } from "@mlforge/sdk";

const forge = new MLForge();

// Initialize with stored token if available
await forge.initAuth();

if (!forge.isAuthenticated()) {
  // Show login button
  document.getElementById("loginBtn").onclick = async () => {
    const token = await forge.login();
    console.log("Logged in with token:", token);
    // Token is stored in localStorage automatically
  };
}

// Use SDK
const datasets = await forge.datasets.list();
```

## Features

### Automatic Storage
- **Node.js**: Token stored at `~/.mlforge/credentials.json` with expiration metadata
- **Browser**: Token stored in `localStorage` with key `mlforge_token`

### OAuth Flow
1. Starts local callback server (Node.js only, port 3333 or next available)
2. Opens browser to MLForge OAuth page (`mlforge.in/auth`)
3. User authorizes the application
4. Callback returns token to local server
5. Token automatically saved to appropriate storage
6. Server shuts down after callback

### Graceful Error Handling
- **ENOENT**: Missing credentials file returns `null` (no error)
- **Port in use**: Automatically tries next port (3333 → 3334 → 3335, etc.)
- **Callback timeout**: 30-second timeout (configurable)
- **Browser environment**: Falls back to `window.postMessage` for cross-tab communication

### Automatic Expiration
- Node.js: Tokens expire after 24 hours (configurable)
- Browser: No expiration enforcement (relies on server)
- `getStoredToken()` returns `null` if token expired

## API Reference

### Constructor Options

```typescript
interface MLForgeOptions & AuthOptions {
  // HTTP Client Options
  baseUrl?: string;                    // Default: http://127.0.0.1:8005
  timeout?: number;                    // Default: 30_000ms
  token?: string;                      // Pre-load token

  // OAuth Options
  clientId?: string;                   // Default: "mlforge-sdk-default"
  oauthBaseUrl?: string;               // Default: "https://mlforge.in/auth"
  defaultPort?: number;                // Default: 3333
  callbackTimeout?: number;            // Default: 30_000ms
}

const forge = new MLForge({
  baseUrl: "http://localhost:8005",
  defaultPort: 4000,
  callbackTimeout: 60_000
});
```

### Methods

#### `initAuth(): Promise<void>`
Load stored token from storage and authenticate automatically.

```typescript
await forge.initAuth();
```

#### `login(): Promise<string>`
Start OAuth flow. Opens browser, waits for callback, stores token.

```typescript
const token = await forge.login();
```

#### `logout(): Promise<void>`
Remove token from storage and clear authentication.

```typescript
await forge.logout();
```

#### `authenticate(token: string): void`
Manually set authentication token.

```typescript
forge.authenticate("your-jwt-token");
```

#### `isAuthenticated(): boolean`
Check if currently authenticated.

```typescript
if (forge.isAuthenticated()) {
  // Make API calls
}
```

#### `hasStoredToken(): Promise<boolean>`
Check if a stored token exists (without requiring full initialization).

```typescript
const hasToken = await forge.hasStoredToken();
```

#### `clearAuth(): void`
Clear current authentication token (does NOT remove from storage).

```typescript
forge.clearAuth();
```

#### `getAuthClient(): AuthClient`
Get the underlying `AuthClient` for advanced use cases.

```typescript
const auth = forge.getAuthClient();
const token = await auth.getStoredToken();
```

## Advanced Usage

### Custom OAuth Configuration

```typescript
const forge = new MLForge({
  clientId: "my-custom-client-id",
  oauthBaseUrl: "https://custom.oauth.server/auth",
  defaultPort: 5000,
  callbackTimeout: 60_000 // 60 seconds
});
```

### Direct AuthClient Usage

```typescript
import { AuthClient } from "@mlforge/sdk";

const auth = new AuthClient({
  clientId: "my-app",
  defaultPort: 3333
});

// Login
const token = await auth.login();

// Check stored token
const storedToken = await auth.getStoredToken();

// Logout
await auth.logout();

// Check if token exists
const hasToken = await auth.hasToken();
```

### Error Handling

```typescript
try {
  const token = await forge.login();
} catch (error) {
  if (error.message.includes("timeout")) {
    console.error("User took too long to authorize");
  } else if (error.message.includes("port")) {
    console.error("All callback ports are in use");
  } else if (error.message.includes("OAuth error")) {
    console.error("OAuth server returned error:", error.message);
  } else {
    console.error("Unexpected error:", error);
  }
}
```

### Token Expiration Handling

```typescript
// In Node.js, check token expiration
const storedToken = await forge.getAuthClient().getStoredToken();

if (!storedToken) {
  // Token expired or not found
  const newToken = await forge.login();
}
```

## Storage Details

### Node.js (~/.mlforge/credentials.json)

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refreshToken": "optional-refresh-token",
  "expiresAt": 1719878400000
}
```

### Browser (localStorage)

Key: `mlforge_token`
Value: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

## Security Considerations

1. **Token Storage**: Tokens are stored in accessible locations:
   - Node.js: File with restricted permissions (user-only by default)
   - Browser: localStorage (accessible to any JS on the same origin)

2. **HTTPS**: Always use HTTPS in production for OAuth flows

3. **Origin Validation**: Browser flow validates origin before accepting tokens (for cross-tab communication)

4. **Token Expiration**: Server should validate token expiration; client checks on load

5. **Logout**: Always call `logout()` before closing the application

## Browser Compatibility

- **Storage**: Requires `localStorage` support (all modern browsers)
- **OAuth**: Requires ability to open popup windows
- **Fallback**: Uses `window.postMessage` for cross-tab token delivery

## Troubleshooting

### "Port already in use" Error
The SDK automatically tries the next port (3334, 3335, etc.). If you see this persistently:
- Check what's using port 3333: `lsof -i :3333` (macOS/Linux) or `netstat -ano | findstr :3333` (Windows)
- Specify a custom port: `new MLForge({ defaultPort: 5000 })`

### "Token timeout" Error
User took longer than 30 seconds to authorize:
- Increase timeout: `new MLForge({ callbackTimeout: 60_000 })`
- Check network connectivity
- Verify OAuth server is responding

### "OAuth error" Message
Check the MLForge OAuth server logs and ensure:
- Client ID is correct
- Redirect URI matches configured callback URL
- OAuth server is accessible

### No Token Stored
If `getStoredToken()` returns `null`:
- **Node.js**: Check `~/.mlforge/credentials.json` exists and is readable
- **Browser**: Check `localStorage` via browser DevTools
- **Token Expired**: Node.js tokens expire after 24 hours

## Examples

### Complete Node.js CLI App

```typescript
import { MLForge } from "@mlforge/sdk";

async function main() {
  const forge = new MLForge();
  
  // Try to restore previous session
  await forge.initAuth();
  
  if (!forge.isAuthenticated()) {
    console.log("Initiating login...");
    await forge.login();
    console.log("Login successful!");
  }
  
  // Fetch and display models
  const models = await forge.models.list();
  console.log("Available models:", models);
  
  // Clean up
  process.on("SIGINT", async () => {
    await forge.logout();
    process.exit(0);
  });
}

main().catch(console.error);
```

### React Component

```typescript
import { MLForge } from "@mlforge/sdk";
import { useEffect, useState } from "react";

export function MLForgeLogin() {
  const [forge] = useState(() => new MLForge());
  const [isAuth, setIsAuth] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      await forge.initAuth();
      setIsAuth(forge.isAuthenticated());
      setLoading(false);
    };
    initAuth();
  }, []);

  const handleLogin = async () => {
    setLoading(true);
    try {
      await forge.login();
      setIsAuth(true);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await forge.logout();
    setIsAuth(false);
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      {isAuth ? (
        <>
          <p>Logged in!</p>
          <button onClick={handleLogout}>Logout</button>
        </>
      ) : (
        <button onClick={handleLogin}>Login with MLForge</button>
      )}
    </div>
  );
}
```

## Platform Support

| Platform  | Storage      | Browser Open | Port Finding | Status |
|-----------|--------------|--------------|--------------|--------|
| Node.js   | File system  | ✓ (open pkg) | ✓            | Ready  |
| Browser   | localStorage | ✓ (popup)    | N/A          | Ready  |
| Electron  | File system  | ✓            | ✓            | Ready  |

## Migration from Manual Token Management

If you were manually managing tokens:

```typescript
// Before
const forge = new MLForge({ token: myStoredToken });

// After (recommended)
const forge = new MLForge();
await forge.initAuth(); // Auto-loads stored token
// Or
forge.authenticate(myToken); // Explicit token
```
