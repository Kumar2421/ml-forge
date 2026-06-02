import type { HttpClient } from "./http.js";
export interface BenchmarkResult {
    id: string;
    job_id: string;
    metrics: Record<string, unknown>;
    telemetry_summary: Record<string, unknown>;
    created_at?: string;
    model_id?: string;
    dataset_id?: string;
    task?: string;
    framework?: string;
    hardware?: string;
    precision?: string;
}
export interface BenchmarkJob {
    id: string;
    model_id: string;
    dataset_id: string;
    task: string;
    framework: string;
    hardware: string;
    precision: string;
    batch_size: number;
    status: string;
    progress?: number;
    logs?: string[];
}
export interface BenchmarkRunOptions {
    project_id: string;
    model_id: string;
    dataset_id?: string;
    task?: string;
    framework?: string;
    hardware?: string;
    precision?: string;
    batch_size?: number;
    [key: string]: unknown;
}
export declare class BenchmarkClient {
    private http;
    constructor(http: HttpClient);
    listResults(opts?: {
        limit?: number;
    }): Promise<BenchmarkResult[]>;
    listJobs(opts?: {
        status?: string;
        model_id?: string;
        limit?: number;
    }): Promise<BenchmarkJob[]>;
    run(opts: BenchmarkRunOptions): Promise<{
        job_id: string;
        status: string;
    }>;
    validate(opts: Record<string, unknown>): Promise<Record<string, unknown>>;
    getJob(jobId: string): Promise<BenchmarkJob>;
    getResult(jobId: string): Promise<BenchmarkResult>;
}
//# sourceMappingURL=benchmark.d.ts.map