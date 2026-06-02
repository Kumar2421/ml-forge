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

export class ExportsClient {
  constructor(private http: HttpClient) {}

  async list(opts?: {
    project_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<ExportJob[]> {
    return this.http.get<ExportJob[]>("/exports", {
      project_id: opts?.project_id,
      limit: opts?.limit ?? 50,
      offset: opts?.offset ?? 0,
    } as Record<string, string | number | boolean>);
  }

  async get(exportId: string): Promise<ExportJob> {
    return this.http.get<ExportJob>(`/exports/${exportId}`);
  }

  async start(opts: ExportOptions): Promise<{ job_id: string; status: string }> {
    return this.http.post<{ job_id: string; status: string }>("/exports", opts);
  }

  async cancel(exportId: string): Promise<void> {
    return this.http.post<void>(`/exports/${exportId}/cancel`);
  }

  async download(exportId: string): Promise<Blob> {
    const response = await fetch(this.http["baseUrl"] + `/exports/${exportId}/download`);
    if (!response.ok) {
      throw new Error(`Export download failed: ${response.statusText}`);
    }
    return response.blob();
  }
}
