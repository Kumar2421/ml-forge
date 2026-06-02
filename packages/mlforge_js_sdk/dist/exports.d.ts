import type { HttpClient } from "./http.js";
export interface ExportJob {
    id: string;
    project_id: string;
    run_id: string;
    format: string;
    status: string;
    progress?: number;
    artifact_url?: string;
    created_at?: string;
    completed_at?: string;
}
export interface ExportOptions {
    project_id: string;
    run_id: string;
    format: string;
    include_weights?: boolean;
    include_metadata?: boolean;
    [key: string]: unknown;
}
export declare class ExportsClient {
    private http;
    constructor(http: HttpClient);
    list(opts?: {
        project_id?: string;
        limit?: number;
        offset?: number;
    }): Promise<ExportJob[]>;
    get(exportId: string): Promise<ExportJob>;
    start(opts: ExportOptions): Promise<{
        job_id: string;
        status: string;
    }>;
    cancel(exportId: string): Promise<void>;
    download(exportId: string): Promise<Blob>;
}
//# sourceMappingURL=exports.d.ts.map