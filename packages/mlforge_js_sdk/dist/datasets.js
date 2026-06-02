export class DatasetsClient {
    constructor(http) {
        this.http = http;
    }
    async list(opts) {
        return this.http.get("/datasets", {
            task: opts?.task,
            format: opts?.format,
            search: opts?.search,
            limit: opts?.limit ?? 100,
            offset: opts?.offset ?? 0,
        });
    }
    async get(datasetId) {
        return this.http.get(`/datasets/${datasetId}`);
    }
    async getAnalytics(datasetId) {
        return this.http.get(`/datasets/${datasetId}/analytics`);
    }
    async import(datasetId, opts) {
        return this.http.post(`/datasets/${datasetId}/import`, opts);
    }
    async listJobs(opts) {
        return this.http.get("/datasets/jobs", { limit: opts?.limit ?? 50 });
    }
    async getJob(jobId) {
        return this.http.get(`/datasets/jobs/${jobId}`);
    }
    async stopJob(jobId) {
        return this.http.post(`/datasets/jobs/${jobId}/stop`);
    }
    async pauseJob(jobId) {
        return this.http.post(`/datasets/jobs/${jobId}/pause`);
    }
    async resumeJob(jobId) {
        return this.http.post(`/datasets/jobs/${jobId}/resume`);
    }
    async delete(datasetId, opts) {
        return this.http.delete(`/datasets/${datasetId}`, {
            delete_files: opts?.delete_files ?? false,
        });
    }
    async searchRoboflow(opts) {
        return this.http.post("/datasets/search/roboflow", opts);
    }
    async syncRoboflow(opts) {
        return this.http.post("/datasets/sync/roboflow", opts);
    }
}
//# sourceMappingURL=datasets.js.map