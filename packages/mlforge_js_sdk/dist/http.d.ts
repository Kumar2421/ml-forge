export interface MLForgeOptions {
    baseUrl?: string;
    timeout?: number;
    token?: string;
}
export declare class ApiError extends Error {
    status: number;
    body: unknown;
    constructor(status: number, message: string, body?: unknown);
}
export declare class HttpClient {
    private baseUrl;
    private timeout;
    private token?;
    constructor(options?: MLForgeOptions);
    get<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T>;
    post<T>(path: string, body?: unknown): Promise<T>;
    delete<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T>;
    private _buildHeaders;
    private _fetch;
}
//# sourceMappingURL=http.d.ts.map