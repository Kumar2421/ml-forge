export class ModelsClient {
    constructor(http) {
        this.http = http;
    }
    async list(params) {
        return this.http.get("/models", params);
    }
    async get(modelId) {
        return this.http.get(`/models/${modelId}`);
    }
    async download(modelId) {
        return this.http.post("/download", { model_id: modelId });
    }
    async getJob(jobId) {
        return this.http.get(`/jobs/${jobId}`);
    }
    async listJobs() {
        return this.http.get("/jobs");
    }
}
//# sourceMappingURL=models.js.map