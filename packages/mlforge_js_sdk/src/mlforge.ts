import { HttpClient, type MLForgeOptions } from "./http.js";
import { ModelsClient } from "./models.js";
import { TrainingClient } from "./training.js";
import { InferenceClient } from "./inference.js";
import { DatasetsClient } from "./datasets.js";
import { BenchmarkClient } from "./benchmark.js";
import { ProjectsClient } from "./projects.js";
import { ExportsClient } from "./exports.js";
import { AuthClient, type AuthOptions } from "./auth.js";

export class MLForge {
  private http: HttpClient;
  private auth: AuthClient;
  private _token?: string;

  readonly models: ModelsClient;
  readonly training: TrainingClient;
  readonly inference: InferenceClient;
  readonly datasets: DatasetsClient;
  readonly benchmark: BenchmarkClient;
  readonly projects: ProjectsClient;
  readonly exports: ExportsClient;

  constructor(options?: MLForgeOptions & AuthOptions) {
    this.http = new HttpClient(options);
    this.auth = new AuthClient(options);

    this.models = new ModelsClient(this.http);
    this.training = new TrainingClient(this.http);
    this.inference = new InferenceClient(this.http);
    this.datasets = new DatasetsClient(this.http);
    this.benchmark = new BenchmarkClient(this.http);
    this.projects = new ProjectsClient(this.http);
    this.exports = new ExportsClient(this.http);

    // Load stored token on init if not provided
    if (options?.token) {
      this.authenticate(options.token);
    }
  }

  /**
   * Initialize and auto-load stored token if available.
   * Call this after construction to restore previous authentication.
   */
  async initAuth(): Promise<void> {
    const storedToken = await this.auth.getStoredToken();
    if (storedToken) {
      this.authenticate(storedToken);
    }
  }

  /**
   * Initiate OAuth login flow.
   * Opens browser → mlforge.in/auth → stores token locally.
   */
  async login(): Promise<string> {
    const token = await this.auth.login();
    this.authenticate(token);
    return token;
  }

  /**
   * Logout and remove stored authentication token.
   */
  async logout(): Promise<void> {
    await this.auth.logout();
    this.clearAuth();
  }

  /**
   * Authenticate with a JWT token.
   * Token is automatically sent in Authorization header for all requests.
   */
  authenticate(token: string): void {
    this._token = token;
    this.http["token"] = token;
  }

  /**
   * Get current authentication status.
   */
  isAuthenticated(): boolean {
    return Boolean(this._token) || Boolean((this.http as any)["token"]);
  }

  /**
   * Check if a stored token exists (doesn't require SDK initialization).
   */
  async hasStoredToken(): Promise<boolean> {
    return this.auth.hasToken();
  }

  /**
   * Clear authentication token.
   */
  clearAuth(): void {
    this._token = undefined;
    (this.http as any)["token"] = undefined;
  }

  /**
   * Get the auth client instance for advanced use cases.
   */
  getAuthClient(): AuthClient {
    return this.auth;
  }
}

export default MLForge;
