/**
 * MLForge SDK OAuth Authentication Examples
 * Demonstrates cross-platform OAuth login for Node.js and browser environments
 */

import { MLForge, AuthClient, type AuthOptions } from "../index.js";

// ============================================================================
// Example 1: Node.js - Simple OAuth Login with Auto-Restore
// ============================================================================

async function nodeJsBasicLogin() {
  console.log("Example 1: Node.js Basic Login");

  // Create SDK instance
  const forge = new MLForge();

  // Try to restore previous session
  await forge.initAuth();

  if (forge.isAuthenticated()) {
    console.log("✓ Already authenticated!");
    const models = await forge.models.list();
    console.log(`Found ${models.length} models`);
  } else {
    console.log("Starting OAuth login...");
    const token = await forge.login();
    console.log("✓ Login successful! Token saved to ~/.mlforge/credentials.json");
    console.log(`Token: ${token.substring(0, 20)}...`);
  }
}

// ============================================================================
// Example 2: Node.js - Custom Port and Timeout Configuration
// ============================================================================

async function nodeJsCustomConfig() {
  console.log("\nExample 2: Custom Configuration");

  const forge = new MLForge({
    baseUrl: "http://localhost:8005",
    defaultPort: 4000, // Use port 4000 instead of 3333
    callbackTimeout: 60_000, // 60 second timeout
    clientId: "my-custom-app",
  });

  try {
    const token = await forge.login();
    console.log("✓ Login successful with custom config");
  } catch (error) {
    if ((error as Error).message.includes("port")) {
      console.error("All callback ports are in use");
    } else if ((error as Error).message.includes("timeout")) {
      console.error("Login timed out");
    } else {
      console.error("Login error:", error);
    }
  }
}

// ============================================================================
// Example 3: Node.js - Manual Token Management
// ============================================================================

async function nodeJsManualToken() {
  console.log("\nExample 3: Manual Token Management");

  const forge = new MLForge();

  // Check if token exists without full initialization
  const hasToken = await forge.hasStoredToken();
  console.log(`Has stored token: ${hasToken}`);

  // Manually get the auth client
  const auth = forge.getAuthClient();
  const storedToken = await auth.getStoredToken();

  if (storedToken) {
    // Authenticate with existing token
    forge.authenticate(storedToken);
    console.log("✓ Authenticated with stored token");
  } else {
    // Need to login
    const newToken = await forge.login();
    console.log("✓ Login successful");
  }

  // Later, logout
  await forge.logout();
  console.log("✓ Logged out successfully");
}

// ============================================================================
// Example 4: Direct AuthClient Usage (Advanced)
// ============================================================================

async function directAuthClient() {
  console.log("\nExample 4: Direct AuthClient Usage");

  // Create auth client directly
  const auth = new AuthClient({
    clientId: "my-app",
    oauthBaseUrl: "https://custom.oauth.server/auth",
    defaultPort: 3333,
    callbackTimeout: 30_000,
  });

  // Start login
  const token = await auth.login();
  console.log("✓ Login successful");

  // Check stored token
  const stored = await auth.getStoredToken();
  console.log(`Stored token matches: ${stored === token}`);

  // Check if token exists
  const has = await auth.hasToken();
  console.log(`Has token: ${has}`);

  // Cleanup
  await auth.logout();
  console.log("✓ Token removed");
}

// ============================================================================
// Example 5: Browser - OAuth Login in React
// ============================================================================

// This is TypeScript/React pseudocode - actual implementation would use React hooks
async function browserReactComponent() {
  console.log("\nExample 5: Browser React Component");

  const codeExample = `
import { MLForge } from "@mlforge/sdk";
import { useEffect, useState } from "react";

export function MLForgeAuthComponent() {
  const [forge] = useState(() => new MLForge());
  const [isAuth, setIsAuth] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      // Try to restore previous session
      await forge.initAuth();
      setIsAuth(forge.isAuthenticated());
      setLoading(false);
    };
    initAuth();
  }, [forge]);

  const handleLogin = async () => {
    setLoading(true);
    try {
      await forge.login();
      setIsAuth(true);
    } catch (error) {
      console.error("Login failed:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await forge.logout();
    setIsAuth(false);
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      {isAuth ? (
        <>
          <h1>Welcome to MLForge!</h1>
          <button onClick={handleLogout}>Logout</button>
        </>
      ) : (
        <button onClick={handleLogin}>Login with MLForge OAuth</button>
      )}
    </div>
  );
}
  `;

  console.log(codeExample);
}

