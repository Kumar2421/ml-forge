import { createServer, type Server } from "http";
import { resolve } from "path";
import { existsSync, readFileSync, writeFileSync, mkdirSync, unlinkSync } from "fs";
import { homedir } from "os";

// Runtime detection
const isNode = typeof process !== "undefined" && process.versions?.node;
const isBrowser = typeof window !== "undefined" && typeof localStorage !== "undefined";

interface TokenData {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: number;
}

export interface AuthOptions {
  clientId?: string;
  redirectUri?: string;
  oauthBaseUrl?: string;
  defaultPort?: number;
  callbackTimeout?: number;
}

/**
 * Cross-platform OAuth authentication client for MLForge SDK
 * Supports browser (localStorage) and Node.js (file-based storage)
 */
export class AuthClient {
  private clientId: string;
  private oauthBaseUrl: string;
  private defaultPort: number;
  private callbackTimeout: number;
  private credentialsPath: string;
  private server: Server | null = null;

  constructor(options: AuthOptions = {}) {
    this.clientId = options.clientId || "mlforge-sdk-default";
    this.oauthBaseUrl = options.oauthBaseUrl || "https://mlforge.in/auth";
    this.defaultPort = options.defaultPort || 3333;
    this.callbackTimeout = options.callbackTimeout || 30_000; // 30s

    // Node.js: set up credentials file path
    if (isNode) {
      const homeDir = homedir();
      this.credentialsPath = resolve(homeDir, ".mlforge", "credentials.json");
    } else {
      this.credentialsPath = ""; // Not used in browser
    }
  }

  /**
   * Initiate OAuth login flow
   * Opens browser → mlforge.in/auth → callback with token → stores locally
   */
  async login(): Promise<string> {
    if (!isNode && !isBrowser) {
      throw new Error(
        "AuthClient: Unsupported environment. Must run in Node.js or browser."
      );
    }

    // Start callback server (Node.js only)
    if (isNode) {
      const token = await this._nodeLogin();
      return token;
    } else {
      // Browser flow - simplified (token passed via callback)
      const token = await this._browserLogin();
      return token;
    }
  }

  /**
   * Node.js OAuth flow
   * 1. Start callback server on localhost
   * 2. Open browser with auth URL
   * 3. Wait for callback with token
   * 4. Store token to ~/.mlforge/credentials.json
   */
  private async _nodeLogin(): Promise<string> {
    const port = await this._findAvailablePort(this.defaultPort);
    const callbackUrl = `http://localhost:${port}/callback`;

    // Start callback server
    const token = await this._startCallbackServer(port);

    // Open browser
    await this._openBrowser(callbackUrl);

    // Store token
    this._storeTokenNode(token);

    return token;
  }

