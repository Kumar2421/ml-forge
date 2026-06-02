import type { HttpClient } from "./http.js";
export interface Model {
    id: string;
    name: string;
    task: string;
    framework: string;
    version: string;
    tags: string[];
    size?: string;
    description?: string;
    download_url?: string;
}
export interface ModelJob {
    id: string;
    model_id: string;
    status: "queued" | "running" | "completed" | "failed" | "cancelled";
    progress: number;
    message: string;
    created_at: string;
}
export declare class ModelsClient {
    private http;
    constructor(http: HttpClient);
    list(params?: {
        task?: string;
        framework?: string;
        query?: string;
    }): Promise<Model[]>;
    get(modelId: string): Promise<Model>;
    download(modelId: string): Promise<{
        job_id: string;
    }>;
    getJob(jobId: string): Promise<ModelJob>;
    listJobs(): Promise<ModelJob[]>;
}
//# sourceMappingURL=models.d.ts.map