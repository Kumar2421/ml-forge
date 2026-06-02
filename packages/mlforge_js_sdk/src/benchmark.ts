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

export class BenchmarkClient {
  constructor(private http: HttpClient) {}

  async listResults(opts?: { limit?: number }): Promise<BenchmarkResult[]> {
    return this.http.get<BenchmarkResult[]>("/benchmark/results/all", {
      limit: opts?.limit ?? 100,
    });
  }

  async listJobs(opts?: { status?: string; model_id?: string; limit?: number }): Promise<BenchmarkJob[]> {
    return this.http.get<BenchmarkJob[]>("/benchmark/jobs", {
      status: opts?.status,
      model_id: opts?.model_id,
      limit: opts?.limit ?? 100,
    } as Record<string, string | number | boolean>);
  }

  async run(opts: BenchmarkRunOptions): Promise<{ job_id: string; status: string }> {
    return this.http.post<{ job_id: string; status: string }>("/benchmark/run", opts);
  }

  async validate(opts: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.http.post<Record<string, unknown>>("/benchmark/validate", opts);
  }

  async getJob(jobId: string): Promise<BenchmarkJob> {
    return this.http.get<BenchmarkJob>(`/benchmark/${jobId}`);
  }

  async getResult(jobId: string): Promise<BenchmarkResult> {
    return this.http.get<BenchmarkResult>(`/benchmark/${jobId}/result`);
  }
}
