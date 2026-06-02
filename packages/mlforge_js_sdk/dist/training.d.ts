import type { HttpClient } from "./http.js";
export interface TrainRun {
    id: string;
    model_id: string;
    dataset_id: string;
    task: string;
    status: "queued" | "running" | "completed" | "failed" | "stopped";
    epoch: number;
    total_epochs: number;
    metrics: Record<string, number>;
    created_at: string;
    completed_at?: string;
}
export interface TrainStartOptions {
    model_id: string;
    dataset_id: string;
    task: string;
    epochs?: number;
    batch_size?: number;
    imgsz?: number;
    lr?: number;
    optimizer?: string;
    device?: string;
    augmentation?: Record<string, unknown>;
    hyperparams?: Record<string, unknown>;
}
export declare class TrainingClient {
    private http;
    constructor(http: HttpClient);
    start(opts: TrainStartOptions): Promise<{
        run_id: string;
    }>;
    stop(runId: string): Promise<void>;
    pause(runId: string): Promise<void>;
    resume(runId: string): Promise<void>;
    get(runId: string): Promise<TrainRun>;
    list(): Promise<TrainRun[]>;
    getHistory(runId: string): Promise<{
        epoch: number;
        metrics: Record<string, number>;
    }[]>;
}
//# sourceMappingURL=training.d.ts.map