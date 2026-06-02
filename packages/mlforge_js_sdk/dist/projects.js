export class ProjectsClient {
    constructor(http) {
        this.http = http;
    }
    async list(opts) {
        return this.http.get("/projects", {
            limit: opts?.limit ?? 200,
            offset: opts?.offset ?? 0,
        });
    }
    async create(opts) {
        return this.http.post("/projects", opts);
    }
    async get(projectId) {
        return this.http.get(`/projects/${projectId}`);
    }
    async open(projectId) {
        return this.http.post(`/projects/${projectId}/open`);
    }
    async delete(projectId) {
        return this.http.delete(`/projects/${projectId}`);
    }
}
//# sourceMappingURL=projects.js.map