// ============================================================================
// Example 6: Error Handling
// ============================================================================

async function errorHandling() {
  console.log("\nExample 6: Error Handling");

  const forge = new MLForge();

  try {
    const token = await forge.login();
    console.log("✓ Login successful");
  } catch (error) {
    const err = error as Error;

    if (err.message.includes("timeout")) {
      console.error("❌ OAuth timeout - user took too long to authorize");
      console.error("💡 Increase timeout: new MLForge({ callbackTimeout: 60_000 })");
    } else if (err.message.includes("port")) {
      console.error("❌ All callback ports are in use");
      console.error("💡 Try a different port: new MLForge({ defaultPort: 5000 })");
    } else if (err.message.includes("OAuth error")) {
      console.error("❌ OAuth server rejected the request");
      console.error("💡 Check client ID and redirect URI configuration");
    } else {
      console.error("❌ Unexpected error:", err.message);
    }
  }
}

// ============================================================================
// Example 7: Token Lifecycle Management
// ============================================================================

async function tokenLifecycleManagement() {
  console.log("\nExample 7: Token Lifecycle Management");

  const forge = new MLForge();

  // Step 1: Restore previous session
  console.log("1. Restoring session...");
  await forge.initAuth();

  if (!forge.isAuthenticated()) {
    console.log("2. No previous session, starting login...");
    await forge.login();
  }

  // Step 2: Make authenticated requests
  console.log("3. Making authenticated requests...");
  try {
    const models = await forge.models.list();
    const datasets = await forge.datasets.list();
    console.log(`✓ Retrieved ${models.length} models and ${datasets.length} datasets`);
  } catch (error) {
    console.error("❌ Request failed:", error);

    // Token might have expired - try refreshing
    if ((error as any).status === 401) {
      console.log("4. Token expired, need to re-authenticate...");
      await forge.logout();
      await forge.login();
    }
  }

  // Step 3: Cleanup on app exit
  console.log("5. Cleaning up...");
  await forge.logout();
  console.log("✓ Logged out successfully");
}

// ============================================================================
// Example 8: Multi-Environment Setup (Node.js or Browser)
// ============================================================================

async function multiEnvironment() {
  console.log("\nExample 8: Multi-Environment Setup");

  // Detect environment
  const isNode = typeof process !== "undefined" && process.versions?.node;
  const isBrowser = typeof window !== "undefined";

  const forge = new MLForge({
    // Common options
    baseUrl: "http://localhost:8005",

    // Environment-specific options
    defaultPort: isNode ? 3333 : undefined, // Only used in Node.js
    callbackTimeout: 30_000,
  });

  console.log(`Environment: ${isNode ? "Node.js" : isBrowser ? "Browser" : "Unknown"}`);

  // Initialize auth
  await forge.initAuth();

  if (!forge.isAuthenticated()) {
    console.log("Starting login...");
    await forge.login();
  }

  console.log("✓ Ready to use SDK");
}

// ============================================================================
// Run examples (uncomment the one you want to test)
// ============================================================================

async function main() {
  try {
    // Uncomment the example you want to run:

    // await nodeJsBasicLogin();
    // await nodeJsCustomConfig();
    // await nodeJsManualToken();
    // await directAuthClient();
    // await browserReactComponent();
    // await errorHandling();
    // await tokenLifecycleManagement();
    // await multiEnvironment();

    console.log("\n✓ All examples are available - uncomment the one you want to test!");
  } catch (error) {
    console.error("Error running example:", error);
  }
}

// Uncomment to run:
// main().catch(console.error);

export {
  nodeJsBasicLogin,
  nodeJsCustomConfig,
  nodeJsManualToken,
  directAuthClient,
  browserReactComponent,
  errorHandling,
  tokenLifecycleManagement,
  multiEnvironment,
};
