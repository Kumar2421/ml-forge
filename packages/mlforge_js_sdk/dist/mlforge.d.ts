import { type MLForgeOptions } from "./http.js";
import { ModelsClient } from "./models.js";
import { TrainingClient } from "./training.js";
import { InferenceClient } from "./inference.js";
import { DatasetsClient } from "./datasets.js";
import { BenchmarkClient } from "./benchmark.js";
import { ProjectsClient } from "./projects.js";
import { ExportsClient } from "./exports.js";
import { AuthClient, type AuthOptions } from "./auth.js";
export declare class MLForge {
    private http;
    private auth;
    private _token?;
    readonly models: ModelsClient;
    readonly training: TrainingClient;
    readonly inference: InferenceClient;
    readonly datasets: DatasetsClient;
    readonly benchmark: BenchmarkClient;
    readonly projects: ProjectsClient;
    readonly exports: ExportsClient;
    constructor(options?: MLForgeOptions & AuthOptions);
    /**
     * Initialize and auto-load stored token if available.
     * Call this after construction to restore previous authentication.
     */
    initAuth(): Promise<void>;
    /**
     * Initiate OAuth login flow.
     * Opens browser → mlforge.in/auth → stores token locally.
     */
    login(): Promise<string>;
    /**
     * Logout and remove stored authentication token.
     */
    logout(): Promise<void>;
    /**
     * Authenticate with a JWT token.
     * Token is automatically sent in Authorization header for all requests.
     */
    authenticate(token: string): void;
    /**
     * Get current authentication status.
     */
    isAuthenticated(): boolean;
    /**
     * Check if a stored token exists (doesn't require SDK initialization).
     */
    hasStoredToken(): Promise<boolean>;
    /**
     * Clear authentication token.
     */
    clearAuth(): void;
    /**
     * Get the auth client instance for advanced use cases.
     */
    getAuthClient(): AuthClient;
}
export default MLForge;
//# sourceMappingURL=mlforge.d.ts.map