  /**
   * Browser-based OAuth flow
   * Uses window.open and postMessage for cross-tab communication
   */
  private async _browserLogin(): Promise<string> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        window.removeEventListener("message", listener);
        reject(new Error("OAuth login timeout (30s)"));
      }, this.callbackTimeout);

      const listener = (event: MessageEvent) => {
        // Validate origin (in real implementation, validate against known auth domain)
        if (!event.data?.mlforgeToken) return;

        clearTimeout(timeout);
        window.removeEventListener("message", listener);

        const token = event.data.mlforgeToken;
        this._storeTokenBrowser(token);
        resolve(token);
      };

      window.addEventListener("message", listener);

      // Build auth URL with callback
      const authUrl = new URL(this.oauthBaseUrl);
      authUrl.searchParams.set("client_id", this.clientId);
      authUrl.searchParams.set("redirect_uri", window.location.origin);
      authUrl.searchParams.set("response_type", "token");

      // Open auth window
      window.open(authUrl.toString(), "mlforge_auth", "width=500,height=600");
    });
  }

  /**
   * Start HTTP callback server to receive OAuth token
   */
  private _startCallbackServer(port: number): Promise<string> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        if (this.server) this.server.close();
        reject(new Error(`OAuth callback timeout (${this.callbackTimeout}ms)`));
      }, this.callbackTimeout);

      this.server = createServer((req, res) => {
        if (req.url?.startsWith("/callback")) {
          const url = new URL(req.url, `http://localhost:${port}`);
          const token = url.searchParams.get("token");
          const error = url.searchParams.get("error");

          if (error) {
            res.writeHead(400, { "Content-Type": "text/plain" });
            res.end(`OAuth Error: ${error}`);
            clearTimeout(timeout);
            if (this.server) this.server.close();
            reject(new Error(`OAuth error: ${error}`));
            return;
          }

          if (!token) {
            res.writeHead(400, { "Content-Type": "text/plain" });
            res.end("Missing token parameter");
            clearTimeout(timeout);
            if (this.server) this.server.close();
            reject(new Error("OAuth callback missing token"));
            return;
          }

          // Success response
          res.writeHead(200, { "Content-Type": "text/html" });
          res.end(
            "<html><body><h1>Authentication successful!</h1>" +
            "<p>You can close this window and return to your application.</p></body></html>"
          );

          clearTimeout(timeout);
          if (this.server) this.server.close();
          this.server = null;
          resolve(token);
        } else {
          res.writeHead(404);
          res.end("Not found");
        }
      });

      this.server.listen(port, () => {
        // Server started, ready to receive callback
      });

      this.server.on("error", (err: any) => {
        clearTimeout(timeout);
        reject(err);
      });
    });
  }

  /**
   * Find an available port starting from defaultPort
   * Tries defaultPort, defaultPort+1, defaultPort+2, etc.
   */
  private _findAvailablePort(startPort: number): Promise<number> {
    return new Promise((resolve) => {
      const tryPort = (port: number) => {
        const server = createServer();
        server.listen(port, () => {
          server.close();
          resolve(port);
        });
        server.on("error", () => {
          tryPort(port + 1);
        });
      };
      tryPort(startPort);
    });
  }

  /**
   * Open browser to OAuth URL
   */
  private async _openBrowser(callbackUrl: string): Promise<void> {
    if (!isNode) return;

    const authUrl = new URL(this.oauthBaseUrl);
    authUrl.searchParams.set("client_id", this.clientId);
    authUrl.searchParams.set("callback", callbackUrl);
    authUrl.searchParams.set("response_type", "token");

    try {
      // Dynamic import to avoid breaking browser environments
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const open = await import("open" as any);
      const openFn = open.default || open;
      await openFn(authUrl.toString());
    } catch (err) {
      console.warn(
        "Could not open browser automatically. Please visit the URL manually:",
        authUrl.toString()
      );
    }
  }

  /**
   * Get stored token from storage
   * Browser: localStorage
   * Node.js: ~/.mlforge/credentials.json
   */
  async getStoredToken(): Promise<string | null> {
    if (isBrowser) {
      return this._getStoredTokenBrowser();
    } else if (isNode) {
      return this._getStoredTokenNode();
    }
    return null;
  }

  /**
   * Browser: Get token from localStorage
   */
  private _getStoredTokenBrowser(): string | null {
    try {
      return localStorage.getItem("mlforge_token");
    } catch (err) {
      console.warn("Failed to read from localStorage:", err);
      return null;
    }
  }

  /**
   * Node.js: Get token from ~/.mlforge/credentials.json
   */
  private _getStoredTokenNode(): string | null {
    try {
      if (!existsSync(this.credentialsPath)) {
        return null;
      }

      const content = readFileSync(this.credentialsPath, "utf-8");
      const data: TokenData = JSON.parse(content);

      // Check expiration
      if (data.expiresAt && data.expiresAt < Date.now()) {
        return null; // Token expired
      }

      return data.accessToken;
    } catch (err) {
      // File doesn't exist or JSON parse error - return null gracefully
      if ((err as any).code === "ENOENT") {
        return null;
      }
      console.warn("Failed to read credentials:", err);
      return null;
    }
  }

  /**
   * Store token to browser localStorage
   */
  private _storeTokenBrowser(token: string): void {
    try {
      localStorage.setItem("mlforge_token", token);
    } catch (err) {
      console.warn("Failed to store token in localStorage:", err);
    }
  }

  /**
   * Store token to Node.js ~/.mlforge/credentials.json
   */
  private _storeTokenNode(token: string): void {
    try {
      const dir = resolve(homedir(), ".mlforge");
      if (!existsSync(dir)) {
        mkdirSync(dir, { recursive: true });
      }

      const tokenData: TokenData = {
        accessToken: token,
        expiresAt: Date.now() + 24 * 60 * 60 * 1000, // 24 hours
      };

      writeFileSync(this.credentialsPath, JSON.stringify(tokenData, null, 2));
    } catch (err) {
      console.warn("Failed to store credentials:", err);
      throw err;
    }
  }

  /**
   * Logout and remove token from storage
   */
  async logout(): Promise<void> {
    if (isBrowser) {
      this._logoutBrowser();
    } else if (isNode) {
      this._logoutNode();
    }
  }

  /**
   * Browser: Remove token from localStorage
   */
  private _logoutBrowser(): void {
    try {
      localStorage.removeItem("mlforge_token");
    } catch (err) {
      console.warn("Failed to remove token from localStorage:", err);
    }
  }

  /**
   * Node.js: Remove credentials file
   */
  private _logoutNode(): void {
    try {
      if (existsSync(this.credentialsPath)) {
        unlinkSync(this.credentialsPath);
      }
    } catch (err) {
      console.warn("Failed to remove credentials file:", err);
    }
  }

  /**
   * Check if token exists (doesn't validate expiration for quick checks)
   */
  async hasToken(): Promise<boolean> {
    const token = await this.getStoredToken();
    return token !== null && token.length > 0;
  }

  /**
   * Clear callback server if it's still running
   */
  closeCallbackServer(): void {
    if (this.server) {
      this.server.close();
      this.server = null;
    }
  }
}

export default AuthClient;
