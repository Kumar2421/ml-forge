export class ApiError extends Error {
    constructor(status, message, body) {
        super(`MLForge API ${status}: ${message}`);
        this.status = status;
        this.body = body;
        this.name = "ApiError";
    }
}
export class HttpClient {
    constructor(options = {}) {
        this.baseUrl = (options.baseUrl ?? "http://127.0.0.1:8005").replace(/\/$/, "");
        this.timeout = options.timeout ?? 30000;
        this.token = options.token;
    }
    async get(path, params) {
        const url = new URL(this.baseUrl + path);
        if (params)
            Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));
        return this._fetch(url.toString(), {
            method: "GET",
            headers: this._buildHeaders(),
        });
    }
    async post(path, body) {
        return this._fetch(this.baseUrl + path, {
            method: "POST",
            headers: this._buildHeaders({ "Content-Type": "application/json" }),
            body: body != null ? JSON.stringify(body) : undefined,
        });
    }
    async delete(path, params) {
        const url = new URL(this.baseUrl + path);
        if (params)
            Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));
        return this._fetch(url.toString(), {
            method: "DELETE",
            headers: this._buildHeaders(),
        });
    }
    _buildHeaders(extra = {}) {
        const headers = { ...extra };
        if (this.token) {
            headers["Authorization"] = `Bearer ${this.token}`;
        }
        return headers;
    }
    async _fetch(url, init) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeout);
        try {
            const res = await fetch(url, { ...init, signal: controller.signal });
            clearTimeout(timer);
            if (!res.ok) {
                const text = await res.text().catch(() => "");
                throw new ApiError(res.status, res.statusText, text);
            }
            if (res.status === 204)
                return undefined;
            return res.json();
        }
        catch (e) {
            clearTimeout(timer);
            if (e instanceof ApiError)
                throw e;
            throw new ApiError(0, e.message);
        }
    }
}
//# sourceMappingURL=http.js.map