import { createServer } from "http";
import { resolve } from "path";
import { existsSync, readFileSync, writeFileSync, mkdirSync, unlinkSync } from "fs";
import { homedir } from "os";
// Runtime detection
const isNode = typeof process !== "undefined" && process.versions?.node;
const isBrowser = typeof window !== "undefined" && typeof localStorage !== "undefined";
/**
 * Cross-platform OAuth authentication client for MLForge SDK
 * Supports browser (localStorage) and Node.js (file-based storage)
 */
export class AuthClient {
    constructor(options = {}) {
        this.server = null;
        this.clientId = options.clientId || "mlforge-sdk-default";
        this.oauthBaseUrl = options.oauthBaseUrl || "https://mlforge.in/auth";
        this.defaultPort = options.defaultPort || 3333;
        this.callbackTimeout = options.callbackTimeout || 30000; // 30s
        // Node.js: set up credentials file path
        if (isNode) {
            const homeDir = homedir();
            this.credentialsPath = resolve(homeDir, ".mlforge", "credentials.json");
        }
        else {
            this.credentialsPath = ""; // Not used in browser
        }
    }
    /**
     * Initiate OAuth login flow
     * Opens browser → mlforge.in/auth → callback with token → stores locally
     */
    async login() {
        if (!isNode && !isBrowser) {
            throw new Error("AuthClient: Unsupported environment. Must run in Node.js or browser.");
        }
        // Start callback server (Node.js only)
        if (isNode) {
            const token = await this._nodeLogin();
            return token;
        }
        else {
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
    async _nodeLogin() {
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
    async _browserLogin() {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                window.removeEventListener("message", listener);
                reject(new Error("OAuth login timeout (30s)"));
            }, this.callbackTimeout);
            const listener = (event) => {
                // Validate origin (in real implementation, validate against known auth domain)
                if (!event.data?.mlforgeToken)
                    return;
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
    _startCallbackServer(port) {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                if (this.server)
                    this.server.close();
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
                        if (this.server)
                            this.server.close();
                        reject(new Error(`OAuth error: ${error}`));
                        return;
                    }
                    if (!token) {
                        res.writeHead(400, { "Content-Type": "text/plain" });
                        res.end("Missing token parameter");
                        clearTimeout(timeout);
                        if (this.server)
                            this.server.close();
                        reject(new Error("OAuth callback missing token"));
                        return;
                    }
                    // Success response
                    res.writeHead(200, { "Content-Type": "text/html" });
                    res.end("<html><body><h1>Authentication successful!</h1>" +
                        "<p>You can close this window and return to your application.</p></body></html>");
                    clearTimeout(timeout);
                    if (this.server)
                        this.server.close();
                    this.server = null;
                    resolve(token);
                }
                else {
                    res.writeHead(404);
                    res.end("Not found");
                }
            });
            this.server.listen(port, () => {
                // Server started, ready to receive callback
            });
            this.server.on("error", (err) => {
                clearTimeout(timeout);
                reject(err);
            });
        });
    }
    /**
     * Find an available port starting from defaultPort
     * Tries defaultPort, defaultPort+1, defaultPort+2, etc.
     */
    _findAvailablePort(startPort) {
        return new Promise((resolve) => {
            const tryPort = (port) => {
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
    async _openBrowser(callbackUrl) {
        if (!isNode)
            return;
        const authUrl = new URL(this.oauthBaseUrl);
        authUrl.searchParams.set("client_id", this.clientId);
        authUrl.searchParams.set("callback", callbackUrl);
        authUrl.searchParams.set("response_type", "token");
        try {
            // Dynamic import to avoid breaking browser environments
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const open = await import("open");
            const openFn = open.default || open;
            await openFn(authUrl.toString());
        }
        catch (err) {
            console.warn("Could not open browser automatically. Please visit the URL manually:", authUrl.toString());
        }
    }
    /**
     * Get stored token from storage
     * Browser: localStorage
     * Node.js: ~/.mlforge/credentials.json
     */
    async getStoredToken() {
        if (isBrowser) {
            return this._getStoredTokenBrowser();
        }
        else if (isNode) {
            return this._getStoredTokenNode();
        }
        return null;
    }
    /**
     * Browser: Get token from localStorage
     */
    _getStoredTokenBrowser() {
        try {
            return localStorage.getItem("mlforge_token");
        }
        catch (err) {
            console.warn("Failed to read from localStorage:", err);
            return null;
        }
    }
    /**
     * Node.js: Get token from ~/.mlforge/credentials.json
     */
    _getStoredTokenNode() {
        try {
            if (!existsSync(this.credentialsPath)) {
                return null;
            }
            const content = readFileSync(this.credentialsPath, "utf-8");
            const data = JSON.parse(content);
            // Check expiration
            if (data.expiresAt && data.expiresAt < Date.now()) {
                return null; // Token expired
            }
            return data.accessToken;
        }
        catch (err) {
            // File doesn't exist or JSON parse error - return null gracefully
            if (err.code === "ENOENT") {
                return null;
            }
            console.warn("Failed to read credentials:", err);
            return null;
        }
    }
    /**
     * Store token to browser localStorage
     */
    _storeTokenBrowser(token) {
        try {
            localStorage.setItem("mlforge_token", token);
        }
        catch (err) {
            console.warn("Failed to store token in localStorage:", err);
        }
    }
    /**
     * Store token to Node.js ~/.mlforge/credentials.json
     */
    _storeTokenNode(token) {
        try {
            const dir = resolve(homedir(), ".mlforge");
            if (!existsSync(dir)) {
                mkdirSync(dir, { recursive: true });
            }
            const tokenData = {
                accessToken: token,
                expiresAt: Date.now() + 24 * 60 * 60 * 1000, // 24 hours
            };
            writeFileSync(this.credentialsPath, JSON.stringify(tokenData, null, 2));
        }
        catch (err) {
            console.warn("Failed to store credentials:", err);
            throw err;
        }
    }
    /**
     * Logout and remove token from storage
     */
    async logout() {
        if (isBrowser) {
            this._logoutBrowser();
        }
        else if (isNode) {
            this._logoutNode();
        }
    }
    /**
     * Browser: Remove token from localStorage
     */
    _logoutBrowser() {
        try {
            localStorage.removeItem("mlforge_token");
        }
        catch (err) {
            console.warn("Failed to remove token from localStorage:", err);
        }
    }
    /**
     * Node.js: Remove credentials file
     */
    _logoutNode() {
        try {
            if (existsSync(this.credentialsPath)) {
                unlinkSync(this.credentialsPath);
            }
        }
        catch (err) {
            console.warn("Failed to remove credentials file:", err);
        }
    }
    /**
     * Check if token exists (doesn't validate expiration for quick checks)
     */
    async hasToken() {
        const token = await this.getStoredToken();
        return token !== null && token.length > 0;
    }
    /**
     * Clear callback server if it's still running
     */
    closeCallbackServer() {
        if (this.server) {
            this.server.close();
            this.server = null;
        }
    }
}
export default AuthClient;
//# sourceMappingURL=auth.js.map