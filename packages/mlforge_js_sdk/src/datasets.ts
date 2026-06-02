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

export class DatasetsClient {
  constructor(private http: HttpClient) {}

  async list(opts?: {
    task?: string;
    format?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<Dataset[]> {
    return this.http.get<Dataset[]>("/datasets", {
      task: opts?.task,
      format: opts?.format,
      search: opts?.search,
      limit: opts?.limit ?? 100,
      offset: opts?.offset ?? 0,
    } as Record<string, string | number | boolean>);
  }

  async get(datasetId: string): Promise<Dataset> {
    return this.http.get<Dataset>(`/datasets/${datasetId}`);
  }

  async getAnalytics(datasetId: string): Promise<DatasetAnalytics> {
    return this.http.get<DatasetAnalytics>(`/datasets/${datasetId}/analytics`);
  }

  async import(datasetId: string, opts: ImportOptions): Promise<{ job_id: string; dataset_id: string }> {
    return this.http.post<{ job_id: string; dataset_id: string }>(
      `/datasets/${datasetId}/import`,
      opts
    );
  }

  async listJobs(opts?: { limit?: number }): Promise<DatasetJob[]> {
    return this.http.get<DatasetJob[]>("/datasets/jobs", { limit: opts?.limit ?? 50 });
  }

  async getJob(jobId: string): Promise<DatasetJob> {
    return this.http.get<DatasetJob>(`/datasets/jobs/${jobId}`);
  }

  async stopJob(jobId: string): Promise<void> {
    return this.http.post<void>(`/datasets/jobs/${jobId}/stop`);
  }

  async pauseJob(jobId: string): Promise<void> {
    return this.http.post<void>(`/datasets/jobs/${jobId}/pause`);
  }

  async resumeJob(jobId: string): Promise<void> {
    return this.http.post<void>(`/datasets/jobs/${jobId}/resume`);
  }

  async delete(datasetId: string, opts?: { delete_files?: boolean }): Promise<void> {
    return this.http.delete<void>(`/datasets/${datasetId}`, {
      delete_files: opts?.delete_files ?? false,
    });
  }

  async searchRoboflow(opts: {
    api_key: string;
    query?: string;
    workspace?: string;
    page?: number;
    page_size?: number;
  }): Promise<Dataset[]> {
    return this.http.post<Dataset[]>("/datasets/search/roboflow", opts);
  }

  async syncRoboflow(opts: { api_key: string; workspace: string }): Promise<{ status: string }> {
    return this.http.post<{ status: string }>("/datasets/sync/roboflow", opts);
  }
}
