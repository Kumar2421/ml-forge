import type { HttpClient } from "./http.js";

export interface Project {
  id: string;
  name: string;
  path: string;
  created_at: string;
  last_opened: string;
  status?: string;
}

export interface ProjectCreateOptions {
  name: string;
}

export class ProjectsClient {
  constructor(private http: HttpClient) {}

  async list(opts?: { limit?: number; offset?: number }): Promise<Project[]> {
    return this.http.get<Project[]>("/projects", {
      limit: opts?.limit ?? 200,
      offset: opts?.offset ?? 0,
    });
  }

  async create(opts: ProjectCreateOptions): Promise<Project> {
    return this.http.post<Project>("/projects", opts);
  }

  async get(projectId: string): Promise<Project> {
    return this.http.get<Project>(`/projects/${projectId}`);
  }

  async open(projectId: string): Promise<void> {
    return this.http.post<void>(`/projects/${projectId}/open`);
  }

  async delete(projectId: string): Promise<void> {
    return this.http.delete<void>(`/projects/${projectId}`);
  }
}
