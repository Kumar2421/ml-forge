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
export declare class ProjectsClient {
    private http;
    constructor(http: HttpClient);
    list(opts?: {
        limit?: number;
        offset?: number;
    }): Promise<Project[]>;
    create(opts: ProjectCreateOptions): Promise<Project>;
    get(projectId: string): Promise<Project>;
    open(projectId: string): Promise<void>;
    delete(projectId: string): Promise<void>;
}
//# sourceMappingURL=projects.d.ts.map