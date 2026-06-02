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
export declare class AuthClient {
    private clientId;
    private oauthBaseUrl;
    private defaultPort;
    private callbackTimeout;
    private credentialsPath;
    private server;
    constructor(options?: AuthOptions);
    /**
     * Initiate OAuth login flow
     * Opens browser → mlforge.in/auth → callback with token → stores locally
     */
    login(): Promise<string>;
    /**
     * Node.js OAuth flow
     * 1. Start callback server on localhost
     * 2. Open browser with auth URL
     * 3. Wait for callback with token
     * 4. Store token to ~/.mlforge/credentials.json
     */
    private _nodeLogin;
    /**
     * Browser-based OAuth flow
     * Uses window.open and postMessage for cross-tab communication
     */
    private _browserLogin;
    /**
     * Start HTTP callback server to receive OAuth token
     */
    private _startCallbackServer;
    /**
     * Find an available port starting from defaultPort
     * Tries defaultPort, defaultPort+1, defaultPort+2, etc.
     */
    private _findAvailablePort;
    /**
     * Open browser to OAuth URL
     */
    private _openBrowser;
    /**
     * Get stored token from storage
     * Browser: localStorage
     * Node.js: ~/.mlforge/credentials.json
     */
    getStoredToken(): Promise<string | null>;
    /**
     * Browser: Get token from localStorage
     */
    private _getStoredTokenBrowser;
    /**
     * Node.js: Get token from ~/.mlforge/credentials.json
     */
    private _getStoredTokenNode;
    /**
     * Store token to browser localStorage
     */
    private _storeTokenBrowser;
    /**
     * Store token to Node.js ~/.mlforge/credentials.json
     */
    private _storeTokenNode;
    /**
     * Logout and remove token from storage
     */
    logout(): Promise<void>;
    /**
     * Browser: Remove token from localStorage
     */
    private _logoutBrowser;
    /**
     * Node.js: Remove credentials file
     */
    private _logoutNode;
    /**
     * Check if token exists (doesn't validate expiration for quick checks)
     */
    hasToken(): Promise<boolean>;
    /**
     * Clear callback server if it's still running
     */
    closeCallbackServer(): void;
}
export default AuthClient;
//# sourceMappingURL=auth.d.ts.map