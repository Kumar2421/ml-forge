# MLForge SDK OAuth - Quick Start Guide

## Installation

```bash
npm install @mlforge/sdk
```

## Node.js Usage (30 seconds)

```typescript
import { MLForge } from "@mlforge/sdk";

const forge = new MLForge();

// Restore previous session or login
await forge.initAuth();

if (!forge.isAuthenticated()) {
  // Opens browser to MLForge OAuth page
  await forge.login();
}

// Use SDK
const models = await forge.models.list();
console.log(models);

// Logout
await forge.logout();
```

## Browser Usage (30 seconds)

```typescript
import { MLForge } from "@mlforge/sdk";

const forge = new MLForge();

// Try to restore session
await forge.initAuth();

// Show login button if not authenticated
if (!forge.isAuthenticated()) {
  document.querySelector("#loginBtn").onclick = async () => {
    await forge.login();
  };
}

// Use SDK
const datasets = await forge.datasets.list();
console.log(datasets);
```

## Configuration Options

```typescript
const forge = new MLForge({
  // (Optional) Pre-set API base URL
  baseUrl: "http://localhost:8005",
  
  // (Optional) Custom OAuth client ID
  clientId: "my-app-id",
  
  // (Optional) Custom OAuth server
  oauthBaseUrl: "https://custom.oauth.server/auth",
  
  // (Optional) Custom callback port (Node.js only)
  defaultPort: 4000,
  
  // (Optional) Increase timeout for slow networks
  callbackTimeout: 60_000,
  
  // (Optional) Pre-load token from external source
  token: "eyJ..."
});
```

## Automatic Token Storage

**Node.js:**
```
~/.mlforge/credentials.json
```

**Browser:**
```
localStorage (key: mlforge_token)
```

## Common Patterns

### Pattern 1: Auto-authenticate on startup

```typescript
const forge = new MLForge();
await forge.initAuth();

if (!forge.isAuthenticated()) {
  console.log("Please login");
}
```

### Pattern 2: Check without full initialization

```typescript
const auth = forge.getAuthClient();
if (await auth.hasToken()) {
  console.log("Token exists!");
}
```

### Pattern 3: Handle login errors

```typescript
try {
  await forge.login();
} catch (error) {
  if (error.message.includes("timeout")) {
    console.error("User took too long to authorize");
  } else if (error.message.includes("port")) {
    console.error("Port in use, trying next port");
  }
}
```

### Pattern 4: React component

```typescript
import { MLForge } from "@mlforge/sdk";
import { useEffect, useState } from "react";

export function LoginComponent() {
  const [forge] = useState(() => new MLForge());
  const [isAuth, setIsAuth] = useState(false);

  useEffect(() => {
    forge.initAuth().then(() => {
      setIsAuth(forge.isAuthenticated());
    });
  }, [forge]);

  return isAuth ? (
    <button onClick={() => forge.logout()}>Logout</button>
  ) : (
    <button onClick={() => forge.login()}>Login</button>
  );
}
```

## API Summary

### MLForge Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `initAuth()` | Promise<void> | Load stored token if available |
| `login()` | Promise<string> | Start OAuth flow, return token |
| `logout()` | Promise<void> | Remove token from storage |
| `isAuthenticated()` | boolean | Check if currently authenticated |
| `hasStoredToken()` | Promise<boolean> | Check if token exists |
| `authenticate(token)` | void | Manually set token |
| `clearAuth()` | void | Clear current token |
| `getAuthClient()` | AuthClient | Get auth client instance |

### AuthClient Methods (Advanced)

```typescript
const auth = forge.getAuthClient();

await auth.login()                // Start OAuth flow
await auth.getStoredToken()       // Get token from storage
await auth.logout()               // Remove token
await auth.hasToken()             // Check if token exists
auth.closeCallbackServer()        // Close callback server
```

## Troubleshooting

### "Port already in use"
```typescript
const forge = new MLForge({ defaultPort: 5000 });
```

### "Token timeout"
```typescript
const forge = new MLForge({ callbackTimeout: 60_000 });
```

### "Browser didn't open"
- The OAuth URL will be printed to console
- Open it manually in your browser
- Token will still be captured

### "ENOENT: no such file"
- Normal on first login
- SDK automatically creates `~/.mlforge/` directory
- Check folder permissions

### Token not persisting
- **Node.js**: Check `~/.mlforge/credentials.json` exists
- **Browser**: Check localStorage in DevTools
- Verify file permissions (Node.js)

## Next Steps

1. **Read full docs**: See `AUTH_GUIDE.md` for complete documentation
2. **See examples**: Check `oauth-auth.example.ts` for 8+ examples
3. **Explore API**: Check `dist/index.d.ts` for TypeScript definitions

## Support

For issues or questions:
1. Check `AUTH_GUIDE.md` troubleshooting section
2. Review examples in `oauth-auth.example.ts`
3. Check OAuth server logs
4. Verify configuration options

## What Gets Stored

**Node.js (~/.mlforge/credentials.json):**
- accessToken: Your OAuth token
- refreshToken: (optional) For token refresh
- expiresAt: Unix timestamp of expiration

**Browser (localStorage):**
- mlforge_token: Your OAuth token

**Nothing is logged or sent** except to the OAuth server during login.
