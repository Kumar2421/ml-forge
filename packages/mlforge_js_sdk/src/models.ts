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

export class ModelsClient {
  constructor(private http: HttpClient) {}

  async list(params?: { task?: string; framework?: string; query?: string }): Promise<Model[]> {
    return this.http.get<Model[]>("/models", params as Record<string, string>);
  }

  async get(modelId: string): Promise<Model> {
    return this.http.get<Model>(`/models/${modelId}`);
  }

  async download(modelId: string): Promise<{ job_id: string }> {
    return this.http.post<{ job_id: string }>("/download", { model_id: modelId });
  }

  async getJob(jobId: string): Promise<ModelJob> {
    return this.http.get<ModelJob>(`/jobs/${jobId}`);
  }

  async listJobs(): Promise<ModelJob[]> {
    return this.http.get<ModelJob[]>("/jobs");
  }
}
