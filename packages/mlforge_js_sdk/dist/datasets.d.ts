import type { HttpClient } from "./http.js";
export interface Dataset {
    id: string;
    name: string;
    format?: string;
    images?: number;
    classes?: number;
    size_label?: string;
}
export interface DatasetJob {
    id: string;
    type: string;
    status: string;
    dataset_id: string;
    dataset_name: string;
    progress?: number;
    message?: string;
    error?: string;
}
export interface DatasetAnalytics {
    dataset_id: string;
    healthScore?: number;
    split?: Record<string, number>;
    qualityIssues?: Record<string, number>;
    classDistribution?: Array<Record<string, unknown>>;
}
export interface ImportOptions {
    project_id: string;
    [key: string]: unknown;
}
export declare class DatasetsClient {
    private http;
    constructor(http: HttpClient);
    list(opts?: {
        task?: string;
        format?: string;
        search?: string;
        limit?: number;
        offset?: number;
    }): Promise<Dataset[]>;
    get(datasetId: string): Promise<Dataset>;
    getAnalytics(datasetId: string): Promise<DatasetAnalytics>;
    import(datasetId: string, opts: ImportOptions): Promise<{
        job_id: string;
        dataset_id: string;
    }>;
    listJobs(opts?: {
        limit?: number;
    }): Promise<DatasetJob[]>;
    getJob(jobId: string): Promise<DatasetJob>;
    stopJob(jobId: string): Promise<void>;
    pauseJob(jobId: string): Promise<void>;
    resumeJob(jobId: string): Promise<void>;
    delete(datasetId: string, opts?: {
        delete_files?: boolean;
    }): Promise<void>;
    searchRoboflow(opts: {
        api_key: string;
        query?: string;
        workspace?: string;
        page?: number;
        page_size?: number;
    }): Promise<Dataset[]>;
    syncRoboflow(opts: {
        api_key: string;
        workspace: string;
    }): Promise<{
        status: string;
    }>;
}
//# sourceMappingURL=datasets.d.ts.map