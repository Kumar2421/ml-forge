export interface MLForgeOptions {
  baseUrl?: string;
  timeout?: number;
  token?: string;
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body?: unknown) {
    super(`MLForge API ${status}: ${message}`);
    this.status = status;
    this.body = body;
    this.name = "ApiError";
  }
}

export class HttpClient {
  private baseUrl: string;
  private timeout: number;
  private token?: string;

  constructor(options: MLForgeOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "http://127.0.0.1:8005").replace(/\/$/, "");
    this.timeout = options.timeout ?? 30_000;
    this.token = options.token;
  }

  async get<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
    const url = new URL(this.baseUrl + path);
    if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));
    return this._fetch<T>(url.toString(), {
      method: "GET",
      headers: this._buildHeaders(),
    });
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    return this._fetch<T>(this.baseUrl + path, {
      method: "POST",
      headers: this._buildHeaders({ "Content-Type": "application/json" }),
      body: body != null ? JSON.stringify(body) : undefined,
    });
  }

  async delete<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
    const url = new URL(this.baseUrl + path);
    if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));
    return this._fetch<T>(url.toString(), {
      method: "DELETE",
      headers: this._buildHeaders(),
    });
  }

  private _buildHeaders(extra: Record<string, string> = {}): Record<string, string> {
    const headers = { ...extra };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    return headers;
  }

  private async _fetch<T>(url: string, init: RequestInit): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);
    try {
      const res = await fetch(url, { ...init, signal: controller.signal });
      clearTimeout(timer);

      if (!res.ok) {
        let body: unknown = null;
        const contentType = res.headers.get("content-type");

        try {
          if (contentType?.includes("application/json")) {
            body = await res.json();
          } else {
            body = await res.text().catch(() => "");
          }
        } catch {
          body = await res.text().catch(() => "");
        }

        // Handle 402 Payment Required (quota exceeded)
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

        throw new ApiError(res.status, res.statusText, body);
      }

      if (res.status === 204) return undefined as T;
      return res.json() as Promise<T>;
    } catch (e) {
      clearTimeout(timer);
      if (e instanceof ApiError) throw e;
      throw new ApiError(0, (e as Error).message);
    }
  }
}
