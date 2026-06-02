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

export class TrainingClient {
  constructor(private http: HttpClient) {}

  async start(opts: TrainStartOptions): Promise<{ run_id: string }> {
    return this.http.post<{ run_id: string }>("/train/start", opts);
  }

  async stop(runId: string): Promise<void> {
    return this.http.post<void>(`/train/runs/${runId}/stop`);
  }

  async pause(runId: string): Promise<void> {
    return this.http.post<void>(`/train/runs/${runId}/pause`);
  }

  async resume(runId: string): Promise<void> {
    return this.http.post<void>(`/train/runs/${runId}/resume`);
  }

  async get(runId: string): Promise<TrainRun> {
    return this.http.get<TrainRun>(`/train/runs/${runId}`);
  }

  async list(): Promise<TrainRun[]> {
    return this.http.get<TrainRun[]>("/train/runs");
  }

  async getHistory(runId: string): Promise<{ epoch: number; metrics: Record<string, number> }[]> {
    return this.http.get<{ epoch: number; metrics: Record<string, number> }[]>(
      `/train/runs/${runId}/history`
    );
  }
}
