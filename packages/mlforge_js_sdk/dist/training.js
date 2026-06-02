export class TrainingClient {
    constructor(http) {
        this.http = http;
    }
    async start(opts) {
        return this.http.post("/train/start", opts);
    }
    async stop(runId) {
        return this.http.post(`/train/runs/${runId}/stop`);
    }
    async pause(runId) {
        return this.http.post(`/train/runs/${runId}/pause`);
    }
    async resume(runId) {
        return this.http.post(`/train/runs/${runId}/resume`);
    }
    async get(runId) {
        return this.http.get(`/train/runs/${runId}`);
    }
    async list() {
        return this.http.get("/train/runs");
    }
    async getHistory(runId) {
        return this.http.get(`/train/runs/${runId}/history`);
    }
}
//# sourceMappingURL=training.js.map