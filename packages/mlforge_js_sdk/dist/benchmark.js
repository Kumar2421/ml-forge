export class BenchmarkClient {
    constructor(http) {
        this.http = http;
    }
    async listResults(opts) {
        return this.http.get("/benchmark/results/all", {
            limit: opts?.limit ?? 100,
        });
    }
    async listJobs(opts) {
        return this.http.get("/benchmark/jobs", {
            status: opts?.status,
            model_id: opts?.model_id,
            limit: opts?.limit ?? 100,
        });
    }
    async run(opts) {
        return this.http.post("/benchmark/run", opts);
    }
    async validate(opts) {
        return this.http.post("/benchmark/validate", opts);
    }
    async getJob(jobId) {
        return this.http.get(`/benchmark/${jobId}`);
    }
    async getResult(jobId) {
        return this.http.get(`/benchmark/${jobId}/result`);
    }
}
//# sourceMappingURL=benchmark.js.map